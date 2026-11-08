"""
Central-projection (pinhole) camera model.
==========================================

Notation of the lecture slides: a point P = (X, Y, Z) in the camera frame
projects to the normalized image coordinates p = (x, y) = (X/Z, Y/Z), i.e. on
an image plane at f = 1. Pixel coordinates follow the discrete camera model

    u = (f / rho_u) x + u_0,     v = (f / rho_v) y + v_0.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


def project(points) -> np.ndarray:
    """Normalized image coordinates (x, y) = (X/Z, Y/Z) of camera-frame points (n, 3)."""
    points = np.atleast_2d(np.asarray(points, float))
    return points[:, :2] / points[:, 2:3]


def back_project(xy, Z) -> np.ndarray:
    """Camera-frame points (x Z, y Z, Z) from normalized coordinates and depths."""
    xy = np.atleast_2d(np.asarray(xy, float))
    Z = np.broadcast_to(np.asarray(Z, float), (xy.shape[0],))
    return np.column_stack([xy * Z[:, None], Z])


@dataclass(frozen=True)
class Intrinsics:
    """Focal length f, pixel sizes rho_u, rho_v, and principal point (u0, v0)."""
    f: float = 0.004                      # 4 mm
    rho_u: float = 5e-6                   # 5 um pixels
    rho_v: float = 5e-6
    u0: float = 320.0
    v0: float = 240.0

    @property
    def K(self) -> np.ndarray:
        """Matrix of the intrinsic parameters, [u, v, 1]^T = K [x, y, 1]^T."""
        return np.array([[self.f / self.rho_u, 0.0, self.u0],
                         [0.0, self.f / self.rho_v, self.v0],
                         [0.0, 0.0, 1.0]])

    def to_pixels(self, xy) -> np.ndarray:
        xy = np.atleast_2d(np.asarray(xy, float))
        return np.column_stack([self.f / self.rho_u * xy[:, 0] + self.u0,
                                self.f / self.rho_v * xy[:, 1] + self.v0])

    def to_normalized(self, uv) -> np.ndarray:
        uv = np.atleast_2d(np.asarray(uv, float))
        return np.column_stack([(uv[:, 0] - self.u0) * self.rho_u / self.f,
                                (uv[:, 1] - self.v0) * self.rho_v / self.f])


# ---------------------------------------------------------------- lens distortion
# Model of the slides (Brown), applied to normalized image coordinates (x, y),
# as in OpenCV and in Corke's book; D = (k1, k2, k3, p1, p2):
#   x_d = x (1 + k1 r^2 + k2 r^4 + k3 r^6) + 2 p1 x y + p2 (r^2 + 2 x^2)
#   y_d = y (1 + k1 r^2 + k2 r^4 + k3 r^6) + p1 (r^2 + 2 y^2) + 2 p2 x y

def distort(xy, D) -> np.ndarray:
    """Distorted normalized coordinates of ideal ones (n, 2); D = (k1, k2, k3, p1, p2)."""
    xy = np.atleast_2d(np.asarray(xy, float))
    k1, k2, k3, p1, p2 = (list(D) + [0.0] * 5)[:5]
    x, y = xy[:, 0], xy[:, 1]
    r2 = x * x + y * y
    radial = 1 + k1 * r2 + k2 * r2 ** 2 + k3 * r2 ** 3
    return np.column_stack([x * radial + 2 * p1 * x * y + p2 * (r2 + 2 * x * x),
                            y * radial + p1 * (r2 + 2 * y * y) + 2 * p2 * x * y])


def undistort(xy_d, D, iterations: int = 30) -> np.ndarray:
    """Ideal normalized coordinates of distorted ones, by fixed-point iteration."""
    xy_d = np.atleast_2d(np.asarray(xy_d, float))
    k1, k2, k3, p1, p2 = (list(D) + [0.0] * 5)[:5]
    xy = xy_d.copy()
    for _ in range(iterations):
        x, y = xy[:, 0], xy[:, 1]
        r2 = x * x + y * y
        radial = 1 + k1 * r2 + k2 * r2 ** 2 + k3 * r2 ** 3
        dx = 2 * p1 * x * y + p2 * (r2 + 2 * x * x)
        dy = p1 * (r2 + 2 * y * y) + 2 * p2 * x * y
        xy = np.column_stack([(xy_d[:, 0] - dx) / radial, (xy_d[:, 1] - dy) / radial])
    return xy


def project_pixels(K, T_cw, points, D=None) -> np.ndarray:
    """Pixels of world points (n, 3) seen by a camera with intrinsic matrix K,
    extrinsics T_cw = {}^C T_0 (world in the camera frame) and distortion D."""
    K = np.asarray(K, float)
    P = np.asarray(points, float) @ np.asarray(T_cw)[:3, :3].T + np.asarray(T_cw)[:3, 3]
    xy = P[:, :2] / P[:, 2:3]
    if D is not None:
        xy = distort(xy, D)
    return xy @ K[:2, :2].T + K[:2, 2]
