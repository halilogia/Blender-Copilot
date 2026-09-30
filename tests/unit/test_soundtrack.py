"""Unit tests for the procedural soundtrack (pure Python)."""

import os
import tempfile
import unittest
import wave

from core.soundtrack import MAX_SECONDS, MOODS, RATE, render, write_wav


def rms(samples):
    return (sum(s * s for s in samples) / len(samples)) ** 0.5


class TestSoundtrack(unittest.TestCase):
    def test_every_mood_renders_audible_bounded_audio(self):
        for mood in MOODS:
            samples = render(mood, 6.0)
            self.assertEqual(len(samples), 6 * RATE, mood)
            peak = max(abs(s) for s in samples)
            self.assertLess(peak, 32768, mood)
            self.assertGreater(peak, 0.5 * 32767, mood)               # normalised, not silent
            self.assertGreater(rms(samples), 1500, mood)              # a bed, not a click

    def test_fades_in_and_out(self):
        s = render("epic", 6.0)
        self.assertLess(abs(s[0]), 50)
        self.assertLess(abs(s[-1]), 50)
        self.assertLess(rms(s[:200]), rms(s[RATE:RATE + 2000]))

    def test_same_seed_same_audio_and_moods_differ(self):
        a, b = render("tense", 4.0, seed=3), render("tense", 4.0, seed=3)
        self.assertEqual(a, b)
        self.assertNotEqual(render("calm", 4.0), render("playful", 4.0))
        self.assertNotEqual(render("tense", 4.0, seed=1), render("tense", 4.0, seed=2))

    def test_bad_arguments(self):
        with self.assertRaises(ValueError):
            render("polka", 5.0)
        with self.assertRaises(ValueError):
            render("calm", 0.2)
        with self.assertRaises(ValueError):
            render("calm", MAX_SECONDS + 1)

    def test_wav_file_is_valid(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "m.wav")
            info = write_wav(path, "night", 5.0)
            with wave.open(path, "rb") as f:
                self.assertEqual((f.getnchannels(), f.getsampwidth(), f.getframerate()), (1, 2, RATE))
                self.assertEqual(f.getnframes(), 5 * RATE)
            self.assertAlmostEqual(info["seconds"], 5.0, places=2)


if __name__ == "__main__":
    unittest.main()
