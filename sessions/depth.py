"""
Lecture 2, demo 5 - The depth in the interaction matrix (slides 33-34).
=======================================================================

The scene of slide 33: the true depth at the goal is Z = 3. The interaction
matrix uses either the true depths (a 3-D sensor), a constant guess Z_hat, or
an online estimate: with L_p = [L_nu / Z, L_omega], the measured image motion
gives A phi = b, with A = L_nu nu_c, b = s_dot - L_omega omega_c and phi = 1/Z,
solved by least squares for each point. A run with the true depths is kept as
the reference.
"""
from __future__ import annotations

import numpy as np

from course.geometry import inverse
from course.servo import IBVS, simulate

from .common import Session
from .servo_common import scene, start_pose, trajectory

DT, STEPS = 0.04, 1200
MODES = ("true", "constant", "online")
START = ([0.45, -0.3, -2.1], [0.1, -0.2, 0.45])        # the "general" start of the other demos, scaled by 3


class DepthSession(Session):

    def __init__(self):
        self.scene = scene(depth=3.0, half=0.9)
        self.act_reset()

    def act_reset(self):
        self.mode, self.Z_hat, self.lam = "constant", 1.0, 0.8
        self._run()
        return self.state()

    def act_set(self, mode=None, Z_hat=None, lam=None):
        if mode is not None:
            if mode not in MODES:
                raise KeyError(f"unknown depth mode: {mode}")
            self.mode = mode
        if Z_hat is not None:
            self.Z_hat = float(np.clip(Z_hat, 0.3, 30.0))
        if lam is not None:
            self.lam = float(np.clip(lam, 0.1, 2.0))
        self._run()
        return self.state()

    def _simulate(self, depth):
        sc = self.scene
        controller = IBVS(sc["s_star"], sc["Z_star"], lam=self.lam, depth=depth, Z_hat=self.Z_hat)
        return simulate(start_pose(sc["T_od"], *START), sc["points"], controller, dt=DT, steps=STEPS, tol=1e-4)

    def _run(self):
        self.out = self._simulate(self.mode)
        self.reference = self.out if self.mode == "true" else self._simulate("true")

    def state(self) -> dict:
        sc = self.scene
        T_do = inverse(sc["T_od"])
        final = T_do @ self.out["T"][-1]
        ref = self.reference
        return {
            "mode": self.mode, "Z_hat0": self.Z_hat, "lam": self.lam,
            "points": sc["points"], "T_od": sc["T_od"], "s_star": sc["s_star"], "Z_star": sc["Z_star"],
            "final_position_error": float(np.linalg.norm(final[:3, 3])),
            "reference": {"times": ref["times"], "e_norm": ref["e_norm"], "nu_norm": np.linalg.norm(ref["v"][:, :3], axis=1),
                          "status": ref["status"]},
            "nu_norm": np.linalg.norm(self.out["v"][:, :3], axis=1),
            **trajectory(self.out),
        }
