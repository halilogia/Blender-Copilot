"""Text to mouth movement (no audio, no bpy): a cheap lip-sync approximation.

Every letter gets a mouth opening between 0 (closed) and 1 (wide open): open vowels open wide, closed vowels less,
consonants nearly closed, spaces and punctuation close the mouth (longer pauses for , . ! ?). The curve is sampled per
frame at a natural speaking speed. Works for English and Turkish text.
"""

from typing import List

CHARS_PER_SECOND = 13.0
VOWELS = {"a": 1.0, "e": 0.6, "i": 0.35, "o": 0.85, "u": 0.55, "ı": 0.4, "ö": 0.7, "ü": 0.5, "â": 1.0, "î": 0.35, "û": 0.55}
CONSONANT = 0.15
PAUSES = {" ": 0.0, ",": 0.0, ".": 0.0, "!": 0.0, "?": 0.0, ";": 0.0, ":": 0.0}
LONG_PAUSE = {",": 3, ".": 5, "!": 5, "?": 5, ";": 3, ":": 3}      # extra silent letters after the mark


def speech_seconds(text: str) -> float:
    """How long the text takes to say at the default speed (at least half a second)."""
    keys = _keys(text)
    return max(0.5, len(keys) / CHARS_PER_SECOND)


def _keys(text: str) -> List[float]:
    keys: List[float] = []
    for ch in str(text or "").lower():
        if ch in VOWELS:
            keys.append(VOWELS[ch])
        elif ch in PAUSES:
            keys.append(0.0)
            keys.extend([0.0] * LONG_PAUSE.get(ch, 0))
        elif ch.isalpha():
            keys.append(CONSONANT)
        # digits and other symbols are skipped
    return keys or [0.0]


def mouth_curve(text: str, frames: int, fps: int) -> List[float]:
    """Mouth opening (0..1) for each of ``frames`` frames; the text is spoken from the first frame, then the mouth rests."""
    if frames < 1 or fps <= 0:
        raise ValueError("frames must be at least 1 and fps positive.")
    keys = _keys(text)
    out: List[float] = []
    for i in range(frames):
        pos = (i / fps) * CHARS_PER_SECOND
        if pos >= len(keys) - 1:
            out.append(0.0 if pos > len(keys) else keys[-1] * max(0.0, len(keys) - pos))
            continue
        lo = int(pos)
        frac = pos - lo
        out.append(keys[lo] * (1.0 - frac) + keys[lo + 1] * frac)
    return out
