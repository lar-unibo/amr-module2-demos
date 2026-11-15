"""
Lecture 3, demo 4 - Grasp selection from point clouds (slides 51-57, 60).
=========================================================================

A cross-section of a table scene with a novel object (box, blob, cup), seen
by one or two depth cameras above it. The page follows the pipeline of slide
52: normals and surface variation by local PCA (with a probe that shows the
neighbourhood of one point), antipodal pairs inside the friction cones, gripper
poses checked for collisions along the straight approach, the cost of slide 57,
and the pregrasp pose of slide 60. Distances in metres.
"""
from __future__ import annotations

import numpy as np

from course.grasp_selection import (GRIPPER, angle_between, antipodal_pairs, best_distinct, blob, box, cup,
                                    depth_scan, evaluate_grasps, local_pca, orient_towards)

from .common import Session

OBJECTS = {"box": box(), "blob": blob(), "cup": cup()}
CAMERAS = np.array([[-0.16, 0.42], [0.16, 0.42]])
TARGET = np.array([0.0, 0.05])
SCAN = {"pixels": 320, "fov_deg": 44.0}
VIEW_X = (-0.13, 0.13)                       # table points kept for drawing
DEFAULTS = {"object": "box", "cameras": 2, "noise": 0.0005, "k": 15, "orient": True, "mu": 0.4,
            "opening": 0.085, "alpha_reach": 0.5, "alpha_clear": 0.3, "d": 0.06}
PRESETS = {
    "default": {},
    "one-camera": {"cameras": 1},
    "cup": {"object": "cup"},
    "blob": {"object": "blob"},
    "no-orientation": {"orient": False},
    "narrow": {"opening": 0.05},
}
PROBE_AT = {"box": [-0.03, 0.07], "blob": [-0.04, 0.045], "cup": [0.046, 0.08]}
LIMITS = {"noise": (0.0, 0.003), "k": (3, 40), "mu": (0.05, 1.2), "opening": (0.02, 0.12),
          "alpha_reach": (0.0, 2.0), "alpha_clear": (0.0, 2.0), "d": (0.02, 0.15)}


class GraspSelectionSession(Session):

    def __init__(self, preset: str = "default"):
        self.act_preset(preset if preset in PRESETS else "default")

    # ------------------------------------------------------------------ actions
    def act_reset(self):
        return self.act_preset("default")

    def act_preset(self, name: str):
        self.params = {**DEFAULTS, **PRESETS[name]}
        self.preset = name
        self.probe_target = np.array(PROBE_AT[self.params["object"]], float)
        self._scan()
        return self.state()

    def act_set(self, **changes):
        scan = normals = False
        for key, value in changes.items():
            if key not in DEFAULTS:
                raise KeyError(key)
            if key == "object":
                if value not in OBJECTS:
                    raise KeyError(value)
                self.probe_target = np.array(PROBE_AT[value], float)
            elif key == "cameras":
                value = 2 if int(value) >= 2 else 1
            elif key == "orient":
                value = bool(value)
            elif key == "k":
                value = int(np.clip(round(value), *LIMITS["k"]))
            else:
                value = float(np.clip(value, *LIMITS[key]))
            self.params[key] = value
            scan |= key in ("object", "cameras", "noise")
            normals |= key in ("k", "orient")
        self.preset = None
        if scan:
            self._scan()
        elif normals:
            self._normals()
        else:
            self._grasps()
        return self.state()

    def act_probe(self, x: float, z: float):
        """Move the probe to the measured point nearest to (x, z)."""
        self.probe_target = np.array([x, z], float)
        return self.state()

    # ------------------------------------------------------------------ pipeline
    def _scan(self):
        """Depth scans, fusion of the cameras, segmentation (the table points are removed)."""
        p = self.params
        polygon = OBJECTS[p["object"]]
        self.scans = [depth_scan(polygon, CAMERAS[c], TARGET, noise=p["noise"], seed=11 + c, **SCAN)
                      for c in range(p["cameras"])]
        obj = [s["on_object"] for s in self.scans]
        self.cloud = np.vstack([s["points"][m] for s, m in zip(self.scans, obj)])
        self.camera_of = np.concatenate([np.full(m.sum(), c) for c, m in enumerate(obj)])
        self.true_normals = np.vstack([s["normals"][m] for s, m in zip(self.scans, obj)])
        self.table = np.vstack([s["points"][~m] for s, m in zip(self.scans, obj)])
        self._normals()

    def _normals(self):
        p = self.params
        self.pca = local_pca(self.cloud, p["k"])
        v0 = self.pca["v0"]
        if p["orient"]:
            self.normals = orient_towards(v0, self.cloud, CAMERAS[self.camera_of])
        else:
            # PCA gives +-v0: without a rule the sign is arbitrary (here: random, fixed per point)
            signs = np.random.default_rng(5).choice([-1.0, 1.0], len(self.cloud))
            self.normals = v0 * signs[:, None]
        self._grasps()

    def _grasps(self):
        p = self.params
        self.pairs = antipodal_pairs(self.cloud, self.normals, p["mu"], p["opening"])
        self.grasps = evaluate_grasps(self.cloud, self.pairs, max_opening=p["opening"], pregrasp=p["d"],
                                      alpha_reach=p["alpha_reach"], alpha_clear=p["alpha_clear"])
        self.top = best_distinct(self.grasps)

    # ------------------------------------------------------------------ state
    def _probe(self) -> dict:
        i = int(np.argmin(np.linalg.norm(self.cloud - self.probe_target, axis=1)))
        pca = self.pca
        return {"index": i, "point": self.cloud[i], "neighbours": pca["neighbours"][i], "mean": pca["mean"][i],
                "lam": pca["lam"][i], "v0": pca["v0"][i], "v1": pca["v1"][i], "sigma": float(pca["sigma"][i]),
                "normal": self.normals[i], "camera": int(self.camera_of[i]), "true_normal": self.true_normals[i],
                "error_deg": float(np.degrees(angle_between(self.normals[i], self.true_normals[i]))),
                "flipped": bool(self.pca["v0"][i] @ self.normals[i] < 0)}

    def state(self) -> dict:
        p, G = self.params, self.grasps
        free = ~G["collision"]
        # the pairs drawn: collision-free ones first, at most 240
        shown = np.r_[np.flatnonzero(free), np.flatnonzero(~free)][:240]
        top = [{
            "i": int(G["i"][k]), "j": int(G["j"][k]),
            "contacts": [self.cloud[G["i"][k]], self.cloud[G["j"][k]]],
            "normals": [self.normals[G["i"][k]], self.normals[G["j"][k]]],
            "distance": float(G["dist"][k]), "opening": float(G["opening"][k]),
            "centre": G["centre"][k], "xg": G["xg"][k], "zg": G["zg"][k], "pregrasp": G["pregrasp"][k],
            "theta1": float(np.degrees(G["theta1"][k])), "theta2": float(np.degrees(G["theta2"][k])),
            "c_antipodal": float(G["c_antipodal"][k]), "c_reach": float(G["c_reach"][k]),
            "c_clear": float(G["c_clear"][k]), "cost": float(G["cost"][k]), "clearance": float(G["clearance"][k]),
        } for k in self.top]
        in_view = (self.table[:, 0] > VIEW_X[0]) & (self.table[:, 0] < VIEW_X[1])
        err = np.degrees(angle_between(self.normals, self.true_normals))
        return {
            **p, "preset": self.preset, "cone_half_angle": float(np.degrees(np.arctan(p["mu"]))),
            "outline": np.vstack([OBJECTS[p["object"]], OBJECTS[p["object"]][:1]]),
            "camera_positions": CAMERAS[:p["cameras"]], "target": TARGET,
            "rays": [s["points"][::14] for s in self.scans],
            "table": self.table[in_view], "cloud": self.cloud, "camera_of": self.camera_of,
            "normals": self.normals, "sigma": self.pca["sigma"], "probe": self._probe(),
            "pairs": [[int(G["i"][k]), int(G["j"][k]), bool(free[k])] for k in shown],
            "counts": {"points": len(self.cloud), "within_opening": self.pairs["within_opening"],
                       "antipodal": len(self.pairs["i"]), "evaluated": len(G["cost"]), "free": int(free.sum())},
            "normal_error": {"median": float(np.median(err)), "inward": float(np.mean(err > 90))},
            "top": top, "gripper": {**GRIPPER, "max_opening": p["opening"]},
        }
