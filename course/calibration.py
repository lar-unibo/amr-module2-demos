"""
Camera calibration with Zhang's method (lecture 1, slides 24-36).
================================================================

Notation of the slides: a planar pattern (checkerboard) with Z = 0 in its own
frame is seen in several views; for each view, [u v 1]^T ~ K [r1 r2 t] [X Y 1]^T
= H [X Y 1]^T. The five steps:

1. a homography H per view (DLT, solved by SVD);
2. the intrinsics from B = K^-T K^-1, two linear constraints per view,
   h1^T B h2 = 0 and h1^T B h1 = h2^T B h2 (zero skew assumed, as on the
   slides: 4 parameters fu, fv, u0, v0);
3. the pose of the pattern in each view, r1 = l K^-1 h1, r2 = l K^-1 h2,
   t = l K^-1 h3, r3 = r1 x r2, with l = 1 / ||K^-1 h1||;
4. the radial distortion (k1, k2) by linear least squares;
5. all parameters refined together by minimizing the reprojection error
   (Levenberg-Marquardt).
"""
from __future__ import annotations

import numpy as np

from .camera import distort, project_pixels
from .geometry import exp_so3, log_so3, pose
from .pose import homography


def checkerboard(rows: int = 6, cols: int = 7, square: float = 0.02) -> np.ndarray:
    """Inner corners of a checkerboard in its own frame (Z = 0), row by row from the top-left."""
    i, j = np.meshgrid(np.arange(rows), np.arange(cols), indexing="ij")
    return np.column_stack([j.ravel() * square, i.ravel() * square, np.zeros(rows * cols)])


def intrinsic_matrix(fu, fv, u0, v0, skew=0.0) -> np.ndarray:
    return np.array([[fu, skew, u0], [0.0, fv, v0], [0.0, 0.0, 1.0]])


# ---------------------------------------------------------------- step 2
def _v(H, i, j):
    hi, hj = H[:, i], H[:, j]
    return np.array([hi[0] * hj[0], hi[0] * hj[1] + hi[1] * hj[0], hi[1] * hj[1],
                     hi[2] * hj[0] + hi[0] * hj[2], hi[2] * hj[1] + hi[1] * hj[2], hi[2] * hj[2]])


DEGENERATE = 2e-3          # threshold on the conditioning of the (normalized) system for B


def intrinsics_from_homographies(Hs, zero_skew: bool = True, image_size=(640, 480)):
    """K from the homographies of the views (closed form of Zhang, 2000).

    The pixel coordinates are first normalized (centred on the image and
    scaled to about 1), so that the entries of B are comparable. Returns
    (K, info): info["ok"] is False when the views do not constrain K: too few
    views, or views without enough tilt (all the pattern planes nearly
    parallel), where the system for B is degenerate (info["condition"] is
    the ratio of its fifth to its first singular value).
    """
    w, h = image_size
    scale = (w + h) / 2
    N = np.array([[1 / scale, 0, -w / 2 / scale], [0, 1 / scale, -h / 2 / scale], [0, 0, 1]])
    rows = []
    for H in Hs:
        H = N @ H
        H = H / np.linalg.norm(H)                       # balances the views
        rows += [_v(H, 0, 1), _v(H, 0, 0) - _v(H, 1, 1)]
    if zero_skew:
        rows.append(np.array([0.0, 1.0, 0.0, 0.0, 0.0, 0.0]) * np.linalg.norm(rows, axis=1).mean())
    V = np.array(rows)
    _, sigma, Vt = np.linalg.svd(V)
    b = Vt[-1]
    condition = float(sigma[4] / sigma[0]) if len(sigma) >= 5 else 0.0      # rank 5 needed
    B11, B12, B22, B13, B23, B33 = b
    info = {"ok": False, "sigma": sigma, "condition": condition}
    den = B11 * B22 - B12 ** 2
    if len(Hs) < (2 if zero_skew else 3):
        info["reason"] = f"too few views (at least {2 if zero_skew else 3})"
        return None, info
    if abs(den) < 1e-300 or condition < DEGENERATE:
        info["reason"] = "degenerate views: the pattern planes are nearly parallel (tilt the views)"
        return None, info
    v0 = (B12 * B13 - B11 * B23) / den
    lam = B33 - (B13 ** 2 + v0 * (B12 * B13 - B11 * B23)) / B11
    if lam / B11 <= 0 or lam * B11 / den <= 0:
        info["reason"] = "no real solution: the views need more tilt"
        return None, info
    fu = np.sqrt(lam / B11)
    fv = np.sqrt(lam * B11 / den)
    skew = -B12 * fu ** 2 * fv / lam
    u0 = skew * v0 / fv - B13 * fu ** 2 / lam
    info["ok"] = True
    K = np.linalg.inv(N) @ intrinsic_matrix(fu, fv, u0, v0, 0.0 if zero_skew else skew)
    return K / K[2, 2], info


# ---------------------------------------------------------------- step 3
def pose_from_homography(K, H):
    """{}^c T_t of the pattern in one view (r1, r2, t from K^-1 H; r3 = r1 x r2)."""
    A = np.linalg.solve(K, H)
    lam = 1.0 / np.linalg.norm(A[:, 0])
    if A[2, 2] * lam < 0:                               # the pattern is in front of the camera
        lam = -lam
    r1, r2, t = lam * A[:, 0], lam * A[:, 1], lam * A[:, 2]
    U, _, Vt = np.linalg.svd(np.column_stack([r1, r2, np.cross(r1, r2)]))
    R = U @ np.diag([1.0, 1.0, np.linalg.det(U @ Vt)]) @ Vt
    return pose(R, t)


# ---------------------------------------------------------------- step 4
def radial_least_squares(K, poses, objects, observed):
    """(k1, k2) from the gap between observed pixels and the ideal projection."""
    rows, rhs = [], []
    u0, v0 = K[0, 2], K[1, 2]
    for T, uv in zip(poses, observed):
        P = objects @ T[:3, :3].T + T[:3, 3]
        xy = P[:, :2] / P[:, 2:3]
        ideal = xy @ K[:2, :2].T + K[:2, 2]
        r2 = np.sum(xy ** 2, axis=1)
        for (u, v), (uo, vo), r in zip(ideal, uv, r2):
            rows += [[(u - u0) * r, (u - u0) * r * r], [(v - v0) * r, (v - v0) * r * r]]
            rhs += [uo - u, vo - v]
    k = np.linalg.lstsq(np.array(rows), np.array(rhs), rcond=None)[0]
    return np.array([k[0], k[1], 0.0, 0.0, 0.0])


# ---------------------------------------------------------------- step 5
def reprojection_rms(K, D, poses, objects, observed) -> float:
    errors = [project_pixels(K, T, objects, D) - uv for T, uv in zip(poses, observed)]
    return float(np.sqrt(np.mean(np.concatenate(errors) ** 2) * 2))     # RMS of the 2-D error


def _pack(K, D, poses):
    head = [K[0, 0], K[1, 1], K[0, 2], K[1, 2], D[0], D[1]]
    views = [np.r_[log_so3(T[:3, :3]), T[:3, 3]] for T in poses]
    return np.array(head), [np.array(v) for v in views]


def _unpack(head, views):
    K = intrinsic_matrix(*head[:4])
    D = np.array([head[4], head[5], 0.0, 0.0, 0.0])
    return K, D, [pose(exp_so3(v[:3]), v[3:]) for v in views]


def refine(K, D, poses, objects, observed, iterations: int = 30):
    """Levenberg-Marquardt on (fu, fv, u0, v0, k1, k2) and the 6 pose parameters of each view.

    The Jacobian is computed by finite differences, block by block: the
    parameters of a view only affect that view's residuals.
    """
    head, views = _pack(K, D, poses)
    n = len(views)

    def residual_view(h, v, i):
        Kh, Dh, (T,) = _unpack(h, [v])
        return (project_pixels(Kh, T, objects, Dh) - observed[i]).ravel()

    def residuals(h, vs):
        return np.concatenate([residual_view(h, vs[i], i) for i in range(n)])

    mu, r = 1e-3, residuals(head, views)
    m = len(r) // n
    for _ in range(iterations):
        J = np.zeros((len(r), 6 + 6 * n))
        for j in range(6):
            step = 1e-6 * max(1.0, abs(head[j]))
            h2 = head.copy()
            h2[j] += step
            J[:, j] = (residuals(h2, views) - r) / step
        for i in range(n):
            base = r[i * m:(i + 1) * m]
            for j in range(6):
                v2 = views[i].copy()
                v2[j] += 1e-7
                J[i * m:(i + 1) * m, 6 + 6 * i + j] = (residual_view(head, v2, i) - base) / 1e-7
        A, g = J.T @ J, J.T @ r
        while True:
            delta = -np.linalg.solve(A + mu * np.diag(np.diag(A) + 1e-12), g)
            h_new = head + delta[:6]
            v_new = [views[i] + delta[6 + 6 * i:12 + 6 * i] for i in range(n)]
            r_new = residuals(h_new, v_new)
            if r_new @ r_new < r @ r:
                head, views, r, mu = h_new, v_new, r_new, max(mu / 3, 1e-9)
                break
            mu *= 4
            if mu > 1e8:
                return _unpack(head, views)
        if np.linalg.norm(delta) < 1e-10 * (1 + np.linalg.norm(head)):
            break
    return _unpack(head, views)


# ---------------------------------------------------------------- the whole method
def calibrate(objects, observed, do_refine: bool = True, image_size=(640, 480)) -> dict:
    """Run the five steps; return the estimates and the reprojection error after each step."""
    out = {"ok": False, "steps": []}
    Hs = [homography(objects[:, :2], uv) for uv in observed]
    h_err = [np.linalg.norm((np.c_[objects[:, :2], np.ones(len(objects))] @ H.T)[:, :2]
                            / (np.c_[objects[:, :2], np.ones(len(objects))] @ H.T)[:, 2:] - uv, axis=1)
             for H, uv in zip(Hs, observed)]
    out["homographies"] = Hs
    out["steps"].append({"step": 1, "name": "homographies",
                         "rms": float(np.sqrt(np.mean(np.concatenate(h_err) ** 2)))})
    K, info = intrinsics_from_homographies(Hs, image_size=image_size)
    out["condition"] = info["condition"]
    if K is None:
        out["reason"] = info["reason"]
        return out
    poses = [pose_from_homography(K, H) for H in Hs]
    D0 = np.zeros(5)
    out["steps"].append({"step": 2, "name": "intrinsics", "K": K, "D": D0,
                         "rms": reprojection_rms(K, D0, poses, objects, observed)})
    out["steps"].append({"step": 3, "name": "pose of each view", "K": K, "D": D0, "poses": poses,
                         "rms": reprojection_rms(K, D0, poses, objects, observed)})
    D = radial_least_squares(K, poses, objects, observed)
    out["steps"].append({"step": 4, "name": "radial distortion", "K": K, "D": D,
                         "rms": reprojection_rms(K, D, poses, objects, observed)})
    if do_refine:
        K, D, poses = refine(K, D, poses, objects, observed)
        out["steps"].append({"step": 5, "name": "refinement", "K": K, "D": D, "poses": poses,
                             "rms": reprojection_rms(K, D, poses, objects, observed)})
    out.update({"ok": True, "K": K, "D": D, "poses": poses})
    return out


# ---------------------------------------------------------------- synthetic views
def view_poses(n: int, tilt_deg: float = 35.0, distance: float = 0.45, center=(0.06, 0.05, 0.0),
               roll_deg: float = 20.0, spread: float = 0.0, accept=None, rng=None):
    """{}^c T_t of n views of a pattern centred at `center`, seen from `distance`.

    Each camera is shifted by up to `spread` along the pattern plane (so the
    pattern appears in different parts of the image) and looks from a direction
    tilted by up to `tilt_deg` from the normal of the pattern, with a random
    azimuth and roll. tilt_deg = 0 gives fronto-parallel views (degenerate).
    `accept(T)` can reject a view (e.g. corners outside the image).
    """
    from .geometry import look_at, inverse
    rng = np.random.default_rng(0) if rng is None else rng
    center = np.asarray(center, float)
    out = []
    while len(out) < n:
        for _ in range(200):
            theta = np.radians(tilt_deg) * np.sqrt(rng.uniform(0.25, 1.0))
            phi = rng.uniform(0, 2 * np.pi)
            target = center + np.r_[rng.uniform(-spread, spread, 2), 0.0]     # the camera is shifted, not turned
            eye = target + distance * np.array([np.sin(theta) * np.cos(phi), np.sin(theta) * np.sin(phi), -np.cos(theta)])
            roll = np.radians(rng.uniform(-roll_deg, roll_deg))
            up = np.array([np.sin(roll), -np.cos(roll), 0.0])
            T = inverse(look_at(eye, target, up=up))         # {}^c T_t
            if accept is None or accept(T):
                break
        out.append(T)
    return out
