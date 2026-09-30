"""Unit tests for the deterministic shot checks (pure Python)."""

import unittest

from core.shot_qa import frame_issues, light_issues, rect_of, verdict


def codes(issues):
    return [i["code"] for i in issues]


def pts(xmin, xmax, ymin, ymax, z=5.0):
    return [(xmin, ymin, z), (xmax, ymin, z), (xmin, ymax, z), (xmax, ymax, z)]


class TestShotQA(unittest.TestCase):
    def test_a_well_framed_subject_has_no_issues(self):
        self.assertEqual(frame_issues(rect_of(pts(0.3, 0.7, 0.15, 0.85))), [])

    def test_cut_off_sides_are_named(self):
        r = frame_issues(rect_of(pts(-0.2, 0.6, 0.2, 1.3)))
        self.assertEqual(codes(r), ["SUBJECT_CUT"])
        self.assertIn("left", r[0]["message"])
        self.assertIn("top", r[0]["message"])
        self.assertIn("distance", r[0]["fix"])

    def test_too_small_and_too_big(self):
        self.assertEqual(codes(frame_issues(rect_of(pts(0.47, 0.53, 0.45, 0.55)))), ["SUBJECT_TOO_SMALL"])
        self.assertEqual(codes(frame_issues(rect_of(pts(0.01, 0.99, 0.02, 0.98)))), ["SUBJECT_TOO_BIG"])

    def test_off_centre_subject(self):
        r = frame_issues(rect_of(pts(0.72, 0.95, 0.4, 0.6)))
        self.assertEqual(codes(r), ["SUBJECT_OFF_CENTER"])
        self.assertIn("right", r[0]["message"])

    def test_behind_the_camera(self):
        self.assertEqual(codes(frame_issues(rect_of([(0.5, 0.5, -3.0), (0.6, 0.5, -3.0)]))), ["SUBJECT_BEHIND_CAMERA"])
        mixed = rect_of(pts(0.3, 0.7, 0.2, 0.8) + [(0.5, 0.5, -1.0)])
        self.assertIn("CAMERA_INSIDE_SUBJECT", codes(frame_issues(mixed)))

    def test_light_checks(self):
        self.assertEqual(light_issues({"mean": 0.4, "white": 0.02, "black": 0.1}), [])
        self.assertEqual(codes(light_issues({"mean": 0.04, "white": 0.0, "black": 0.9})), ["TOO_DARK"])
        self.assertEqual(codes(light_issues({"mean": 0.3, "white": 0.0, "black": 0.7})), ["MOSTLY_BLACK"])
        self.assertEqual(codes(light_issues({"mean": 0.95, "white": 0.9, "black": 0.0})), ["TOO_BRIGHT"])
        self.assertEqual(codes(light_issues({"mean": 0.6, "white": 0.4, "black": 0.0})), ["BLOWN_OUT"])
        for issue in light_issues({"mean": 0.04, "white": 0.0, "black": 0.9}):
            self.assertIn("set_environment", issue["fix"])

    def test_verdict_merges_frames(self):
        frames = [{"frame": 1, "issues": []},
                  {"frame": 12, "issues": [{"code": "SUBJECT_CUT", "message": "cut", "fix": "x"}]},
                  {"frame": 24, "issues": [{"code": "SUBJECT_CUT", "message": "cut", "fix": "x"}, {"code": "TOO_DARK", "message": "dark", "fix": "y"}]}]
        v = verdict(frames)
        self.assertFalse(v["ok"])
        self.assertEqual([i["code"] for i in v["issues"]], ["SUBJECT_CUT", "TOO_DARK"])
        self.assertEqual(v["issues"][0]["frames"], [12, 24])
        self.assertTrue(verdict([{"frame": 1, "issues": []}])["ok"])
        self.assertEqual(verdict([{"frame": 1, "issues": []}])["summary"], "the shot looks fine")


if __name__ == "__main__":
    unittest.main()
