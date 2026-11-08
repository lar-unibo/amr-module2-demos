"""
Lecture 2, demo 4 - IBVS control law and its issues (slides 31-32 and 36).
=========================================================================

v_c = -lambda L_hat^+ (s - s*) with four points. The page compares the three
usual choices of L_hat (at the current features, at the desired ones, or
their mean) on the start poses of slide 36: rotations about the optical axis
give camera retreat (L(s)), advance (L(s*)), or a pure rotation (mean).
"""
from __future__ import annotations

import numpy as np

from course.geometry import inverse
from course.servo import IBVS, simulate

from .common import Session
from .servo_common import START_POSES, scene, start_pose, trajectory

DT, STEPS = 0.04, 450
INTERACTIONS = ("current", "desired", "mean")


class IBVSSession(Session):

    def __init__(self):
        self.scene = scene()
        self.act_reset()

    def act_reset(self):
        self.preset, self.interaction, self.lam = "general", "current", 0.8
        self.translation, self.rotation = (np.array(x, float) for x in START_POSES["general"][:2])
        self._run()
        return self.state()

    def act_set(self, preset=None, interaction=None, lam=None, translation=None, rotation=None):
        if preset is not None:
            self.preset = preset
            self.translation, self.rotation = (np.array(x, float) for x in START_POSES[preset][:2])
        if translation is not None:
            self.translation, self.preset = np.clip(np.asarray(translation, float), -1.0, 1.0), None
        if rotation is not None:
            self.rotation, self.preset = np.clip(np.asarray(rotation, float), -np.pi, np.pi), None
        if interaction is not None:
            if interaction not in INTERACTIONS:
                raise KeyError(f"unknown interaction matrix: {interaction}")
            self.interaction = interaction
        if lam is not None:
            self.lam = float(np.clip(lam, 0.1, 2.0))
        self._run()
        return self.state()

    def _run(self):
        sc = self.scene
        controller = IBVS(sc["s_star"], sc["Z_star"], lam=self.lam, interaction=self.interaction)
        T0 = start_pose(sc["T_od"], self.translation, self.rotation)
        self.out = simulate(T0, sc["points"], controller, dt=DT, steps=STEPS)

    def state(self) -> dict:
        sc = self.scene
        T_do = inverse(sc["T_od"])
        camera_in_desired = np.array([(T_do @ T)[:3, 3] for T in self.out["T"]])
        return {
            "preset": self.preset, "presets": {k: v[2] for k, v in START_POSES.items()},
            "interaction": self.interaction, "lam": self.lam,
            "translation": self.translation, "rotation": self.rotation,
            "points": sc["points"], "T_od": sc["T_od"], "s_star": sc["s_star"],
            "camera_in_desired": camera_in_desired,
            **trajectory(self.out),
        }
