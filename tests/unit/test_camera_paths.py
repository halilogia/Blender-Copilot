"""Unit tests for camera move presets (pure math, no Blender)."""

import math
import unittest

from core.camera_paths import FOLLOW_PRESETS, MAX_FRAMES, PRESETS, camera_position, camera_rolls, camera_samples, frame_count

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

    def test_there_are_at_least_thirty_five_presets(self):
        self.assertGreaterEqual(len(PRESETS), 35)

    def test_dolly_left_and_right_truck_sideways_and_keep_the_direction(self):
        for name in ("dolly_left", "dolly_right"):
            s = camera_samples(name, 20, C, 1.0)
            move_cam = tuple(b - a for a, b in zip(s[0][0], s[-1][0]))
            move_aim = tuple(b - a for a, b in zip(s[0][1], s[-1][1]))
            self.assertGreater(math.hypot(*move_cam), 0.5, name)
            for a, b in zip(move_cam, move_aim):
                self.assertAlmostEqual(a, b, places=9)
        left = camera_samples("dolly_left", 20, C, 1.0)
        right = camera_samples("dolly_right", 20, C, 1.0)
        az = math.radians(35.0)                      # default azimuth: the camera's right vector is (-cos az, sin az, 0)
        rvec = (-math.cos(az), math.sin(az), 0.0)
        along = lambda s_: sum((b - a) * r for a, b, r in zip(s_[0][0], s_[-1][0], rvec))  # noqa: E731
        self.assertGreater(along(right), 0.5)
        self.assertLess(along(left), -0.5)

    def test_super_dolly_covers_more_ground_than_dolly(self):
        a = camera_samples("dolly_in", 20, C, 1.0)
        b = camera_samples("super_dolly_in", 20, C, 1.0)
        self.assertGreater(dist(b[0][0], b[-1][0]), dist(a[0][0], a[-1][0]) * 1.5)

    def test_reverse_dolly_zoom_keeps_the_subject_size(self):
        s = camera_samples("dolly_zoom_out", 20, C, 1.0)
        sizes = [focal / dist(pos, C) for pos, _, focal in s]
        self.assertAlmostEqual(min(sizes), max(sizes), places=4)
        self.assertLess(s[-1][2], s[0][2])

    def test_zoom_variants_change_only_the_lens(self):
        for name in ("rapid_zoom_in", "rapid_zoom_out", "crash_zoom_out", "yoyo_zoom"):
            s = camera_samples(name, 24, C, 1.0)
            self.assertEqual(s[0][0], s[-1][0], name)
            self.assertNotEqual(min(f for _, _, f in s), max(f for _, _, f in s), name)
        self.assertLess(camera_samples("rapid_zoom_out", 20, C, 1.0)[-1][2], camera_samples("rapid_zoom_out", 20, C, 1.0)[0][2])

    def test_jib_moves_straight_up_or_down(self):
        up = camera_samples("jib_up", 20, C, 1.0)
        down = camera_samples("jib_down", 20, C, 1.0)
        self.assertGreater(up[-1][0][2], up[0][0][2] + 1.0)
        self.assertLess(down[-1][0][2], down[0][0][2] - 1.0)
        self.assertAlmostEqual(up[0][0][0], up[-1][0][0], places=9)

    def test_aerial_pullback_rises_and_backs_off(self):
        s = camera_samples("aerial_pullback", 20, C, 1.0)
        self.assertGreater(dist(s[-1][0], C), dist(s[0][0], C) * 3)
        self.assertGreater(s[-1][0][2], s[0][0][2] + 1.0)

    def test_orbit_360_returns_to_the_start_direction(self):
        s = camera_samples("orbit_360", 49, C, 1.0)
        self.assertLess(dist(s[0][0], s[-1][0]), 1e-6)
        self.assertGreater(max(dist(p, s[0][0]) for p, _, _ in s), 2.0)

    def test_hero_cam_looks_up_from_below_the_subject(self):
        s = camera_samples("hero_cam", 10, C, 1.0)
        self.assertLess(s[0][0][2], C[2])

    def test_overhead_is_nearly_straight_down(self):
        pos = camera_samples("overhead", 10, C, 1.0)[5][0]
        self.assertGreater(pos[2] - C[2], 0.95 * dist(pos, C) * 0.98)

    def test_rolls_are_zero_except_for_dutch_and_barrel_roll(self):
        for name in PRESETS:
            rolls = camera_rolls(name, 24, 1.0)
            self.assertEqual(len(rolls), 24)
            if name not in ("dutch_angle", "barrel_roll"):
                self.assertTrue(all(v == 0.0 for v in rolls), name)
        self.assertAlmostEqual(camera_rolls("dutch_angle", 5, 1.0)[2], 15.0)
        barrel = camera_rolls("barrel_roll", 25, 1.0)
        self.assertAlmostEqual(barrel[0], 0.0)
        self.assertAlmostEqual(barrel[-1], 360.0)

    def test_snorricam_is_a_follow_preset_and_sits_close_in_front(self):
        self.assertIn("snorricam", FOLLOW_PRESETS)
        pos, aim, _ = camera_samples("snorricam", 5, C, 1.0)[0]
        self.assertGreater(pos[1], aim[1])
        self.assertLess(dist(pos, aim), 1.5)


if __name__ == "__main__":
    unittest.main()
