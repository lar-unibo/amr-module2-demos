"""
Lecture 1, demo 1 - Image formation and central projection (slides 13-18).
=========================================================================

A camera {C} looks at a small house on a table (world frame {0}, z up). Its
pose gives the extrinsics {}^C T_0, and a point P_C = (X, Y, Z) in the camera
frame projects to x = f X / Z, y = f Y / Z on the image plane (at z = f).
Depth is lost: moving a point along its projection ray, or scaling the whole
scene about the camera, leaves the image unchanged. A second panel shows the
thin-lens equation 1/z_o + 1/z_i = 1/f.
"""
from __future__ import annotations

import numpy as np

from course.geometry import transform

from .camera_common import H, RHO, W, camera_pose, extrinsics, house
from .common import Session


class ProjectionSession(Session):

    def __init__(self):
        self.vertices, self.edges = house()
        self.act_reset()

    def act_reset(self):
        self.azimuth, self.elevation, self.distance, self.f_mm = 35.0, 25.0, 1.0, 4.0
        self.selected, self.ray, self.scale, self.z_object = 6, 1.0, 1.0, 0.5
        return self.state()

    def act_set(self, azimuth=None, elevation=None, distance=None, f_mm=None, selected=None, ray=None, scale=None, z_object=None):
        for name, value, lo, hi in (("azimuth", azimuth, -180, 180), ("elevation", elevation, 5, 85),
                                    ("distance", distance, 0.4, 2.5), ("f_mm", f_mm, 2, 12), ("ray", ray, 0.4, 2.5),
                                    ("scale", scale, 0.4, 2.0), ("z_object", z_object, 0.001, 10.0)):
            if value is not None:
                setattr(self, name, float(np.clip(value, lo, hi)))
        if selected is not None:
            self.selected = int(np.clip(selected, 0, len(self.vertices) - 1))
        return self.state()

    def state(self) -> dict:
        T_0c = camera_pose(self.azimuth, self.elevation, self.distance)
        T_c0 = extrinsics(T_0c)
        f = self.f_mm * 1e-3
        P_c = transform(T_c0, self.vertices) * self.scale             # scaling the scene about the camera
        P_c[self.selected] *= self.ray                                  # moving one point along its ray
        world = transform(T_0c, P_c)
        image = f * P_c[:, :2] / P_c[:, 2:3]                           # x = f X / Z, y = f Y / Z (metres)
        z_i = 1.0 / (1.0 / f - 1.0 / self.z_object) if self.z_object > f else float("inf")
        ratios = np.geomspace(1.02, 1e4, 300)                      # thin lens in units of f
        r = self.z_object / f                                           # z_o in units of f
        zi_r = r / (r - 1.0) if abs(r - 1.0) > 1e-9 else None           # z_i / f (negative: virtual image)
        lens = {"zo_over_f": r, "zi_over_f": zi_r, "real": r > 1.0,
                "magnification": (-zi_r / r) if zi_r is not None else None,
                "curve_zo": ratios, "curve_zi": ratios / (ratios - 1.0)}
        return {
            "azimuth": self.azimuth, "elevation": self.elevation, "distance": self.distance, "f_mm": self.f_mm,
            "selected": self.selected, "ray": self.ray, "scale": self.scale, "z_object": self.z_object,
            "T_0c": T_0c, "T_c0": T_c0, "world": world, "edges": self.edges, "P_c": P_c,
            "image_mm": image * 1e3, "sensor_mm": [W * RHO * 1e3, H * RHO * 1e3],
            "fov_deg": [float(np.degrees(2 * np.arctan(W * RHO / (2 * f)))), float(np.degrees(2 * np.arctan(H * RHO / (2 * f))))],
            "z_image_mm": z_i * 1e3 if np.isfinite(z_i) else None, "lens": lens,
        }
