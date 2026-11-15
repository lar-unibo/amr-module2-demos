"""Lecture 3, part 2: closed-form registration, ICP, the simulated depth camera, and the two demos."""
from __future__ import annotations

import json
import unittest

import numpy as np

from course.geometry import exp_so3, inverse, pose, transform
from course.pointcloud import BRACKET, DepthCamera, box_edges, inside, sample_surface
from course.pose import kabsch
from course.registration import (icp, knn, nearest, pca_normals, point_to_plane_step, register,
                                 rotation_error)
from sessions import runtime

RNG = np.random.default_rng(7)


def random_pose(rng, angle=None):
    axis = rng.normal(size=3)
    axis /= np.linalg.norm(axis)
    return pose(exp_so3(axis * (rng.uniform(0, np.pi) if angle is None else angle)), rng.normal(scale=0.3, size=3))


class ClosedForm(unittest.TestCase):

    def test_matches_kabsch(self):
        """Slide notation (SVD of sum s~ m~^T, R = U D V^T) = the transposed convention of kabsch."""
        for _ in range(50):
            m = RNG.normal(size=(int(RNG.integers(3, 40)), 3))
            T = random_pose(RNG)
            s = transform(T, m) + RNG.normal(scale=0.05, size=m.shape)
            out = register(m, s)
            R, t = kabsch(m, s)
            np.testing.assert_allclose(out["R"], R, atol=1e-9)
            np.testing.assert_allclose(out["t"], t, atol=1e-9)
            self.assertAlmostEqual(np.linalg.det(out["R"]), 1.0, places=9)

    def test_three_exact_pairs_fix_the_pose(self):
        m = np.array([[0.0, 0, 0], [0.1, 0, 0], [0, 0.05, 0.02]])
        T = random_pose(RNG)
        out = register(m, transform(T, m))
        np.testing.assert_allclose(out["T"], T, atol=1e-12)
        self.assertLess(out["rms"], 1e-12)

    def test_translation_maps_the_centroids(self):
        m = RNG.normal(size=(20, 3))
        s = transform(random_pose(RNG), m) + RNG.normal(scale=0.1, size=m.shape)
        out = register(m, s)
        np.testing.assert_allclose(out["R"] @ out["m_bar"] + out["t"], out["s_bar"], atol=1e-12)
        np.testing.assert_allclose(out["M"], sum(np.outer(a, b) for a, b in zip(s - s.mean(0), m - m.mean(0))), atol=1e-12)

    def test_d_avoids_a_reflection(self):
        """A mirrored scene: U V^T is the mirror (det -1, zero cost); D gives the best rotation,
        whose cost is higher by 4 sigma_3 (slide 45: tr(Sigma Q) loses 2 sigma_3)."""
        m = RNG.normal(size=(15, 3))
        mirror = np.diag([1.0, 1.0, -1.0])
        s = m @ mirror.T @ exp_so3([0.3, -0.2, 0.5]).T
        raw = register(m, s, correct=False)
        fixed = register(m, s, correct=True)
        self.assertLess(raw["det_UVt"], 0)
        self.assertAlmostEqual(np.linalg.det(raw["R"]), -1.0, places=9)
        self.assertLess(raw["cost"], 1e-20)
        self.assertAlmostEqual(np.linalg.det(fixed["R"]), 1.0, places=9)
        self.assertAlmostEqual(fixed["cost"] - raw["cost"], 4 * raw["sigma"][2], places=9)
        # no rotation does better than the corrected one
        for _ in range(200):
            R = exp_so3(RNG.normal(size=3))
            t = s.mean(0) - R @ m.mean(0)
            self.assertGreaterEqual(np.sum((m @ R.T + t - s) ** 2), fixed["cost"] - 1e-9)


class Neighbours(unittest.TestCase):

    def test_nearest_and_knn(self):
        A, B = RNG.normal(size=(300, 3)), RNG.normal(size=(500, 3))
        idx, dist = nearest(A, B, block=64)
        D = np.linalg.norm(A[:, None] - B[None], axis=2)
        np.testing.assert_array_equal(idx, D.argmin(axis=1))
        np.testing.assert_allclose(dist, D.min(axis=1), atol=1e-9)
        nb = knn(B, 5)
        np.testing.assert_array_equal(nb[:, 0], np.arange(len(B)))
        DB = np.linalg.norm(B[:, None] - B[None], axis=2)
        np.testing.assert_allclose(np.sort(DB, axis=1)[:, :5], np.take_along_axis(DB, nb, axis=1), atol=1e-12)

    def test_pca_normals_of_a_plane(self):
        uv = RNG.uniform(-1, 1, size=(200, 2))
        R = exp_so3([0.4, 0.2, -0.3])
        P = np.column_stack([uv, 0.0 * uv[:, 0]]) @ R.T
        normals, variation = pca_normals(P, k=8, viewpoint=R @ [0, 0, 5.0])
        np.testing.assert_allclose(normals, np.tile(R[:, 2], (200, 1)), atol=1e-9)   # towards the viewpoint
        self.assertLess(variation.max(), 1e-12)


class ICP(unittest.TestCase):

    def setUp(self):
        self.model, self.model_normals = sample_surface(BRACKET, 800, np.random.default_rng(1))

    def test_point_to_plane_step_is_first_order(self):
        q = self.model[::4]
        n = self.model_normals[::4]
        for scale in (1e-2, 1e-3):
            w, t = scale * np.array([0.3, -0.5, 0.2]), scale * np.array([0.02, 0.01, -0.03])
            s = q @ exp_so3(w).T + t
            dR, dt = point_to_plane_step(q, s, n @ exp_so3(w).T)
            err = rotation_error(dR, exp_so3(w)) + np.linalg.norm(dt - t)
            self.assertLess(err, 50 * scale ** 2)                 # the error of a linearization

    def test_converges_without_noise(self):
        T_true = pose(exp_so3([0, 0, 0.4]), [0.02, 0.0, 0.0])
        scene = transform(T_true, self.model[:300]) + 0.0
        T0 = pose(exp_so3([0, 0, 0.55]), [0.03, -0.01, 0.0])
        for metric, normals in (("point", None), ("plane", self.model_normals[:300] @ T_true[:3, :3].T)):
            out = icp(self.model, scene, T0, iterations=80, metric=metric, normals=normals)
            self.assertTrue(out[-1]["converged"], msg=metric)
            np.testing.assert_allclose(out[-1]["T"], T_true, atol=1e-6, err_msg=metric)

    def test_point_to_point_error_never_increases(self):
        """Each step minimizes E for the current pairs, and new closest points can only shorten them."""
        T_true = pose(exp_so3([0, 0, 0.2]))
        scene = transform(T_true, self.model[::3]) + np.random.default_rng(2).normal(scale=0.002, size=(267, 3))
        out = icp(self.model, scene, pose(exp_so3([0, 0, 0.6]), [0.02, 0.02, 0]), iterations=60, tol=0)
        E = np.array([r["E"] for r in out])
        self.assertTrue(np.all(np.diff(E) <= 1e-12 * E[:-1]))


class DepthCameraModel(unittest.TestCase):

    def test_surface_samples(self):
        P, N = sample_surface(BRACKET, 500, np.random.default_rng(0))
        self.assertEqual(len(P), 500)
        self.assertTrue(np.all(inside(BRACKET, P - 1e-4 * N)))      # just inside the object
        self.assertFalse(np.any(inside(BRACKET, P + 1e-4 * N)))     # just outside: an outer face
        self.assertEqual(len(box_edges(BRACKET)), 12 * len(BRACKET))

    def test_rendered_points(self):
        cam = DepthCamera(eye=(0.36, -0.25, 0.30))
        T_obj = pose(exp_so3([0, 0, 0.17]))
        view = cam.render(BRACKET, T_obj)
        pc = view["points_c"]
        # s^c = d K^-1 [u v 1]^T: projecting back gives the pixel
        uv = pc @ cam.K.T
        np.testing.assert_allclose(uv[:, :2] / uv[:, 2:], view["uv"], atol=1e-9)
        np.testing.assert_allclose(pc[:, 2], view["d"], atol=1e-12)
        # on the surface of the object, on faces turned towards the camera
        local = transform(inverse(T_obj) @ cam.T_cam, pc)
        normals = view["normals_c"]
        self.assertTrue(np.all(inside(BRACKET, local - 1e-5 * (normals @ (inverse(T_obj) @ cam.T_cam)[:3, :3].T))))
        self.assertTrue(np.all(np.sum(normals * pc, axis=1) < 0))
        # self-occlusion: fewer points than faces turned towards the camera would give
        self.assertGreater(len(pc), 400)


class RegistrationDemo(unittest.TestCase):
    """The experiments of the lesson."""

    def setUp(self):
        token = json.loads(runtime.start("registration"))["session"]
        self.call = lambda action, **p: json.loads(runtime.call(token, action, json.dumps(p)))

    def test_three_pairs_and_noise(self):
        S = self.call("preset", name="three")
        self.assertLess(S["rot_err"], 1e-6)
        self.assertLess(S["trans_err"], 1e-6)
        default = self.call("preset", name="default")
        noisy = self.call("preset", name="noisy")
        self.assertLess(default["rot_err"], 1.0)
        self.assertGreater(noisy["rot_err"], 2.0)
        self.assertLess(noisy["rot_err"], 5.0)                       # "about 3 degrees"
        more = self.call("set", n=120)
        self.assertLess(more["rot_err"], noisy["rot_err"])

    def test_wrong_pairs(self):
        default = self.call("preset", name="default")
        wrong = self.call("preset", name="wrong")
        self.assertLess(default["rms"], 4.0)
        self.assertGreater(wrong["rms"], 20.0)                       # "from 3 to 25 mm"
        self.assertGreater(wrong["rot_err"], 3.5 * default["rot_err"])

    def test_mirror(self):
        S = self.call("preset", name="mirror")
        self.assertLess(S["det_UVt"], 0)
        self.assertLess(S["det_R"], 0)
        self.assertIsNone(S["rot_err"])
        self.assertAlmostEqual(S["rms"], 7.8, delta=0.05)
        self.assertAlmostEqual(S["rms_other"], 8.2, delta=0.05)
        fixed = self.call("set", correct=True)
        self.assertGreater(fixed["det_R"], 0)
        self.assertAlmostEqual(fixed["rot_err"], 1.8, delta=0.1)
        cost_gap = (fixed["rms"] ** 2 - S["rms"] ** 2) * fixed["n"] * 1e-6     # m^2
        self.assertAlmostEqual(cost_gap / (4 * fixed["sigma"][2]), 1.0, delta=1e-2)  # sigma is rounded in JSON
        self.assertGreater(self.call("set", noise=0.5)["det_UVt"], 0)          # less noise: no reflection

    def test_resample(self):
        a = self.call("reset")
        b = self.call("resample")
        self.assertEqual(b["seed"], a["seed"] + 1)
        self.assertFalse(np.allclose(a["s"], b["s"]))


class ICPDemo(unittest.TestCase):

    def setUp(self):
        token = json.loads(runtime.start("icp"))["session"]
        self.call = lambda action, **p: json.loads(runtime.call(token, action, json.dumps(p)))

    def test_good_guess_and_point_to_plane(self):
        good = self.call("preset", name="good")
        self.assertTrue(good["found"] and good["converged"])
        self.assertLess(good["rot_err"][-1], 0.3)
        self.assertLess(good["trans_err"][-1], 1.0)
        self.assertAlmostEqual(good["iterations"], 26, delta=3)
        self.assertGreater(good["n_scene"], 500)
        plane = self.call("preset", name="plane")
        self.assertTrue(plane["found"] and plane["converged"])
        self.assertLess(plane["iterations"], 0.6 * good["iterations"])         # "14 instead of 26"

    def test_bad_guess_is_a_local_minimum(self):
        S = self.call("preset", name="far")
        self.assertTrue(S["converged"])
        self.assertFalse(S["found"])
        self.assertGreater(S["rot_err"][-1], 80)
        self.assertGreater(S["rms"][-1], 3 * S["rms_true"])                    # E is worse than at the truth
        # the basin of the true pose, with the offset of this preset: from about -80 to +100 degrees
        self.assertTrue(self.call("set", yaw0=-80)["found"])
        self.assertTrue(self.call("set", yaw0=100)["found"])
        self.assertFalse(self.call("set", yaw0=110)["found"])

    def test_outliers_and_rejection(self):
        S = self.call("preset", name="outliers")
        self.assertEqual(S["n_outliers"], 120)
        self.assertFalse(S["found"])
        self.assertGreater(S["rot_err"][-1], 4.0)
        R = self.call("preset", name="rejection")
        self.assertTrue(R["found"])
        self.assertLess(R["rot_err"][-1], 0.5)
        self.assertGreater(len(R["rejected"][-1]), 60)                         # most outliers are dropped
        W = self.call("set", reject="worst", reject_worst=15)
        self.assertTrue(W["found"])

    def test_records_are_consistent(self):
        S = self.call("preset", name="good")
        self.assertEqual(len(S["T"]), S["iterations"] + 1)
        self.assertEqual(len(S["pairs"][0]), S["n_scene"])
        self.assertTrue(all(0 <= j < len(S["model"]) for j in S["pairs"][-1]))


if __name__ == "__main__":
    unittest.main()
