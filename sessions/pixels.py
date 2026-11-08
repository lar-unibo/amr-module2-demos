"""
Lecture 1, demo 2 - Discrete camera model, camera matrix and homography (slides 19-23).
======================================================================================

The image plane is a W x H grid of pixels of size rho_w x rho_h, with the origin
at the top-left corner: u = x / rho_w + u0, v = y / rho_h + v0. The intrinsic
matrix K, the extrinsics {}^C T_0 and the projection [I|0] form the 3x4
camera matrix C = K [I|0] {}^C T_0, defined up to scale (11 unknowns). For
the points of the table (Z = 0) it reduces to the 3x3 homography H.
"""
from __future__ import annotations

import numpy as np

from course.calibration import intrinsic_matrix
from course.geometry import transform

from .camera_common import H, RHO, W, camera_pose, extrinsics, house
from .common import Session

TABLE = 0.3                           # half side of the table grid (m)


class PixelsSession(Session):

    def __init__(self):
        self.vertices, self.edges = house()
        self.act_reset()

    def act_reset(self):
        self.f_mm, self.rho_w_um, self.rho_h_um, self.u0, self.v0 = 4.0, 5.0, 5.0, 320.0, 240.0
        self.azimuth, self.elevation, self.distance, self.selected = 35.0, 30.0, 1.1, 6
        return self.state()

    def act_set(self, f_mm=None, rho_w_um=None, rho_h_um=None, u0=None, v0=None, azimuth=None, elevation=None, distance=None,
                selected=None):
        for name, value, lo, hi in (("f_mm", f_mm, 2, 12), ("rho_w_um", rho_w_um, 2, 10), ("rho_h_um", rho_h_um, 2, 10),
                                    ("u0", u0, 200, 440), ("v0", v0, 140, 340), ("azimuth", azimuth, -180, 180),
                                    ("elevation", elevation, 10, 80), ("distance", distance, 0.5, 2.0)):
            if value is not None:
                setattr(self, name, float(np.clip(value, lo, hi)))
        if selected is not None:
            self.selected = int(np.clip(selected, 0, len(self.vertices) - 1))
        return self.state()

    def state(self) -> dict:
        f, rw, rh = self.f_mm * 1e-3, self.rho_w_um * 1e-6, self.rho_h_um * 1e-6
        K = intrinsic_matrix(f / rw, f / rh, self.u0, self.v0)
        T_0c = camera_pose(self.azimuth, self.elevation, self.distance)
        T_c0 = extrinsics(T_0c)
        C = K @ np.hstack([np.eye(3), np.zeros((3, 1))]) @ T_c0           # C = K [I|0] {}^C T_0
        Hm = K @ T_c0[:3][:, [0, 1, 3]]                                    # K [r1 r2 t]: points with Z = 0
        P_c = transform(T_c0, self.vertices)
        image = f * P_c[:, :2] / P_c[:, 2:3]                               # metres on the image plane
        uv = np.column_stack([image[:, 0] / rw + self.u0, image[:, 1] / rh + self.v0])
        lines = []
        for c in np.linspace(-TABLE, TABLE, 7):                            # the table grid, mapped by H
            for a, b in (((c, -TABLE), (c, TABLE)), ((-TABLE, c), (TABLE, c))):
                pts = np.linspace(a, b, 2)
                q = np.c_[pts, np.ones(2)] @ Hm.T
                lines.append(q[:, :2] / q[:, 2:])
        return {
            "f_mm": self.f_mm, "rho_w_um": self.rho_w_um, "rho_h_um": self.rho_h_um, "u0": self.u0, "v0": self.v0,
            "azimuth": self.azimuth, "elevation": self.elevation, "distance": self.distance, "selected": self.selected,
            "W": W, "H": H, "K": K, "C": C / C[2, 3], "Hm": Hm / Hm[2, 2], "T_0c": T_0c, "T_c0": T_c0,
            "world": self.vertices, "edges": self.edges, "P_c": P_c, "image_mm": image * 1e3, "uv": uv,
            "table_lines": lines, "table_half": TABLE,
            "sensor_mm": [W * rw * 1e3, H * rh * 1e3],
            "fov_deg": [float(np.degrees(2 * np.arctan(W * rw / (2 * f)))), float(np.degrees(2 * np.arctan(H * rh / (2 * f))))],
            "C_check": float(np.abs((np.c_[self.vertices, np.ones(len(self.vertices))] @ C.T)[:, :2]
                                    / (np.c_[self.vertices, np.ones(len(self.vertices))] @ C.T)[:, 2:] - uv).max()),
        }
