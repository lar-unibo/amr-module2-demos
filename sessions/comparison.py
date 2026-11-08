"""
Lecture 2, demo 6 - PBVS vs IBVS with calibration errors (slide 35 and the summary).
==================================================================================

Both controllers start from the same pose and see the same pixels, measured
with the true intrinsics K. Each converts pixels to normalized coordinates
with the *assumed* intrinsics K_hat:

* IBVS compares the current pixels with the desired ones, recorded by the
  same camera at the goal: both go through the same K_hat, so e = 0 exactly
  at the true goal, whatever the calibration error;
* PBVS estimates the pose of the target from the image with K_hat: the
  estimate is biased, and the camera stops where the *estimate* reads the
  desired pose.
"""
from __future__ import annotations

import numpy as np

from course.camera import Intrinsics
from course.geometry import inverse, log_so3
from course.servo import IBVS, PBVS, measure, simulate

from .common import Session
from .servo_common import START_POSES, scene, start_pose, trajectory

DT, STEPS = 0.04, 450
K_TRUE = Intrinsics(f=0.004, rho_u=5e-6, rho_v=5e-6, u0=320.0, v0=240.0)
PRESETS = ("general", "translation", "rot_z_1", "tilt")


def pose_error(T_od, T_oc):
    T = inverse(T_od) @ T_oc
    return float(np.linalg.norm(T[:3, 3])), float(np.degrees(np.linalg.norm(log_so3(T[:3, :3]))))


class ComparisonSession(Session):

    def __init__(self):
        self.scene = scene()
        self.act_reset()

    def act_reset(self):
        self.preset, self.focal_error, self.center_error, self.noise, self.lam = "general", 0.0, 0.0, 0.0, 0.8
        self._run()
        return self.state()

    def act_set(self, preset=None, focal_error=None, center_error=None, noise=None, lam=None):
        if preset is not None:
            if preset not in PRESETS:
                raise KeyError(f"unknown preset: {preset}")
            self.preset = preset
        if focal_error is not None:
            self.focal_error = float(np.clip(focal_error, -0.3, 0.3))
        if center_error is not None:
            self.center_error = float(np.clip(center_error, -60.0, 60.0))
        if noise is not None:
            self.noise = float(np.clip(noise, 0.0, 2.0))
        if lam is not None:
            self.lam = float(np.clip(lam, 0.1, 2.0))
        self._run()
        return self.state()

    def _run(self):
        sc = self.scene
        K_hat = Intrinsics(f=K_TRUE.f * (1 + self.focal_error), rho_u=K_TRUE.rho_u, rho_v=K_TRUE.rho_v,
                           u0=K_TRUE.u0 + self.center_error, v0=K_TRUE.v0 - 0.5 * self.center_error)
        desired_pixels = measure(sc["T_od"], sc["points"], K_TRUE)["uv"]
        T0 = start_pose(sc["T_od"], *START_POSES[self.preset][:2])
        common = dict(dt=DT, steps=STEPS, K=K_TRUE, tol=1e-6, pixel_noise=self.noise, seed=1)
        self.ibvs = simulate(T0, sc["points"], IBVS(None, sc["Z_star"], lam=self.lam, K_hat=K_hat, uv_star=desired_pixels), **common)
        pbvs = PBVS(sc["points"], sc["T_od"], lam=self.lam, perfect_pose=False, K_hat=K_hat)
        self.pbvs = simulate(T0, sc["points"], pbvs, **common)       # T_hat: the pose PBVS believes it has

    def state(self) -> dict:
        sc = self.scene
        tail = 20                                      # average the last steps (noise)
        errors = {}
        for name, out in (("ibvs", self.ibvs), ("pbvs", self.pbvs)):
            final = [pose_error(sc["T_od"], T) for T in out["T"][-tail:]]
            errors[name] = {"position": float(np.mean([e[0] for e in final])), "rotation": float(np.mean([e[1] for e in final]))}
        return {
            "preset": self.preset, "presets": {k: START_POSES[k][2] for k in PRESETS},
            "focal_error": self.focal_error, "center_error": self.center_error, "noise": self.noise, "lam": self.lam,
            "points": sc["points"], "T_od": sc["T_od"], "s_star": sc["s_star"], "errors": errors,
            "ibvs": trajectory(self.ibvs), "pbvs": {**trajectory(self.pbvs), "estimate": self.pbvs["T_hat"]},
        }
