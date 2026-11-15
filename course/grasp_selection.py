"""
Grasp selection from a point cloud, in a vertical plane (lecture 3, slides 52-58, 61).
=====================================================================================

A cross-section of the scene: x horizontal, z up, the table at z = 0, a novel
object on it (no model). The pipeline of slide 52:

1. **Depth data** (slide 37). A depth camera with one row of pixels measures the
   depth d along its optical axis for each pixel u; the point is
   p = d K^{-1} [u, 1]^T in the camera frame, then in the world frame through the
   known camera pose. Depth noise is added along the ray; surfaces seen at a
   grazing angle give no measurement (dropouts). Points on the table are removed
   (segmentation), and two cameras can be fused.
2. **Normals and curvature** (slides 53-55). For each point, its k nearest points
   p_j give Cov_i = 1/k sum (p_j - pbar)(p_j - pbar)^T, eigenvalues
   lambda_0 <= lambda_1, eigenvectors v_0, v_1: v_0 is the normal (up to its sign,
   flipped towards the camera that saw the point: n_i . (p_cam - p_i) > 0, so it
   points outwards) and sigma_i = lambda_0 / (lambda_0 + lambda_1) is the surface
   variation. In 2-D sigma is in [0, 1/2] (in 3-D, with three eigenvalues, [0, 1/3]).
3. **Antipodal candidates** (slides 56-57). Contacts c_1, c_2 with outward normals
   n_1, n_2 and u = (c_2 - c_1) / ||c_2 - c_1|| are accepted if
   angle(u, -n_1) < arctan(mu) and angle(-u, -n_2) < arctan(mu), and
   ||c_2 - c_1|| < the maximum opening of the parallel-jaw gripper.
4. **Evaluate and select** (slide 58). The gripper closes along u and approaches
   along z_g, perpendicular to u (from above, never from below the table). Poses
   whose fingers, palm or wrist, swept along the straight approach from the
   pregrasp pose (slide 61: same orientation, d back along z_g), hit a measured
   point or the table are discarded. The others get the cost
   C = C_antipodal + alpha_reach C_reach + alpha_clear C_clear (alpha_antipodal = 1).
"""
from __future__ import annotations

import numpy as np

from .grasp import cross2

# ---------------------------------------------------------------------- objects (closed polygons, counter-clockwise)
def box(width: float = 0.06, height: float = 0.10):
    w = width / 2
    return np.array([[-w, 0.0], [w, 0.0], [w, height], [-w, height]])


def blob(samples: int = 180):
    """A smooth irregular object, like the one of the antipodal figure (slide 56), resting on
    the table: a rounded box (superellipse |x/a|^3.2 + |z/b|^3.2 = 1) with wavy sides."""
    phi = 2 * np.pi * np.arange(samples) / samples
    c, s = np.cos(phi), np.sin(phi)
    r = 1.0 / (np.abs(c / 0.038) ** 3.2 + np.abs(s / 0.04) ** 3.2) ** (1 / 3.2)
    r = r * (1 + 0.08 * np.cos(3 * phi + 0.5) + 0.04 * np.sin(2 * phi + 0.3))
    pts = np.column_stack([r * c, r * s])
    pts[:, 1] -= pts[:, 1].min()
    return pts


def cup():
    """Cross-section of a cup: two thin walls with a rim, and a base."""
    return np.array([[-0.040, 0.0], [0.040, 0.0], [0.046, 0.090], [0.040, 0.090], [0.034, 0.008],
                     [-0.034, 0.008], [-0.040, 0.090], [-0.046, 0.090]])


def edge_normals(polygon):
    """Outward unit normal of each edge (polygon[i] -> polygon[i+1]) of a counter-clockwise polygon."""
    e = np.roll(polygon, -1, axis=0) - polygon
    n = np.column_stack([e[:, 1], -e[:, 0]])
    return n / np.linalg.norm(n, axis=1, keepdims=True)


# ---------------------------------------------------------------------- depth camera (slide 37)
def cast(origin, directions, polygon):
    """First hit of each ray origin + t d (t > 0) with the polygon or the table z = 0.

    Returns t (inf: no hit), the outward normal at the hit, and whether the hit is on the object.
    """
    o, d = np.asarray(origin, float), np.asarray(directions, float)
    a = polygon
    e = np.roll(polygon, -1, axis=0) - a
    denom = cross2(d[:, None, :], e[None, :, :])                      # rays x edges
    ao = a[None, :, :] - o
    with np.errstate(divide="ignore", invalid="ignore"):
        t = cross2(ao, e[None, :, :]) / denom
        s = cross2(ao, d[:, None, :]) / denom
    valid = (np.abs(denom) > 1e-12) & (t > 1e-9) & (s >= 0) & (s <= 1)
    t = np.where(valid, t, np.inf)
    j = np.argmin(t, axis=1)
    t_obj = t[np.arange(len(d)), j]
    with np.errstate(divide="ignore", invalid="ignore"):
        t_tab = np.where(d[:, 1] < -1e-12, -o[1] / d[:, 1], np.inf)
    on_object = t_obj < t_tab
    normals = np.where(on_object[:, None], edge_normals(polygon)[j], np.array([0.0, 1.0]))
    return np.minimum(t_obj, t_tab), normals, on_object


def depth_scan(polygon, camera, target, *, pixels: int = 200, fov_deg: float = 50.0, noise: float = 0.0,
               grazing: float = 0.15, dropout: float = 0.04, seed: int = 0) -> dict:
    """One scan of a 1-D depth camera at `camera` looking at `target`.

    Pixel u has the normalized coordinate x_n = (u - u0) / f; the measured depth d
    (along the optical axis) gives p = d (axis + x_n * right), i.e. p = d K^{-1} [u, 1]^T
    rotated into the world. Noise: d + noise * N(0, 1) (the same random draws for
    every noise level). No measurement where the ray meets the surface at a grazing
    angle (|cos| < grazing) and for a random `dropout` fraction of the pixels.
    """
    rng = np.random.default_rng(seed)
    gauss, drop = rng.standard_normal(pixels), rng.random(pixels) < dropout
    o = np.asarray(camera, float)
    axis = (np.asarray(target, float) - o) / np.linalg.norm(np.asarray(target, float) - o)
    right = np.array([axis[1], -axis[0]])
    xn = np.tan(np.radians(fov_deg) / 2) * ((np.arange(pixels) + 0.5) / pixels * 2 - 1)
    rays = axis[None] + xn[:, None] * right[None]
    unit = rays / np.linalg.norm(rays, axis=1, keepdims=True)
    t, normals, on_object = cast(o, unit, polygon)
    depth = t * (unit @ axis)
    cos = np.abs(np.sum(unit * normals, axis=1))
    ok = np.isfinite(t) & (cos > grazing) & ~drop
    measured = depth + noise * gauss
    points = o + measured[:, None] * rays
    return {"points": points[ok], "true_points": (o + t[:, None] * unit)[ok], "normals": normals[ok],
            "on_object": on_object[ok], "pixel": np.flatnonzero(ok), "origin": o}


# ---------------------------------------------------------------------- normals and curvature (slides 53-55)
def nearest(P, k: int):
    """Indices of the k nearest points of each point (itself included), nearest first."""
    D = np.sum((P[:, None, :] - P[None, :, :]) ** 2, axis=2)
    k = min(k, len(P))
    idx = np.argpartition(D, k - 1, axis=1)[:, :k]
    order = np.argsort(np.take_along_axis(D, idx, axis=1), axis=1)
    return np.take_along_axis(idx, order, axis=1)


def local_pca(P, k: int) -> dict:
    """Cov_i of the k nearest points, eigenvalues lambda_0 <= lambda_1, eigenvectors v_0, v_1,
    and the surface variation sigma_i = lambda_0 / (lambda_0 + lambda_1)."""
    P = np.asarray(P, float)
    idx = nearest(P, k)
    Q = P[idx]
    mean = Q.mean(axis=1)
    X = Q - mean[:, None, :]
    cov = np.einsum("nki,nkj->nij", X, X) / idx.shape[1]
    lam, vec = np.linalg.eigh(cov)                                  # ascending eigenvalues
    sigma = lam[:, 0] / np.maximum(lam.sum(axis=1), 1e-300)
    return {"neighbours": idx, "mean": mean, "cov": cov, "lam": lam, "v0": vec[:, :, 0], "v1": vec[:, :, 1],
            "sigma": sigma}


def orient_towards(normals, points, viewpoints):
    """Flip each normal so that n_i . (p_cam - p_i) > 0 (slide 54): outward normals."""
    s = np.sign(np.sum(normals * (viewpoints - points), axis=1))
    return normals * np.where(s == 0, 1.0, s)[:, None]


def angle_between(a, b):
    a, b = np.asarray(a, float), np.asarray(b, float)
    c = np.sum(a * b, axis=-1) / (np.linalg.norm(a, axis=-1) * np.linalg.norm(b, axis=-1))
    return np.arccos(np.clip(c, -1.0, 1.0))


# ---------------------------------------------------------------------- antipodal candidates (slides 56-57)
def antipodal_pairs(P, N, mu: float, max_opening: float, min_opening: float = 0.004) -> dict:
    """All pairs (i < j) and the antipodal test with outward normals N.

    theta_1 = angle(u, -n_i), theta_2 = angle(-u, -n_j), u = (p_j - p_i) / ||p_j - p_i||;
    accepted if both are below arctan(mu) and min_opening < ||p_j - p_i|| < max_opening.
    """
    i, j = np.triu_indices(len(P), 1)
    d = P[j] - P[i]
    dist = np.linalg.norm(d, axis=1)
    fits = (dist < max_opening) & (dist > min_opening)
    i, j, d, dist = i[fits], j[fits], d[fits], dist[fits]
    u = d / dist[:, None]
    th1, th2 = angle_between(u, -N[i]), angle_between(-u, -N[j])
    half = np.arctan(mu)
    ok = (th1 < half) & (th2 < half)
    return {"i": i[ok], "j": j[ok], "dist": dist[ok], "u": u[ok], "theta1": th1[ok], "theta2": th2[ok],
            "within_opening": int(fits.sum()), "half_angle": float(half)}


# ---------------------------------------------------------------------- gripper, collisions, cost (slides 57-58, 61)
GRIPPER = {"finger_width": 0.008, "finger_length": 0.045, "tip": 0.004, "palm_height": 0.012,
           "wrist_width": 0.016, "wrist_length": 0.03, "margin": 0.02}


def gripper_boxes(opening: float, max_opening: float, sweep: float = 0.0, g=GRIPPER):
    """Rectangles [x0, x1, z0, z1] of the open gripper in its frame (origin between the
    finger pads, x_g the closing axis, z_g the approach axis), swept back by `sweep` along -z_g:
    the volume the gripper crosses on the straight line from the pregrasp to the grasp pose."""
    tf, L, tip, tp = g["finger_width"], g["finger_length"], g["tip"], g["palm_height"]
    half_palm = max_opening / 2 + tf                                 # the palm does not change with the opening
    w = opening / 2
    return np.array([
        [w, w + tf, -L - sweep, tip],                                # fingers
        [-w - tf, -w, -L - sweep, tip],
        [-half_palm, half_palm, -L - tp - sweep, -L],                # palm
        [-g["wrist_width"] / 2, g["wrist_width"] / 2, -L - tp - g["wrist_length"] - sweep, -L - tp],
    ])


def evaluate_grasps(P, pairs: dict, *, max_opening: float, pregrasp: float, alpha_reach: float,
                    alpha_clear: float, limit: int = 500, clear_scale: float = 0.01, g=GRIPPER) -> dict:
    """Gripper poses for the antipodal pairs, collision check, and cost.

    For each pair: centre between the contacts, x_g = u, z_g perpendicular to u
    (both signs, keeping those that do not come from below), opening = the contact
    distance + a margin (at most the maximum opening). A pose collides if a measured
    point lies inside the swept gripper or the swept gripper goes below the table.
    Cost terms in [0, 1]: C_antipodal = max(theta_1, theta_2) / arctan(mu),
    C_reach = angle(z_g, straight down) / 90 deg, C_clear = 1 - clearance / 1 cm (>= 0).
    Only the `limit` most antipodal pairs are evaluated.
    """
    order = np.argsort(np.maximum(pairs["theta1"], pairs["theta2"]), kind="stable")[:limit]
    i, j, u, dist = pairs["i"][order], pairs["j"][order], pairs["u"][order], pairs["dist"][order]
    th1, th2 = pairs["theta1"][order], pairs["theta2"][order]
    perp = np.column_stack([-u[:, 1], u[:, 0]])
    rows = np.r_[np.arange(len(i)), np.arange(len(i))]
    zg = np.vstack([perp, -perp])
    keep = zg[:, 1] <= 0.05                                          # not from below the table
    rows, zg = rows[keep], zg[keep]
    xg = u[rows]
    centre = 0.5 * (P[i[rows]] + P[j[rows]])
    opening = np.minimum(dist[rows] + g["margin"], max_opening)
    m = len(rows)
    boxes = np.stack([gripper_boxes(w, max_opening, pregrasp, g) for w in opening]) if m else np.zeros((0, 4, 4))
    # measured points in each gripper frame
    rel = P[None, :, :] - centre[:, None, :]
    px = np.einsum("mnk,mk->mn", rel, xg)
    pz = np.einsum("mnk,mk->mn", rel, zg)
    dx = np.maximum(np.maximum(boxes[:, None, :, 0] - px[:, :, None], px[:, :, None] - boxes[:, None, :, 1]), 0)
    dz = np.maximum(np.maximum(boxes[:, None, :, 2] - pz[:, :, None], pz[:, :, None] - boxes[:, None, :, 3]), 0)
    dist_pts = np.hypot(dx, dz).min(axis=2)                           # distance of each point from the gripper
    inside = ((px[:, :, None] > boxes[:, None, :, 0]) & (px[:, :, None] < boxes[:, None, :, 1]) &
              (pz[:, :, None] > boxes[:, None, :, 2]) & (pz[:, :, None] < boxes[:, None, :, 3])).any(axis=2)
    # the lowest corner of the swept gripper, against the table z = 0
    cx = boxes[:, :, [0, 1, 0, 1]]
    cz = boxes[:, :, [2, 2, 3, 3]]
    corner_z = centre[:, 1, None, None] + cx * xg[:, 1, None, None] + cz * zg[:, 1, None, None]
    lowest = corner_z.reshape(m, -1).min(axis=1) if m else np.zeros(0)
    collision = inside.any(axis=1) | (lowest < 0)
    clearance = np.minimum(dist_pts.min(axis=1) if m else np.zeros(0), np.maximum(lowest, 0))
    half = pairs["half_angle"]
    c_antipodal = np.maximum(th1[rows], th2[rows]) / half
    c_reach = angle_between(zg, np.array([0.0, -1.0])) / (np.pi / 2)
    c_clear = np.maximum(0.0, 1 - clearance / clear_scale)
    cost = c_antipodal + alpha_reach * c_reach + alpha_clear * c_clear
    return {"i": i[rows], "j": j[rows], "dist": dist[rows], "theta1": th1[rows], "theta2": th2[rows],
            "centre": centre, "xg": xg, "zg": zg, "opening": opening, "collision": collision,
            "clearance": clearance, "c_antipodal": c_antipodal, "c_reach": c_reach, "c_clear": c_clear,
            "cost": cost, "pregrasp": centre - pregrasp * zg}


def best_distinct(grasps: dict, count: int = 5, min_distance: float = 0.008, min_angle: float = 0.26):
    """Indices of the cheapest collision-free poses, skipping near duplicates (same place and direction)."""
    free = np.flatnonzero(~grasps["collision"])
    chosen = []
    for k in free[np.argsort(grasps["cost"][free], kind="stable")]:
        if all(np.linalg.norm(grasps["centre"][k] - grasps["centre"][c]) > min_distance
               or angle_between(grasps["zg"][k], grasps["zg"][c]) > min_angle for c in chosen):
            chosen.append(int(k))
        if len(chosen) == count:
            break
    return chosen
