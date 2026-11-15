"""
Point-cloud registration: closed form with known correspondences, and ICP.
=========================================================================

Lecture 3, slides 39-51, in the notation of the slides:

* model points m_i, in the object frame; scene points s_j = T_cam s_j^c, in
  the world frame; the unknown is T_obj = [[R, t], [0, 1]] with R m + t ~ s;
* with known correspondences (m_i <-> s_i), the least-squares solution is in
  closed form (Arun et al. 1987, Umeyama 1991):

      m_bar, s_bar                     centroids
      M = sum_i s~_i m~_i^T            cross-covariance of the centred points
      M = U Sigma V^T                  SVD
      R* = U D V^T,  D = diag(1, 1, det(U V^T))
      t* = s_bar - R* m_bar

  (`course/pose.py::kabsch` computes the same R, t with the transposed
  convention: SVD of sum m~ s~^T);
* without correspondences, ICP alternates the closest model point m_c(j) for
  each scene point s_j and the alignment of the pairs: point-to-point (the
  closed form) or point-to-plane (linearized for a small rotation, a 6 x 6
  least-squares problem). Pairs can be rejected by distance or by rank.

numpy only: the nearest neighbours are found by brute force, in blocks.
"""
from __future__ import annotations

import numpy as np

from .geometry import exp_so3, log_so3, pose


# ---------------------------------------------------------------------- known correspondences
def register(m, s, correct: bool = True) -> dict:
    """Closed-form R*, t* minimizing sum ||R m_i + t - s_i||^2 (slides 43-44).

    m, s: (N, 3) matched points (N >= 3, not collinear). With correct=False
    the matrix D is left out: R = U V^T, which is a reflection when
    det(U V^T) = -1. Returns every intermediate quantity of the slides.
    """
    m, s = np.asarray(m, float), np.asarray(s, float)
    m_bar, s_bar = m.mean(axis=0), s.mean(axis=0)
    m_t, s_t = m - m_bar, s - s_bar
    M = s_t.T @ m_t                                      # sum_i s~_i m~_i^T
    U, sigma, Vt = np.linalg.svd(M)
    det_uv = float(np.linalg.det(U @ Vt))
    D = np.diag([1.0, 1.0, np.sign(det_uv) if correct else 1.0])
    R = U @ D @ Vt
    t = s_bar - R @ m_bar
    residual = m @ R.T + t - s
    return {"m_bar": m_bar, "s_bar": s_bar, "M": M, "U": U, "sigma": sigma, "Vt": Vt, "D": D,
            "det_UVt": det_uv, "R": R, "t": t, "T": pose(R, t) if np.linalg.det(R) > 0 else _homogeneous(R, t),
            "cost": float(np.sum(residual ** 2)), "rms": float(np.sqrt(np.mean(np.sum(residual ** 2, axis=1))))}


def _homogeneous(R, t):
    T = np.eye(4)
    T[:3, :3], T[:3, 3] = R, t
    return T


def rotation_error(R_a, R_b) -> float:
    """Angle (rad) of the rotation R_a^T R_b."""
    return float(np.linalg.norm(log_so3(np.asarray(R_a).T @ np.asarray(R_b))))


# ---------------------------------------------------------------------- neighbours and normals
def nearest(A, B, block: int = 256):
    """For each row of A, the index of the nearest row of B and the distance (brute force)."""
    A, B = np.asarray(A, float), np.asarray(B, float)
    b2 = np.sum(B * B, axis=1)
    index = np.empty(len(A), int)
    dist2 = np.empty(len(A))
    for k in range(0, len(A), block):
        a = A[k:k + block]
        d2 = np.sum(a * a, axis=1)[:, None] + b2[None, :] - 2.0 * a @ B.T
        j = np.argmin(d2, axis=1)
        index[k:k + block] = j
        dist2[k:k + block] = d2[np.arange(len(a)), j]
    return index, np.sqrt(np.maximum(dist2, 0.0))


def knn(P, k: int):
    """Indices of the k nearest points of each point of P (itself included)."""
    P = np.asarray(P, float)
    d2 = np.sum(P * P, axis=1)
    D = d2[:, None] + d2[None, :] - 2.0 * P @ P.T
    return np.argsort(D, axis=1)[:, :k]


def pca_normals(P, k: int = 10, viewpoint=None):
    """Normals by local PCA: eigenvector of the smallest eigenvalue of the covariance of the
    k nearest points (slides 53-55), flipped towards the viewpoint; also the surface
    variation lambda_0 / (lambda_0 + lambda_1 + lambda_2)."""
    P = np.asarray(P, float)
    idx = knn(P, k)
    nb = P[idx]                                           # (N, k, 3)
    centred = nb - nb.mean(axis=1, keepdims=True)
    cov = np.einsum("nki,nkj->nij", centred, centred) / k
    lam, vec = np.linalg.eigh(cov)                        # ascending eigenvalues
    normals = vec[:, :, 0]
    if viewpoint is not None:
        flip = np.sum(normals * (np.asarray(viewpoint, float) - P), axis=1) < 0
        normals[flip] *= -1
    variation = lam[:, 0] / np.maximum(lam.sum(axis=1), 1e-300)
    return normals, variation


# ---------------------------------------------------------------------- ICP
def _reject(dist, distance=None, worst=0.0):
    """Mask of the pairs kept: closer than `distance`, and not among the worst `worst` fraction."""
    keep = np.ones(len(dist), bool)
    if distance is not None and distance > 0:
        keep &= dist <= distance
    if worst > 0:
        n_drop = int(np.floor(worst * len(dist)))
        if n_drop > 0:
            keep[np.argsort(dist)[len(dist) - n_drop:]] = False
    if keep.sum() < 3:                                     # keep at least the three best pairs
        keep[np.argsort(dist)[:3]] = True
    return keep


def point_to_plane_step(q, s, n):
    """Small motion (R, t) of the points q reducing sum(((R q + t - s) . n)^2), linearized at R = I.

    ((I + [w]x) q + t - s) . n = (q - s) . n + (q x n) . w + n . t: a linear least-squares
    problem in x = [w, t]; R = exp(w) keeps it a rotation.
    """
    A = np.hstack([np.cross(q, n), n])
    b = -np.sum((q - s) * n, axis=1)
    x = np.linalg.lstsq(A, b, rcond=None)[0]
    return exp_so3(x[:3]), x[3:]


def icp(model, scene, T0, iterations: int = 60, metric: str = "point", normals=None,
        reject_distance=None, reject_worst: float = 0.0, tol: float = 1e-4,
        min_step=(np.radians(0.02), 2e-5)) -> list:
    """Iterative closest point (slide 47), from the initial guess T0 of T_obj.

    At every iteration: the closest model point m_c(j) of each scene point s_j
    (model at the current pose), rejection, the alignment of the kept pairs
    (point-to-point: closed form on (m_c(j), s_j); point-to-plane: one
    linearized step with the scene normals n_j), and the error E of the kept
    pairs (sum of squared distances, or of distances along n_j). Converged when
    E changes by less than tol (relative), or the pose moves by less than
    min_step (rotation, translation), or after `iterations`.

    Returns one record per iteration, the initial guess first:
    T, E, rms, pairs (c(j) for every j), kept (mask), n_kept; and in the last
    record converged (bool).
    """
    model, scene = np.asarray(model, float), np.asarray(scene, float)
    T = np.array(T0, float)
    out = []
    E_prev = np.inf
    T_prev = None
    for it in range(iterations + 1):
        moved = model @ T[:3, :3].T + T[:3, 3]
        pairs, dist = nearest(scene, moved)
        keep = _reject(dist, reject_distance, reject_worst)
        if metric == "plane":
            r = np.sum((moved[pairs] - scene) * normals, axis=1)
            E = float(np.sum(r[keep] ** 2))
        else:
            E = float(np.sum(dist[keep] ** 2))
        out.append({"T": T.copy(), "E": E, "rms": float(np.sqrt(np.mean(dist[keep] ** 2))),
                    "pairs": pairs, "kept": keep, "n_kept": int(keep.sum()), "converged": False})
        if T_prev is not None:
            small_step = (rotation_error(T_prev[:3, :3], T[:3, :3]) < min_step[0]
                          and np.linalg.norm(T[:3, 3] - T_prev[:3, 3]) < min_step[1])
            if small_step or abs(E_prev - E) <= tol * max(E_prev, 1e-300):
                out[-1]["converged"] = True
                break
        if it == iterations:
            break
        E_prev, T_prev = E, T.copy()
        if metric == "plane":
            dR, dt = point_to_plane_step(moved[pairs][keep], scene[keep], normals[keep])
            T = pose(dR @ T[:3, :3], dR @ T[:3, 3] + dt)
        else:
            T = register(model[pairs][keep], scene[keep])["T"]
    return out
