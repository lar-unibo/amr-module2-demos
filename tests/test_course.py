"""Checks of the course package against first principles and against the lecture slides."""
from __future__ import annotations

import unittest

import numpy as np

from course import (Intrinsics, back_project, exp_se3, exp_so3, inverse, log_so3, null_space,
                    point_interaction, point_interaction_pixels, project, stacked_interaction,
                    transform)

RNG = np.random.default_rng(0)
SQUARE = np.array([[-0.25, -0.25, 3.0], [0.25, -0.25, 3.0], [0.25, 0.25, 3.0], [-0.25, 0.25, 3.0]])


def image_velocity_fd(P, v, dt=1e-6):
    """Image velocity of a static point P (camera frame) when the camera moves with v."""
    moved = transform(inverse(exp_se3(v, dt)), P)
    return (project(moved)[0] - project(P)[0]) / dt


class Geometry(unittest.TestCase):

    def test_angle_axis_round_trip(self):
        for _ in range(50):
            m = RNG.normal(size=3)
            m /= np.linalg.norm(m)
            w = RNG.uniform(0, np.pi - 1e-3) * m
            np.testing.assert_allclose(log_so3(exp_so3(w)), w, atol=1e-9)

    def test_angle_axis_at_pi(self):
        m = np.array([1.0, 2.0, -2.0]) / 3.0
        w = log_so3(exp_so3(np.pi * m))
        self.assertAlmostEqual(np.linalg.norm(w), np.pi, places=9)
        np.testing.assert_allclose(np.abs(w / np.pi), np.abs(m), atol=1e-9)

    def test_exp_se3_matches_fine_integration(self):
        v = np.array([0.3, -0.2, 0.5, 0.4, -0.7, 0.2])
        T = np.eye(4)
        n = 20000
        for _ in range(n):                         # T <- T exp(xi dt), first order in dt
            step = np.eye(4)
            step[:3, :3] = exp_so3(v[3:] / n)
            step[:3, 3] = v[:3] / n
            T = T @ step
        np.testing.assert_allclose(exp_se3(v, 1.0), T, atol=1e-4)

    def test_point_velocity_in_camera_frame(self):
        """Slide 'Point Motion': P_dot = -nu - omega x P."""
        P = np.array([0.2, -0.1, 2.0])
        v = np.array([0.1, 0.3, -0.2, 0.5, 0.1, -0.4])
        dt = 1e-6
        P_dot = (transform(inverse(exp_se3(v, dt)), P) - P) / dt
        np.testing.assert_allclose(P_dot, -v[:3] - np.cross(v[3:], P), atol=1e-5)


class InteractionMatrix(unittest.TestCase):

    def test_matches_finite_differences(self):
        for _ in range(20):
            P = back_project(RNG.uniform(-0.5, 0.5, 2), RNG.uniform(0.5, 5.0))[0]
            v = RNG.normal(size=6)
            x, y = project(P)[0]
            np.testing.assert_allclose(point_interaction(x, y, P[2]) @ v, image_velocity_fd(P, v), atol=1e-4)

    def test_pixel_version_is_the_scaled_normalized_one(self):
        """Slide 'Pixels' (square pixels): L_pixels = (f / rho) L_normalized at x = rho u_bar / f."""
        cam = Intrinsics(f=0.004, rho_u=5e-6, rho_v=5e-6)
        for _ in range(10):
            u_bar, v_bar, Z = RNG.uniform(-300, 300), RNG.uniform(-200, 200), RNG.uniform(0.5, 4)
            L_pix = point_interaction_pixels(u_bar, v_bar, Z, cam.f, cam.rho_u)
            L_norm = point_interaction(cam.rho_u * u_bar / cam.f, cam.rho_v * v_bar / cam.f, Z)
            np.testing.assert_allclose(L_pix, cam.f / cam.rho_u * L_norm, rtol=1e-12, atol=1e-9)

    def test_intrinsics_round_trip(self):
        cam = Intrinsics()
        xy = RNG.uniform(-0.3, 0.3, (5, 2))
        np.testing.assert_allclose(cam.to_normalized(cam.to_pixels(xy)), xy, atol=1e-12)

    def test_one_point_has_rank_two_and_motions_along_the_ray_are_invisible(self):
        x, y, Z = 0.2, -0.1, 2.0
        L = point_interaction(x, y, Z)
        self.assertEqual(np.linalg.matrix_rank(L), 2)
        self.assertEqual(null_space(L).shape, (6, 4))
        ray = np.array([x, y, 1.0])
        np.testing.assert_allclose(L @ np.r_[ray, 0, 0, 0], 0, atol=1e-12)   # translation along the ray
        np.testing.assert_allclose(L @ np.r_[0, 0, 0, ray], 0, atol=1e-12)   # rotation about the ray

    def test_four_points_projection_and_pseudoinverse(self):
        """Slides 38-39: L L^+ is an 8x8 projection of rank 6, L^+ L = I_6."""
        xy = project(SQUARE)
        L = stacked_interaction(xy, SQUARE[:, 2])
        P = L @ np.linalg.pinv(L)
        np.testing.assert_allclose(P, P.T, atol=1e-12)
        np.testing.assert_allclose(P @ P, P, atol=1e-12)
        # explicit tolerance: the zero singular values of P are rounding noise (~1e-15, amplified by
        # the conditioning of L), which numpy's default threshold may count depending on the BLAS
        self.assertEqual(np.linalg.matrix_rank(P, tol=1e-9), 6)
        np.testing.assert_allclose(np.linalg.pinv(L) @ L, np.eye(6), atol=1e-12)

    def test_wrong_constant_depth_gives_a_diagonal_product(self):
        """Slide 39: same-depth points, guess Z_hat: L_hat^+ L = diag(Z_hat/Z I3, I3) > 0."""
        xy = project(SQUARE)
        L = stacked_interaction(xy, 3.0)
        for Z_hat in (0.3, 1.0, 10.0, 30.0):
            product = np.linalg.pinv(stacked_interaction(xy, Z_hat)) @ L
            np.testing.assert_allclose(product, np.diag([Z_hat / 3.0] * 3 + [1.0] * 3), atol=1e-10)


if __name__ == "__main__":
    unittest.main()
