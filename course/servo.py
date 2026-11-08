"""
Closed-loop visual servoing: PBVS and IBVS on a planar target.
=============================================================

Notation of the lecture slides:

* the target points P_o are given in the object frame F_o (plane z = 0);
* {}^o T_c is the current camera pose, {}^o T_d the desired one;
* the features of IBVS are the normalized image points, s in R^(2n), and the
  error is e = s - s*; the control law is v_c = -lambda L_hat^+ e;
* the features of PBVS are s = ({}^d t_c, theta m), s* = 0, and the control
  law is nu_c = -lambda {}^d R_c^T {}^d t_c, omega_c = -lambda theta m.

Controllers see only measurements (image points, optionally pixels, depths
"from a 3-D sensor", or the true pose when a perfect pose estimate is
assumed), never the simulator's state. The camera moves with the commanded
velocity for one period dt (exact rigid motion).
"""
from __future__ import annotations

import numpy as np

from .camera import Intrinsics
from .geometry import exp_se3, exp_so3, inverse, log_so3, pose, transform
from .interaction import stacked_interaction
from .pose import planar_pose

FOV = (0.6, 0.45)            # image half-width and half-height (normalized coordinates)
MIN_DEPTH = 0.05             # a point closer than this is lost (behind or at the camera)
FAR = 30.0                   # the camera is lost beyond this distance from the target


def square_target(half: float = 0.2) -> np.ndarray:
    """4 corners of a square in the plane z = 0 of the object frame (counterclockwise)."""
    return np.array([[-half, -half, 0.0], [half, -half, 0.0], [half, half, 0.0], [-half, half, 0.0]])


def frontal_pose(depth: float) -> np.ndarray:
    """{}^o T_d of a camera facing the target from `depth`, axes aligned with F_o."""
    return pose(np.eye(3), np.array([0.0, 0.0, -depth]))


def relative_pose(T_od, translation, rotation) -> np.ndarray:
    """{}^o T_c of a camera displaced from the desired one by ({}^d t_c, theta m)."""
    return T_od @ pose(exp_so3(rotation), translation)


def measure(T_oc, points, K: Intrinsics | None = None) -> dict:
    """What the camera measures: normalized points s, depths Z, pixels (if K), and the true pose."""
    P = transform(inverse(T_oc), points)
    Z = P[:, 2]
    s = P[:, :2] / Z[:, None]
    out = {"s": s, "Z": Z, "T_oc": T_oc}
    if K is not None:
        out["uv"] = K.to_pixels(s)
    return out


class IBVS:
    """v_c = -lambda L_hat^+ (s - s*), with a choice of interaction matrix and depth.

    interaction: 'current' L(s, Z_hat), 'desired' L(s*, Z*), 'mean' of the two.
    depth: 'true' (3-D sensor), 'constant' (Z_hat for every point),
           'desired' (Z* of the desired pose), 'online' (least-squares estimate).
    K_hat: intrinsics assumed to convert pixels into normalized coordinates
           (None: the normalized points are measured exactly).
    """

    def __init__(self, s_star, Z_star, lam=0.5, interaction="current", depth="true",
                 Z_hat=1.0, K_hat: Intrinsics | None = None, uv_star=None):
        self.lam, self.interaction, self.depth, self.K_hat = lam, interaction, depth, K_hat
        self.s_star = K_hat.to_normalized(uv_star) if K_hat is not None else np.asarray(s_star, float)
        self.Z_star = np.broadcast_to(np.asarray(Z_star, float), (len(self.s_star),)).copy()
        self.Z_est = np.full(len(self.s_star), float(Z_hat))
        self.L_star = stacked_interaction(self.s_star, self.Z_star)
        self.prev = None                         # (s, v) of the previous iteration

    def features(self, meas):
        return self.K_hat.to_normalized(meas["uv"]) if self.K_hat is not None else meas["s"]

    def _update_depth(self, s, dt):
        """Slide 'How to get Z': A phi = b per point, phi = 1/Z, from the last motion."""
        if self.prev is None:
            return
        s_prev, v = self.prev
        s_dot = (s - s_prev) / dt
        mid = 0.5 * (s + s_prev)
        nu, omega = v[:3], v[3:]
        for i, (x, y) in enumerate(mid):
            A = np.array([[-1.0, 0.0, x], [0.0, -1.0, y]]) @ nu
            b = s_dot[i] - np.array([[x * y, -(1 + x * x), y], [1 + y * y, -x * y, -x]]) @ omega
            if A @ A > 1e-10:                    # unobservable without translation: keep the estimate
                phi = (A @ b) / (A @ A)
                if phi > 1e-3:
                    self.Z_est[i] = min(1.0 / phi, 100.0)

    def depths(self, meas):
        if self.depth == "true":
            return meas["Z"]
        if self.depth == "desired":
            return self.Z_star
        return self.Z_est                        # 'constant' or 'online'

    def matrix(self, s, Z):
        if self.interaction == "desired":
            return self.L_star
        L = stacked_interaction(s, Z)
        return 0.5 * (L + self.L_star) if self.interaction == "mean" else L

    def command(self, meas, dt):
        s = self.features(meas)
        if self.depth == "online":
            self._update_depth(s, dt)
        Z = self.depths(meas)
        e = (s - self.s_star).ravel()
        L = self.matrix(s, Z)
        e_proj = np.linalg.pinv(L) @ e           # e' = L_hat^+ e (slide 39)
        v = -self.lam * e_proj
        self.prev = (s.copy(), v.copy())
        return v, {"e": e, "e_norm": float(np.linalg.norm(e)), "e_proj_norm": float(np.linalg.norm(e_proj)),
                   "Z_hat": np.array(Z, float)}


class PBVS:
    """nu_c = -lambda {}^d R_c^T {}^d t_c, omega_c = -lambda theta m (slide 'PBVS Control Law').

    perfect_pose: use the true pose; otherwise estimate it from the image of the
    planar target, with the assumed intrinsics K_hat (pixels -> normalized).
    """

    def __init__(self, points, T_od, lam=0.5, perfect_pose=True, K_hat: Intrinsics | None = None):
        self.points, self.T_od, self.lam = np.asarray(points, float), T_od, lam
        self.perfect_pose, self.K_hat = perfect_pose, K_hat
        self.T_co_prev = None

    def estimate(self, meas):
        if self.perfect_pose:
            return meas["T_oc"]
        s = self.K_hat.to_normalized(meas["uv"]) if self.K_hat is not None else meas["s"]
        T_co = planar_pose(self.points, s, initial=self.T_co_prev)
        self.T_co_prev = T_co
        return inverse(T_co)

    def command(self, meas, dt):
        T_oc_hat = self.estimate(meas)
        T_dc = inverse(self.T_od) @ T_oc_hat
        R, t = T_dc[:3, :3], T_dc[:3, 3]
        theta_m = log_so3(R)
        v = np.r_[-self.lam * R.T @ t, -self.lam * theta_m]
        e = np.r_[t, theta_m]
        return v, {"e": e, "e_norm": float(np.linalg.norm(e)), "t": t, "theta_m": theta_m, "T_oc_hat": T_oc_hat}


def simulate(T_oc0, points, controller, dt=0.04, steps=250, K: Intrinsics | None = None,
             tol=1e-5, fov=FOV, pixel_noise: float = 0.0, seed: int = 0) -> dict:
    """Run the loop from {}^o T_c = T_oc0. Returns the trajectory and a status.

    With intrinsics K the camera also measures pixels, with Gaussian noise of
    standard deviation `pixel_noise` (pixels) if given.

    status: 'converged' (||e|| < tol), 'stalled' (v ~ 0 with e != 0: a local
    minimum), 'point lost' (a point reached the camera plane), 'camera lost'
    (too far from the target), or 'running' (the time ran out first).
    """
    T = np.array(T_oc0, float)
    rng = np.random.default_rng(seed)
    rec = {k: [] for k in ("s", "Z", "T", "v", "e_norm", "e_proj_norm", "Z_hat", "e", "T_hat")}
    status = "running"
    for k in range(steps + 1):
        meas = measure(T, points, K)
        if K is not None and pixel_noise > 0:
            meas["uv"] = meas["uv"] + rng.normal(scale=pixel_noise, size=meas["uv"].shape)
        if np.any(meas["Z"] < MIN_DEPTH):
            status = "point lost"
            break
        v, info = controller.command(meas, dt)
        rec["s"].append(meas["s"])
        rec["Z"].append(meas["Z"])
        rec["T"].append(T.copy())
        rec["v"].append(v)
        rec["e"].append(info["e"])
        rec["e_norm"].append(info["e_norm"])
        rec["e_proj_norm"].append(info.get("e_proj_norm", np.nan))
        rec["Z_hat"].append(info.get("Z_hat", np.full(len(points), np.nan)))
        rec["T_hat"].append(info.get("T_oc_hat", T))           # PBVS: the estimated pose
        if info["e_norm"] < tol:
            status = "converged"
            break
        if k > 10 and np.linalg.norm(v) < 1e-4 * controller.lam and info["e_norm"] > 1e-3:
            status = "stalled"
            break
        if k == steps:
            break
        T = T @ exp_se3(v, dt)
        if np.linalg.norm(T[:3, 3]) > FAR:
            status = "camera lost"
            break
    out = {key: np.array(value) for key, value in rec.items()}
    s = out["s"]
    out["visible"] = np.all((np.abs(s[..., 0]) <= fov[0]) & (np.abs(s[..., 1]) <= fov[1]), axis=1)
    out["times"] = dt * np.arange(len(s))
    out["status"] = status
    return out
