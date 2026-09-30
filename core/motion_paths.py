"""Character motion presets as plain math (no bpy): per frame, a rotation for each body part and a root offset.

Conventions: the character stands on Z=0, faces +Y (its right hand is on the +X side). Parts hang from their pivot:
a leg or arm pointing down along -Z swings FORWARD (toward +Y) with a positive X rotation. An upright part
(torso, head) leans forward with a negative X rotation. ``root`` is (sideways, forward, up) in meters in the
character's own frame; ``animate_character`` turns it into a location for the rig. Rotations are radians.
"""

import math
from typing import Dict, List, Optional, Tuple

ROLES = ("head", "torso", "arm_l", "arm_r", "leg_l", "leg_r")

PRESETS: Dict[str, str] = {
    "idle": "standing, slow breathing and a little sway",
    "walk": "walking forward, legs and arms swing in opposition, body bobs",
    "run": "running forward, longer swing, leaning in",
    "aim": "right arm forward and left arm supporting, as if holding a rifle; breathing",
    "wave": "right arm raised and waving",
    "jump": "a jump: arms swing up, legs tuck, the body rises and lands",
}

MIN_FRAMES = 2
MAX_FRAMES = 480

Rot = Tuple[float, float, float]
Sample = Dict[str, object]


def _zero() -> Dict[str, Rot]:
    return {role: (0.0, 0.0, 0.0) for role in ROLES}


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def motion_samples(preset: str, frames: int, fps: int, height: float, intensity: float = 1.0,
                   distance: Optional[float] = None) -> List[Sample]:
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
    for i in range(frames):
        t = i / fps                     # seconds
        u = i / n                       # 0..1 through the shot
        rot = _zero()
        root = [0.0, 0.0, 0.0]
        if preset == "idle":
            breath = math.sin(2 * math.pi * t / 3.6)
            rot["torso"] = (-0.012 * k * breath, 0.0, 0.03 * k * math.sin(2 * math.pi * t / 7.0))
            rot["head"] = (0.0, 0.0, 0.14 * k * math.sin(2 * math.pi * t / 6.0))
            rot["arm_l"] = (0.05 * k * breath, 0.0, 0.0)
            rot["arm_r"] = (-0.05 * k * breath, 0.0, 0.0)
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
            root[1] = float(distance) * u if distance is not None else stride * h * t / period
        elif preset == "aim":
            breath = math.sin(2 * math.pi * t / 3.6)
            rot["arm_r"] = (1.45 + 0.02 * breath, 0.0, 0.0)
            rot["arm_l"] = (1.25 + 0.02 * breath, 0.0, 0.0)
            rot["leg_l"] = (0.1, 0.0, 0.0)
            rot["leg_r"] = (-0.15, 0.0, 0.0)
            rot["torso"] = (-0.05 + 0.01 * breath, 0.0, 0.0)
            rot["head"] = (0.04, 0.0, 0.05 * k * math.sin(2 * math.pi * t / 5.0))
        elif preset == "wave":
            breath = math.sin(2 * math.pi * t / 3.6)
            rot["arm_r"] = (math.pi * 0.94, 0.5 * k * math.sin(2 * math.pi * 1.6 * t), 0.0)
            rot["arm_l"] = (0.04 * breath, 0.0, 0.0)
            rot["head"] = (0.0, 0.0, 0.12 * k * math.sin(2 * math.pi * t / 3.0))
            rot["torso"] = (-0.01 * breath, 0.0, 0.0)
        elif preset == "jump":
            lift = 4.0 * u * (1.0 - u)            # 0 -> 1 -> 0
            root[2] = 0.5 * h * k * lift
            swing = _lerp(0.0, 2.6, min(1.0, u / 0.4)) if u < 0.4 else _lerp(2.6, 0.2, (u - 0.4) / 0.6)
            rot["arm_l"] = (swing * min(k, 1.0), 0.0, 0.0)
            rot["arm_r"] = (swing * min(k, 1.0), 0.0, 0.0)
            rot["leg_l"] = (0.5 * math.sin(math.pi * u), 0.0, 0.0)
            rot["leg_r"] = (0.5 * math.sin(math.pi * u), 0.0, 0.0)
            rot["torso"] = (-0.15 * math.sin(math.pi * u), 0.0, 0.0)
        out.append({"rot": rot, "root": (root[0], root[1], root[2])})
    return out
