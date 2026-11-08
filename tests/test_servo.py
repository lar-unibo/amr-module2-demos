"""Closed-loop behaviours claimed on the lecture slides (PBVS, IBVS, depth, calibration, P3P)."""
from __future__ import annotations

import unittest

import numpy as np

from course import inverse, log_so3, look_at, transform
from course.camera import Intrinsics
from course.pose import p3p, planar_pose
from course.servo import IBVS, PBVS, frontal_pose, measure, relative_pose, simulate, square_target

P = square_target(0.2)
T_OD = frontal_pose(1.0)
DESIRED = measure(T_OD, P)
GENERAL = relative_pose(T_OD, [0.25, -0.15, -0.4], [0.2, -0.3, 0.6])


def ibvs(T0, steps=600, **options):
    controller = IBVS(DESIRED["s"], DESIRED["Z"], lam=0.8, **options)
    return simulate(T0, P, controller, dt=0.04, steps=steps)


def positions_in_desired_frame(out):
    return np.array([(inverse(T_OD) @ T)[:3, 3] for T in out["T"]])


class PBVSClaims(unittest.TestCase):

    def test_straight_camera_path_about_a_fixed_axis(self):
        """Slide 'PBVS Control Law': straight line in 3-D, rotation about a fixed axis."""
        out = simulate(GENERAL, P, PBVS(P, T_OD, lam=0.8), dt=0.04, steps=600)
        self.assertEqual(out["status"], "converged")
        p = positions_in_desired_frame(out)
        d = p - p[0]
        u = d[-1] / np.linalg.norm(d[-1])
        off_line = np.linalg.norm(d - np.outer(d @ u, u), axis=1).max()
        self.assertLess(off_line, 0.01 * np.linalg.norm(d[-1]))      # discrete-time integration only
        axes = [log_so3((inverse(T_OD) @ T)[:3, :3]) for T in out["T"][:-10]]
        axes = np.array([a / np.linalg.norm(a) for a in axes])
        np.testing.assert_allclose(axes - axes[0], 0.0, atol=1e-9)

    def test_pose_estimation_is_exact_with_the_right_calibration(self):
        m = measure(GENERAL, P)
        np.testing.assert_allclose(planar_pose(P, m["s"]), inverse(GENERAL), atol=1e-9)


class IBVSClaims(unittest.TestCase):

    def test_image_paths_are_nearly_straight(self):
        out = ibvs(GENERAL)
        self.assertEqual(out["status"], "converged")
        s = out["s"]
        length = np.sum(np.linalg.norm(np.diff(s, axis=0), axis=2), axis=0)
        chord = np.linalg.norm(s[-1] - s[0], axis=1)
        np.testing.assert_array_less(length / chord, 1.01)

    def test_rotation_about_the_optical_axis(self):
        """Slide 'IBVS Issues': L(s) retreats, L(s*) advances, the mean rotates in place."""
        for interaction, sign in (("current", -1), ("desired", +1)):
            z = positions_in_desired_frame(ibvs(relative_pose(T_OD, [0, 0, 0], [0, 0, 1.0]), interaction=interaction))[:, 2]
            self.assertGreater(sign * z[np.argmax(np.abs(z))], 0.1, msg=interaction)
        mean = ibvs(relative_pose(T_OD, [0, 0, 0], [0, 0, 2.8]), interaction="mean")
        self.assertEqual(mean["status"], "converged")
        self.assertLess(np.abs(positions_in_desired_frame(mean)).max(), 1e-6)

    def test_rotation_by_pi(self):
        """L(s): the camera retreats to infinity; L(s*): the points pass behind the camera."""
        self.assertEqual(ibvs(relative_pose(T_OD, [0, 0, 0], [0, 0, np.pi]))["status"], "camera lost")
        self.assertEqual(ibvs(relative_pose(T_OD, [0, 0, 0], [0, 0, np.pi]), interaction="desired")["status"], "point lost")


class DepthClaims(unittest.TestCase):
    """Slides 33-34: true Z = 3; constant guesses Z_hat = 1 and 10; online estimation."""

    def setUp(self):
        self.P = square_target(0.5)
        self.T_od = frontal_pose(3.0)
        self.desired = measure(self.T_od, self.P)
        self.T0 = relative_pose(self.T_od, [0.5, -0.3, -1.0], [0.1, -0.2, 0.5])

    def run_with(self, **options):
        c = IBVS(self.desired["s"], self.desired["Z"], lam=0.8, **options)
        return simulate(self.T0, self.P, c, dt=0.04, steps=1500, tol=1e-4)

    def test_constant_guesses_converge_with_scaled_translation(self):
        runs = {Z_hat: self.run_with(depth="constant", Z_hat=Z_hat) for Z_hat in (1.0, 3.0, 10.0)}
        for out in runs.values():
            self.assertEqual(out["status"], "converged")
        self.assertGreater(runs[1.0]["times"][-1], 2 * runs[3.0]["times"][-1])        # slower
        nu = {k: np.abs(o["v"][:, :3]).max() for k, o in runs.items()}
        self.assertGreater(nu[10.0], 2.5 * nu[3.0])                                   # larger velocities

    def test_online_estimate_converges_to_the_true_depth(self):
        out = self.run_with(depth="online", Z_hat=1.0)
        self.assertEqual(out["status"], "converged")
        np.testing.assert_allclose(out["Z_hat"][-1], out["Z"][-1], rtol=1e-3)


class CalibrationClaims(unittest.TestCase):

    def test_ibvs_reaches_the_goal_pbvs_does_not(self):
        """Summary: calibration errors - PBVS highly sensitive, IBVS robust."""
        K = Intrinsics()
        K_hat = Intrinsics(f=1.1 * K.f, u0=K.u0 + 10, v0=K.v0 - 5)
        desired = measure(T_OD, P, K)
        runs = {
            "ibvs": IBVS(None, DESIRED["Z"], lam=0.8, K_hat=K_hat, uv_star=desired["uv"]),
            "pbvs": PBVS(P, T_OD, lam=0.8, perfect_pose=False, K_hat=K_hat),
        }
        error = {}
        for name, controller in runs.items():
            out = simulate(GENERAL, P, controller, dt=0.04, steps=800, K=K, tol=1e-6)
            self.assertEqual(out["status"], "converged", msg=name)
            error[name] = np.linalg.norm((inverse(T_OD) @ out["T"][-1])[:3, 3])
        self.assertLess(error["ibvs"], 1e-4)
        self.assertGreater(error["pbvs"], 0.02)


class P3PClaims(unittest.TestCase):
    """Slide 'Why 4 points?': 3 points, up to 4 poses with the same image."""

    def test_slide_configuration(self):
        tri = np.array([[0, 0.577, 0], [-0.5, -0.289, 0], [0.5, -0.289, 0]])
        center = np.array([0.0, 0.0, 0.0])
        T1 = look_at([0, 0, 1], [0, 0, 0], up=[0, 1, 0])
        P_c = transform(inverse(T1), tri)
        solutions = p3p(tri, P_c)
        self.assertEqual(len(solutions), 4)
        centers = np.array([inverse(S)[:3, 3] for S in solutions])
        self.assertTrue(np.any(np.all(np.abs(centers - [0, 0, 1]) < 1e-6, axis=1)))       # pose 1
        self.assertTrue(np.any(np.all(np.abs(centers - [0, 0.7217, 0.25]) < 2e-3, axis=1)))  # pose 2 of the slide
        image = P_c[:, :2] / P_c[:, 2:]
        center_image_1 = transform(inverse(T1), center)[:2] / transform(inverse(T1), center)[2]
        for S in solutions:
            q = transform(S, tri)
            np.testing.assert_allclose(q[:, :2] / q[:, 2:], image, atol=1e-9)               # points 1-3 identical
            c = transform(S, center)
            if not np.allclose(inverse(S)[:3, 3], [0, 0, 1], atol=1e-6):
                self.assertGreater(np.linalg.norm(c[:2] / c[2] - center_image_1), 0.05)      # point 4 differs


if __name__ == "__main__":
    unittest.main()
