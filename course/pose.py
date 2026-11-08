"""
Pose estimation from point correspondences.
===========================================

* `planar_pose`: the pose of a planar target from its normalized image points
  (homography, then Gauss-Newton refinement of the reprojection error); this
  is the "pose estimation" block of PBVS.
* `p3p`: every camera pose that sees three known points at the measured
  directions (slide "Why 4 points?"): up to four solutions.
* `kabsch`: the rigid motion that best maps one point set onto another.

Poses are returned as {}^c T_o: the object frame expressed in the camera frame.
"""
from __future__ import annotations

import numpy as np

from .geometry import exp_so3, pose


def kabsch(A, B):
    """R, t minimizing sum ||R a_i + t - b_i||^2 (A, B: (n, 3), n >= 3 non-collinear)."""
    A, B = np.asarray(A, float), np.asarray(B, float)
    ca, cb = A.mean(axis=0), B.mean(axis=0)
    U, _, Vt = np.linalg.svd((A - ca).T @ (B - cb))
    D = np.diag([1.0, 1.0, np.sign(np.linalg.det(Vt.T @ U.T))])
    R = Vt.T @ D @ U.T
    return R, cb - R @ ca


def homography(obj_xy, img_xy):
    """DLT homography with Hartley normalization: img ~ H obj (both (n, 2), n >= 4), H[2, 2] = 1."""
    def normalizer(p):
        c = p.mean(axis=0)
        scale = np.sqrt(2.0) / max(np.mean(np.linalg.norm(p - c, axis=1)), 1e-12)
        return np.array([[scale, 0, -scale * c[0]], [0, scale, -scale * c[1]], [0, 0, 1]])
    Ta, Tb = normalizer(obj_xy), normalizer(img_xy)
    a = (Ta @ np.c_[obj_xy, np.ones(len(obj_xy))].T).T
    b = (Tb @ np.c_[img_xy, np.ones(len(img_xy))].T).T
    rows = []
    for (x, y, w), (u, v, z) in zip(a, b):
        rows.append([0, 0, 0, -z * x, -z * y, -z * w, v * x, v * y, v * w])
        rows.append([z * x, z * y, z * w, 0, 0, 0, -u * x, -u * y, -u * w])
    H = np.linalg.svd(np.array(rows))[2][-1].reshape(3, 3)
    H = np.linalg.inv(Tb) @ H @ Ta
    return H / H[2, 2]


def refine_pose(T_co, obj, img_xy, iterations: int = 10):
    """Gauss-Newton on the reprojection error, perturbing the pose in the camera frame."""
    T = np.array(T_co, float)
    obj, img_xy = np.asarray(obj, float), np.asarray(img_xy, float)
    for _ in range(iterations):
        P = obj @ T[:3, :3].T + T[:3, 3]
        X, Y, Z = P.T
        residual = (P[:, :2] / P[:, 2:3] - img_xy).ravel()
        J = np.zeros((2 * len(obj), 6))
        for i in range(len(obj)):
            dproj = np.array([[1 / Z[i], 0, -X[i] / Z[i] ** 2], [0, 1 / Z[i], -Y[i] / Z[i] ** 2]])
            dP = np.hstack([np.eye(3), -np.array([[0, -Z[i], Y[i]], [Z[i], 0, -X[i]], [-Y[i], X[i], 0]])])
            J[2 * i:2 * i + 2] = dproj @ dP
        delta = np.linalg.lstsq(J, -residual, rcond=None)[0]
        R_delta = exp_so3(delta[3:])
        T = pose(R_delta @ T[:3, :3], R_delta @ T[:3, 3] + delta[:3])
        if np.linalg.norm(delta) < 1e-12:
            break
    return T


def planar_pose(obj, img_xy, initial=None):
    """{}^c T_o of a planar target (points with z = 0 in the object frame) from normalized image points."""
    obj, img_xy = np.asarray(obj, float), np.asarray(img_xy, float)
    if initial is None:
        H = homography(obj[:, :2], img_xy)
        H /= np.mean([np.linalg.norm(H[:, 0]), np.linalg.norm(H[:, 1])])
        if H[2, 2] < 0:                          # the target must be in front of the camera
            H = -H
        r1, r2, t = H[:, 0], H[:, 1], H[:, 2]
        U, _, Vt = np.linalg.svd(np.column_stack([r1, r2, np.cross(r1, r2)]))
        R = U @ np.diag([1, 1, np.linalg.det(U @ Vt)]) @ Vt
        initial = pose(R, t)
    return refine_pose(initial, obj, img_xy)


def p3p(obj, bearings, samples: int = 4000):
    """All camera poses {}^c T_o that see the 3 points `obj` along the directions `bearings`.

    Unknown distances d_i along the unit bearings j_i must satisfy the law of
    cosines for the three sides of the triangle. For each distance d_1 the
    other two follow (two signs each); the remaining equation is solved by
    scanning d_1 and refining every sign change by bisection. Only positive
    distances are kept; each solution gives a pose by `kabsch`.
    """
    P = np.asarray(obj, float)
    j = np.asarray(bearings, float)
    j = j / np.linalg.norm(j, axis=1, keepdims=True)
    a, b, c = (np.linalg.norm(P[1] - P[2]), np.linalg.norm(P[0] - P[2]), np.linalg.norm(P[0] - P[1]))
    cos_a, cos_b, cos_g = j[1] @ j[2], j[0] @ j[2], j[0] @ j[1]
    sin_b, sin_g = np.sqrt(max(1 - cos_b ** 2, 0)), np.sqrt(max(1 - cos_g ** 2, 0))
    d1_max = min(c / max(sin_g, 1e-12), b / max(sin_b, 1e-12))

    def branch(d1, sign2, sign3):
        r2, r3 = c * c - (d1 * sin_g) ** 2, b * b - (d1 * sin_b) ** 2
        if r2 < 0 or r3 < 0:
            return None
        d2 = d1 * cos_g + sign2 * np.sqrt(r2)
        d3 = d1 * cos_b + sign3 * np.sqrt(r3)
        return d2, d3, d2 * d2 + d3 * d3 - 2 * d2 * d3 * cos_a - a * a

    solutions = []
    grid = np.linspace(1e-9, d1_max * (1 - 1e-12), samples)
    for sign2 in (1, -1):
        for sign3 in (1, -1):
            values = [branch(d, sign2, sign3) for d in grid]
            for k in range(len(grid) - 1):
                if values[k] is None or values[k + 1] is None or values[k][2] * values[k + 1][2] > 0:
                    continue
                lo, hi = grid[k], grid[k + 1]
                for _ in range(80):
                    mid = 0.5 * (lo + hi)
                    if branch(lo, sign2, sign3)[2] * branch(mid, sign2, sign3)[2] <= 0:
                        hi = mid
                    else:
                        lo = mid
                d1 = 0.5 * (lo + hi)
                d2, d3, _ = branch(d1, sign2, sign3)
                if min(d1, d2, d3) <= 0:
                    continue
                points_c = np.array([d1, d2, d3])[:, None] * j
                R, t = kabsch(P, points_c)
                T = pose(R, t)
                if not any(np.allclose(T, S, atol=1e-6) for S in solutions):
                    solutions.append(T)
    return solutions
