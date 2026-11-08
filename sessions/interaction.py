"""
Lecture 2, demo 2 - Interaction matrix of a point (slides 25-29).
=================================================================

A static point P = (x Z, y Z, Z) is seen by a camera that moves for a time
`horizon` with the constant velocity v_c = (nu_c, omega_c). The page compares
the image path of the point (exact rigid motion and projection) with the
first-order prediction s + L_p v_c t, splits the image velocity into its
translational part (proportional to 1/Z) and its rotational part
(independent of Z), and shows the camera motions that leave the point still
(the 4-dimensional null space of L_p).
"""
from __future__ import annotations

import numpy as np

from course import (back_project, exp_se3, inverse, null_space, point_interaction, project,
                    transform)

from .common import Session

LIMITS = {"x": (-0.6, 0.6), "y": (-0.45, 0.45), "Z": (0.3, 5.0), "horizon": (0.2, 3.0)}
V_MAX = 0.6                 # m/s for nu_c, rad/s for omega_c
SPEED = 0.3                 # speed of the preset motions
SAMPLES = 41                # points along the image path
MIN_DEPTH = 0.05            # the point is drawn only while in front of the camera


def _unit(v):
    v = np.asarray(v, float)
    return v / np.linalg.norm(v)


class InteractionSession(Session):

    def __init__(self):
        self.rng = np.random.default_rng(3)
        self.act_reset()

    # ------------------------------------------------------------ actions
    def act_reset(self):
        self.x, self.y, self.Z, self.horizon = 0.2, -0.1, 1.5, 1.0
        self.v = np.array([SPEED, 0.0, 0.0, 0.0, 0.0, 0.0])
        self.preset = "lateral"
        return self.state()

    def act_set(self, x=None, y=None, Z=None, horizon=None, v=None):
        for name, value in (("x", x), ("y", y), ("Z", Z), ("horizon", horizon)):
            if value is not None:
                setattr(self, name, float(np.clip(value, *LIMITS[name])))
        if v is not None:
            self.v = np.clip(np.asarray(v, float), -V_MAX, V_MAX)
            self.preset = None
        elif self.preset in ("ray", "roll_ray", "null"):   # these depend on (x, y, Z): recompute
            self._apply_preset(self.preset)
        return self.state()

    def act_preset(self, name: str):
        self._apply_preset(name)
        return self.state()

    def _apply_preset(self, name: str):
        ray = _unit([self.x, self.y, 1.0])
        motions = {
            "zero": np.zeros(6),
            "lateral": np.r_[SPEED, 0, 0, 0, 0, 0],
            "forward": np.r_[0, 0, SPEED, 0, 0, 0],
            "pan": np.r_[0, 0, 0, 0, SPEED, 0],
            "roll": np.r_[0, 0, 0, 0, 0, SPEED],
            "ray": np.r_[SPEED * ray, 0, 0, 0],          # translation along the projection ray
            "roll_ray": np.r_[0, 0, 0, SPEED * ray],     # rotation about the projection ray
        }
        if name == "null":                               # a random camera motion in Null(L_p)
            N = null_space(point_interaction(self.x, self.y, self.Z))
            v = N @ self.rng.standard_normal(N.shape[1])
            v *= 1.5 * SPEED / np.linalg.norm(v)
            self.v = v * min(1.0, V_MAX / np.abs(v).max())
        elif name in motions:
            self.v = motions[name]
        else:
            raise KeyError(f"unknown preset: {name}")
        self.preset = name

    # ------------------------------------------------------------ state
    def state(self) -> dict:
        L = point_interaction(self.x, self.y, self.Z)
        s = np.array([self.x, self.y])
        P = back_project(s, self.Z)[0]
        s_dot = L @ self.v

        times = np.linspace(0.0, self.horizon, SAMPLES)
        cameras = np.array([exp_se3(self.v, t) for t in times])        # poses in the initial camera frame
        points = np.array([transform(inverse(T), P) for T in cameras])  # P seen from the moving camera
        in_front = points[:, 2] > MIN_DEPTH
        path = np.full((SAMPLES, 2), np.nan)
        path[in_front] = project(points[in_front])
        linear = s + np.outer(times, s_dot)

        dt = 1e-5                                                       # measured velocity at t = 0
        s_dt = project(transform(inverse(exp_se3(self.v, dt)), P))[0]
        travel = np.linalg.norm(path[-1] - s) if in_front[-1] else np.nan
        gap = np.linalg.norm(path[-1] - linear[-1]) if in_front[-1] else np.nan
        N = null_space(L)
        return {
            "x": self.x, "y": self.y, "Z": self.Z, "horizon": self.horizon, "v": self.v,
            "preset": self.preset, "limits": LIMITS, "v_max": V_MAX,
            "L": L, "s": s, "P": P,
            "s_dot": s_dot, "s_dot_translation": L[:, :3] @ self.v[:3],
            "s_dot_rotation": L[:, 3:] @ self.v[3:], "s_dot_measured": (s_dt - s) / dt,
            "times": times, "path": path, "linear": linear,
            "camera_origins": cameras[:, :3, 3], "camera_final": cameras[-1],
            "depth_final": points[-1, 2], "in_view": bool(np.all(in_front)),
            "travel": travel, "gap": gap,
            "rank": int(np.linalg.matrix_rank(L)), "null_basis": N,
            "v_in_null": float(np.linalg.norm(L @ self.v)) < 1e-9 * max(1.0, np.linalg.norm(self.v)),
        }
