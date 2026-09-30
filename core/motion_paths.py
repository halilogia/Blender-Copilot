"""Character motion presets as plain math (no bpy): per frame, a rotation for each body part and a root offset.

Conventions: the character stands on Z=0, faces +Y (its right hand is on the +X side). Parts hang from their pivot:
a leg or arm pointing down along -Z swings FORWARD (toward +Y) with a positive X rotation. An upright part
(torso, head) leans forward with a negative X rotation. ``root`` is (sideways, forward, up) in meters in the
character's own frame; ``animate_character`` turns it into a location for the rig. Rotations are radians.
"""

import math
from typing import Dict, List, Optional, Tuple

from core.lipsync import mouth_curve

# forearm_* and shin_* are optional lower limb parts (elbow and knee joints)
ROLES = ("head", "torso", "arm_l", "arm_r", "leg_l", "leg_r", "forearm_l", "forearm_r", "shin_l", "shin_r",
         "eye_l", "eye_r", "mouth")
FACE_ROLES = ("eye_l", "eye_r", "mouth")      # small parts on the head: they change SCALE (blink, mouth), not rotation

PRESETS: Dict[str, str] = {
    "idle": "standing, slow breathing and a little sway",
    "walk": "walking forward, legs and arms swing in opposition, body bobs",
    "run": "running forward, longer swing, leaning in",
    "aim": "right arm forward and left arm supporting, as if holding a rifle; breathing",
    "wave": "right arm raised and waving",
    "jump": "a jump: arms swing up, legs tuck, the body rises and lands",
    "talk": "talking: the mouth follows the text (lip sync), small nods and hand gestures",
    "happy": "happy: squinting eyes, wide smile, bouncing with raised arms",
    "surprised": "surprised: wide eyes, open mouth, a step back",
    "angry": "angry: narrowed eyes, tight mouth, clenched fists, head down and shaking",
}

MIN_FRAMES = 2
MAX_FRAMES = 480

Rot = Tuple[float, float, float]
Sample = Dict[str, object]


def _zero() -> Dict[str, Rot]:
    return {role: (0.0, 0.0, 0.0) for role in ROLES}


def _ease(x: float) -> float:
    """Smoothstep 0..1."""
    x = min(1.0, max(0.0, x))
    return x * x * (3.0 - 2.0 * x)


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def _blink(t: float) -> float:
    """Eye height factor: 1 open, about 0.1 for the moment of a blink every 3.4 seconds."""
    phase = (t - 1.2) % 3.4
    if phase < 0.16:
        return 1.0 - 0.9 * math.sin(math.pi * phase / 0.16)
    return 1.0


def motion_samples(preset: str, frames: int, fps: int, height: float, intensity: float = 1.0,
                   distance: Optional[float] = None, text: Optional[str] = None) -> List[Sample]:
    """``frames`` samples: {"rot": {role: (rx, ry, rz)}, "root": (sideways, forward, up)}.

    ``distance`` (meters) sets how far walk and run travel over the whole shot; by default the natural speed for the
    character's height is used. ``intensity`` scales swing sizes.
    """
    if preset not in PRESETS:
        raise ValueError(f"Unknown motion preset '{preset}'. Choose one of: {', '.join(sorted(PRESETS))}.")
    if frames < MIN_FRAMES:
        raise ValueError(f"frames must be at least {MIN_FRAMES}.")
    if fps <= 0:
        raise ValueError("fps must be positive.")
    h = max(float(height), 0.05)
    k = max(0.0, float(intensity))
    out: List[Sample] = []
    n = frames - 1
    speech = mouth_curve(text, frames, fps) if (preset == "talk" and text) else None
    for i in range(frames):
        t = i / fps                     # seconds
        u = i / n                       # 0..1 through the shot
        rot = _zero()
        root = [0.0, 0.0, 0.0]
        blink = _blink(t)
        # scale multipliers of the face parts (1 = as modelled); every preset blinks, some change the expression
        face = {"eye_l": (1.0, 1.0, blink), "eye_r": (1.0, 1.0, blink), "mouth": (1.0, 1.0, 1.0)}
        if preset == "idle":
            breath = math.sin(2 * math.pi * t / 3.6)
            rot["torso"] = (-0.012 * k * breath, 0.0, 0.03 * k * math.sin(2 * math.pi * t / 7.0))
            rot["head"] = (0.0, 0.0, 0.14 * k * math.sin(2 * math.pi * t / 6.0))
            rot["arm_l"] = (0.05 * k * breath, 0.0, 0.0)
            rot["arm_r"] = (-0.05 * k * breath, 0.0, 0.0)
            rot["forearm_l"] = (0.12, 0.0, 0.0)
            rot["forearm_r"] = (0.12, 0.0, 0.0)
            root[2] = 0.004 * h * breath
        elif preset in ("walk", "run"):
            period, amp, arm, lean, bob, stride = (1.0, 0.45, 0.8, 0.05, 0.025, 0.78) if preset == "walk" else (0.62, 0.85, 1.05, 0.2, 0.06, 1.9)
            phi = 2 * math.pi * t / period
            a = amp * k
            rot["leg_r"] = (a * math.sin(phi), 0.0, 0.0)
            rot["leg_l"] = (-a * math.sin(phi), 0.0, 0.0)
            rot["arm_r"] = (-arm * a * math.sin(phi), 0.0, 0.0)
            rot["arm_l"] = (arm * a * math.sin(phi), 0.0, 0.0)
            rot["torso"] = (-lean * (1 if preset == "walk" else k), 0.0, 0.08 * k * math.sin(phi))
            rot["head"] = (lean * 0.5, 0.0, -0.05 * k * math.sin(phi))
            root[2] = bob * h * k * (1 - math.cos(2 * phi)) / 2
            # knees bend while a leg swings forward (the shin folds backward); elbows bend as an arm swings forward
            knee = (1.1 if preset == "walk" else 1.6) * a
            rot["shin_r"] = (-knee * max(0.0, math.cos(phi)), 0.0, 0.0)
            rot["shin_l"] = (-knee * max(0.0, -math.cos(phi)), 0.0, 0.0)
            elbow = 0.6 if preset == "walk" else 1.3
            rot["forearm_r"] = (elbow * max(0.0, rot["arm_r"][0]) + (0.15 if preset == "walk" else 0.9), 0.0, 0.0)
            rot["forearm_l"] = (elbow * max(0.0, rot["arm_l"][0]) + (0.15 if preset == "walk" else 0.9), 0.0, 0.0)
            root[1] = float(distance) * u if distance is not None else stride * h * t / period
        elif preset == "aim":
            breath = math.sin(2 * math.pi * t / 3.6)
            rot["arm_r"] = (1.45 + 0.02 * breath, 0.0, 0.0)
            rot["arm_l"] = (1.25 + 0.02 * breath, 0.0, 0.0)
            rot["leg_l"] = (0.1, 0.0, 0.0)
            rot["leg_r"] = (-0.15, 0.0, 0.0)
            rot["torso"] = (-0.05 + 0.01 * breath, 0.0, 0.0)
            rot["head"] = (0.04, 0.0, 0.05 * k * math.sin(2 * math.pi * t / 5.0))
            rot["forearm_r"] = (0.12, 0.0, 0.0)
            rot["forearm_l"] = (0.3, 0.0, 0.0)
        elif preset == "wave":
            breath = math.sin(2 * math.pi * t / 3.6)
            rot["arm_r"] = (math.pi * 0.94, 0.5 * k * math.sin(2 * math.pi * 1.6 * t), 0.0)
            rot["arm_l"] = (0.04 * breath, 0.0, 0.0)
            rot["head"] = (0.0, 0.0, 0.12 * k * math.sin(2 * math.pi * t / 3.0))
            rot["torso"] = (-0.01 * breath, 0.0, 0.0)
            rot["forearm_r"] = (0.0, 0.7 * k * math.sin(2 * math.pi * 1.6 * t + 0.6), 0.0)
            rot["forearm_l"] = (0.12, 0.0, 0.0)
        elif preset == "jump":
            lift = 4.0 * u * (1.0 - u)            # 0 -> 1 -> 0
            root[2] = 0.5 * h * k * lift
            swing = _lerp(0.0, 2.6, min(1.0, u / 0.4)) if u < 0.4 else _lerp(2.6, 0.2, (u - 0.4) / 0.6)
            rot["arm_l"] = (swing * min(k, 1.0), 0.0, 0.0)
            rot["arm_r"] = (swing * min(k, 1.0), 0.0, 0.0)
            rot["leg_l"] = (0.5 * math.sin(math.pi * u), 0.0, 0.0)
            rot["leg_r"] = (0.5 * math.sin(math.pi * u), 0.0, 0.0)
            rot["torso"] = (-0.15 * math.sin(math.pi * u), 0.0, 0.0)
            rot["shin_l"] = (-1.0 * math.sin(math.pi * u), 0.0, 0.0)
            rot["shin_r"] = (-1.0 * math.sin(math.pi * u), 0.0, 0.0)
            rot["forearm_l"] = (0.4 * math.sin(math.pi * u), 0.0, 0.0)
            rot["forearm_r"] = (0.4 * math.sin(math.pi * u), 0.0, 0.0)
        elif preset == "talk":
            if speech is not None:
                opening = speech[i]
            else:                                    # no text: lively syllable rhythm
                opening = max(0.0, math.sin(2 * math.pi * 3.3 * t)) * (0.6 + 0.4 * math.sin(2 * math.pi * 0.7 * t + 1.0))
            face["mouth"] = (1.0, 1.0, 0.2 + 1.3 * opening)
            rot["head"] = (0.04 * math.sin(2 * math.pi * 1.4 * t) * k, 0.0, 0.08 * math.sin(2 * math.pi * 0.6 * t) * k)
            rot["arm_r"] = (0.5 + 0.35 * math.sin(2 * math.pi * 0.9 * t), 0.0, 0.0)
            rot["forearm_r"] = (0.9 + 0.4 * math.sin(2 * math.pi * 1.3 * t + 0.5), 0.0, 0.0)
            rot["arm_l"] = (0.05, 0.0, 0.0)
            rot["forearm_l"] = (0.15, 0.0, 0.0)
            rot["torso"] = (-0.02 + 0.015 * math.sin(2 * math.pi * t / 3.6), 0.0, 0.0)
        elif preset == "happy":
            face["eye_l"] = (1.0, 1.0, 0.55 * blink)
            face["eye_r"] = (1.0, 1.0, 0.55 * blink)
            face["mouth"] = (1.6, 1.0, 0.6)
            root[2] = 0.08 * h * k * abs(math.sin(2 * math.pi * 1.5 * t))
            rot["arm_l"] = (2.2 + 0.3 * math.sin(2 * math.pi * 1.5 * t), 0.0, 0.0)
            rot["arm_r"] = (2.2 - 0.3 * math.sin(2 * math.pi * 1.5 * t), 0.0, 0.0)
            rot["forearm_l"] = (0.3, 0.0, 0.0)
            rot["forearm_r"] = (0.3, 0.0, 0.0)
            rot["torso"] = (0.08, 0.0, 0.0)
            rot["head"] = (0.1, 0.0, 0.06 * math.sin(2 * math.pi * 1.5 * t))
        elif preset == "surprised":
            step = _ease(min(1.0, t / 0.4))
            face["eye_l"] = (1.4, 1.0, 1.4)
            face["eye_r"] = (1.4, 1.0, 1.4)
            face["mouth"] = (0.8, 1.0, 1.8)
            root[1] = -0.15 * h * step
            rot["head"] = (0.12 * step, 0.0, 0.0)
            rot["torso"] = (0.1 * step, 0.0, 0.0)
            rot["arm_l"] = (0.6 * step, 0.0, 0.0)
            rot["arm_r"] = (0.6 * step, 0.0, 0.0)
            rot["forearm_l"] = (0.5 * step, 0.0, 0.0)
            rot["forearm_r"] = (0.5 * step, 0.0, 0.0)
        elif preset == "angry":
            face["eye_l"] = (1.0, 1.0, 0.55 * blink)
            face["eye_r"] = (1.0, 1.0, 0.55 * blink)
            face["mouth"] = (1.2, 1.0, 0.35)
            rot["head"] = (-0.15, 0.0, 0.1 * math.sin(2 * math.pi * 3.0 * t) * k)
            rot["torso"] = (-0.12 + 0.01 * math.sin(2 * math.pi * t / 3.0), 0.0, 0.0)
            rot["forearm_l"] = (1.4, 0.0, 0.0)
            rot["forearm_r"] = (1.4, 0.0, 0.0)
            rot["arm_l"] = (0.2, 0.0, 0.0)
            rot["arm_r"] = (0.2, 0.0, 0.0)
        out.append({"rot": rot, "root": (root[0], root[1], root[2]), "scale": face})
    return out
