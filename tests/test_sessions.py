"""The demo sessions start, answer their actions, and serialize to JSON (as in the browser)."""
from __future__ import annotations

import json
import unittest

import numpy as np

from sessions import runtime
from sessions.catalog import DEMOS, catalog


class Runtime(unittest.TestCase):

    def test_every_demo_starts(self):
        for demo_id in DEMOS:
            reply = json.loads(runtime.start(demo_id, "{}"))
            self.assertNotIn("error", reply, msg=demo_id)
            self.assertIn("session", reply)

    def test_errors_are_reported(self):
        self.assertIn("error", json.loads(runtime.start("no-such-demo")))
        token = json.loads(runtime.start("interaction"))["session"]
        self.assertIn("error", json.loads(runtime.call(token, "no_such_action")))
        self.assertIn("expired", json.loads(runtime.call("bad-token", "reset"))["error"])

    def test_catalog_has_every_lecture(self):
        data = catalog()
        self.assertEqual([lec["number"] for lec in data["lectures"]], [1, 2])
        json.dumps(data)


class InteractionDemo(unittest.TestCase):

    def setUp(self):
        self.token = json.loads(runtime.start("interaction"))["session"]

    def call(self, action, **payload):
        reply = json.loads(runtime.call(self.token, action, json.dumps(payload)))
        self.assertNotIn("error", reply)
        return reply

    def test_prediction_is_first_order(self):
        self.call("preset", name="forward")              # the depth changes: a curved image path
        S = self.call("set", horizon=0.2)
        np.testing.assert_allclose(S["s_dot_measured"], S["s_dot"], atol=1e-4)
        short = S["gap"]
        long = self.call("set", horizon=2.0)["gap"]
        self.assertGreater(long, 10 * short)             # the linear prediction degrades with time

    def test_sideways_translation_gives_a_straight_image_path(self):
        S = self.call("preset", name="lateral")          # Z constant: x(t) = (X - nu t) / Z exactly
        self.assertLess(S["gap"], 1e-12)

    def test_motions_along_the_ray_do_not_move_the_point(self):
        for name in ("ray", "roll_ray"):                 # the projection ray itself is unchanged
            S = self.call("preset", name=name)
            self.assertTrue(S["v_in_null"], msg=name)
            path = np.array(S["path"], float)
            np.testing.assert_allclose(path - path[0], 0.0, atol=1e-6, err_msg=name)

    def test_a_null_space_motion_is_invisible_only_to_first_order(self):
        S = self.call("preset", name="null")
        self.assertTrue(S["v_in_null"])
        np.testing.assert_allclose(S["s_dot"], 0.0, atol=1e-9)
        path = np.array(S["path"], float)
        drift = np.linalg.norm(path - path[0], axis=1)
        self.assertGreater(drift[-1], 1e-3)              # L_p changes along the motion
        self.assertAlmostEqual(drift[2] / drift[1], 4.0, delta=0.2)   # but it starts quadratically

    def test_translation_scales_with_inverse_depth(self):
        self.call("preset", name="lateral")
        near = np.array(self.call("set", Z=1.0)["s_dot_translation"])
        far = np.array(self.call("set", Z=4.0)["s_dot_translation"])
        np.testing.assert_allclose(near, 4.0 * far, rtol=1e-9)
        self.call("preset", name="pan")
        rot_near = self.call("set", Z=1.0)["s_dot_rotation"]
        rot_far = self.call("set", Z=4.0)["s_dot_rotation"]
        np.testing.assert_allclose(rot_near, rot_far)

    def test_rank_and_null_space(self):
        S = self.call("reset")
        self.assertEqual(S["rank"], 2)
        self.assertEqual(np.array(S["null_basis"]).shape, (6, 4))



class ClosedLoopDemos(unittest.TestCase):
    """The presets of the PBVS and IBVS pages behave as their lessons say."""

    def run_preset(self, demo, **payload):
        token = json.loads(runtime.start(demo))["session"]
        reply = json.loads(runtime.call(token, "set", json.dumps(payload)))
        self.assertNotIn("error", reply)
        return reply

    @staticmethod
    def border(S):
        s = np.array(S["s"])
        return max(np.abs(s[..., 0]).max() / S["fov"][0], np.abs(s[..., 1]).max() / S["fov"][1])

    def test_every_preset_starts_inside_the_image(self):
        from sessions.servo_common import START_POSES
        for preset in START_POSES:
            S = self.run_preset("pbvs", preset=preset)
            s0 = np.array(S["s"][0])
            self.assertTrue(np.all(np.abs(s0[:, 0]) <= S["fov"][0]) and np.all(np.abs(s0[:, 1]) <= S["fov"][1]), msg=preset)

    def test_pbvs_large_tilt_leaves_the_image_ibvs_does_not(self):
        pbvs = self.run_preset("pbvs", preset="tilt")
        ibvs = self.run_preset("ibvs", preset="tilt")
        self.assertEqual(pbvs["status"], "converged")
        self.assertEqual(ibvs["status"], "converged")
        self.assertGreater(self.border(pbvs), 1.2)
        self.assertLess(self.border(ibvs), 1.0)

    def test_ibvs_rotation_presets(self):
        self.assertEqual(self.run_preset("ibvs", preset="rot_z_pi")["status"], "camera lost")
        self.assertEqual(self.run_preset("ibvs", preset="rot_z_pi", interaction="mean")["status"], "stalled")
        retreat = self.run_preset("ibvs", preset="rot_z_2.8")
        self.assertLess(min(z for _, _, z in retreat["camera_in_desired"]), -1.0)        # several metres
        mean = self.run_preset("ibvs", preset="rot_z_2.8", interaction="mean")
        self.assertLess(np.abs(np.array(mean["camera_in_desired"])).max(), 1e-6)       # pure rotation


class NewDemos(unittest.TestCase):
    """The experiments the lessons of demos 3, 5, 6 and 7 ask for."""

    def start(self, demo):
        token = json.loads(runtime.start(demo))["session"]
        return lambda action, **payload: json.loads(runtime.call(token, action, json.dumps(payload)))

    def test_four_points(self):
        call = self.start("four-points")
        S = call("reset")
        self.assertEqual(len(S["solutions"]), 4)
        np.testing.assert_allclose(np.array(S["solutions"][1])[:3, 3], [0, 0.7217, 0.25], atol=2e-3)   # pose 2 of the slide
        self.assertLess(max(S["triangle_gap"]), 1e-9)
        self.assertGreater(min(S["point4_gap"][1:]), 0.1)
        self.assertGreater(S["runs"]["three"]["final_distance"], 0.5)        # 3 points: wrong pose, e = 0
        self.assertEqual(S["runs"]["three"]["status"], "converged")
        self.assertLess(S["runs"]["four"]["final_distance"], 1e-3)           # 4 points: the desired pose

    def test_depth(self):
        call = self.start("depth")
        slow = call("set", mode="constant", Z_hat=1.0)
        exact = call("set", mode="constant", Z_hat=3.0)
        fast = call("set", mode="constant", Z_hat=10.0)
        online = call("set", mode="online", Z_hat=1.0)
        for S in (slow, exact, fast, online):
            self.assertEqual(S["status"], "converged")
            self.assertLess(S["final_position_error"], 5e-3)
        self.assertGreater(slow["times"][-1], 2.5 * exact["times"][-1])
        self.assertGreater(max(fast["nu_norm"]), 3 * max(exact["nu_norm"]))
        np.testing.assert_allclose(online["Z_hat"][-1], online["Z"][-1], rtol=1e-2)

    def test_comparison(self):
        call = self.start("comparison")
        S = call("set", focal_error=0.1, center_error=20)
        self.assertLess(S["errors"]["ibvs"]["position"], 1e-3)
        self.assertGreater(S["errors"]["pbvs"]["position"], 0.03)
        tilt = call("set", preset="tilt", focal_error=0.0, center_error=0.0)
        border = lambda run: max(np.abs(np.array(run["s"])[..., 0]).max() / 0.6, np.abs(np.array(run["s"])[..., 1]).max() / 0.45)
        self.assertGreater(border(tilt["pbvs"]), 1.0)
        self.assertLess(border(tilt["ibvs"]), 1.0)

    def test_stability(self):
        call = self.start("stability")
        S = call("reset")
        self.assertEqual(S["status"], "converged")
        A = call("analyze", k=0)
        self.assertEqual(sum(abs(x) < 1e-9 for x in A["global"]), 2)          # L L^+ has two zero eigenvalues
        np.testing.assert_allclose(A["local"], 1.0, atol=1e-9)                # L^+ L = I
        S = call("set", offset=[0.12, 0.06])
        self.assertEqual(S["status"], "stalled")
        A = call("analyze", k=len(S["s"]) - 1)
        self.assertGreater(A["e_norm"], 0.02)
        self.assertLess(A["e_proj_norm"], 1e-3)
        dip = call("set", offset=[0, 0], preset="rot_z_1", interaction="desired")
        self.assertEqual(dip["status"], "converged")
        self.assertLess(min(dip["margin"]), 0.0)                              # sufficient, not necessary
        # positive is only a local guarantee: the eigenvalue stays at 1, and the run still fails
        lost = call("set", preset="rot_z_pi", interaction="current", depth="true")
        self.assertEqual(lost["status"], "camera lost")
        np.testing.assert_allclose(lost["margin"], 1.0, atol=1e-6)
        self.assertGreater(lost["e_proj_norm"][-1], 10 * lost["e_proj_norm"][0])   # e' grows
        stuck = call("set", preset="general", offset=[0.12, 0.06])
        self.assertEqual(stuck["status"], "stalled")
        np.testing.assert_allclose(stuck["margin"], 1.0, atol=1e-6)
        # an unreachable target: IBVS stops at the best fit, the smallest error any pose can reach
        self.assertFalse(stuck["target_reachable"])
        self.assertAlmostEqual(stuck["e_norm"][-1], stuck["best_error"], places=4)
        self.assertTrue(call("set", offset=[0, 0])["target_reachable"])


class LectureOneDemos(unittest.TestCase):
    """The experiments the lessons of lecture 1 ask for."""

    def start(self, demo):
        token = json.loads(runtime.start(demo))["session"]
        return lambda action, **payload: json.loads(runtime.call(token, action, json.dumps(payload)))

    def test_projection_depth_is_lost(self):
        call = self.start("projection")
        base = np.array(call("reset")["image_mm"])
        moved = call("set", ray=2.0)
        scaled = call("set", ray=1.0, scale=1.7)
        np.testing.assert_allclose(moved["image_mm"], base, atol=1e-9)
        np.testing.assert_allclose(scaled["image_mm"], base, atol=1e-9)
        self.assertFalse(np.allclose(moved["world"], call("reset")["world"]))
        lens = call("set", z_object=2.0)
        self.assertAlmostEqual(lens["z_image_mm"], 1 / (1 / 4.0 - 1 / 2000.0), places=6)

    def test_pixels_camera_matrix(self):
        call = self.start("pixels")
        S = call("reset")
        self.assertLess(S["C_check"], 1e-9)
        same = call("set", f_mm=8.0, rho_w_um=10.0, rho_h_um=10.0)          # f / rho unchanged: same image
        np.testing.assert_allclose(same["uv"], S["uv"], atol=1e-9)

    def test_distortion_presets(self):
        call = self.start("distortion")
        for name in ("barrel", "pincushion", "tangential", "wide-angle"):
            S = call("preset", name=name)
            self.assertLess(S["correction_error_px"], 0.01, msg=name)
        self.assertEqual(call("preset", name="none")["corner_shift_px"], 0.0)

    def test_stereo(self):
        call = self.start("stereo")
        exact = call("set", step="exact", noise=0.0, probe_z=5.0)
        self.assertAlmostEqual(exact["probe_reconstructed"][2], 5.0, places=6)
        np.testing.assert_allclose(exact["back_projection"], exact["probe"], atol=1e-9)
        coarse = call("set", step="1 pixel", probe_z=12.0)
        self.assertGreater(coarse["probe_resolution"], 1.0)                   # metres at 12 m with 1-pixel steps
        self.assertGreater(call("set", b=0.4)["curve_d"][0], coarse["curve_d"][0])


if __name__ == "__main__":
    unittest.main()
