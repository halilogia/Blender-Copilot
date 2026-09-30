"""Procedural background music as a WAV file (pure Python, no bpy, no samples, no downloads).

Six moods built from a few oscillators and noise hits: calm, tense, epic, playful, night and synthwave. It is not a
composer, it is a mood bed that fits a film: chords or a drone, a bass or pulse, a light rhythm, fade in and out.
Deterministic for a given seed. 22.05 kHz, mono, 16 bit.
"""

import math
import random
import struct
import wave
from array import array
from typing import Dict, List

RATE = 22050
MAX_SECONDS = 90.0
MOODS: Dict[str, str] = {
    "calm": "slow warm pads on a gentle chord loop",
    "tense": "low drone, heartbeat pulses and a thin uneasy high note",
    "epic": "driving bass pulse, big chords and drum hits",
    "playful": "bouncy plucked arpeggios and a light beat",
    "night": "deep slow pad with sparse bell notes",
    "synthwave": "pulsing bass arpeggio, bright chords and a steady kick",
}


def _hz(midi: float) -> float:
    return 440.0 * 2.0 ** ((midi - 69.0) / 12.0)


def _add_tone(buf: List[float], start: float, seconds: float, freq: float, amp: float, attack: float, release: float,
              harmonics=((1, 1.0),), decay: float = 0.0) -> None:
    n0 = int(start * RATE)
    n = int(seconds * RATE)
    for i in range(n):
        j = n0 + i
        if j >= len(buf):
            break
        t = i / RATE
        env = min(1.0, t / max(attack, 1e-3))
        left = seconds - t
        if left < release:
            env *= max(0.0, left / release)
        if decay:
            env *= math.exp(-decay * t)
        w = 0.0
        for mult, gain in harmonics:
            w += gain * math.sin(2.0 * math.pi * freq * mult * t)
        buf[j] += amp * env * w


def _add_noise_hit(buf: List[float], start: float, seconds: float, amp: float, rng: random.Random, tone: float = 0.0) -> None:
    n0 = int(start * RATE)
    n = int(seconds * RATE)
    for i in range(n):
        j = n0 + i
        if j >= len(buf):
            break
        env = math.exp(-6.0 * i / max(n, 1))
        s = rng.uniform(-1.0, 1.0)
        if tone:
            s = 0.5 * s + 0.5 * math.sin(2.0 * math.pi * tone * (i / RATE) * (1.0 - 0.6 * i / max(n, 1)))
        buf[j] += amp * env * s


def _chords(name: str):
    # (root midi, minor?) per bar
    return {
        "calm": [(57, True), (53, False), (48, False), (55, False)],          # Am F C G
        "tense": [(45, True), (45, True), (44, False), (45, True)],
        "epic": [(50, True), (46, False), (53, False), (48, False)],           # Dm Bb F C
        "playful": [(60, False), (65, False), (67, False), (60, False)],      # C F G C
        "night": [(52, True), (48, False), (45, True), (47, False)],
        "synthwave": [(57, True), (53, False), (60, False), (55, False)],
    }[name]


def _triad(root: int, minor: bool):
    return [root, root + (3 if minor else 4), root + 7]


def render(mood: str, seconds: float, seed: int = 1) -> array:
    """Return the samples (16 bit signed) of a mood bed that lasts ``seconds``."""
    if mood not in MOODS:
        raise ValueError(f"Unknown mood '{mood}'. Choose one of: {', '.join(MOODS)}.")
    if not (1.0 <= float(seconds) <= MAX_SECONDS):
        raise ValueError(f"seconds must be between 1 and {MAX_SECONDS:.0f}.")
    rng = random.Random(seed)
    total = int(float(seconds) * RATE)
    buf = [0.0] * total
    bpm = {"calm": 70, "tense": 60, "epic": 110, "playful": 120, "night": 60, "synthwave": 100}[mood]
    beat = 60.0 / bpm
    bar = beat * 4
    chords = _chords(mood)
    bars = int(seconds / bar) + 1
    soft = ((1, 1.0), (2, 0.3), (3, 0.1))
    for b in range(bars):
        t0 = b * bar
        root, minor = chords[b % len(chords)]
        notes = _triad(root, minor)
        if mood in ("calm", "night"):
            for note in notes:
                _add_tone(buf, t0, bar + 0.4, _hz(note), 0.11, 0.6, 0.8, soft)
            _add_tone(buf, t0, bar, _hz(root - 12), 0.13, 0.5, 0.6)
            if mood == "night" and b % 2 == 1:
                for k, note in enumerate((notes[2] + 12, notes[1] + 12)):
                    _add_tone(buf, t0 + beat * (1 + 1.7 * k), 2.0, _hz(note), 0.05, 0.005, 1.6, ((1, 1.0), (2.76, 0.4)), decay=1.5)
            if mood == "calm":
                for k in range(8):
                    _add_tone(buf, t0 + k * beat / 2, beat, _hz(notes[k % 3] + 12), 0.035, 0.01, 0.4, ((1, 1.0),), decay=3.0)
        elif mood == "tense":
            _add_tone(buf, t0, bar + 0.3, _hz(root - 12), 0.2, 0.8, 0.5, ((1, 1.0), (1.5, 0.35), (2.02, 0.25)))
            _add_tone(buf, t0, bar, _hz(root + 25 + (b % 2) * 1), 0.03, 1.5, 1.0)
            for k in range(4):
                _add_noise_hit(buf, t0 + k * beat, 0.25, 0.22, rng, tone=55.0)
                _add_noise_hit(buf, t0 + k * beat + 0.18, 0.2, 0.14, rng, tone=48.0)
        elif mood == "epic":
            for note in notes:
                _add_tone(buf, t0, bar + 0.2, _hz(note - 12), 0.09, 0.05, 0.3, ((1, 1.0), (2, 0.5), (3, 0.3)))
            for k in range(8):
                _add_tone(buf, t0 + k * beat / 2, beat / 2, _hz(root - 24), 0.16, 0.005, 0.1, ((1, 1.0), (2, 0.4)))
            for k in range(4):
                _add_noise_hit(buf, t0 + k * beat, 0.3, 0.3 if k % 2 == 0 else 0.16, rng, tone=60.0 if k % 2 == 0 else 0.0)
        elif mood == "playful":
            for k in range(8):
                _add_tone(buf, t0 + k * beat / 2, beat * 0.6, _hz(notes[[0, 1, 2, 1][k % 4]] + 12), 0.09, 0.005, 0.25,
                          ((1, 1.0), (3, 0.2)), decay=4.0)
            _add_tone(buf, t0, beat * 0.9, _hz(root - 12), 0.14, 0.01, 0.2)
            _add_tone(buf, t0 + 2 * beat, beat * 0.9, _hz(root - 5), 0.12, 0.01, 0.2)
            for k in range(4):
                _add_noise_hit(buf, t0 + k * beat + beat / 2, 0.08, 0.07, rng)
        else:  # synthwave
            for k in range(16):
                _add_tone(buf, t0 + k * beat / 4, beat / 4 * 0.9, _hz(root - 12 + [0, 0, 12, 0][k % 4]), 0.12, 0.004, 0.05,
                          ((1, 1.0), (2, 0.5), (3, 0.33), (4, 0.25)))
            for note in notes:
                _add_tone(buf, t0, bar, _hz(note + 12), 0.05, 0.05, 0.5, soft)
            for k in range(4):
                _add_noise_hit(buf, t0 + k * beat, 0.25, 0.28, rng, tone=58.0)
                _add_noise_hit(buf, t0 + k * beat + beat / 2, 0.06, 0.05, rng)
    peak = max((abs(v) for v in buf), default=1.0) or 1.0
    scale = 0.7 * 32767.0 / peak
    fade_in, fade_out = int(0.3 * RATE), int(min(1.5, seconds / 3) * RATE)
    out = array("h")
    for i, v in enumerate(buf):
        g = 1.0
        if i < fade_in:
            g = i / fade_in
        if total - i < fade_out:
            g = min(g, (total - i) / fade_out)
        out.append(int(max(-32767, min(32767, v * scale * g))))
    return out


def write_wav(path: str, mood: str, seconds: float, seed: int = 1) -> Dict[str, object]:
    """Render a mood bed and write it as a 16 bit mono WAV file."""
    samples = render(mood, seconds, seed)
    with wave.open(str(path), "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(RATE)
        f.writeframes(samples.tobytes() if struct.pack("=h", 1) == struct.pack("<h", 1) else _swap(samples))
    return {"mood": mood, "seconds": round(len(samples) / RATE, 2), "rate": RATE, "samples": len(samples)}


def _swap(samples: array) -> bytes:
    swapped = array("h", samples)
    swapped.byteswap()
    return swapped.tobytes()
