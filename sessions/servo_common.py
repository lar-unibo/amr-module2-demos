"""
Shared pieces of the closed-loop demos (PBVS, IBVS, depth, comparison, stability).
=================================================================================

The world frame of the 3-D views is the object frame F_o, with the axes of the
desired camera (x right, y down, z toward the target). The target is a square
(side 0.6 m) in the plane z = 0; the desired camera faces it from z = -Z*.
"""
from __future__ import annotations

import numpy as np

from course.servo import FOV, frontal_pose, measure, relative_pose, square_target

# Initial poses relative to the desired camera: ({}^d t_c, theta m), and a short label.
# With the default scene (square of side 0.6 m, desired camera 1 m in front), every
# start sees the four points inside the image border.
START_POSES = {
    "general": ([0.15, -0.1, -0.7], [0.1, -0.2, 0.45], "general"),
    "translation": ([0.3, 0.2, -0.5], [0.0, 0.0, 0.0], "translation"),
    "rot_z_1": ([0.0, 0.0, 0.0], [0.0, 0.0, 1.0], "1 rad about z"),
    "rot_z_2.8": ([0.0, 0.0, 0.0], [0.0, 0.0, 2.8], "2.8 rad about z"),
    "rot_z_pi": ([0.0, 0.0, 0.0], [0.0, 0.0, np.pi], "π rad about z"),
    "tilt": ([-0.43, 0.54, 0.24], [0.12, 0.91, -1.58], "large tilt"),
}


def scene(depth: float = 1.0, half: float = 0.3) -> dict:
    """Target points, desired pose and desired features for a frontal desired camera."""
    points = square_target(half)
    T_od = frontal_pose(depth)
    desired = measure(T_od, points)
    return {"points": points, "T_od": T_od, "s_star": desired["s"], "Z_star": desired["Z"]}


def start_pose(T_od, translation, rotation):
    return relative_pose(T_od, np.asarray(translation, float), np.asarray(rotation, float))


def trajectory(out: dict) -> dict:
    """The parts of a simulation the page draws and plots."""
    T = out["T"]
    return {
        "times": out["times"], "s": out["s"], "Z": out["Z"], "T": T, "positions": T[:, :3, 3],
        "v": out["v"], "e": out["e"], "e_norm": out["e_norm"], "e_proj_norm": out["e_proj_norm"],
        "Z_hat": out["Z_hat"], "visible": out["visible"], "status": out["status"],
        "all_visible": bool(np.all(out["visible"])), "fov": FOV,
    }
