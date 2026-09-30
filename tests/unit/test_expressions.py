"""Unit tests for lip sync and facial expression presets (pure math, no Blender)."""

import unittest

from core.lipsync import CHARS_PER_SECOND, mouth_curve, speech_seconds
from core.motion_paths import FACE_ROLES, PRESETS, ROLES, motion_samples


class TestLipSync(unittest.TestCase):
    def test_values_stay_between_zero_and_one(self):
        for text in ("Merhaba, ben bir asker!", "Hello there. How are you?", "aaa eee", "", "12345", "öüı"):
            curve = mouth_curve(text, 120, 24)
            self.assertEqual(len(curve), 120)
            self.assertTrue(all(0.0 <= v <= 1.0 for v in curve), text)

    def test_open_vowels_open_wider_than_consonants_and_closed_vowels(self):
        a = max(mouth_curve("aaaa", 24, 24))
        i = max(mouth_curve("iiii", 24, 24))
        k = max(mouth_curve("kkkk", 24, 24))
        self.assertGreater(a, i)
        self.assertGreater(i, k)

    def test_pauses_close_the_mouth(self):
        curve = mouth_curve("aa. aa", 60, 24)
        self.assertLess(min(curve[6:12]), 0.05)               # the full stop and the space between the words

    def test_mouth_rests_after_the_text(self):
        curve = mouth_curve("ok", 96, 24)
        self.assertEqual(curve[-1], 0.0)
        self.assertEqual(curve[-20], 0.0)

    def test_speech_seconds_follows_the_length(self):
        self.assertGreater(speech_seconds("a" * 130), 9.5)
        self.assertLess(speech_seconds("a" * 130), 10.5)
        self.assertEqual(speech_seconds(""), 0.5)
        self.assertEqual(CHARS_PER_SECOND, 13.0)

    def test_turkish_letters_are_vowels(self):
        self.assertGreater(max(mouth_curve("ö", 12, 24)), 0.3)
        self.assertGreater(max(mouth_curve("ı", 12, 24)), 0.2)

    def test_bad_arguments(self):
        with self.assertRaises(ValueError):
            mouth_curve("a", 0, 24)
        with self.assertRaises(ValueError):
            mouth_curve("a", 5, 0)


class TestExpressions(unittest.TestCase):
    def test_face_roles_are_known_roles(self):
        self.assertEqual(set(FACE_ROLES), {"eye_l", "eye_r", "mouth"})
        self.assertTrue(set(FACE_ROLES) <= set(ROLES))

    def test_every_preset_gives_face_scales(self):
        for name in PRESETS:
            for f in motion_samples(name, 24, 24, 1.8):
                self.assertEqual(set(f["scale"]), set(FACE_ROLES), name)
                for triple in f["scale"].values():
                    self.assertTrue(all(0.0 < v < 5.0 for v in triple), (name, triple))

    def test_everybody_blinks_now_and_then(self):
        s = motion_samples("idle", 24 * 8, 24, 1.8)
        heights = [f["scale"]["eye_l"][2] for f in s]
        self.assertLess(min(heights), 0.2)                       # a blink closes the eyes
        self.assertEqual(heights[0], 1.0)
        self.assertGreater(sum(1 for v in heights if v > 0.99), len(heights) * 0.8)
        self.assertEqual([f["scale"]["eye_l"] for f in s], [f["scale"]["eye_r"] for f in s])

    def test_talk_moves_the_mouth_with_the_text(self):
        s = motion_samples("talk", 48, 24, 1.8, text="Merhaba, ben bir asker.")
        openings = [f["scale"]["mouth"][2] for f in s]
        self.assertGreater(max(openings), 1.0)
        self.assertLess(min(openings), 0.4)
        # without text the mouth still moves
        free = [f["scale"]["mouth"][2] for f in motion_samples("talk", 48, 24, 1.8)]
        self.assertGreater(max(free) - min(free), 0.5)

    def test_talk_gestures_with_the_right_arm(self):
        s = motion_samples("talk", 48, 24, 1.8)
        self.assertGreater(max(f["rot"]["arm_r"][0] for f in s) - min(f["rot"]["arm_r"][0] for f in s), 0.4)

    def test_happy_squints_and_smiles(self):
        f = motion_samples("happy", 24, 24, 1.8)[10]
        self.assertLess(f["scale"]["eye_l"][2], 0.7)
        self.assertGreater(f["scale"]["mouth"][0], 1.3)
        self.assertGreater(max(g["root"][2] for g in motion_samples("happy", 24, 24, 1.8)), 0.01)

    def test_surprised_opens_eyes_and_mouth_and_steps_back(self):
        s = motion_samples("surprised", 30, 24, 1.8)
        last = s[-1]
        self.assertGreater(last["scale"]["eye_l"][2], 1.3)
        self.assertGreater(last["scale"]["mouth"][2], 1.5)
        self.assertLess(last["root"][1], -0.1)

    def test_angry_narrows_eyes_and_lowers_the_head(self):
        s = motion_samples("angry", 30, 24, 1.8)
        self.assertLess(s[10]["scale"]["eye_r"][2], 0.7)
        self.assertLess(s[10]["rot"]["head"][0], -0.1)
        self.assertGreater(s[10]["rot"]["forearm_l"][0], 1.0)


if __name__ == "__main__":
    unittest.main()
