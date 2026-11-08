"""
Interaction matrix (image Jacobian) of point features.
======================================================

Slides "IBVS Interaction Matrix": for a point with normalized coordinates
(x, y) and depth Z, seen by a camera moving with v_c = (nu_c, omega_c),

    s_dot = L_p v_c,    L_p = [[-1/Z,    0, x/Z,    x y, -(1+x^2),  y],
                               [   0, -1/Z, y/Z, 1+y^2,     -x y, -x]].

The first three columns (translation) scale with 1/Z; the last three
(rotation) do not depend on Z.
"""
from __future__ import annotations

import numpy as np


def point_interaction(x: float, y: float, Z: float) -> np.ndarray:
    """2x6 interaction matrix of a point in normalized image coordinates."""
    return np.array([[-1.0 / Z, 0.0, x / Z, x * y, -(1.0 + x * x), y],
                     [0.0, -1.0 / Z, y / Z, 1.0 + y * y, -x * y, -x]])


def point_interaction_pixels(u_bar: float, v_bar: float, Z: float, f: float, rho: float) -> np.ndarray:
    """2x6 interaction matrix in pixels, for square pixels (rho_u = rho_v = rho).

    u_bar = u - u0 and v_bar = v - v0 are measured from the principal point.
    """
    return np.array([
        [-f / (rho * Z), 0.0, u_bar / Z, rho * u_bar * v_bar / f, -(f * f + rho * rho * u_bar ** 2) / (rho * f), v_bar],
        [0.0, -f / (rho * Z), v_bar / Z, (f * f + rho * rho * v_bar ** 2) / (rho * f), -rho * u_bar * v_bar / f, -u_bar],
    ])


def stacked_interaction(xy, Z) -> np.ndarray:
    """(2n x 6) interaction matrix of n points: the L_p of each point, stacked."""
    xy = np.atleast_2d(np.asarray(xy, float))
    Z = np.broadcast_to(np.asarray(Z, float), (xy.shape[0],))
    return np.vstack([point_interaction(x, y, z) for (x, y), z in zip(xy, Z)])


def null_space(L, tol: float = 1e-10) -> np.ndarray:
    """Orthonormal basis (columns) of the camera velocities with L v = 0."""
    _, sigma, Vt = np.linalg.svd(L)
    rank = int(np.sum(sigma > tol * max(sigma.max(), 1.0)))
    return Vt[rank:].T
