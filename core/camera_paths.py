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
    "dolly_left": "camera trucks sideways to the left, keeping its direction",
    "dolly_right": "camera trucks sideways to the right, keeping its direction",
    "super_dolly_in": "long fast push-in from far to very close",
    "super_dolly_out": "long fast pull-out from very close to far",
    "dolly_zoom_out": "reverse vertigo: camera moves in while the lens zooms out, subject keeps its size",
    "rapid_zoom_in": "fast smooth zoom in",
    "rapid_zoom_out": "fast smooth zoom out",
    "crash_zoom_out": "sudden fast zoom out",
    "yoyo_zoom": "the lens zooms in and out twice",
    "jib_up": "camera lifts straight up while looking at the subject",
    "jib_down": "camera drops straight down while looking at the subject",
    "aerial_pullback": "camera starts close and pulls back and up into a high aerial view",
    "fpv_drone": "fast swooping fly-in like an FPV drone",
    "bullet_time": "wide fast-slow-fast arc around the subject at low height (freeze the subject's motion for the classic look)",
    "dutch_angle": "static shot with the horizon tilted",
    "barrel_roll": "the camera rolls a full turn while pushing in",
    "snorricam": "camera locked in front of the subject's upper body, moving with it (follow is on)",
    "hero_cam": "low angle, slow push-in, subject looms",
    "overhead": "top-down view with a slow drift",
    "robo_arm": "precise multi-axis arc: sweeps around, rises and closes in",
    "hyperlapse": "long fast forward flight toward the subject with a little shake",
    "orbit_360": "a full circle around the subject",
    "eyes_in": "push in to an extreme close-up of the face",
    "mouth_in": "push in to the lower face",
    "lazy_susan": "tight half circle at close range, like a turntable",
    "incline": "diagonal move: the camera comes down and in while drifting sideways",
    "road_rush": "low fast tracking run toward the subject with shake, wide lens",
    "glam": "slow low-angle arc, flattering and heroic",
    "spiral_in": "orbit while closing in",
    "spiral_out": "orbit while pulling away",
    "fisheye": "locked camera with an extreme wide lens",
    "telephoto": "locked camera far away with a long lens: compressed depth",
    "rise_reveal": "camera lifts while the view tilts down from the sky to the subject",
    "crane_over": "camera swings up over the subject's head and down the other side",
}

FOLLOW_PRESETS = ("snorricam",)

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
        elif preset in ("dolly_left", "dolly_right"):
            amp = r * 1.5 * k
            s = _mix(-amp, amp, e) * (1 if preset == "dolly_right" else -1)
            pos = _add(base, _scale(right, s))
            aim = _add(c, _scale(right, s))
        elif preset in ("super_dolly_in", "super_dolly_out"):
            a, b = (2.6, 0.4) if preset == "super_dolly_in" else (0.4, 2.6)
            pos = camera_position(c, d * _mix(a, b, e), az, el)
        elif preset == "dolly_zoom_out":
            dist = d * _mix(2.0, 0.8, e)
            pos = camera_position(c, dist, az, el)
            focal = f0 * dist / (d * 2.0)
        elif preset in ("rapid_zoom_in", "rapid_zoom_out"):
            a, b = (f0, f0 * 3.0) if preset == "rapid_zoom_in" else (f0 * 3.0, f0)
            focal = _mix(a, b, _ease(t / 0.5))
        elif preset == "crash_zoom_out":
            focal = _mix(f0 * 2.4, f0 * 0.7, _ease(t / 0.25))
        elif preset == "yoyo_zoom":
            focal = f0 * (1.0 + 1.2 * (0.5 - 0.5 * math.cos(2 * math.pi * 2 * t)))
        elif preset in ("jib_up", "jib_down"):
            amp = r * 1.6 * k
            dz = _mix(-amp, amp, e) * (1 if preset == "jib_up" else -1)
            pos = (base[0], base[1], base[2] + dz)
        elif preset == "aerial_pullback":
            pos = camera_position(c, d * _mix(0.5, 2.6, e), az, _mix(8.0, 55.0, e))
        elif preset == "fpv_drone":
            wob = math.sin(2 * math.pi * 1.5 * t)
            pos = camera_position(c, d * _mix(2.4, 0.8, e), az + _mix(-90.0, 130.0, t), el + 12.0 * wob * k)
            aim = (c[0] + 0.05 * r * wob, c[1], c[2])
        elif preset == "bullet_time":
            pos = camera_position(c, d * 0.9, az - 100.0 + 200.0 * e, 5.0)
        elif preset == "dutch_angle":
            pass
        elif preset == "barrel_roll":
            pos = camera_position(c, d * _mix(1.2, 0.9, e), az, el)
        elif preset == "snorricam":
            aim = (c[0], c[1], c[2] + r * 0.5)
            pos = camera_position(aim, d * 0.35, 0.0, 8.0)
        elif preset == "hero_cam":
            pos = camera_position(c, d * _mix(1.1, 0.8, e), az, _mix(-8.0, -4.0, e))
            aim = (c[0], c[1], c[2] + r * 0.15)
        elif preset == "overhead":
            pos = camera_position(c, d * 1.2, az + _mix(0.0, 40.0, e), 80.0)
        elif preset == "robo_arm":
            pos = camera_position(c, d * _mix(1.3, 0.8, e), az + _mix(-40.0, 110.0, e), _mix(10.0, 45.0, math.sin(math.pi * t)))
        elif preset == "hyperlapse":
            amp = d * 0.006 * k
            pos = camera_position(c, d * _mix(3.0, 0.5, t), az, el)
            pos = (pos[0] + amp * _noise(t * 8.0, 1.0), pos[1] + amp * _noise(t * 8.0, 2.0), pos[2] + amp * _noise(t * 8.0, 3.0))
            focal = min(f0, 24.0)
        elif preset == "orbit_360":
            pos = camera_position(c, d, az + 360.0 * t, el)
        elif preset == "eyes_in":
            aim = (c[0], c[1], c[2] + r * 0.55)
            pos = camera_position(aim, d * _mix(0.9, 0.22, e), az * 0.3, el)
        elif preset == "mouth_in":
            aim = (c[0], c[1], c[2] + r * 0.45)
            pos = camera_position(aim, d * _mix(0.7, 0.18, e), az * 0.3, el)
        elif preset == "lazy_susan":
            pos = camera_position(c, d * 0.55, az - 100.0 + 200.0 * t, el)
        elif preset == "incline":
            pos = camera_position(c, d * _mix(1.4, 0.7, e), az + _mix(0.0, 40.0, e), _mix(45.0, 8.0, e))
        elif preset == "road_rush":
            amp = d * 0.01 * k
            pos = camera_position(c, d * _mix(2.2, 0.7, t), az + 15.0, 4.0)
            pos = (pos[0] + amp * _noise(t * 10.0, 1.0), pos[1] + amp * _noise(t * 10.0, 2.0), pos[2] + amp * _noise(t * 10.0, 3.0))
            focal = min(f0, 24.0)
        elif preset == "glam":
            pos = camera_position(c, d * 0.85, az + _mix(-25.0, 25.0, e), 6.0)
            aim = (c[0], c[1], c[2] + r * 0.1)
            focal = max(f0, 50.0)
        elif preset in ("spiral_in", "spiral_out"):
            a, b = (1.6, 0.6) if preset == "spiral_in" else (0.6, 1.6)
            pos = camera_position(c, d * _mix(a, b, e), az + 270.0 * t, el)
        elif preset == "fisheye":
            focal = 10.0
        elif preset == "telephoto":
            pos = camera_position(c, d * 2.5, az, el)
            focal = f0 * 2.5
        elif preset == "rise_reveal":
            pos = (base[0], base[1], base[2] + _mix(-1.0, 0.6, e) * r)
            aim = (c[0], c[1], c[2] + _mix(0.9, 0.0, e) * r)
        elif preset == "crane_over":
            pos = camera_position(c, d * 1.1, az + 180.0 * e, 5.0 + 70.0 * math.sin(math.pi * t))
        out.append((pos, aim, max(10.0, min(300.0, focal))))
    return out


def camera_rolls(preset: str, frames: int, intensity: float = 1.0) -> List[float]:
    """Camera roll in degrees for each frame (0 for most presets)."""
    if preset not in PRESETS:
        raise ValueError(f"Unknown camera preset '{preset}'.")
    k = max(0.0, float(intensity))
    n = max(frames - 1, 1)
    if preset == "dutch_angle":
        return [15.0 * k] * frames
    if preset == "barrel_roll":
        return [360.0 * _ease(i / n) for i in range(frames)]
    return [0.0] * frames
