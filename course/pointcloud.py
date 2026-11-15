"""
A known object made of boxes, its model points, and a simulated depth camera.
============================================================================

Lecture 3, slides 37-39. The object is a union of axis-aligned boxes in its
own frame; the model points m_i are sampled on its outer surface (CAD model).
The depth camera casts one ray per pixel, keeps the first surface it hits, and
measures the depth d along its optical axis, so that

    s^c = d K^-1 [u, v, 1]^T            (point in the camera frame, slide 37)
    s   = T_cam s^c                     (point in the world frame, slide 41).

Only the side of the object that faces the camera is seen (partial view, self
occlusion); the depth is perturbed along the ray, grazing surfaces give no
measurement (dropouts), and stray points can be added (outliers).
"""
from __future__ import annotations

import numpy as np

from .geometry import inverse, look_at, transform

# An L-shaped bracket with a tab (metres), z up, origin at the centre of the base bottom.
BRACKET = np.array([
    [[-0.08, -0.05, 0.00], [0.08, 0.05, 0.03]],          # base
    [[0.04, -0.05, 0.03], [0.08, 0.05, 0.12]],           # upright
    [[-0.08, 0.015, 0.03], [-0.04, 0.05, 0.06]],         # tab
])


def inside(boxes, P, eps: float = 0.0):
    """Points strictly inside the union of the boxes (shrunk by eps)."""
    P = np.atleast_2d(P)
    hit = np.zeros(len(P), bool)
    for lo, hi in boxes:
        hit |= np.all((P > lo + eps) & (P < hi - eps), axis=1)
    return hit


def sample_surface(boxes, n: int, rng):
    """About n points uniformly spread on the outer surface of the union of boxes, with outward normals."""
    faces = []                                            # (origin, edge u, edge v, normal)
    for lo, hi in boxes:
        size = hi - lo
        for axis in range(3):
            u, v = [(a, np.eye(3)[a] * size[a]) for a in range(3) if a != axis]
            for side, value in ((-1.0, lo[axis]), (1.0, hi[axis])):
                origin = lo.copy()
                origin[axis] = value
                faces.append((origin, u[1], v[1], side * np.eye(3)[axis]))
    areas = np.array([np.linalg.norm(np.cross(u, v)) for _, u, v, _ in faces])
    total = areas.sum()
    points, normals = [], []
    for (origin, u, v, nrm), area in zip(faces, areas):
        k = int(round(3 * n * area / total))              # oversample: hidden parts are removed below
        a, b = rng.random((k, 1)), rng.random((k, 1))
        p = origin + a * u + b * v
        keep = ~inside(boxes, p + 1e-4 * nrm)              # outward from an outer face: out of the object
        points.append(p[keep])
        normals.append(np.tile(nrm, (keep.sum(), 1)))
    P, N = np.vstack(points), np.vstack(normals)
    pick = rng.choice(len(P), size=min(n, len(P)), replace=False)
    return P[pick], N[pick]


def box_edges(boxes):
    """The 12 edges of every box, as pairs of points (for drawing)."""
    edges = []
    for lo, hi in boxes:
        c = np.array([[x, y, z] for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])])
        for i in range(8):
            for j in range(i + 1, 8):
                if np.sum(c[i] != c[j]) == 1:
                    edges.append([c[i], c[j]])
    return np.array(edges)


class DepthCamera:
    """A pinhole depth camera: K, image size, pose T_cam = {}^N T_cam (z along the optical axis)."""

    def __init__(self, eye=(0.32, -0.36, 0.40), target=(0.0, 0.0, 0.04), width: int = 80, height: int = 60,
                 f: float = 95.0):
        self.T_cam = look_at(eye, target, up=(0.0, 0.0, -1.0))   # image "down" towards the table
        self.width, self.height = width, height
        self.K = np.array([[f, 0.0, width / 2.0], [0.0, f, height / 2.0], [0.0, 0.0, 1.0]])

    def render(self, boxes, T_obj, noise: float = 0.0, grazing: float = 0.12, rng=None):
        """Ray-cast every pixel. Returns pixels (u, v), depths d, points s^c, normals (camera frame).

        noise: standard deviation of the depth (m), along the ray; grazing: rays that
        meet the surface with |cos(incidence)| below this give no measurement.
        """
        rng = rng or np.random.default_rng(0)
        u, v = np.meshgrid(np.arange(self.width) + 0.5, np.arange(self.height) + 0.5)
        uv1 = np.column_stack([u.ravel(), v.ravel(), np.ones(u.size)])
        rays_c = uv1 @ np.linalg.inv(self.K).T                  # K^-1 [u v 1]^T: z = 1
        T_oc = inverse(T_obj) @ self.T_cam                      # camera in the object frame
        origin = T_oc[:3, 3]
        dirs = rays_c @ T_oc[:3, :3].T
        best = np.full(len(dirs), np.inf)
        normal_o = np.zeros_like(dirs)
        with np.errstate(divide="ignore", invalid="ignore"):
            for lo, hi in boxes:
                t1, t2 = (lo - origin) / dirs, (hi - origin) / dirs
                t_near, t_far = np.minimum(t1, t2), np.maximum(t1, t2)
                t_in = np.nanmax(t_near, axis=1)
                t_out = np.nanmin(t_far, axis=1)
                hit = (t_out >= t_in) & (t_in > 0) & (t_in < best)
                axis = np.nanargmax(np.where(np.isnan(t_near), -np.inf, t_near), axis=1)
                best[hit] = t_in[hit]
                nrm = np.zeros_like(dirs)
                nrm[np.arange(len(dirs)), axis] = -np.sign(dirs[np.arange(len(dirs)), axis])
                normal_o[hit] = nrm[hit]
        hit = np.isfinite(best)
        d = best[hit]                                           # the rays have z = 1: t is the depth
        normals_c = normal_o[hit] @ T_oc[:3, :3]               # object -> camera frame
        ray_unit = rays_c[hit] / np.linalg.norm(rays_c[hit], axis=1, keepdims=True)
        incidence = np.abs(np.sum(ray_unit * normals_c, axis=1))
        ok = incidence >= grazing
        d = d[ok] + noise * rng.standard_normal(ok.sum())
        points_c = d[:, None] * rays_c[hit][ok]                 # s^c = d K^-1 [u v 1]^T
        return {"uv": uv1[hit][ok, :2], "d": d, "points_c": points_c, "normals_c": normals_c[ok]}

    def to_world(self, points_c):
        return transform(self.T_cam, points_c)
