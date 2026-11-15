"""
Lecture 3, demo 2 - Point-cloud registration with known correspondences (slides 39-44).
=======================================================================================

Model points m_i (object frame) and scene points s_i = T_obj m_i + noise,
paired by index. The closed-form solution of the slides: centroids,
cross-covariance M = sum s~_i m~_i^T, SVD M = U Sigma V^T, R* = U D V^T,
t* = s_bar - R* m_bar. Options: wrong pairs (least squares is not robust), a
thin flat plate (nearly coplanar points: the best orthogonal matrix can be a
reflection), and the correction D switched off.
"""
from __future__ import annotations

import numpy as np

from course.geometry import exp_so3, pose, transform
from course.pointcloud import BRACKET, box_edges, sample_surface
from course.registration import register, rotation_error

from .common import Session

# an L-shaped plate 2 mm thick (metres), z up
PLATE = np.array([
    [[-0.08, -0.05, 0.0], [0.08, 0.0, 0.002]],
    [[0.03, 0.0, 0.0], [0.08, 0.07, 0.002]],
])
OBJECTS = {"bracket": BRACKET, "plate": PLATE}
N_MAX = 120
PARAMS = {"n": (3, N_MAX), "noise": (0.0, 20.0), "wrong": (0, 60), "yaw": (-180.0, 180.0), "tilt": (-90.0, 90.0),
          "tx": (0.0, 0.4), "tz": (-0.1, 0.25), "seed": (0, 999)}
BASE = {"object": "bracket", "n": 30, "noise": 2.0, "wrong": 0, "yaw": 50.0, "tilt": 30.0, "tx": 0.26, "tz": 0.08,
        "correct": True, "seed": 0}
PRESETS = {
    "default": {},
    "three": {"n": 3, "noise": 0.0},
    "noisy": {"noise": 10.0},
    "wrong": {"wrong": 4},
    "mirror": {"object": "plate", "n": 12, "noise": 5.0, "correct": False, "seed": 0},
}


class RegistrationSession(Session):

    def __init__(self, preset: str = "default"):
        self.models = {name: sample_surface(boxes, N_MAX, np.random.default_rng(4))[0]
                       for name, boxes in OBJECTS.items()}
        self.act_preset(preset if preset in PRESETS else "default")

    def act_reset(self):
        return self.act_preset("default")

    def act_preset(self, name: str):
        self.params = {**BASE, **PRESETS[name]}
        self.preset = name
        return self.state()

    def act_set(self, **changes):
        for key, value in changes.items():
            if key in PARAMS:
                lo, hi = PARAMS[key]
                self.params[key] = type(lo)(np.clip(value, lo, hi))
            elif key == "object" and value in OBJECTS:
                self.params[key] = value
            elif key == "correct":
                self.params[key] = bool(value)
            else:
                raise KeyError(key)
        self.params["wrong"] = min(self.params["wrong"], self.params["n"] - 3 if self.params["n"] > 3 else 0)
        self.preset = None
        return self.state()

    def act_resample(self):
        """New noise (and new wrong pairs): another seed."""
        return self.act_set(seed=(self.params["seed"] + 1) % 1000)

    def T_true(self):
        p = self.params
        R = exp_so3([0.0, 0.0, np.radians(p["yaw"])]) @ exp_so3([np.radians(p["tilt"]), 0.0, 0.0])
        return pose(R, [p["tx"], 0.05, p["tz"]])

    def state(self) -> dict:
        p = self.params
        rng = np.random.default_rng(100 + p["seed"])
        m = self.models[p["object"]][:p["n"]]
        T = self.T_true()
        s = transform(T, m) + rng.normal(scale=p["noise"] / 1000, size=m.shape)
        wrong = np.zeros(p["n"], bool)
        if p["wrong"] > 0:                                     # pair some scene points with the wrong model point
            idx = rng.choice(p["n"], size=p["wrong"], replace=False)
            s[idx] = s[np.roll(idx, 1)]
            wrong[idx] = True
        out = register(m, s, correct=p["correct"])
        other = register(m, s, correct=not p["correct"])
        R, t = out["R"], out["t"]
        is_rotation = bool(np.linalg.det(R) > 0)
        boxes = OBJECTS[p["object"]]
        return {
            **p, "preset": self.preset, "presets": list(PRESETS),
            "m": m, "s": s, "wrong_mask": wrong, "T_true": T, "edges": box_edges(boxes),
            "m_bar": out["m_bar"], "s_bar": out["s_bar"], "M": out["M"], "U": out["U"], "sigma": out["sigma"],
            "Vt": out["Vt"], "D": out["D"], "det_UVt": out["det_UVt"], "R": R, "t": t, "det_R": float(np.linalg.det(R)),
            "aligned": transform(_affine(R, t), m),
            "rms": 1000 * out["rms"], "rms_other": 1000 * other["rms"],
            "rot_err": float(np.degrees(rotation_error(T[:3, :3], R))) if is_rotation else None,
            "trans_err": float(1000 * np.linalg.norm(t - T[:3, 3])),
            "is_rotation": is_rotation,
        }


def _affine(R, t):
    A = np.eye(4)
    A[:3, :3], A[:3, 3] = R, t
    return A
