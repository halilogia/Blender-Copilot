"""Unit tests for camera move presets (pure math, no Blender)."""

import math
import unittest

from core.camera_paths import MAX_FRAMES, PRESETS, camera_position, camera_samples, frame_count

C = (0.0, 0.0, 1.0)


def dist(a, b):
    return math.dist(a, b)


class TestCameraPaths(unittest.TestCase):
    def test_every_preset_gives_the_requested_number_of_finite_samples(self):
        for name in PRESETS:
            samples = camera_samples(name, 24, C, 1.0)
            self.assertEqual(len(samples), 24, name)
            for pos, aim, focal in samples:
                self.assertTrue(all(math.isfinite(v) for v in (*pos, *aim, focal)), name)
                self.assertGreaterEqual(focal, 10.0)

    def test_unknown_preset_and_short_shot_are_rejected(self):
        with self.assertRaises(ValueError):
            camera_samples("teleport", 24, C, 1.0)
        with self.assertRaises(ValueError):
            camera_samples("static", 1, C, 1.0)

    def test_azimuth_zero_is_in_front_on_the_plus_y_side(self):
        pos = camera_position(C, 5.0, 0.0, 0.0)
        self.assertAlmostEqual(pos[1], 5.0)
        self.assertAlmostEqual(pos[0], 0.0)
        self.assertAlmostEqual(camera_position(C, 5.0, 90.0, 0.0)[0], 5.0)

    def test_static_does_not_move(self):
        s = camera_samples("static", 10, C, 1.0)
        self.assertEqual(s[0], s[-1])

    def test_dolly_in_gets_closer_and_dolly_out_farther(self):
        a = camera_samples("dolly_in", 20, C, 1.0)
        b = camera_samples("dolly_out", 20, C, 1.0)
        self.assertLess(dist(a[-1][0], C), dist(a[0][0], C))
        self.assertGreater(dist(b[-1][0], C), dist(b[0][0], C))

    def test_orbit_keeps_distance_and_turns_by_the_angle(self):
        s = camera_samples("orbit", 30, C, 1.0, angle=180.0, azimuth=0.0)
        radii = [dist(p, C) for p, _, _ in s]
        self.assertAlmostEqual(min(radii), max(radii), places=6)
        self.assertLess(s[-1][0][1], -1.0)          # half way round: now on the -Y side
        self.assertEqual(s[0][1], C)                 # always aims at the subject

    def test_crane_up_rises_and_keeps_aiming_at_the_subject(self):
        s = camera_samples("crane_up", 20, C, 1.0)
        self.assertGreater(s[-1][0][2], s[0][0][2] + 1.0)
        self.assertEqual(s[10][1], C)

    def test_pan_and_tilt_move_the_aim_point_not_the_camera(self):
        for name in ("pan_left", "pan_right", "tilt_up", "tilt_down", "whip_pan"):
            s = camera_samples(name, 20, C, 1.0)
            self.assertEqual(s[0][0], s[-1][0], name)
            self.assertNotEqual(s[0][1], s[-1][1], name)
        up = camera_samples("tilt_up", 20, C, 1.0)
        self.assertGreater(up[-1][1][2], up[0][1][2])

    def test_whip_pan_is_fast_in_the_middle(self):
        s = camera_samples("whip_pan", 41, C, 1.0)
        early = dist(s[0][1], s[8][1])
        mid = dist(s[16][1], s[24][1])
        self.assertGreater(mid, early * 5)

    def test_dolly_zoom_keeps_the_subject_size(self):
        s = camera_samples("dolly_zoom", 20, C, 1.0)
        sizes = [focal / dist(pos, C) for pos, _, focal in s]
        self.assertAlmostEqual(min(sizes), max(sizes), places=4)
        self.assertGreater(s[-1][2], s[0][2])

    def test_crash_zoom_changes_only_the_lens(self):
        s = camera_samples("crash_zoom_in", 24, C, 1.0)
        self.assertEqual(s[0][0], s[-1][0])
        self.assertGreater(s[-1][2], s[0][2] * 2.5)

    def test_handheld_shakes_a_little_and_is_repeatable(self):
        a = camera_samples("handheld", 30, C, 1.0)
        b = camera_samples("handheld", 30, C, 1.0)
        self.assertEqual(a, b)
        offsets = [dist(p, a[0][0]) for p, _, _ in a]
        self.assertGreater(max(offsets), 0.0)
        self.assertLess(max(offsets), 0.2)

    def test_frame_count_is_clamped(self):
        self.assertEqual(frame_count(5, 24), 120)
        self.assertEqual(frame_count(0.01, 24), 2)
        self.assertEqual(frame_count(9999, 60), MAX_FRAMES)


if __name__ == "__main__":
    unittest.main()
