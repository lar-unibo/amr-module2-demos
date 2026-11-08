"""
Normal stereo and pixels to 3-D points (lecture 1, slides 41-44).
================================================================

Two identical cameras with parallel optical axes; the right one is displaced by
the baseline b along x. With the focal length in pixels f' = f / rho_w, a point
(X, Y, Z) in the left camera frame is seen at

    u_L = f' X / Z + u0,   u_R = f' (X - b) / Z + u0,   v = f' Y / Z + v0,

so the disparity d = u_L - u_R = b f' / Z, and Z = b f' / d. A disparity error
delta_d gives a depth error delta_Z ~ Z^2 / (b f') delta_d.
"""
from __future__ import annotations

import numpy as np


def project_stereo(points, b, f_px, u0, v0):
    """(u_L, u_R, v) of points (n, 3) given in the left camera frame."""
    P = np.atleast_2d(np.asarray(points, float))
    X, Y, Z = P.T
    return np.column_stack([f_px * X / Z + u0, f_px * (X - b) / Z + u0, f_px * Y / Z + v0])


def triangulate(u_left, u_right, v, b, f_px, u0, v0):
    """3-D points (left camera frame) from matched pixels; disparities <= 0 give NaN."""
    d = np.asarray(u_left, float) - np.asarray(u_right, float)
    with np.errstate(divide="ignore", invalid="ignore"):
        Z = np.where(d > 0, b * f_px / d, np.nan)
    X = (np.asarray(u_left, float) - u0) * Z / f_px
    Y = (np.asarray(v, float) - v0) * Z / f_px
    return np.column_stack([X, Y, Z])


def depth_resolution(Z, b, f_px, disparity_step=1.0):
    """Depth change for a disparity change of one step: about Z^2 / (b f') * step."""
    Z = np.asarray(Z, float)
    return Z ** 2 / (b * f_px) * disparity_step


def back_project(u, v, Z, K):
    """Slide 41: P_C = Z K^-1 [u v 1]^T."""
    uv1 = np.vstack([np.atleast_1d(u), np.atleast_1d(v), np.ones(np.size(u))])
    return (np.atleast_1d(Z) * (np.linalg.inv(K) @ uv1)).T
