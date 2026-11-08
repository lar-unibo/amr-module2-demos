"""Lecture 1: projection, distortion, Zhang's calibration, hand-eye calibration, stereo."""
from __future__ import annotations

import unittest

import numpy as np

from course import exp_so3, inverse, pose
from course.calibration import calibrate, checkerboard, intrinsic_matrix, view_poses
from course.camera import distort, project_pixels, undistort
from course.handeye import motions, pose_error, solve_ax_xb
from course.stereo import back_project, depth_resolution, project_stereo, triangulate

K_TRUE = intrinsic_matrix(800.0, 780.0, 325.0, 236.0)
D_TRUE = np.array([-0.25, 0.08, 0.0, 0.0, 0.0])


def observe(K, D, poses, objects, noise=0.0, seed=0):
    rng = np.random.default_rng(seed)
    return [project_pixels(K, T, objects, D) + rng.normal(scale=noise, size=(len(objects), 2)) for T in poses]


class Distortion(unittest.TestCase):

    def test_round_trip(self):
        xy = np.random.default_rng(1).uniform(-0.4, 0.4, (50, 2))
        for D in ([-0.25, 0.08, 0, 0, 0], [0.2, -0.05, 0.01, 0.001, -0.002]):
            np.testing.assert_allclose(undistort(distort(xy, D), D), xy, atol=1e-9)

    def test_barrel_moves_points_inward(self):
        xy = np.array([[0.4, 0.3]])
        self.assertLess(np.linalg.norm(distort(xy, [-0.2, 0, 0, 0, 0])), np.linalg.norm(xy))
        self.assertGreater(np.linalg.norm(distort(xy, [0.2, 0, 0, 0, 0])), np.linalg.norm(xy))


class Zhang(unittest.TestCase):

    def setUp(self):
        self.board = checkerboard(6, 7, 0.02)
        self.poses = view_poses(8, tilt_deg=40, rng=np.random.default_rng(3))

    def test_exact_without_distortion(self):
        out = calibrate(self.board, observe(K_TRUE, None, self.poses, self.board), do_refine=False)
        self.assertTrue(out["ok"])
        np.testing.assert_allclose(out["steps"][1]["K"], K_TRUE, rtol=1e-6)        # step 2, closed form
        for T_est, T in zip(out["poses"], self.poses):
            np.testing.assert_allclose(T_est, T, atol=1e-7)                      # step 3

    def test_refinement_recovers_distortion(self):
        out = calibrate(self.board, observe(K_TRUE, D_TRUE, self.poses, self.board))
        self.assertTrue(out["ok"])
        np.testing.assert_allclose(out["K"], K_TRUE, rtol=1e-5)
        np.testing.assert_allclose(out["D"][:2], D_TRUE[:2], atol=1e-5)
        rms = [s["rms"] for s in out["steps"][1:]]
        self.assertLess(rms[-1], 1e-6)
        self.assertLess(rms[-1], rms[0])

    def test_noise(self):
        out = calibrate(self.board, observe(K_TRUE, D_TRUE, self.poses, self.board, noise=0.3))
        self.assertTrue(out["ok"])
        np.testing.assert_allclose(np.diag(out["K"])[:2], np.diag(K_TRUE)[:2], rtol=0.02)
        self.assertLess(abs(out["steps"][-1]["rms"] - 0.3 * np.sqrt(2)), 0.15)    # down to the noise level

    def test_fronto_parallel_views_are_degenerate(self):
        flat = view_poses(8, tilt_deg=0, rng=np.random.default_rng(4))
        for noise in (0.0, 0.3):
            out = calibrate(self.board, observe(K_TRUE, None, flat, self.board, noise=noise))
            self.assertFalse(out["ok"], msg=noise)
            self.assertIn("parallel", out["reason"])
        slight = view_poses(8, tilt_deg=8, rng=np.random.default_rng(4))
        self.assertTrue(calibrate(self.board, observe(K_TRUE, None, slight, self.board, noise=0.3), do_refine=False)["ok"])

    def test_two_views_are_enough_with_zero_skew(self):
        out = calibrate(self.board, observe(K_TRUE, None, self.poses[:2], self.board), do_refine=False)
        self.assertTrue(out["ok"])
        np.testing.assert_allclose(out["K"], K_TRUE, rtol=1e-6)
        self.assertFalse(calibrate(self.board, observe(K_TRUE, None, self.poses[:1], self.board))["ok"])


class HandEye(unittest.TestCase):

    def setUp(self):
        rng = np.random.default_rng(5)
        self.X = pose(exp_so3([0.1, -0.2, 0.3]), [0.03, -0.02, 0.08])           # {}^g T_c (or {}^b T_c)
        self.T_bt = pose(exp_so3([np.pi, 0, 0]), [0.6, 0.0, 0.0])             # fixed pattern
        self.robot = [pose(exp_so3(rng.normal(scale=0.4, size=3)), [0.4, 0, 0.4] + rng.normal(scale=0.08, size=3)) for _ in range(8)]

    def test_eye_in_hand(self):
        camera = [inverse(G @ self.X) @ self.T_bt for G in self.robot]        # {}^c T_t
        pairs = motions(self.robot, camera, "eye-in-hand")
        for A, B in pairs:
            np.testing.assert_allclose(A @ self.X, self.X @ B, atol=1e-12)
        X, info = solve_ax_xb(pairs)
        self.assertTrue(info["ok"])
        np.testing.assert_allclose(X, self.X, atol=1e-9)

    def test_eye_to_hand(self):
        T_gt = pose(exp_so3([0.2, 0.1, 0.0]), [0.0, 0.05, 0.1])                # pattern on the gripper
        camera = [inverse(self.X) @ G @ T_gt for G in self.robot]             # {}^c T_t, X = {}^b T_c
        pairs = motions(self.robot, camera, "eye-to-hand")
        for A, B in pairs:
            np.testing.assert_allclose(A @ self.X, self.X @ B, atol=1e-12)
        X, info = solve_ax_xb(pairs)
        self.assertTrue(info["ok"])
        self.assertLess(pose_error(X, self.X)[0], 1e-9)

    def test_degenerate_motions(self):
        translations = [pose(np.eye(3), [0.4, 0, 0.4] + 0.05 * np.random.default_rng(i).normal(size=3)) for i in range(5)]
        camera = [inverse(G @ self.X) @ self.T_bt for G in translations]
        self.assertFalse(solve_ax_xb(motions(translations, camera))[1]["ok"])
        one_axis = [pose(exp_so3([0, 0, a]), [0.4, 0.1 * a, 0.4]) for a in (0.0, 0.3, -0.5, 0.8)]
        camera = [inverse(G @ self.X) @ self.T_bt for G in one_axis]
        _, info = solve_ax_xb(motions(one_axis, camera))
        self.assertFalse(info["ok"])
        self.assertEqual(info["axes_rank"], 1)


class Stereo(unittest.TestCase):

    def test_triangulation_inverts_projection(self):
        P = np.array([[0.1, -0.05, 1.0], [-0.3, 0.2, 3.5], [0.0, 0.0, 8.0]])
        uLuRv = project_stereo(P, b=0.12, f_px=700, u0=320, v0=240)
        np.testing.assert_allclose(triangulate(*uLuRv.T, b=0.12, f_px=700, u0=320, v0=240), P, atol=1e-12)
        np.testing.assert_allclose(uLuRv[:, 0] - uLuRv[:, 1], 0.12 * 700 / P[:, 2])           # d = b f' / Z

    def test_depth_resolution_grows_with_z_squared(self):
        r = depth_resolution([1.0, 2.0, 4.0], b=0.12, f_px=700)
        np.testing.assert_allclose(r[1:] / r[:-1], 4.0)

    def test_back_projection(self):
        P = np.array([0.2, -0.1, 1.5])
        uv = project_pixels(K_TRUE, np.eye(4), P[None])
        np.testing.assert_allclose(back_project(uv[0, 0], uv[0, 1], 1.5, K_TRUE)[0], P, atol=1e-12)


if __name__ == "__main__":
    unittest.main()
