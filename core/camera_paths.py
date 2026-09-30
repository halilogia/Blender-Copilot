"""Camera move presets as plain math (no bpy): one (position, aim point, focal length) sample per frame.

Conventions: Z is up, a model faces +Y, so azimuth 0 puts the camera in FRONT of the subject (on the +Y side) and
azimuth 90 on the +X side. Distances are meters. ``camera_move`` keyframes every sample, so the motion is exact and
repeatable, which is what a prompt-driven camera preset needs.
"""

import math
from typing import Dict, List, Optional, Sequence, Tuple

Vec = Tuple[float, float, float]
Sample = Tuple[Vec, Vec, float]

PRESETS: Dict[str, str] = {
    "static": "locked camera",
    "dolly_in": "camera moves toward the subject",
    "dolly_out": "camera moves away from the subject",
    "orbit": "camera circles the subject (angle degrees, default 120)",
    "arc_left": "camera swings 60 degrees to the left around the subject",
    "arc_right": "camera swings 60 degrees to the right around the subject",
    "crane_up": "camera rises while looking at the subject",
    "crane_down": "camera descends while looking at the subject",
    "pan_left": "camera stays, view turns left",
    "pan_right": "camera stays, view turns right",
    "tilt_up": "camera stays, view tilts up",
    "tilt_down": "camera stays, view tilts down",
    "whip_pan": "very fast pan to the right in the middle of the shot",
    "dolly_zoom": "vertigo effect: camera pulls back while the lens zooms in, subject keeps its size",
    "crash_zoom_in": "sudden fast zoom into the subject",
    "handheld": "small hand shake around a framed subject",
}

MIN_FRAMES = 2
MAX_FRAMES = 480


def _ease(t: float) -> float:
    """Smoothstep: slow start, slow end."""
    t = min(1.0, max(0.0, t))
    return t * t * (3.0 - 2.0 * t)


def _mix(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def _add(a: Vec, b: Vec) -> Vec:
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def _scale(a: Vec, s: float) -> Vec:
    return (a[0] * s, a[1] * s, a[2] * s)


def camera_position(center: Vec, distance: float, azimuth_deg: float, elevation_deg: float) -> Vec:
    """Point on a sphere around ``center``: azimuth 0 = +Y side, 90 = +X side; elevation above the horizon."""
    az, el = math.radians(azimuth_deg), math.radians(elevation_deg)
    flat = distance * math.cos(el)
    return (center[0] + flat * math.sin(az), center[1] + flat * math.cos(az), center[2] + distance * math.sin(el))


def frame_count(duration_seconds: float, fps: int) -> int:
    frames = int(round(float(duration_seconds) * int(fps)))
    return max(MIN_FRAMES, min(MAX_FRAMES, frames))


def _noise(t: float, seed: float) -> float:
    """Smooth deterministic wobble in [-1, 1] (sum of sines), for hand shake."""
    return (math.sin(t * 9.1 + seed) * 0.5 + math.sin(t * 17.3 + seed * 1.7) * 0.3 + math.sin(t * 31.7 + seed * 2.3) * 0.2)


def camera_samples(preset: str, frames: int, center: Sequence[float], radius: float,
                   distance: Optional[float] = None, elevation: float = 15.0, azimuth: float = 35.0,
                   angle: float = 120.0, intensity: float = 1.0, focal_length: float = 35.0) -> List[Sample]:
    """Return ``frames`` samples of (camera position, aim point, focal length) for the preset."""
    if preset not in PRESETS:
        raise ValueError(f"Unknown camera preset '{preset}'. Choose one of: {', '.join(sorted(PRESETS))}.")
    if frames < MIN_FRAMES:
        raise ValueError(f"frames must be at least {MIN_FRAMES}.")
    c: Vec = (float(center[0]), float(center[1]), float(center[2]))
    r = max(float(radius), 0.05)
    d = float(distance) if distance else r * 2.8
    if d <= 0:
        raise ValueError("distance must be positive.")
    k = max(0.0, float(intensity))
    f0 = float(focal_length)
    az, el = float(azimuth), float(elevation)
    base = camera_position(c, d, az, el)
    # camera-right and up vectors of the framed shot (right = look x up; the camera looks toward the subject)
    az_r = math.radians(az)
    right: Vec = (-math.cos(az_r), math.sin(az_r), 0.0)
    out: List[Sample] = []
    n = frames - 1
    for i in range(frames):
        t = i / n
        e = _ease(t)
        pos, aim, focal = base, c, f0
        if preset == "static":
            pass
        elif preset in ("dolly_in", "dolly_out"):
            a, b = (1.5, 0.7) if preset == "dolly_in" else (0.7, 1.5)
            pos = camera_position(c, d * _mix(a, b, e), az, el)
        elif preset in ("orbit", "arc_left", "arc_right"):
            sweep = {"orbit": float(angle), "arc_left": 60.0, "arc_right": -60.0}[preset]
            pos = camera_position(c, d, az + sweep * (t if preset == "orbit" else e), el)
        elif preset in ("crane_up", "crane_down"):
            a, b = (-4.0, 55.0) if preset == "crane_up" else (55.0, 4.0)
            pos = camera_position(c, d * 1.1, az, _mix(a, b, e))
        elif preset in ("pan_left", "pan_right"):
            amp = r * 1.2 * k
            s = _mix(-amp, amp, e) * (1 if preset == "pan_right" else -1)
            aim = _add(c, _scale(right, s))
        elif preset in ("tilt_up", "tilt_down"):
            amp = r * 1.0 * k
            s = _mix(-amp, amp, e) * (1 if preset == "tilt_up" else -1)
            aim = (c[0], c[1], c[2] + s)
        elif preset == "whip_pan":
            w = _ease((t - 0.35) / 0.3)          # the sweep happens in the middle 30% of the shot
            aim = _add(c, _scale(right, _mix(-r * 4.0, r * 4.0, w) * max(k, 0.1)))
        elif preset == "dolly_zoom":
            dist = d * _mix(0.8, 2.0, e)
            pos = camera_position(c, dist, az, el)
            focal = f0 * dist / (d * 0.8)         # subject size stays constant: focal length follows distance
        elif preset == "crash_zoom_in":
            focal = _mix(f0 * 0.7, f0 * 2.4, _ease(t / 0.25))
        elif preset == "handheld":
            amp = d * 0.012 * k
            pos = (base[0] + amp * _noise(t * 6.0, 1.0), base[1] + amp * _noise(t * 6.0, 2.0), base[2] + amp * _noise(t * 6.0, 3.0))
            aim = (c[0] + amp * 0.6 * _noise(t * 6.0, 4.0), c[1] + amp * 0.6 * _noise(t * 6.0, 5.0), c[2] + amp * 0.6 * _noise(t * 6.0, 6.0))
        out.append((pos, aim, max(10.0, min(300.0, focal))))
    return out
