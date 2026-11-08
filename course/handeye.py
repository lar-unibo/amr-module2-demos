"""
Hand-eye calibration: A X = X B (lecture 1, slides 37-40).
==========================================================

Eye-in-hand: the camera is on the gripper, X = {}^g T_c; for two robot poses
(1) and (2), with {}^b T_g from the kinematics and {}^c T_t from the image of
the fixed pattern t:

    A = ({}^b T_g^(2))^-1 {}^b T_g^(1),     B = {}^c T_t^(2) ({}^c T_t^(1))^-1.

Eye-to-hand: the camera is fixed, X = {}^b T_c, and the pattern is on the
gripper: A = ({}^g T_b^(2))^-1 {}^g T_b^(1), with {}^g T_b = ({}^b T_g)^-1.

Solution (Park and Martin, 1994): the rotations satisfy R_A R_X = R_X R_B, so
the angle-axis vectors satisfy alpha = R_X beta, and R_X is the rotation that
best aligns all the beta with the alpha (SVD); then (R_A - I) t_X = R_X t_B - t_A
gives t_X by linear least squares.
"""
from __future__ import annotations

import numpy as np

from .geometry import inverse, log_so3, pose


def motions(poses_robot, poses_camera, configuration: str = "eye-in-hand"):
    """The pairs (A, B) of consecutive robot poses, as defined on the slides.

    poses_robot: {}^b T_g at every pose; poses_camera: {}^c T_t at every pose.
    """
    if configuration == "eye-in-hand":
        G = list(poses_robot)                            # {}^b T_g
    elif configuration == "eye-to-hand":
        G = [inverse(T) for T in poses_robot]            # {}^g T_b
    else:
        raise ValueError(configuration)
    pairs = []
    for i in range(len(G) - 1):
        A = inverse(G[i + 1]) @ G[i]
        B = poses_camera[i + 1] @ inverse(poses_camera[i])
        pairs.append((A, B))
    return pairs


def solve_ax_xb(pairs):
    """X from the pairs (A, B). Returns (X, info); info["ok"] is False for degenerate motions.

    The rotation needs at least two motions with non-parallel rotation axes:
    info["axes_rank"] is the number of independent axes among the alphas.
    """
    alphas = np.array([log_so3(A[:3, :3]) for A, _ in pairs])
    betas = np.array([log_so3(B[:3, :3]) for _, B in pairs])
    info = {"ok": False}
    if len(pairs) == 0:
        info["reason"] = "no motion"
        return None, info
    sigma = np.linalg.svd(alphas, compute_uv=False) if len(pairs) > 0 else np.zeros(3)
    sigma = np.r_[sigma, np.zeros(3 - len(sigma))]
    info["axes_sigma"] = sigma
    info["axes_rank"] = int(np.sum(sigma > 1e-3 * max(sigma[0], 1e-12))) if sigma[0] > 1e-6 else 0
    if info["axes_rank"] < 2:
        info["reason"] = ("no rotation between the poses: the rotation of X is unobservable"
                          if info["axes_rank"] == 0 else
                          "all rotations about parallel axes: X is not determined")
        return None, info
    M = betas.T @ alphas                                 # sum of beta alpha^T
    U, _, Vt = np.linalg.svd(M)
    R = Vt.T @ np.diag([1.0, 1.0, np.linalg.det(Vt.T @ U.T)]) @ U.T
    C = np.vstack([A[:3, :3] - np.eye(3) for A, _ in pairs])
    d = np.concatenate([R @ B[:3, 3] - A[:3, 3] for A, B in pairs])
    t = np.linalg.lstsq(C, d, rcond=None)[0]
    info["ok"] = True
    return pose(R, t), info


def pose_error(T_est, T_true):
    """(translation error, rotation error in radians) between two poses."""
    E = inverse(T_true) @ T_est
    return float(np.linalg.norm(E[:3, 3])), float(np.linalg.norm(log_so3(E[:3, :3])))
