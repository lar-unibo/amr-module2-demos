"""
Rigid-body geometry: rotations, angle-axis, and camera motion.
=============================================================

Notation of the lecture slides:

* a pose is a 4x4 homogeneous matrix  T = [[R, t], [0, 1]];
  ``{}^a T_b`` is the pose of frame b expressed in frame a;
* the camera velocity is  v_c = (nu_c, omega_c)  in R^6, linear part first,
  both expressed in the camera frame (a body twist);
* a rotation R corresponds to the angle-axis vector  theta * m,  with
  0 <= theta <= pi and ||m|| = 1 (slide "PBVS Angle-Axis Representation").
"""
from __future__ import annotations

import numpy as np

_EPS = 1e-9


def skew(v) -> np.ndarray:
    """[v]_x, so that skew(v) @ x == np.cross(v, x)."""
    x, y, z = np.asarray(v, float)
    return np.array([[0.0, -z, y], [z, 0.0, -x], [-y, x, 0.0]])


def sinc(theta: float) -> float:
    """Cardinal sine sin(theta)/theta, with sinc(0) = 1."""
    return float(np.sinc(theta / np.pi))


def exp_so3(w) -> np.ndarray:
    """Rotation matrix of the angle-axis vector w = theta * m (Rodrigues)."""
    w = np.asarray(w, float)
    theta = np.linalg.norm(w)
    if theta < _EPS:
        return np.eye(3) + skew(w)
    K = skew(w / theta)
    return np.eye(3) + np.sin(theta) * K + (1.0 - np.cos(theta)) * K @ K


def log_so3(R) -> np.ndarray:
    """Angle-axis vector theta * m of a rotation matrix (the slide's formulas).

    theta = arccos((tr R - 1) / 2), theta * m = vee(R - R^T) / (2 sinc theta).
    At theta = pi the formula is singular: the axis is then taken from R + I.
    """
    R = np.asarray(R, float)
    cos_theta = np.clip((np.trace(R) - 1.0) / 2.0, -1.0, 1.0)
    theta = float(np.arccos(cos_theta))
    vee = np.array([R[2, 1] - R[1, 2], R[0, 2] - R[2, 0], R[1, 0] - R[0, 1]])
    if theta < np.pi - 1e-6:
        return vee / (2.0 * sinc(theta))
    # theta = pi: R = 2 m m^T - I, so m is (up to sign) the largest column of R + I.
    B = (R + np.eye(3)) / 2.0
    m = B[:, int(np.argmax(np.diag(B)))]
    m = m / np.linalg.norm(m)
    return theta * m


def pose(R=None, t=None) -> np.ndarray:
    """Homogeneous matrix [[R, t], [0, 1]]."""
    T = np.eye(4)
    if R is not None:
        T[:3, :3] = R
    if t is not None:
        T[:3, 3] = t
    return T


def inverse(T) -> np.ndarray:
    """Inverse of a homogeneous transformation."""
    R, t = T[:3, :3], T[:3, 3]
    return pose(R.T, -R.T @ t)


def transform(T, points) -> np.ndarray:
    """Apply T to an (n, 3) array of points (or to one point)."""
    points = np.asarray(points, float)
    return points @ T[:3, :3].T + T[:3, 3]


def exp_se3(v, dt: float = 1.0) -> np.ndarray:
    """Displacement of a frame moving for dt with the constant body twist v = (nu, omega).

    The new pose is  T(dt) = T(0) @ exp_se3(v, dt).
    """
    v = np.asarray(v, float) * dt
    nu, w = v[:3], v[3:]
    theta = np.linalg.norm(w)
    R = exp_so3(w)
    if theta < _EPS:
        V = np.eye(3) + 0.5 * skew(w)
    else:
        K = skew(w / theta)
        V = np.eye(3) + (1.0 - np.cos(theta)) / theta * K + (theta - np.sin(theta)) / theta * K @ K
    return pose(R, V @ nu)


def look_at(eye, target, up=(0.0, -1.0, 0.0)) -> np.ndarray:
    """Camera pose {}^w T_c with the optical axis z_c from eye toward target.

    Camera frame convention: z forward (optical axis), x to the right, y down.
    """
    eye, target, up = (np.asarray(a, float) for a in (eye, target, up))
    z = target - eye
    z /= np.linalg.norm(z)
    x = np.cross(up, z)
    if np.linalg.norm(x) < _EPS:                    # looking along "up": pick another
        x = np.cross((1.0, 0.0, 0.0), z)
    x /= np.linalg.norm(x)
    y = np.cross(z, x)
    return pose(np.column_stack([x, y, z]), eye)
