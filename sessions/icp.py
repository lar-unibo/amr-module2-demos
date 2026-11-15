"""
Lecture 3, demo 3 - ICP: registration without known correspondences (slides 46-51).
===================================================================================

A known object (an L-shaped bracket, model points m_i sampled on its CAD
surface) lies on the table at the unknown pose T_obj. A depth camera with a
known pose T_cam sees only its front: s_j^c = d K^-1 [u v 1]^T, s_j = T_cam s_j^c,
with noise on the depth, dropouts on grazing surfaces, and optional stray
points (outliers). ICP starts from an initial guess (the true pose turned about
the vertical and shifted on the table) and alternates closest points and
alignment; every iteration is returned, so the page can replay the run.
"""
from __future__ import annotations

import numpy as np

from course.geometry import exp_so3, pose, transform
from course.pointcloud import BRACKET, DepthCamera, box_edges, sample_surface
from course.registration import icp, nearest, pca_normals, rotation_error

from .common import Session

TRUE_YAW = 10.0                      # degrees, the unknown pose of the bracket on the table
MODEL_POINTS = 1000
MAX_ITERATIONS = 60
PARAMS = {"yaw0": (-180.0, 180.0), "dx0": (-6.0, 6.0), "dy0": (-6.0, 6.0), "noise": (0.0, 8.0),
          "outliers": (0, 200), "reject_distance": (0.3, 5.0), "reject_worst": (1.0, 50.0)}
BASE = {"yaw0": 10.0, "dx0": 1.5, "dy0": -1.0, "metric": "point", "reject": "none", "reject_distance": 1.5,
        "reject_worst": 15.0, "noise": 2.0, "outliers": 0}
PRESETS = {
    "good": {},
    "plane": {"metric": "plane"},
    "far": {"yaw0": -90.0, "dx0": 0.0, "dy0": 0.0},
    "outliers": {"outliers": 120},
    "rejection": {"outliers": 120, "reject": "distance"},
}


class ICPSession(Session):

    def __init__(self, preset: str = "good"):
        self.camera = DepthCamera(eye=(0.36, -0.25, 0.30))
        self.T_obj = pose(exp_so3([0.0, 0.0, np.radians(TRUE_YAW)]))
        self.model, _ = sample_surface(BRACKET, MODEL_POINTS, np.random.default_rng(1))
        self.edges = box_edges(BRACKET)
        self._scene_key = None
        self.act_preset(preset if preset in PRESETS else "good")

    # ------------------------------------------------------------------ actions
    def act_reset(self):
        return self.act_preset("good")

    def act_preset(self, name: str):
        self.params = {**BASE, **PRESETS[name]}
        self.preset = name
        self._run()
        return self.state()

    def act_set(self, **changes):
        for key, value in changes.items():
            if key in PARAMS:
                lo, hi = PARAMS[key]
                self.params[key] = type(lo)(np.clip(value, lo, hi))
            elif key == "metric" and value in ("point", "plane"):
                self.params[key] = value
            elif key == "reject" and value in ("none", "distance", "worst"):
                self.params[key] = value
            else:
                raise KeyError(key)
        self.preset = None
        self._run()
        return self.state()

    # ------------------------------------------------------------------ computation
    def _scene(self):
        key = (self.params["noise"], self.params["outliers"])
        if key == self._scene_key:
            return
        cam = self.camera
        view = cam.render(BRACKET, self.T_obj, noise=self.params["noise"] / 1000, rng=np.random.default_rng(2))
        n = int(self.params["outliers"])
        rng = np.random.default_rng(3)
        u, v = rng.uniform(18, 66, n), rng.uniform(10, 54, n)          # stray depths around the object
        d = rng.uniform(view["d"].min() - 0.1, view["d"].max() + 0.1, n)
        stray = d[:, None] * (np.column_stack([u, v, np.ones(n)]) @ np.linalg.inv(cam.K).T)
        points_c = np.vstack([view["points_c"], stray])
        self.uv = np.vstack([view["uv"], np.column_stack([u, v])])
        self.depth = np.r_[view["d"], d]
        self.outlier = np.r_[np.zeros(len(view["d"]), bool), np.ones(n, bool)]
        self.scene = cam.to_world(points_c)                               # s_j = T_cam s_j^c
        normals_c, _ = pca_normals(points_c, 10, viewpoint=[0.0, 0.0, 0.0])
        self.normals = normals_c @ cam.T_cam[:3, :3].T                    # n_j, in the world frame
        self._scene_key = key

    def initial_guess(self):
        p = self.params
        return pose(exp_so3([0.0, 0.0, np.radians(TRUE_YAW + p["yaw0"])]), [p["dx0"] / 100, p["dy0"] / 100, 0.0])

    def _run(self):
        self._scene()
        p = self.params
        self.records = icp(self.model, self.scene, self.initial_guess(), iterations=MAX_ITERATIONS,
                           metric=p["metric"], normals=self.normals,
                           reject_distance=p["reject_distance"] / 100 if p["reject"] == "distance" else None,
                           reject_worst=p["reject_worst"] / 100 if p["reject"] == "worst" else 0.0)

    # ------------------------------------------------------------------ state
    def state(self) -> dict:
        R_true, t_true = self.T_obj[:3, :3], self.T_obj[:3, 3]
        rot = [float(np.degrees(rotation_error(R_true, r["T"][:3, :3]))) for r in self.records]
        trans = [float(1000 * np.linalg.norm(r["T"][:3, 3] - t_true)) for r in self.records]
        last = self.records[-1]
        cam = self.camera
        return {
            **self.params, "preset": self.preset, "presets": list(PRESETS),
            "model": np.round(self.model, 5).tolist(), "edges": self.edges, "T_true": self.T_obj, "T_cam": cam.T_cam,
            "width": cam.width, "height": cam.height, "K": cam.K,
            "scene": np.round(self.scene, 5).tolist(), "uv": np.round(self.uv, 2).tolist(),
            "depth": np.round(self.depth, 5).tolist(), "outlier": self.outlier,
            "n_scene": len(self.scene), "n_outliers": int(self.outlier.sum()),
            "T": [r["T"] for r in self.records], "E": [r["E"] for r in self.records],
            "rms": [1000 * r["rms"] for r in self.records], "n_kept": [r["n_kept"] for r in self.records],
            # c(j) for every scene point, and the rejected j, at every iteration (plain ints: compact JSON)
            "pairs": [r["pairs"].tolist() for r in self.records],
            "rejected": [np.flatnonzero(~r["kept"]).tolist() for r in self.records],
            "rot_err": rot, "trans_err": trans,
            "iterations": len(self.records) - 1, "converged": bool(last["converged"]),
            "found": bool(rot[-1] < 5.0 and trans[-1] < 10.0),
            # the same RMS at the true pose (all pairs): what a perfect estimate would give
            "rms_true": float(1000 * np.sqrt(np.mean(nearest(self.scene, transform(self.T_obj, self.model))[1] ** 2))),
        }
