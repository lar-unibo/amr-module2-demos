"""
Lecture 1, demo 3 - Lens distortion (slides 27-29).
==================================================

The distortion model of the slides, D = (k1, k2, k3, p1, p2), applied to
normalized image coordinates (as in OpenCV): radial terms move points along
lines through the principal point (barrel for k1 < 0, pincushion for k1 > 0),
tangential terms come from a decentred lens. The page distorts a grid and
corrects it again by inverting the model (fixed-point iteration).
"""
from __future__ import annotations

import numpy as np

from course.camera import distort, undistort

from .common import Session

FX = FY = 800.0
U0, V0 = 320.0, 240.0
W, H = 640, 480
PRESETS = {
    "none": [0, 0, 0, 0, 0],
    "barrel": [-0.3, 0.1, 0, 0, 0],
    "pincushion": [0.25, 0.05, 0, 0, 0],
    "tangential": [0, 0, 0, 0.012, -0.008],
    "wide-angle": [-0.38, 0.17, -0.035, 0.0, 0.0],
}


def to_pixels(xy):
    return np.column_stack([FX * xy[:, 0] + U0, FY * xy[:, 1] + V0])


class DistortionSession(Session):

    def __init__(self):
        self.act_preset("barrel")

    def act_preset(self, name: str):
        self.D = np.array(PRESETS[name], float)
        self.preset = name
        return self.state()

    def act_set(self, D=None):
        if D is not None:
            limits = np.array([0.5, 0.3, 0.1, 0.03, 0.03])
            self.D = np.clip(np.asarray(D, float), -limits, limits)
            self.preset = None
        return self.state()

    def state(self) -> dict:
        xs = np.linspace(-U0 / FX, (W - U0) / FX, 17)
        ys = np.linspace(-V0 / FY, (H - V0) / FY, 13)
        t = np.linspace(0, 1, 60)
        lines = [np.column_stack([np.full_like(t, x), ys[0] + t * (ys[-1] - ys[0])]) for x in xs]
        lines += [np.column_stack([xs[0] + t * (xs[-1] - xs[0]), np.full_like(t, y)]) for y in ys]
        distorted = [distort(L, self.D) for L in lines]
        corrected = [undistort(L, self.D) for L in distorted]
        gx, gy = np.meshgrid(np.linspace(xs[0], xs[-1], 9), np.linspace(ys[0], ys[-1], 7))
        ideal = np.column_stack([gx.ravel(), gy.ravel()])
        moved = distort(ideal, self.D)
        corner = np.array([[xs[-1], ys[-1]]])
        return {
            "D": self.D, "preset": self.preset, "presets": list(PRESETS), "W": W, "H": H, "fx": FX, "u0": U0, "v0": V0,
            "ideal_lines": [to_pixels(L) for L in lines], "distorted_lines": [to_pixels(L) for L in distorted],
            "corrected_lines": [to_pixels(L) for L in corrected],
            "arrows_from": to_pixels(ideal), "arrows_to": to_pixels(moved),
            "corner_shift_px": float(np.linalg.norm(to_pixels(distort(corner, self.D)) - to_pixels(corner))),
            "correction_error_px": float(max(np.abs(to_pixels(c) - to_pixels(L)).max() for c, L in zip(corrected, lines))),
        }
