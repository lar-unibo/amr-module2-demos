"""Lecture 3, part 1: planar grasp matrix, positive span, and the closure demo."""
from __future__ import annotations

import json
import unittest
from itertools import combinations

import numpy as np

from course.grasp import (Ellipse, Hourglass, complete_grasp_matrix, cross2, grasp_matrix, nnls,
                          positive_combination, positive_span, primitive_wrenches, smallest_grip, tangent)
from sessions import runtime

RNG = np.random.default_rng(3)


def brute_force_span(W, tol=1e-9):
    """Independent test: a nonzero nu with W nu >= 0 exists iff an extreme ray of the cone
    {nu : W nu >= 0} does; in R^3 its extreme rays are +-(w_i x w_j) (or Null(W) if rank < 3)."""
    rank = np.linalg.matrix_rank(W, tol=1e-9)
    if rank < 3:
        return False
    for i, j in combinations(range(len(W)), 2):
        nu = np.cross(W[i], W[j])
        if np.linalg.norm(nu) < 1e-12:
            continue
        for s in (1, -1):
            if np.all(W @ (s * nu) >= -tol * np.linalg.norm(nu)):
                return False
    return True


class GraspMatrix(unittest.TestCase):

    def test_twists_and_wrenches_are_dual(self):
        """G~_i^T gives the contact twist in {C_i}; G~_i maps contact wrenches to the object."""
        c, n = np.array([[0.3, -0.5], [-0.2, 0.7]]), np.array([[0.6, 0.8], [0.0, -1.0]])
        Gt = complete_grasp_matrix(c, n)
        nu = np.array([0.4, -0.3, 0.9])                          # [v_x, v_y, omega]
        for i in range(2):
            v = nu[:2] + nu[2] * np.array([-c[i, 1], c[i, 0]])  # v + omega x r
            expected = np.r_[v @ n[i], v @ tangent(n[i]), nu[2]]
            np.testing.assert_allclose(Gt[:, 3 * i:3 * i + 3].T @ nu, expected, atol=1e-12)
            lam = np.array([1.3, -0.4, 0.2])                    # [f_n, f_t, m] in {C_i}
            f = lam[0] * n[i] + lam[1] * tangent(n[i])
            np.testing.assert_allclose(Gt[:, 3 * i:3 * i + 3] @ lam, np.r_[f, lam[2] + cross2(c[i], f)], atol=1e-12)

    def test_selection_keeps_the_transmitted_components(self):
        c, n = RNG.normal(size=(3, 2)), RNG.normal(size=(3, 2))
        n /= np.linalg.norm(n, axis=1, keepdims=True)
        G = grasp_matrix(c, n, "PwoF")
        np.testing.assert_allclose(G, np.array([np.r_[ni, cross2(ci, ni)] for ci, ni in zip(c, n)]).T, atol=1e-12)
        G_hf = grasp_matrix(c, n, "HF")
        self.assertEqual(G_hf.shape, (3, 6))
        np.testing.assert_allclose(G_hf[:, ::2], G, atol=1e-12)


class PositiveSpan(unittest.TestCase):

    def test_matches_the_extreme_ray_test(self):
        agree = {True: 0, False: 0}
        for _ in range(400):
            k = RNG.integers(3, 9)
            W = RNG.normal(size=(k, 3))
            out = positive_span(W)
            expected = brute_force_span(W)
            self.assertEqual(out["closed"], expected)
            agree[expected] += 1
            if not out["closed"]:
                nu = out["escape"] if out["escape"] is not None else out["null"][0]
                self.assertTrue(np.all(W @ nu >= -1e-9))
                self.assertGreater(np.linalg.norm(nu), 0.5)
            else:
                alpha = positive_combination(W, out["margin"])
                self.assertTrue(np.all(alpha > 0))
                np.testing.assert_allclose(alpha @ W, 0.0, atol=1e-9)
        self.assertGreater(min(agree.values()), 50)              # both outcomes were exercised

    def test_flat_and_degenerate_sets(self):
        self.assertFalse(positive_span(np.array([[1.0, 0, 0], [-1.0, 0, 0]]))["closed"])
        line = positive_span(np.array([[1.0, 0, 0], [-1.0, 0, 0]]))
        self.assertTrue(line["relative"])                        # origin inside, relative to the line
        self.assertEqual(line["null"].shape, (2, 3))
        square = np.array([[1.0, 0, 0], [0, 1.0, 0], [-1.0, 0, 0], [0, -1.0, 0]])
        out = positive_span(square)
        self.assertEqual((out["rank"], out["closed"], out["relative"]), (2, False, True))
        tetra = np.array([[1.0, 1, 1], [1, -1, -1], [-1, 1, -1], [-1, -1, 1]])
        out = positive_span(tetra)
        self.assertTrue(out["closed"])
        self.assertAlmostEqual(out["margin"], 1 / np.sqrt(3), places=9)   # inscribed sphere of the tetrahedron
        self.assertEqual(len(out["faces"]), 4)

    def test_nnls_matches_enumeration(self):
        for _ in range(60):
            A, b = RNG.normal(size=(5, 4)), RNG.normal(size=5)
            best = np.inf
            for r in range(5):
                for subset in combinations(range(4), r):
                    x = np.zeros(4)
                    if subset:
                        x[list(subset)] = np.linalg.lstsq(A[:, list(subset)], b, rcond=None)[0]
                    if np.all(x >= -1e-12):
                        best = min(best, np.linalg.norm(A @ x - b))
            x = nnls(A, b)
            self.assertTrue(np.all(x >= 0))
            self.assertAlmostEqual(np.linalg.norm(A @ x - b), best, places=8)


class SmallestGrip(unittest.TestCase):

    @staticmethod
    def bisection(W, w):
        """Independent: the smallest s with {alpha >= 0, W^T alpha = -w, sum alpha <= s} feasible,
        each test a non-negative least-squares problem with a slack."""
        k = len(W)
        A = np.block([[W.T, np.zeros((3, 1))], [np.ones((1, k)), np.ones((1, 1))]])
        feasible = lambda s: np.linalg.norm(A @ nnls(A, np.r_[-w, s]) - np.r_[-w, s]) < 1e-9
        lo, hi = 0.0, 1.0
        while not feasible(hi):
            hi *= 2
        for _ in range(60):
            mid = 0.5 * (lo + hi)
            lo, hi = (lo, mid) if feasible(mid) else (mid, hi)
        return hi

    def test_matches_bisection(self):
        shape, solved = Ellipse(), 0
        for _ in range(60):
            idx = RNG.choice(len(shape.points), size=RNG.integers(2, 5), replace=False)
            W, _ = primitive_wrenches(shape.points[idx], shape.normals[idx], "HF", RNG.uniform(0.1, 0.8))
            w = RNG.normal(size=3)
            alpha = smallest_grip(W, w)
            residual = np.linalg.norm(W.T @ nnls(W.T, -w) + w)
            self.assertEqual(alpha is None, residual > 1e-7)           # balanced exactly when some alpha >= 0 is
            if alpha is None:
                continue
            solved += 1
            self.assertTrue(np.all(alpha >= 0))
            np.testing.assert_allclose(W.T @ alpha, -w, atol=1e-9)
            self.assertAlmostEqual(alpha.sum(), self.bisection(W, w), places=6)
        self.assertGreater(solved, 20)


class Shapes(unittest.TestCase):

    def test_boundary_samples_and_normals(self):
        for shape in (Ellipse(), Hourglass(k=0.4), Hourglass(k=0.0), Hourglass(k=-0.1), Hourglass(w0=0.7, h=0.55, k=0.0)):
            np.testing.assert_allclose(shape.clearance(shape.points), 0.0, atol=1e-9)
            np.testing.assert_allclose(np.linalg.norm(shape.normals, axis=1), 1.0)
            corners = getattr(shape, "corners", np.empty((0, 2)))
            away = np.all(np.linalg.norm(shape.points[:, None] - corners[None], axis=2) > 0.05, axis=1)
            points, normals = shape.points[away], shape.normals[away]
            self.assertTrue(np.all(shape.clearance(points + 0.01 * normals) < 0))     # the normals point inside
            self.assertTrue(np.all(shape.clearance(points - 0.01 * normals) > 0))
        self.assertTrue(np.any(np.all(np.isclose(Hourglass().points, [0.22, 0.0]), axis=1)))  # the waist is a sample


class ClosureDemo(unittest.TestCase):
    """The experiments of the lesson."""

    def setUp(self):
        token = json.loads(runtime.start("closure"))["session"]
        self.call = lambda action, **p: json.loads(runtime.call(token, action, json.dumps(p)))

    def test_the_three_grasps_of_the_opening_question(self):
        a = self.call("preset", name="a")
        self.assertTrue(a["closed"])
        self.assertEqual(a["rank_G"], 3)
        self.assertTrue(all(f > 0 for f in np.array(a["internal"]["local"])[:, 0]))
        c = self.call("preset", name="c")
        self.assertFalse(c["closed"])
        self.assertEqual(c["escape"]["second_order"], "escapes")
        b = self.call("preset", name="b")
        self.assertFalse(b["closed"])                             # first order: two contacts are not enough
        self.assertEqual(b["escape"]["second_order"], "held")      # the curvature holds it
        np.testing.assert_allclose(b["escape"]["normal_speeds"], 0.0, atol=1e-9)

    def test_three_fingers_leave_a_free_motion(self):
        self.call("preset", name="a")
        S = self.call("set", fingers=3)
        self.assertFalse(S["closed"])
        speeds = np.array(S["escape"]["normal_speeds"])
        self.assertTrue(np.all(speeds >= -1e-9) and np.any(speeds > 1e-3))

    def test_curvature_of_the_hourglass(self):
        self.call("preset", name="b")
        box = self.call("set", k=0.0)
        self.assertEqual(box["escape"]["second_order"], "escapes")
        np.testing.assert_allclose(box["escape"]["clearance"], 0.0, atol=1e-9)   # it slides
        barrel = self.call("set", k=-0.1)
        self.assertEqual(barrel["escape"]["second_order"], "escapes")
        self.assertGreater(min(barrel["escape"]["clearance"]), 1e-3)            # it leaves the fingers
        self.assertEqual(self.call("set", k=0.1)["escape"]["second_order"], "held")

    def test_second_order_uses_the_room_at_other_fingers(self):
        """Three frictionless fingers whose normals meet at one point: turning about it is free at
        first order; on the ellipse the tip finger gains room while the other two are pushed in,
        and a small shift towards the tip frees them: not held."""
        self.call("preset", name="three")
        S = self.call("set", model="PwoF")
        self.assertEqual((S["hull"]["rank"], S["hull"]["relative"]), (2, True))
        E = S["escape"]
        self.assertEqual(E["second_order"], "escapes")
        self.assertGreater(np.linalg.norm(E["correction"]), 1e-3)
        self.assertGreater(min(E["clearance"]), 0.0)               # the corrected motion touches no finger
        # grasp (b): the balancing combination y = (1, 1) weighs the clearances negatively (Farkas)
        b = self.call("preset", name="b")
        self.assertLess(sum(b["escape"]["clearance"]), 0.0)

    def test_force_closure_and_friction_cones(self):
        pinch = self.call("preset", name="pinch")
        self.assertTrue(pinch["closed"])
        self.assertTrue(self.call("set", mu=0.01)["closed"])        # antipodal: any mu > 0
        self.assertFalse(self.call("set", mu=0.0)["closed"])
        tilted = self.call("preset", name="tilted")
        self.assertAlmostEqual(tilted["angles"][0], 34.2, delta=0.05)
        self.assertFalse(tilted["closed"])
        self.assertEqual(tilted["escape"]["kind"], "wrench")
        self.assertFalse(self.call("set", mu=0.67)["closed"])
        S = self.call("set", mu=0.69)
        self.assertTrue(S["closed"])
        local = np.array(S["internal"]["local"])
        self.assertTrue(np.all(np.abs(local[:, 1]) < S["mu"] * local[:, 0]))    # strictly inside the cones
        self.assertLess(S["internal"]["residual"], 1e-9)                         # G lambda_int = 0
        self.assertTrue(self.call("preset", name="three")["closed"])
        self.call("preset", name="c")
        self.assertTrue(self.call("set", model="HF", mu=0.1)["closed"])          # two hard fingers suffice

    def test_unbalanced_wrench_is_out_of_reach(self):
        S = self.call("preset", name="tilted")
        w = np.array(S["escape"]["wrench"])
        W = np.array(S["wrenches"]) * [1, 1, S["rho"]]            # unscaled primitive wrenches
        scale = np.array([1.0, 1.0, 1.0 / S["rho"] ** 2])
        self.assertTrue(np.all(W @ (w * scale) >= -1e-9))         # (G lambda) . S^2 w >= 0: cannot cancel w

    def test_four_contacts_are_not_sufficient(self):
        self.call("preset", name="a")
        t = np.radians(280)
        S = self.call("move", index=2, x=0.45 * np.cos(t), y=np.sin(t))     # finger 3 next to finger 4
        self.assertEqual(len(S["contacts"]), 4)
        self.assertFalse(S["closed"])
        self.assertEqual(S["escape"]["kind"], "twist")
        self.assertFalse(any(S["escape"]["ghost_fingers_in"]))                 # the drawn motion touches no finger

    def test_statics_of_the_box(self):
        """Slide 28: -G^# w gives each finger mg/2 of friction and no normal force; the squeeze
        needs gamma >= mg / (2 mu), so a soapy box needs more, and mu = 0 cannot hold it."""
        S = self.call("preset", name="box")
        self.assertTrue(S["closed"] and S["load"])
        L = S["statics"]
        np.testing.assert_allclose(L["carry"], [[0.0, 0.5], [0.0, 0.5]], atol=1e-12)
        self.assertEqual(L["carry_inside"], [False, False])
        previous = 0.0
        for mu in (0.4, 0.2, 0.1, 0.05):
            L = self.call("set", mu=mu)["statics"]
            self.assertAlmostEqual(L["gamma"], 1 / (2 * mu), places=9)
            self.assertGreater(L["gamma"], previous)
            previous = L["gamma"]
            total = np.array(L["total"])
            np.testing.assert_allclose(np.abs(total), [[1 / (2 * mu), 0.5]] * 2, atol=1e-9)   # on the cone edge
            np.testing.assert_allclose(total.sum(axis=0), [0.0, 1.0], atol=1e-9)          # balances mg
            self.assertLess(L["residual"], 1e-9)
        self.assertFalse(self.call("set", mu=0.0)["statics"]["feasible"])
        pinch = self.call("preset", name="pinch")
        self.assertIsNone(pinch["statics"])                                    # presets switch the weight off
        self.assertAlmostEqual(self.call("set", load=True)["statics"]["gamma"], 1 / 0.6, places=9)

    def test_statics_of_the_other_grasps(self):
        self.call("preset", name="c")
        L = self.call("set", load=True)["statics"]
        self.assertFalse(L["closed"])
        self.assertTrue(L["feasible"])                                         # not closed, yet it rests on finger 2
        np.testing.assert_allclose(L["total"], [[0.0, 0.0], [0.0, 1.0]], atol=1e-9)
        self.call("preset", name="b")
        S = self.call("set", load=True)
        self.assertEqual(S["escape"]["second_order"], "held")
        self.assertFalse(S["statics"]["feasible"])                              # horizontal normals
        self.call("preset", name="a")
        L = self.call("set", load=True)["statics"]
        self.assertEqual(L["carry_inside"], [False, False, True, True])        # -G^# w pulls at fingers 1 and 2
        self.assertTrue(np.all(np.array(L["lambda"]) >= -1e-12))
        np.testing.assert_allclose(np.array(L["lambda_carry"]) + L["lambda_squeeze"], L["lambda"], atol=1e-12)
        self.call("preset", name="tilted")
        self.assertGreater(self.call("set", load=True, mu=0.69)["statics"]["gamma"], 30)   # near the limit
        self.assertLess(self.call("set", mu=1.0)["statics"]["gamma"], 1.3)

    def test_statics_with_more_ways_to_squeeze(self):
        """Three hard fingers: dim N(G) = 3. The forces are in the cones, balance the weight, and
        need less normal force than squeezing along lambda_int alone."""
        self.call("preset", name="three")
        S = self.call("set", load=True)
        L, mu = S["statics"], S["mu"]
        self.assertEqual(S["nullity"], 3)
        self.assertIsNone(L["gamma"])
        lam = np.array(L["lambda"]).reshape(-1, 2)
        self.assertTrue(np.all(np.abs(lam[:, 1]) <= mu * lam[:, 0] + 1e-9))
        self.assertLess(L["residual"], 1e-9)
        np.testing.assert_allclose(np.array(S["G"]) @ L["lambda_squeeze"], 0.0, atol=1e-6)    # in N(G) (G rounded in the JSON)
        carry = np.array(L["lambda_carry"]).reshape(-1, 2)
        d = np.array(S["internal"]["lambda"]).reshape(-1, 2)
        gamma = max(np.max((s * carry[:, 1] - mu * carry[:, 0]) / (mu * d[:, 0] - s * d[:, 1])) for s in (1, -1))
        self.assertLess(L["grip"], (carry + gamma * d)[:, 0].sum() - 1.0)

    def test_dragging_snaps_to_the_boundary(self):
        S = self.call("move", index=0, x=0.9, y=0.0)
        np.testing.assert_allclose(S["contacts"][0], [0.45, 0.0], atol=1e-9)


if __name__ == "__main__":
    unittest.main()
