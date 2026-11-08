"""
Lecture 1, demo 6 - From pixels to 3-D points, and normal stereo (slides 41-44).
================================================================================

With the depth Z known, a pixel gives the 3-D point P_C = Z K^-1 [u v 1]^T.
Two parallel cameras, with baseline b, measure Z from the disparity:
Z = b f' / d, with f' = f / rho_w in pixels. Disparities are measured in
(sub)pixels, so the depth comes in discrete layers, further apart as Z grows:
delta_Z ~ Z^2 / (b f') delta_d.
"""
from __future__ import annotations

import numpy as np

from course.stereo import depth_resolution, project_stereo, triangulate

from .common import Session

W, H = 640, 480
U0, V0 = 320.0, 240.0
STEPS = {"1 pixel": 1.0, "1/4 pixel": 0.25, "exact": 0.0}


class StereoSession(Session):

    def __init__(self):
        self.act_reset()

    def act_reset(self):
        self.b, self.f_px, self.step, self.noise, self.probe_x, self.probe_z = 0.12, 700.0, "1 pixel", 0.0, 0.3, 3.0
        return self.state()

    def act_set(self, b=None, f_px=None, step=None, noise=None, probe_x=None, probe_z=None):
        for name, value, lo, hi in (("b", b, 0.02, 0.6), ("f_px", f_px, 200, 1600), ("noise", noise, 0.0, 2.0),
                                    ("probe_x", probe_x, -2.0, 2.0), ("probe_z", probe_z, 0.4, 15.0)):
            if value is not None:
                setattr(self, name, float(np.clip(value, lo, hi)))
        if step is not None:
            if step not in STEPS:
                raise KeyError(step)
            self.step = step
        return self.state()

    def _measure(self, P, rng):
        uLuRv = project_stereo(P, self.b, self.f_px, U0, V0)
        d = uLuRv[:, 0] - uLuRv[:, 1] + rng.normal(scale=self.noise, size=len(P))
        q = STEPS[self.step]
        if q > 0:
            d = np.round(d / q) * q
        return uLuRv, d

    def state(self) -> dict:
        probe = np.array([[self.probe_x, 0.3, self.probe_z]])
        p_uv, p_d = self._measure(probe, np.random.default_rng(1))
        p_rec = triangulate(p_uv[:, 0], p_uv[:, 0] - p_d, p_uv[:, 2], self.b, self.f_px, U0, V0)[0]
        zs = np.linspace(0.4, 15.0, 120)
        step = STEPS[self.step] or 1.0
        # the only depths the camera can report: one per disparity value d = k * step
        q = STEPS[self.step]
        layers = [] if q == 0 else [float(self.b * self.f_px / (k * q)) for k in range(1, 4000)
                                    if 0.3 <= self.b * self.f_px / (k * q) <= 16.0]
        K = np.array([[self.f_px, 0, U0], [0, self.f_px, V0], [0, 0, 1]])
        return {
            "b": self.b, "f_px": self.f_px, "step": self.step, "steps": list(STEPS), "noise": self.noise,
            "probe_x": self.probe_x, "probe_z": self.probe_z, "W": W, "H": H, "u0": U0, "v0": V0,
            "probe": probe[0], "probe_left": p_uv[0, [0, 2]], "probe_right": p_uv[0, [1, 2]],
            "probe_disparity_true": float(self.b * self.f_px / self.probe_z), "probe_disparity": float(p_d[0]),
            "probe_reconstructed": p_rec, "probe_resolution": float(depth_resolution(self.probe_z, self.b, self.f_px, step)),
            # slide 41 with the depth measured by the stereo pair
            "back_projection": (p_rec[2] if np.isfinite(p_rec[2]) else np.nan) * np.linalg.inv(K) @ np.array([p_uv[0, 0], p_uv[0, 2], 1.0]),
            "curve_z": zs, "curve_d": self.b * self.f_px / zs,
            "visible": bool(0 <= p_uv[0, 0] < W and 0 <= p_uv[0, 1] < W),
            "layers": layers,
        }
