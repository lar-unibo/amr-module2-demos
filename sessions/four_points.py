"""
Lecture 2, demo 3 - Why 4 points? (slide 30).
=============================================

Three points fix only the angles between the viewing rays: up to four camera
poses see exactly the same image of them (the perspective-3-point problem).
A fourth point tells them apart. The scene of the slide: a triangle lying on
a table (world z up), point 4 at its centre, and the desired camera above it.

The page solves P3P for the image of points 1-3, shows every solution, and
servos with IBVS from near a chosen solution: with 3 points the camera stops
at that solution with e = 0, with 4 points it reaches the desired pose.
"""
from __future__ import annotations

import numpy as np

from course.geometry import exp_so3, inverse, look_at, pose, transform
from course.pose import p3p
from course.servo import IBVS, measure, simulate

from .common import Session

TRIANGLE = np.array([[0.0, 0.577, 0.0], [-0.5, -0.289, 0.0], [0.5, -0.289, 0.0]])
CENTER = np.array([[0.0, 0.0, 0.0]])
POINTS = np.vstack([TRIANGLE, CENTER])
DT, STEPS = 0.04, 450
NUDGE = pose(exp_so3([0.05, -0.04, 0.03]), [0.04, -0.03, 0.02])   # start "near" a solution


class FourPointsSession(Session):

    def __init__(self):
        self.act_reset()

    def act_reset(self):
        self.height, self.dx, self.dy, self.selected = 1.0, 0.0, 0.0, None
        self._solve()
        return self.state()

    def act_set(self, height=None, dx=None, dy=None):
        if height is not None:
            self.height = float(np.clip(height, 0.5, 2.5))
        if dx is not None:
            self.dx = float(np.clip(dx, -0.4, 0.4))
        if dy is not None:
            self.dy = float(np.clip(dy, -0.4, 0.4))
        self._solve()
        return self.state()

    def act_select(self, index: int):
        self.selected = int(index) if 0 <= int(index) < len(self.solutions) else None
        self._servo()
        return self.state()

    def _solve(self):
        eye = np.array([self.dx, self.dy, self.height])
        self.T_desired = look_at(eye, [0.0, 0.0, 0.0], up=[0.0, 1.0, 0.0])      # {}^w T_c, camera looking down
        P_c = transform(inverse(self.T_desired), TRIANGLE)
        solutions = [inverse(S) for S in p3p(TRIANGLE, P_c)]
        # the desired pose first, then the others by their distance from point 1
        # (as on the slide, pose 2 is the solution beyond point 1)
        solutions.sort(key=lambda T: np.linalg.norm(T[:3, 3] - eye))
        solutions[1:] = sorted(solutions[1:], key=lambda T: np.linalg.norm(T[:3, 3] - TRIANGLE[0]))
        self.solutions = solutions
        if self.selected is None or self.selected >= len(solutions):
            self.selected = 1 if len(solutions) > 1 else 0
        self._servo()

    def _servo(self):
        start = self.solutions[self.selected] @ NUDGE
        runs = {}
        for name, points in (("three", TRIANGLE), ("four", POINTS)):
            desired = measure(self.T_desired, points)
            controller = IBVS(desired["s"], desired["Z"], lam=0.8)
            runs[name] = simulate(start, points, controller, dt=DT, steps=STEPS, tol=1e-6)
        self.runs = runs

    def state(self) -> dict:
        images = [measure(T, POINTS)["s"] for T in self.solutions]
        desired = images[0]
        runs = {}
        for name, out in self.runs.items():
            T_end = out["T"][-1]
            runs[name] = {
                "times": out["times"], "positions": out["T"][:, :3, 3], "T": out["T"], "status": out["status"],
                "e_norm": out["e_norm"], "s4": [measure(T, POINTS)["s"] for T in out["T"]],
                "final_distance": float(np.linalg.norm(T_end[:3, 3] - self.T_desired[:3, 3])),
            }
        return {
            "height": self.height, "dx": self.dx, "dy": self.dy, "points": POINTS,
            "solutions": self.solutions, "images": images, "selected": self.selected,
            "point4_gap": [float(np.linalg.norm(img[3] - desired[3])) for img in images],
            "triangle_gap": [float(np.abs(img[:3] - desired[:3]).max()) for img in images],
            "runs": runs,
        }
