"""
Lecture 2, demo 7 - Stability of IBVS (slides 38-39).
=====================================================

IBVS with four points: e in R^8, but only 6 camera velocities. The page
follows the 6-D error the controller acts on, e' = L_hat^+ e (v_c = -lambda e'),
and checks the conditions of the slides at any step: L L_hat^+ (8x8, rank <= 6,
never > 0) and L_hat^+ L (6x6, > 0 near the goal for good estimates).

Moving one desired point makes the target unreachable: no pose sees that
image (8 numbers, 6 degrees of freedom). The camera then stops where e' = 0
while e != 0: the remaining error lies in Ker(L_hat^+), invisible to the
controller. This is the best fit, not a local minimum: the page compares the
final error with the smallest error any pose can reach (the pose that best
fits the desired image, found by the pose estimator).
"""
from __future__ import annotations

import numpy as np

from course.geometry import inverse
from course.interaction import stacked_interaction
from course.pose import planar_pose
from course.servo import IBVS, measure, simulate

from .common import Session
from .servo_common import START_POSES, scene, start_pose, trajectory

DT, STEPS = 0.04, 450
PRESETS = ("general", "translation", "rot_z_1", "rot_z_pi", "tilt")
INTERACTIONS = ("current", "desired", "mean")
SAMPLE_EVERY = 5


def sym_eigenvalues(M):
    return np.sort(np.linalg.eigvalsh(0.5 * (M + M.T)))


class StabilitySession(Session):

    def __init__(self):
        self.scene = scene()
        self.act_reset()

    def act_reset(self):
        self.preset, self.interaction, self.depth, self.Z_hat, self.lam = "general", "current", "true", 1.0, 0.8
        self.offset = np.zeros(2)                # displacement of desired point 1 (image units)
        self._run()
        return self.state()

    def act_set(self, preset=None, interaction=None, depth=None, Z_hat=None, offset=None, lam=None):
        if preset is not None:
            if preset not in PRESETS:
                raise KeyError(f"unknown preset: {preset}")
            self.preset = preset
        if interaction is not None:
            if interaction not in INTERACTIONS:
                raise KeyError(f"unknown interaction matrix: {interaction}")
            self.interaction = interaction
        if depth is not None:
            if depth not in ("true", "constant"):
                raise KeyError(f"unknown depth mode: {depth}")
            self.depth = depth
        if Z_hat is not None:
            self.Z_hat = float(np.clip(Z_hat, 0.1, 30.0))
        if offset is not None:
            self.offset = np.clip(np.asarray(offset, float), -0.25, 0.25)
        if lam is not None:
            self.lam = float(np.clip(lam, 0.1, 2.0))
        self._run()
        return self.state()

    def _controller(self):
        sc = self.scene
        s_star = sc["s_star"].copy()
        s_star[0] += self.offset
        return IBVS(s_star, sc["Z_star"], lam=self.lam, interaction=self.interaction, depth=self.depth, Z_hat=self.Z_hat)

    def _run(self):
        sc = self.scene
        self.controller = self._controller()
        self.out = simulate(start_pose(sc["T_od"], *START_POSES[self.preset][:2]), sc["points"],
                            self._controller(), dt=DT, steps=STEPS)

    def _matrices(self, k):
        """True L and the controller's L_hat at step k."""
        s, Z = self.out["s"][k], self.out["Z"][k]
        L = stacked_interaction(s, Z)
        L_hat = self.controller.matrix(s, Z if self.depth == "true" else self.controller.Z_est)
        return L, L_hat

    def act_analyze(self, k: int):
        k = int(np.clip(k, 0, len(self.out["s"]) - 1))
        L, L_hat = self._matrices(k)
        Lp = np.linalg.pinv(L_hat)
        e = self.out["e"][k]
        P = L @ np.linalg.pinv(L)                # projection onto Range(L)
        return {
            "k": k,
            "global": sym_eigenvalues(L @ Lp),                     # 8 values: L L_hat^+
            "local": sym_eigenvalues(Lp @ L),                      # 6 values: L_hat^+ L
            "e_norm": float(np.linalg.norm(e)),
            "e_proj_norm": float(np.linalg.norm(Lp @ e)),
            "invisible": float(np.linalg.norm(e - P @ e)),        # part of e outside Range(L)
        }

    def state(self) -> dict:
        sc = self.scene
        n = len(self.out["s"])
        samples = list(range(0, n, SAMPLE_EVERY)) + ([n - 1] if (n - 1) % SAMPLE_EVERY else [])
        margin = []
        for k in samples:
            L, L_hat = self._matrices(k)
            margin.append(sym_eigenvalues(np.linalg.pinv(L_hat) @ L)[0])
        s_star = sc["s_star"].copy()
        s_star[0] += self.offset
        reachable = bool(np.linalg.norm(self.offset) < 1e-12)
        if reachable:
            best_error = 0.0
        else:                                    # the camera pose that best fits the desired image
            T_best = inverse(planar_pose(sc["points"], s_star))
            best_error = float(np.linalg.norm(measure(T_best, sc["points"])["s"] - s_star))
        return {
            "target_reachable": reachable, "best_error": best_error, "s_star_original": sc["s_star"],
            "preset": self.preset, "presets": {k: START_POSES[k][2] for k in PRESETS},
            "interaction": self.interaction, "depth": self.depth, "Z_hat_constant": self.Z_hat, "lam": self.lam,
            "offset": self.offset, "points": sc["points"], "T_od": sc["T_od"], "s_star": s_star,
            "margin_times": np.array(samples) * DT, "margin": np.array(margin),
            **trajectory(self.out),
        }
