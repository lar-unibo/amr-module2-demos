"""Lecture 3, slides 51-57 and 60: depth scans, local PCA, antipodal grasps, and the grasp-selection demo."""
from __future__ import annotations

import json
import unittest

import numpy as np

from course.grasp_selection import (antipodal_pairs, box, cast, cup, depth_scan, edge_normals,
                                    evaluate_grasps, gripper_boxes, local_pca, nearest, orient_towards)
from sessions import runtime

RNG = np.random.default_rng(4)


class DepthCamera(unittest.TestCase):

    def test_rays_hit_the_first_surface(self):
        t, n, on_object = cast(np.array([0.0, 0.5]), np.array([[0.0, -1.0], [1.0, 0.0]]), box())
        self.assertAlmostEqual(t[0], 0.4)                      # the top of the box (10 cm high)
        np.testing.assert_allclose(n[0], [0.0, 1.0])
        self.assertTrue(on_object[0])
        self.assertTrue(np.isinf(t[1]))                        # a horizontal ray above the table: no hit
        np.testing.assert_allclose(edge_normals(box()), [[0, -1], [1, 0], [0, 1], [-1, 0]], atol=1e-12)

    def test_depth_along_the_optical_axis(self):
        """p = d K^-1 [u, 1]^T: without noise the points lie on the surface; noise moves them along the ray."""
        camera, target = np.array([-0.16, 0.42]), np.array([0.0, 0.05])
        exact = depth_scan(cup(), camera, target, noise=0.0)
        np.testing.assert_allclose(exact["points"], exact["true_points"], atol=1e-12)
        noisy = depth_scan(cup(), camera, target, noise=0.002)
        shift = noisy["points"] - noisy["true_points"]
        ray = noisy["true_points"] - camera
        np.testing.assert_allclose(shift[:, 0] * ray[:, 1] - shift[:, 1] * ray[:, 0], 0.0, atol=1e-12)
        axis = (target - camera) / np.linalg.norm(target - camera)
        self.assertAlmostEqual(np.std(shift @ axis), 0.002, delta=0.0003)   # noise on the depth d


class LocalPCA(unittest.TestCase):

    def test_line_and_square(self):
        x = np.linspace(0, 0.05, 30)
        line = np.column_stack([x, 0.3 * x + 0.01])
        pca = local_pca(line, 8)
        np.testing.assert_allclose(pca["sigma"], 0.0, atol=1e-12)            # a plane (line): sigma = 0
        normal = np.array([-0.3, 1.0]) / np.hypot(0.3, 1.0)
        np.testing.assert_allclose(np.abs(pca["v0"] @ normal), 1.0, atol=1e-9)
        cross = np.array([[0.01, 0], [-0.01, 0], [0, 0.01], [0, -0.01]])
        self.assertAlmostEqual(local_pca(cross, 4)["sigma"][0], 0.5)          # isotropic scatter: 1/2 in 2-D

    def test_neighbours_and_orientation(self):
        P = RNG.normal(size=(40, 2))
        idx = nearest(P, 5)
        D = np.linalg.norm(P[:, None] - P[None], axis=2)
        np.testing.assert_allclose(np.sort(D, axis=1)[:, :5], np.take_along_axis(D, idx, axis=1))
        n = orient_towards(-np.tile([0.0, 1.0], (40, 1)), P, np.tile([0.0, 10.0], (40, 1)))
        np.testing.assert_allclose(n, np.tile([0.0, 1.0], (40, 1)))


class AntipodalAndGripper(unittest.TestCase):

    def test_antipodal_test_of_slide_57(self):
        P = np.array([[-0.03, 0.05], [0.03, 0.05], [0.03, 0.08]])
        N = np.array([[-1.0, 0.0], [1.0, 0.0], [np.cos(0.3), np.sin(0.3)]])
        pairs = antipodal_pairs(P, N, mu=0.4, max_opening=0.085)
        self.assertEqual(list(zip(pairs["i"], pairs["j"])), [(0, 1)])    # (0, 2): 26.6 deg off -n_0, cone 21.8 deg
        self.assertEqual(len(antipodal_pairs(P, N, mu=0.2, max_opening=0.085)["i"]), 1)
        self.assertEqual(len(antipodal_pairs(P, N, mu=0.4, max_opening=0.05)["i"]), 0)   # does not fit

    def test_gripper_collides_with_the_table_and_points(self):
        P = np.array([[-0.03, 0.02], [0.03, 0.02]])
        N = np.array([[-1.0, 0.0], [1.0, 0.0]])
        pairs = antipodal_pairs(P, N, mu=0.4, max_opening=0.085)
        G = evaluate_grasps(P, pairs, max_opening=0.085, pregrasp=0.05, alpha_reach=0.5, alpha_clear=0.3)
        self.assertEqual(len(G["cost"]), 1)                                # only the approach from above
        np.testing.assert_allclose(G["zg"][0], [0.0, -1.0], atol=1e-12)
        self.assertFalse(G["collision"][0])                                  # fingertips 0.4 cm above the table
        low = antipodal_pairs(P - [0, 0.017], N, mu=0.4, max_opening=0.085)
        self.assertTrue(evaluate_grasps(P - [0, 0.017], low, max_opening=0.085, pregrasp=0.05,
                                        alpha_reach=0.5, alpha_clear=0.3)["collision"][0])
        blocker = np.vstack([P, [[0.0, 0.08]]])                              # a point under the palm
        G = evaluate_grasps(blocker, pairs, max_opening=0.085, pregrasp=0.05, alpha_reach=0.5, alpha_clear=0.3)
        self.assertTrue(G["collision"][0])
        boxes = gripper_boxes(0.06, 0.085, sweep=0.05)
        self.assertAlmostEqual(boxes[0, 2], -0.045 - 0.05)                 # fingers swept back by d


class GraspSelectionDemo(unittest.TestCase):
    """The experiments of the lesson."""

    def setUp(self):
        token = json.loads(runtime.start("grasp-selection"))["session"]
        self.call = lambda action, **p: json.loads(runtime.call(token, action, json.dumps(p)))

    def test_default_box_grasp(self):
        S = self.call("reset")
        self.assertEqual(S["counts"]["points"], 181)
        self.assertGreater(S["counts"]["antipodal"], 300)
        best = S["top"][0]
        self.assertAlmostEqual(best["distance"], 0.06, delta=0.002)       # across the 6 cm box
        self.assertLess(best["c_reach"], 0.05)                             # from above
        self.assertLess(max(best["theta1"], best["theta2"]), 2.0)
        np.testing.assert_allclose(best["pregrasp"], np.array(best["centre"]) - S["d"] * np.array(best["zg"]), atol=1e-6)

    def test_surface_variation(self):
        self.call("reset")
        side = self.call("probe", x=-0.03, z=0.06)["probe"]
        corner = self.call("probe", x=-0.03, z=0.1)["probe"]
        self.assertLess(side["sigma"], 0.01)
        self.assertGreater(corner["sigma"], 0.1)
        self.assertLess(side["error_deg"], 2.0)
        S = self.call("preset", name="cup")
        P, sigma = np.array(S["cloud"]), np.array(S["sigma"])
        self.assertGreater(np.median(sigma[P[:, 1] > 0.085]), 0.15)        # the rim
        self.assertTrue(np.all(sigma <= 0.5 + 1e-12))

    def test_one_camera_misses_the_far_side(self):
        for name in ("default", "blob", "cup"):
            self.call("preset", name=name)
            one = self.call("set", cameras=1)
            self.assertEqual(one["counts"]["antipodal"], 0, msg=name)
            self.assertEqual(one["top"], [], msg=name)
            self.assertGreater(len(self.call("set", cameras=2)["top"]), 0, msg=name)

    def test_unoriented_normals_break_the_test(self):
        oriented = self.call("reset")
        S = self.call("set", orient=False)
        self.assertGreater(S["normal_error"]["inward"], 0.4)
        self.assertLess(S["counts"]["antipodal"], 0.25 * oriented["counts"]["antipodal"])
        self.assertEqual(oriented["normal_error"]["inward"], 0.0)

    def test_friction_and_opening(self):
        self.call("reset")
        counts = [self.call("set", mu=mu)["counts"]["antipodal"] for mu in (0.1, 0.2, 0.4, 0.8)]
        self.assertEqual(counts, sorted(counts))
        self.assertGreater(counts[-1], 5 * counts[0])
        narrow = self.call("set", mu=0.4, opening=0.05)
        self.assertEqual(narrow["top"], [])                                 # the box is 6 cm wide

    def test_neighbourhood_size(self):
        self.call("reset")
        small = self.call("set", k=3, noise=0.0015)
        medium = self.call("set", k=15)
        large = self.call("set", k=40)
        self.assertGreater(small["normal_error"]["median"], 3 * medium["normal_error"]["median"])  # noisy normals
        self.assertLess(large["counts"]["antipodal"], 0.6 * medium["counts"]["antipodal"])         # smoothed edges
        self.assertGreater(max(large["top"][0]["theta1"], large["top"][0]["theta2"]),
                           2 * max(medium["top"][0]["theta1"], medium["top"][0]["theta2"]))

    def test_cup_rim_and_wide_opening(self):
        S = self.call("preset", name="cup")
        rim = S["top"][0]
        self.assertLess(rim["distance"], 0.01)                              # across one wall
        self.assertGreater(rim["centre"][1], 0.05)
        wide = self.call("set", opening=0.12)["top"][0]
        self.assertGreater(wide["distance"], 0.085)                         # the whole cup
        self.assertLess(wide["cost"], rim["cost"])

    def test_probe_and_errors(self):
        self.assertIn("error", json.loads(runtime.call(json.loads(runtime.start("grasp-selection"))["session"],
                                                       "set", json.dumps({"object": "sphere"}))))
        S = self.call("set", k=1000)
        self.assertEqual(S["k"], 40)


if __name__ == "__main__":
    unittest.main()
