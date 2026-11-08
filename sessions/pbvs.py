"""
Lecture 2, demo 1 - Position-based visual servoing (slides 11-19).
==================================================================

The pose of the current camera in the desired frame, {}^d T_c, gives the
features s = ({}^d t_c, theta m) with s* = 0, and the decoupled control law
nu_c = -lambda {}^d R_c^T {}^d t_c, omega_c = -lambda theta m. With a perfect
pose estimate the camera moves along a straight line and rotates about a
fixed axis, while the image paths of the points are not controlled.
"""
from __future__ import annotations

import numpy as np

from course.geometry import inverse
from course.servo import PBVS, simulate

from .common import Session
from .servo_common import START_POSES, scene, start_pose, trajectory

DT, STEPS = 0.04, 450


class PBVSSession(Session):

    def __init__(self):
        self.scene = scene()
        self.act_reset()

    def act_reset(self):
        self.preset, self.lam = "general", 0.8
        self.translation, self.rotation = (np.array(x, float) for x in START_POSES["general"][:2])
        self._run()
        return self.state()

    def act_set(self, preset=None, lam=None, translation=None, rotation=None):
        if preset is not None:
            self.preset = preset
            self.translation, self.rotation = (np.array(x, float) for x in START_POSES[preset][:2])
        if translation is not None:
            self.translation, self.preset = np.clip(np.asarray(translation, float), -1.0, 1.0), None
        if rotation is not None:
            self.rotation, self.preset = np.clip(np.asarray(rotation, float), -np.pi, np.pi), None
        if lam is not None:
            self.lam = float(np.clip(lam, 0.1, 2.0))
        self._run()
        return self.state()

    def _run(self):
        sc = self.scene
        T0 = start_pose(sc["T_od"], self.translation, self.rotation)
        self.out = simulate(T0, sc["points"], PBVS(sc["points"], sc["T_od"], lam=self.lam), dt=DT, steps=STEPS)

    def state(self) -> dict:
        sc = self.scene
        e = self.out["e"]                               # ({}^d t_c, theta m) at every step
        theta = np.linalg.norm(e[:, 3:], axis=1)
        axis = np.where(theta[:, None] > 1e-9, e[:, 3:] / np.maximum(theta[:, None], 1e-12), 0.0)
        return {
            "preset": self.preset, "presets": {k: v[2] for k, v in START_POSES.items()}, "lam": self.lam,
            "points": sc["points"], "T_od": sc["T_od"], "s_star": sc["s_star"],
            "t_dc": e[:, :3], "theta": theta, "axis": axis,
            "camera_in_desired": np.array([(inverse(sc["T_od"]) @ T)[:3, 3] for T in self.out["T"]]),
            **trajectory(self.out),
        }
