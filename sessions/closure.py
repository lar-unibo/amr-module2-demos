"""
Lecture 3, demo 1 - Form and force closure of a planar grasp (slides 8, 23-30).
===============================================================================

Fixed point fingers on the boundary of a planar object (the shapes of the
opening question, slide 8). With frictionless contacts (PwoF) the first-order
test of slide 29 asks whether the normal wrenches, the columns of G, positively
span the wrench space; with hard fingers (HF) the test of slide 30 asks the
same of the edges of the friction cones (force closure). When a test fails the
page shows the reason: a free motion of the object (frictionless) or a wrench
the contacts cannot balance (friction). When the first-order test fails only
because every free motion is tangential to all contacts, as for grasp (b), the
true curved shape is moved along those motions to see whether it pushes into
a finger.
"""
from __future__ import annotations

import numpy as np

from course.grasp import (Ellipse, Hourglass, finite_motion, grasp_matrix, planar_motion,
                          positive_combination, positive_span, primitive_wrenches, tangent,
                          tangential_motions, to_object)

from .common import Session

MODELS = ("PwoF", "HF")
AMPLITUDE = 0.2          # size of the drawn free motion (object units, the object is 2 tall)
TOL = 2e-4               # penetration below this counts as sliding (object units)
GHOSTS = (1 / 3, 2 / 3, 1.0)


def _ellipse_point(deg):
    t = np.radians(deg)
    return [0.45 * np.cos(t), np.sin(t)]


PRESETS = {
    "a": {"shape": "ellipse", "model": "PwoF", "points": [_ellipse_point(d) for d in (40, 125, 230, 310)]},
    "b": {"shape": "hourglass", "k": 0.4, "model": "PwoF", "points": [[0.22, 0.0], [-0.22, 0.0]]},
    "c": {"shape": "ellipse", "model": "PwoF", "points": [_ellipse_point(90), _ellipse_point(270)]},
    "pinch": {"shape": "ellipse", "model": "HF", "mu": 0.3, "points": [_ellipse_point(0), _ellipse_point(180)]},
    "tilted": {"shape": "ellipse", "model": "HF", "mu": 0.3, "points": [_ellipse_point(25), _ellipse_point(205)]},
    "three": {"shape": "ellipse", "model": "HF", "mu": 0.2, "points": [_ellipse_point(d) for d in (90, 210, 330)]},
}


class ClosureSession(Session):

    def __init__(self, preset: str = "a"):
        self.k, self.mu = 0.4, 0.3
        self.act_preset(preset if preset in PRESETS else "a")

    # ------------------------------------------------------------------ actions
    def act_reset(self):
        return self.act_preset("a")

    def act_preset(self, name: str):
        spec = PRESETS[name]
        self.preset = name
        self.shape_name, self.model = spec["shape"], spec["model"]
        self.k = spec.get("k", self.k)
        self.mu = spec.get("mu", self.mu)
        self._build_shape()
        self.contacts = [self._nearest(p) for p in spec["points"]]
        return self.state()

    def act_set(self, shape=None, k=None, model=None, mu=None, fingers=None):
        points = self.shape.points[self.contacts]
        if model is not None:
            if model not in MODELS:
                raise KeyError(model)
            self.model = model
        if mu is not None:
            self.mu = float(np.clip(mu, 0.0, 1.5))
        if shape is not None or k is not None:
            if shape is not None:
                if shape not in ("ellipse", "hourglass"):
                    raise KeyError(shape)
                self.shape_name = shape
            if k is not None:
                self.k = float(np.clip(k, -0.15, 0.8))
            self._build_shape()
            self.contacts = [self._nearest(p) for p in points]
        if fingers is not None:
            self._set_count(int(np.clip(fingers, 1, 6)))
        self.preset = None
        return self.state()

    def act_move(self, index: int, x: float, y: float):
        """Drag finger `index` to the boundary point nearest to (x, y)."""
        self.contacts[int(index)] = self._nearest([x, y])
        self.preset = None
        return self.state()

    # ------------------------------------------------------------------ helpers
    def _build_shape(self):
        self.shape = Ellipse() if self.shape_name == "ellipse" else Hourglass(k=self.k)
        self.rho = float(np.mean(np.linalg.norm(self.shape.points, axis=1)))     # characteristic length

    def _nearest(self, p):
        return int(np.argmin(np.linalg.norm(self.shape.points - np.asarray(p, float), axis=1)))

    def _set_count(self, n):
        self.contacts = self.contacts[:n]
        m = len(self.shape.points)
        while len(self.contacts) < n:                       # a new finger in the middle of the largest gap
            if not self.contacts:
                self.contacts.append(0)
                continue
            s = sorted(self.contacts)
            gaps = [(s[(i + 1) % len(s)] - s[i]) % m or m for i in range(len(s))]
            i = int(np.argmax(gaps))
            self.contacts.append((s[i] + gaps[i] // 2) % m)

    def _moved_outline(self, nu, t):
        R, p = planar_motion(nu, t)
        return self.outline @ R.T + p

    # ------------------------------------------------------------------ state
    def state(self) -> dict:
        c, n = self.shape.points[self.contacts], self.shape.normals[self.contacts]
        self.outline = self.shape.outline()
        G = grasp_matrix(c, n, self.model)
        scale = np.diag([1.0, 1.0, 1.0 / self.rho])                 # moments / rho
        W, owner = primitive_wrenches(c, n, self.model, self.mu if self.model == "HF" else 0.0)
        W = W @ scale
        hull = positive_span(W)
        rank_G = int(np.linalg.matrix_rank(G, tol=1e-9)) if G.size else 0

        escape = {"kind": "none"}
        if not hull["closed"]:
            escape = self._escape(c, G, W, hull)
        internal = None
        if hull["closed"]:
            alpha = positive_combination(W, hull["margin"])
            if self.model == "PwoF":
                local = np.column_stack([alpha, np.zeros_like(alpha)])
            else:
                a = alpha.reshape(-1, 2)
                local = np.column_stack([a.sum(axis=1), self.mu * (a[:, 0] - a[:, 1])])
            lam = local.ravel() if self.model == "HF" else local[:, 0]
            world = local[:, :1] * n + local[:, 1:] * tangent(n)
            k = 1.0 / np.linalg.norm(world, axis=1).max()
            internal = {"local": local * k, "world": world * k, "lambda": lam * k,
                        "residual": float(np.linalg.norm(G @ lam))}

        angles = None
        if len(c) == 2:
            u = (c[1] - c[0]) / max(np.linalg.norm(c[1] - c[0]), 1e-12)
            angles = [float(np.degrees(np.arccos(np.clip(n[0] @ u, -1, 1)))),
                      float(np.degrees(np.arccos(np.clip(n[1] @ -u, -1, 1))))]
        return {
            "preset": self.preset, "shape": self.shape_name, "k": self.k, "model": self.model, "mu": self.mu,
            "cone_half_angle": float(np.degrees(np.arctan(self.mu))), "rho": self.rho,
            "outline": self.outline,
            "contacts": c, "normals": n, "tangents": tangent(n),
            "G": G, "n_l": G.shape[1], "rank_G": rank_G, "nullity": G.shape[1] - rank_G,
            "wrenches": W, "owner": owner, "hull": {k_: hull[k_] for k_ in ("rank", "closed", "relative", "margin", "faces")},
            "closed": hull["closed"], "escape": escape, "internal": internal, "angles": angles,
        }

    def _escape(self, c, G, W, hull) -> dict:
        """Why the test fails: a free motion (PwoF) or an unbalanced wrench (HF)."""
        # e: unit direction in the scaled coordinates (moments / rho, omega * rho) with W e >= 0
        out = {"kind": "twist" if self.model == "PwoF" else "wrench", "second_order": None}
        if self.model == "HF":
            # w = S^-1 e cannot be balanced: (S G lambda) . e >= 0 for every lambda in the cones
            e = hull["null"][0] if hull["relative"] else hull["escape"]
            out["wrench"] = e * np.array([1.0, 1.0, self.rho])
            return out
        correction = np.zeros(3)
        if hull["relative"]:
            # every first-order free motion is tangential at every contact: nu in Null(G^T);
            # the curvature of the true shape decides (second order)
            check = tangential_motions(self.shape, c, W, hull["null"], self.rho, AMPLITUDE, TOL)
            nu = check["twist"]
            out["second_order"] = "held" if check["held"] else "escapes"
            if not check["held"]:
                correction = check["correction"]                    # the second-order shift that frees it
        else:
            nu = hull["escape"] * np.array([1.0, 1.0, 1.0 / self.rho])
            times, _ = finite_motion(self.shape, c, nu, AMPLITUDE)
            nu = nu * times[-1]                                     # the drawn motion takes unit time
        # drawn path: displacement nu s + correction s^2, s in [0, 1]
        end = self.shape.clearance(to_object(c, *planar_motion(nu + correction, 1.0)))
        out.update({
            "twist": nu, "correction": correction, "normal_speeds": G.T @ nu,
            "ghosts": [self._moved_outline(nu * s + correction * s * s, 1.0) for s in GHOSTS],
            "ghost_fingers_in": [bool(x) for x in (end < -TOL)],
            "clearance": end,
        })
        return out
