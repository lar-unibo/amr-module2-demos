"""
Course demos: the computations behind the interactive demos (numpy only).
========================================================================

The notation follows the lecture slides. Modules:

    geometry      rotations, angle-axis, poses, camera motion (body twists)
    camera        central projection, normalized and pixel coordinates
    interaction   interaction matrix of point features, null space
"""
from .camera import Intrinsics, back_project, project
from .geometry import (exp_se3, exp_so3, inverse, log_so3, look_at, pose, sinc, skew,
                       transform)
from .interaction import (null_space, point_interaction, point_interaction_pixels,
                          stacked_interaction)

__all__ = [
    "Intrinsics", "back_project", "project",
    "exp_se3", "exp_so3", "inverse", "log_so3", "look_at", "pose", "sinc", "skew", "transform",
    "null_space", "point_interaction", "point_interaction_pixels", "stacked_interaction",
]
