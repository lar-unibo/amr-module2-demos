"""
Shared pieces of the camera demos of lecture 1.
===============================================

World frame {0}: z up (a table). A camera {C} looks at the scene from a point
given by azimuth, elevation and distance; its frame follows the slides: z along
the optical axis, x to the right, y down. {}^C T_0 maps world points into the
camera frame (the extrinsics).
"""
from __future__ import annotations

import numpy as np

from course.geometry import inverse, look_at

W, H = 640, 480                       # image size in pixels
RHO = 5e-6                            # pixel size (m), from the data sheet
F = 4e-3                              # focal length (m): f / rho = 800 pixels


def camera_pose(azimuth_deg: float, elevation_deg: float, distance: float, target=(0.0, 0.0, 0.1)):
    """{}^0 T_C of a camera looking at `target` (world z up)."""
    a, e = np.radians(azimuth_deg), np.radians(elevation_deg)
    target = np.asarray(target, float)
    eye = target + distance * np.array([np.cos(e) * np.cos(a), np.cos(e) * np.sin(a), np.sin(e)])
    return look_at(eye, target, up=(0.0, 0.0, -1.0))


def extrinsics(T_0c):
    """{}^C T_0 = ({}^0 T_C)^-1."""
    return inverse(T_0c)


def house(size: float = 0.2):
    """Vertices and edges of a small house (a box with a roof) on the table, centred at the origin."""
    s = size / 2
    box = [(-s, -s, 0), (s, -s, 0), (s, s, 0), (-s, s, 0), (-s, -s, size), (s, -s, size), (s, s, size), (-s, s, size)]
    roof = [(-s, 0, 1.5 * size), (s, 0, 1.5 * size)]
    vertices = np.array(box + roof, float)
    edges = [(0, 1), (1, 2), (2, 3), (3, 0), (4, 5), (5, 6), (6, 7), (7, 4), (0, 4), (1, 5), (2, 6), (3, 7),
             (4, 8), (7, 8), (5, 9), (6, 9), (8, 9)]
    return vertices, edges
