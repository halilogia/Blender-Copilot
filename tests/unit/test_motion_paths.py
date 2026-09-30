"""Unit tests for character motion presets (pure math, no Blender)."""

import math
import unittest

from core.motion_paths import PRESETS, ROLES, motion_samples


class TestMotionPaths(unittest.TestCase):
    def test_every_preset_gives_finite_samples_for_every_role(self):
        for name in PRESETS:
            samples = motion_samples(name, 30, 24, 1.8)
            self.assertEqual(len(samples), 30, name)
            for s in samples:
                self.assertEqual(set(s["rot"]), set(ROLES), name)
                for rot in s["rot"].values():
                    self.assertTrue(all(math.isfinite(v) for v in rot), name)
                self.assertTrue(all(math.isfinite(v) for v in s["root"]), name)

    def test_bad_arguments_are_rejected(self):
        with self.assertRaises(ValueError):
            motion_samples("moonwalk", 10, 24, 1.8)
        with self.assertRaises(ValueError):
            motion_samples("walk", 1, 24, 1.8)
        with self.assertRaises(ValueError):
            motion_samples("walk", 10, 0, 1.8)

    def test_walk_swings_legs_in_opposition_and_moves_forward(self):
        s = motion_samples("walk", 49, 24, 1.8)
        for f in s:
            self.assertAlmostEqual(f["rot"]["leg_l"][0], -f["rot"]["leg_r"][0], places=9)
            self.assertAlmostEqual(f["rot"]["arm_l"][0], -f["rot"]["arm_r"][0], places=9)
        # arm opposes the leg on its own side
        mid = s[6]
        self.assertLess(mid["rot"]["leg_r"][0] * mid["rot"]["arm_r"][0], 0.0)
        self.assertGreater(s[-1]["root"][1], s[0]["root"][1] + 1.0)
        self.assertGreater(max(f["root"][2] for f in s), 0.0)

    def test_walk_distance_overrides_the_natural_speed(self):
        s = motion_samples("walk", 25, 24, 1.8, distance=5.0)
        self.assertAlmostEqual(s[0]["root"][1], 0.0)
        self.assertAlmostEqual(s[-1]["root"][1], 5.0)

    def test_run_is_faster_and_swings_wider_than_walk(self):
        walk = motion_samples("walk", 49, 24, 1.8)
        run = motion_samples("run", 49, 24, 1.8)
        self.assertGreater(run[-1]["root"][1], walk[-1]["root"][1])
        self.assertGreater(max(abs(f["rot"]["leg_r"][0]) for f in run), max(abs(f["rot"]["leg_r"][0]) for f in walk))

    def test_idle_stays_in_place(self):
        s = motion_samples("idle", 48, 24, 1.8)
        self.assertLess(max(abs(f["root"][1]) for f in s), 1e-9)
        self.assertLess(max(abs(f["rot"]["arm_r"][0]) for f in s), 0.2)

    def test_aim_raises_both_arms_forward(self):
        f = motion_samples("aim", 10, 24, 1.8)[5]
        self.assertGreater(f["rot"]["arm_r"][0], 1.2)
        self.assertGreater(f["rot"]["arm_l"][0], 1.0)

    def test_wave_raises_the_right_arm_and_swings_it(self):
        s = motion_samples("wave", 48, 24, 1.8)
        self.assertGreater(min(f["rot"]["arm_r"][0] for f in s), 2.5)
        swings = [f["rot"]["arm_r"][1] for f in s]
        self.assertGreater(max(swings) - min(swings), 0.5)

    def test_jump_rises_and_comes_back_down(self):
        s = motion_samples("jump", 25, 24, 1.8)
        self.assertAlmostEqual(s[0]["root"][2], 0.0)
        self.assertAlmostEqual(s[-1]["root"][2], 0.0)
        self.assertGreater(max(f["root"][2] for f in s), 0.4)

    def test_intensity_scales_the_swing(self):
        a = max(abs(f["rot"]["leg_r"][0]) for f in motion_samples("walk", 49, 24, 1.8, intensity=1.0))
        b = max(abs(f["rot"]["leg_r"][0]) for f in motion_samples("walk", 49, 24, 1.8, intensity=0.5))
        self.assertAlmostEqual(b, a / 2, places=6)


if __name__ == "__main__":
    unittest.main()
