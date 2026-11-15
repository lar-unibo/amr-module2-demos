"""
Planar grasp analysis: grasp matrix, contact models, form and force closure.
===========================================================================

Lecture 3, part 1, in the plane. The object frame {B} is at the origin and the
world frame {N} coincides with it at the instant of the analysis. Contact i
is a point c_i of the object boundary with the contact frame {C_i} of the
slides: x-axis n_i, the surface normal pointing INSIDE the object, and t_i in
the tangent line (t_i is n_i turned by +90 degrees, so {C_i} is right-handed).

Planar twists and wrenches have three components,

    twist   nu = [v_x, v_y, omega]^T          wrench  lambda = [f_x, f_y, m]^T,

and power is lambda^T nu. As in the slides (in the plane):

    P_i   = [[1, 0, 0], [0, 1, 0], [-r_y, r_x, 1]],  r = c_i - p_B
            (P_i^T: object twist -> contact twist, P_i: contact wrench -> object wrench)
    R_i   = [n_i  t_i],   Rbar_i = blockdiag(R_i, 1)
    G~_i  = P_i Rbar_i,   G~ = [G~_1 ... G~_nc]      (complete grasp matrix, 3 x 3 n_c)
    H     = blockdiag(H_i): PwoF H_i = [1 0 0], HF H_i = [[1 0 0], [0 1 0]]
    G     = G~ H^T                                    (grasp matrix, 3 x n_l)

Closure (slides 28-30) is decided in the 3-D wrench space. The primitive
contact wrenches are the columns of G for frictionless contacts, and the two
edges of each planar friction cone (f_n >= 0, |f_t| <= mu f_n, spanned exactly
by its two edges: no linearization in the plane) for hard fingers. They must
positively span R^3: the origin must be an interior point of their convex
hull. `positive_span` builds the hull by brute force (a dozen points at
most) and, when the test fails, returns a direction nu with W nu >= 0: a
twist that does not push into any frictionless contact (first order), or a
wrench the contacts cannot balance.

Moments are divided by a characteristic length rho before the hull is built
(and twists use omega * rho), so forces and moments have the same units; the
pairing lambda^T nu, and so every test, does not change.
"""
from __future__ import annotations

from itertools import combinations

import numpy as np


def cross2(a, b):
    """z component of a x b for planar vectors (broadcasts over leading axes)."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    return a[..., 0] * b[..., 1] - a[..., 1] * b[..., 0]


def tangent(n):
    """n turned by +90 degrees: the t-axis of the contact frame."""
    n = np.asarray(n, float)
    return np.stack([-n[..., 1], n[..., 0]], axis=-1)


def rotation2(theta: float):
    c, s = np.cos(theta), np.sin(theta)
    return np.array([[c, -s], [s, c]])


# ---------------------------------------------------------------------- grasp matrix (slides 11-27)
def complete_grasp_matrix(contacts, normals, p_B=(0.0, 0.0)):
    """G~ = [P_1 Rbar_1 ... P_nc Rbar_nc] (3 x 3 n_c); `normals` point inside the object."""
    blocks = []
    for c, n in zip(np.asarray(contacts, float), np.asarray(normals, float)):
        r = c - np.asarray(p_B, float)
        P = np.array([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [-r[1], r[0], 1.0]])
        Rbar = np.eye(3)
        Rbar[:2, :2] = np.column_stack([n, tangent(n)])
        blocks.append(P @ Rbar)
    return np.hstack(blocks) if blocks else np.zeros((3, 0))


def selection_matrix(model: str, n_contacts: int):
    """H = blockdiag(H_i): the components each contact transmits (planar PwoF or HF)."""
    H_i = {"PwoF": np.array([[1.0, 0.0, 0.0]]), "HF": np.array([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]])}[model]
    H = np.zeros((len(H_i) * n_contacts, 3 * n_contacts))
    for i in range(n_contacts):
        H[len(H_i) * i:len(H_i) * (i + 1), 3 * i:3 * i + 3] = H_i
    return H


def grasp_matrix(contacts, normals, model: str = "PwoF", p_B=(0.0, 0.0)):
    """G = G~ H^T (3 x n_l): transmitted contact wrenches (in {C_i}) -> wrench on the object."""
    return complete_grasp_matrix(contacts, normals, p_B) @ selection_matrix(model, len(contacts)).T


def primitive_wrenches(contacts, normals, model: str = "PwoF", mu: float = 0.0, p_B=(0.0, 0.0)):
    """Rows: the wrenches whose non-negative combinations are all the wrenches the contacts can apply.

    PwoF: the unit normal force of each contact. HF: the two edges [1, +mu] and
    [1, -mu] (in {C_i}) of each friction cone. Also returns the contact of each row.
    """
    G = grasp_matrix(contacts, normals, model, p_B)
    if model == "PwoF":
        return G.T, np.arange(len(contacts))
    rows, owner = [], []
    for i in range(len(contacts)):
        for sign in (1.0, -1.0):
            rows.append(G[:, 2 * i:2 * i + 2] @ np.array([1.0, sign * mu]))
            owner.append(i)
    return np.array(rows).reshape(-1, 3), np.array(owner, int)


# ---------------------------------------------------------------------- positive span (slides 29-30)
def _hull_facets(X, tol):
    """Supporting hyperplanes {x : c.x = d} of the points X (k x r, r = 1, 2, 3), all points with c.x <= d."""
    k, r = X.shape
    facets = {}
    for subset in combinations(range(k), r):
        base = X[subset[0]]
        if r == 1:
            candidates = [np.array([1.0])]
        else:
            D = X[list(subset[1:])] - base
            _, S, Vt = np.linalg.svd(D)
            if S[-1] < tol * max(1.0, S[0]):
                continue                                   # the points do not fix a hyperplane
            candidates = [Vt[-1]]
        for c in candidates:
            for sign in (1.0, -1.0):
                cc = sign * c / np.linalg.norm(c)
                d = float(cc @ base)
                s = X @ cc - d
                if s.max() <= tol:
                    key = tuple(np.round(np.r_[cc, d], 7))
                    if key not in facets:
                        facets[key] = (cc, d, np.flatnonzero(np.abs(s) <= tol))
    return list(facets.values())


def _ordered(X, vertices, normal=None):
    """Vertices of a flat face in the order of their angle around its centre (for drawing)."""
    pts = X[vertices]
    centre = pts.mean(axis=0)
    if X.shape[1] == 2:
        e1, e2 = np.array([1.0, 0.0]), np.array([0.0, 1.0])
    else:
        e1 = np.cross(normal, [1.0, 0.0, 0.0] if abs(normal[0]) < 0.9 else [0.0, 1.0, 0.0])
        e1 /= np.linalg.norm(e1)
        e2 = np.cross(normal, e1)
    angles = np.arctan2((pts - centre) @ e2, (pts - centre) @ e1)
    return [int(v) for v in np.asarray(vertices)[np.argsort(angles)]]


def positive_span(W, tol: float = 1e-9) -> dict:
    """Do the rows w_k of W (k x d, d <= 3) positively span R^d?

    They do if and only if the origin is an interior point of their convex hull.
    The hull is computed in the span of the rows (dimension r = rank W), so a
    hull that is flat in R^d is handled too.

    Returns: rank, closed (positive span of R^d), relative (the origin is inside
    the hull relative to the span of the rows), margin (signed distance of the
    origin from the hull boundary, in that span), escape (when not relative: a
    unit nu with W nu >= 0 and W nu != 0, the normal of the hull face nearest to
    the origin), null (a basis of Null(W), one vector per row), and faces (lists
    of row indices, for drawing).
    """
    W = np.atleast_2d(np.asarray(W, float))
    k, d = W.shape
    if k == 0:
        return {"rank": 0, "closed": False, "relative": False, "margin": 0.0, "escape": np.eye(d)[0],
                "null": np.eye(d), "faces": []}
    _, S, Vt = np.linalg.svd(W)
    r = int(np.sum(S > tol * max(1.0, S[0]))) if S[0] > tol else 0
    basis, null = Vt[:r], Vt[r:]
    if r == 0:
        return {"rank": 0, "closed": False, "relative": False, "margin": 0.0, "escape": null[0],
                "null": null, "faces": []}
    X = W @ basis.T                                         # coordinates in the span of the rows
    facets = _hull_facets(X, tol)
    margin = min(f[1] for f in facets)
    relative = margin > tol
    nearest = min(facets, key=lambda f: f[1])
    escape = None if relative else -(basis.T @ nearest[0])
    if r == 3:
        faces = [_ordered(X, f[2], f[0]) for f in facets]
    elif r == 2:
        faces = [_ordered(X, sorted({int(v) for f in facets for v in f[2]}))]
    else:
        faces = [[int(np.argmin(X[:, 0])), int(np.argmax(X[:, 0]))]]
    return {"rank": r, "closed": relative and r == d, "relative": relative, "margin": float(margin),
            "escape": escape, "null": null, "faces": faces}


def nnls(A, b, tol: float = 1e-12, max_iter: int | None = None):
    """x >= 0 minimizing ||A x - b|| (the active-set method of Lawson and Hanson)."""
    A, b = np.asarray(A, float), np.asarray(b, float)
    n = A.shape[1]
    x = np.zeros(n)
    passive = np.zeros(n, bool)
    max_iter = max_iter or 30 * n + 30
    w = A.T @ (b - A @ x)
    for _ in range(max_iter):
        if passive.all() or np.where(passive, -np.inf, w).max() <= tol:
            break
        passive[np.argmax(np.where(passive, -np.inf, w))] = True
        while True:
            z = np.zeros(n)
            z[passive] = np.linalg.lstsq(A[:, passive], b, rcond=None)[0]
            if np.all(z[passive] > tol):
                break
            mask = passive & (z <= tol) & (x - z > 0)
            alpha = float(np.min(x[mask] / (x[mask] - z[mask]))) if mask.any() else 0.0
            x = x + alpha * (z - x)
            passive &= x > tol
            if not passive.any():
                z = np.zeros(n)
                break
        x = z
        w = A.T @ (b - A @ x)
    return x


def smallest_grip(W, w, tol: float = 1e-9):
    """Slide 28: contact forces that balance the external wrench w with the smallest total
    normal force. W holds the primitive wrenches (rows, unit normal force each), so the
    forces are alpha >= 0 with W^T alpha = -w, and the total normal force is sum(alpha).

    A linear program: its optimum is at a vertex, a basis of rank(W) primitive wrenches,
    so every basis is tried (at most 12 choose 3). Returns alpha, or None when no
    non-negative combination balances w.
    """
    W, w = np.atleast_2d(np.asarray(W, float)), np.asarray(w, float)
    r = int(np.linalg.matrix_rank(W, tol=1e-9)) if W.size else 0
    best, best_sum = None, np.inf
    for basis in combinations(range(len(W)), r):
        A = W[list(basis)].T
        a = np.linalg.lstsq(A, -w, rcond=None)[0]
        if np.linalg.norm(A @ a + w) > tol * max(1.0, np.linalg.norm(w)) or a.min() < -tol:
            continue
        if a.sum() < best_sum - 1e-12:
            best, best_sum = np.zeros(len(W)), a.sum()
            best[list(basis)] = np.clip(a, 0.0, None)
    return best


def positive_combination(W, margin: float):
    """alpha > 0 (every entry) with sum_k alpha_k w_k = 0, given that the origin is
    interior to the hull of the rows of W with this margin; the largest entry is 1.

    The point p = -delta * mean(w) is inside the hull (|p| < margin), so it is a
    convex combination beta >= 0 of the rows (non-negative least squares);
    alpha = beta + delta / k then balances: sum alpha_k w_k = p + delta mean(w) = 0.
    """
    W = np.asarray(W, float)
    k = len(W)
    mean = W.mean(axis=0)
    if np.linalg.norm(mean) < 1e-12:
        return np.ones(k)
    delta = 0.5 * margin / np.linalg.norm(mean)
    A = np.vstack([W.T, np.ones(k)])
    beta = nnls(A, np.r_[-delta * mean, 1.0])
    alpha = beta + delta / k
    return alpha / alpha.max()


# ---------------------------------------------------------------------- motions and shapes
def planar_motion(nu, t: float):
    """Pose (R, p) of {B} after moving for t with the constant twist nu = [v_x, v_y, omega]
    (as in the slides: v is the velocity of the origin of {B}, omega the angular velocity)."""
    nu = np.asarray(nu, float)
    return rotation2(nu[2] * t), nu[:2] * t


def to_object(points, R, p):
    """World points in the frame of the object at pose (R, p)."""
    return (np.asarray(points, float) - p) @ R


class Ellipse:
    """x^2/a^2 + y^2/b^2 <= 1. Boundary samples every 360/samples degrees, the axis ends included."""
    kind = "ellipse"

    def __init__(self, a: float = 0.45, b: float = 1.0, samples: int = 720):
        self.a, self.b = float(a), float(b)
        t = 2 * np.pi * np.arange(samples) / samples
        self.points = np.column_stack([a * np.cos(t), b * np.sin(t)])
        outward = np.column_stack([np.cos(t) / a, np.sin(t) / b])
        self.normals = -outward / np.linalg.norm(outward, axis=1, keepdims=True)    # inward

    def outline(self, n: int = 120):
        """Closed polyline of the boundary, for drawing."""
        t = np.linspace(0, 2 * np.pi, n + 1)
        return np.column_stack([self.a * np.cos(t), self.b * np.sin(t)])

    def clearance(self, q):
        """Signed distance from the boundary, positive outside (first order in the distance)."""
        q = np.atleast_2d(np.asarray(q, float))
        F = (q[:, 0] / self.a) ** 2 + (q[:, 1] / self.b) ** 2 - 1.0
        grad = 2 * np.hypot(q[:, 0] / self.a ** 2, q[:, 1] / self.b ** 2)
        return F / np.maximum(grad, 1e-12)


class Hourglass:
    """|y| <= h and |x| <= w(y) = w0 + k y^2: an hourglass (k > 0), a box (k = 0), a barrel (k < 0).

    Boundary samples counter-clockwise (right side up, top, left side down,
    bottom), an odd number per piece: the middle of each piece (the waist, the
    centre of the top) is a sample, the corners are not.
    """
    kind = "hourglass"

    def __init__(self, w0: float = 0.22, h: float = 0.9, k: float = 0.4, samples: int = 720):
        self.w0, self.h, self.k = float(w0), float(h), float(k)
        top = w0 + k * h * h
        side_len = np.sum(np.hypot(np.diff(self.width(np.linspace(-h, h, 400))), 2 * h / 399))
        m_side = 2 * int(round(samples * side_len / (2 * side_len + 4 * top) / 2)) + 1
        m_top = 2 * int(round(samples * 2 * top / (2 * side_len + 4 * top) / 2)) + 1
        y = -h + 2 * h * (np.arange(m_side) + 0.5) / m_side
        x = top - 2 * top * (np.arange(m_top) + 0.5) / m_top
        pieces = [(np.column_stack([self.width(y), y]), np.column_stack([np.ones_like(y), -2 * k * y])),
                  (np.column_stack([x, np.full_like(x, h)]), np.tile([0.0, 1.0], (m_top, 1))),
                  (np.column_stack([-self.width(y[::-1]), y[::-1]]), np.column_stack([-np.ones_like(y), -2 * k * y[::-1]])),
                  (np.column_stack([x[::-1], np.full_like(x, -h)]), np.tile([0.0, -1.0], (m_top, 1)))]
        self.points = np.vstack([p for p, _ in pieces])
        outward = np.vstack([n for _, n in pieces])
        self.normals = -outward / np.linalg.norm(outward, axis=1, keepdims=True)    # inward
        self.corners = np.array([[top, h], [-top, h], [-top, -h], [top, -h]])

    def outline(self, n: int = 60):
        """Closed polyline of the boundary (corners included), for drawing."""
        y = np.linspace(-self.h, self.h, n)
        right = np.column_stack([self.width(y), y])
        left = np.column_stack([-self.width(y[::-1]), y[::-1]])
        return np.vstack([right, left, right[:1]])

    def width(self, y):
        return self.w0 + self.k * np.asarray(y, float) ** 2

    def clearance(self, q):
        """Signed distance from the boundary, positive outside (first order near the sides)."""
        q = np.atleast_2d(np.asarray(q, float))
        side = (np.abs(q[:, 0]) - self.width(q[:, 1])) / np.sqrt(1 + (2 * self.k * q[:, 1]) ** 2)
        return np.maximum(side, np.abs(q[:, 1]) - self.h)


def finite_motion(shape, fingers, nu, amplitude: float, steps: int = 8):
    """Clearances of fixed point fingers while the object moves with the twist nu
    until its boundary points have moved by up to `amplitude` (rows: time)."""
    nu = np.asarray(nu, float)
    r_max = np.linalg.norm(shape.points, axis=1).max()
    duration = amplitude / max(np.linalg.norm(nu[:2]) + abs(nu[2]) * r_max, 1e-12)
    times = duration * np.arange(1, steps + 1) / steps
    clearance = np.array([shape.clearance(to_object(fingers, *planar_motion(nu, t))) for t in times])
    return times, clearance


def tangential_motions(shape, fingers, W, null, rho: float, amplitude: float, tol: float, samples: int = 120):
    """When every first-order free motion keeps all contacts tangential (nu in Null(G^T)),
    the curvature of the surfaces decides (second order).

    Along a direction nu of the null space the true shape is moved until its
    boundary has moved by `amplitude`; the finger clearances g are then second order
    in the motion. At second order the object may also shift by a correction a,
    which changes the clearances by W a (W: the rows of G^T). The direction escapes
    if some correction leaves no finger penetrated, W a + g >= 0. Otherwise it is
    held: by Farkas' lemma, some combination y >= 0 of the rows with W^T y = 0 (the
    normal forces that balance each other) weighs the clearances negatively,
    y . g < 0. Feasibility comes from non-negative least squares on [W, -W, -I]
    (a = a+ - a-, slack s = W a + g >= 0): zero residual, the direction escapes.

    `W`, `null`: rows in scaled coordinates (moments / rho; [v_x, v_y, omega * rho]).
    Returns held (every direction leaves a residual above tol); the direction
    closest to escaping (smallest residual; among escaping ones, the smallest
    correction) as an unscaled twist that takes unit time; its correction a
    (unscaled, a displacement reached at unit time); and the residual.
    """
    W, null = np.atleast_2d(W), np.atleast_2d(null)
    scale = np.array([1.0, 1.0, 1.0 / rho])
    A = np.hstack([W, -W, -np.eye(len(W))])

    def probe(direction):
        """(ranking, residual, correction, duration); the ranking prefers a small residual,
        then a small correction, then the largest clearance left at the nearest finger."""
        times, clearance = finite_motion(shape, fingers, direction * scale, amplitude)
        g = clearance[-1]
        if g.min() >= 0.0:                                   # no finger penetrated: no correction needed
            residual, correction = 0.0, np.zeros(3)
        else:
            x = nnls(A, -g)
            residual = float(np.linalg.norm(A @ x + g))
            correction = x[:3] - x[3:6]
        slack = float((W @ correction + g).min())
        ranking = residual + 1e-3 * float(np.linalg.norm(correction)) - 1e-2 * slack
        return ranking, residual, correction, times[-1]

    if len(null) >= 3:
        best = np.array([1.0, 0.0, 0.0])
    elif len(null) == 1:
        best = min((null[0], -null[0]), key=lambda d: probe(d)[0])
    else:
        angle = lambda a: np.cos(a) * null[0] + np.sin(a) * null[1]
        grid = 2 * np.pi * np.arange(samples) / samples
        a0 = grid[int(np.argmin([probe(angle(a))[0] for a in grid]))]
        lo, hi = a0 - 2 * np.pi / samples, a0 + 2 * np.pi / samples
        for _ in range(30):                                # golden-section refinement
            m1, m2 = hi - 0.618 * (hi - lo), lo + 0.618 * (hi - lo)
            if probe(angle(m1))[0] <= probe(angle(m2))[0]:
                hi = m2
            else:
                lo = m1
        best = angle(0.5 * (lo + hi))
    _, residual, correction, duration = probe(best)
    return {"held": residual > tol, "twist": best * scale * duration, "correction": correction * scale,
            "residual": residual}
