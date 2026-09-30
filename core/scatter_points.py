"""Point sampling and terrain heights as plain math (no bpy), seeded so the same request gives the same world.

``scatter`` places copies of an object by these points (inside an area or along a path, never closer than a minimum
distance, never inside avoided boxes). ``create_terrain`` uses ``height_grid``. Keeping the maths here makes it testable
without Blender and keeps Blender-side code short.
"""

import math
import random
from typing import Any, Dict, List, Optional, Sequence, Tuple

Point = Tuple[float, float]
Rect = Tuple[float, float, float, float]      # xmin, ymin, xmax, ymax

MAX_COUNT = 500


def _inside_rects(x: float, y: float, rects: Sequence[Rect]) -> bool:
    return any(r[0] <= x <= r[2] and r[1] <= y <= r[3] for r in rects)


def _far_enough(x: float, y: float, placed: Sequence[Point], min_distance: float) -> bool:
    limit = min_distance * min_distance
    return all((x - px) ** 2 + (y - py) ** 2 >= limit for px, py in placed)


def area_bounds(area: Dict[str, Any]) -> Rect:
    """Bounding rectangle of {'center': [x, y], 'size': [w, d]} or {'center': [x, y], 'radius': r}."""
    if not isinstance(area, dict):
        raise ValueError("area must be an object such as {\"center\": [0, 0], \"size\": [20, 20]} or {\"center\": [0, 0], \"radius\": 10}.")
    center = area.get("center", [0.0, 0.0])
    try:
        cx, cy = float(center[0]), float(center[1])
        if area.get("radius") is not None:
            r = float(area["radius"])
            if r <= 0:
                raise ValueError("area radius must be positive.")
            return (cx - r, cy - r, cx + r, cy + r)
        size = area.get("size")
        if size is None:
            raise ValueError("area needs size [width, depth] or radius.")
        w, d = float(size[0]), float(size[1])
    except (TypeError, IndexError, KeyError):
        raise ValueError("area center must be [x, y] and size [width, depth].")
    if w <= 0 or d <= 0:
        raise ValueError("area size must be positive.")
    return (cx - w / 2, cy - d / 2, cx + w / 2, cy + d / 2)


def sample_area(area: Dict[str, Any], count: int, min_distance: float, seed: int, avoid: Sequence[Rect] = ()) -> List[Point]:
    """Up to ``count`` random points inside the area with at least ``min_distance`` between them (dart throwing)."""
    x0, y0, x1, y1 = area_bounds(area)
    circle = area.get("radius") is not None
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    radius = (x1 - x0) / 2
    rnd = random.Random(seed)
    placed: List[Point] = []
    for _ in range(max(count, 1) * 60):
        if len(placed) >= count:
            break
        x, y = rnd.uniform(x0, x1), rnd.uniform(y0, y1)
        if circle and (x - cx) ** 2 + (y - cy) ** 2 > radius * radius:
            continue
        if _inside_rects(x, y, avoid) or not _far_enough(x, y, placed, min_distance):
            continue
        placed.append((x, y))
    return placed


def sample_path(points: Sequence[Sequence[float]], count: int, spread: float, min_distance: float, seed: int,
                avoid: Sequence[Rect] = ()) -> List[Point]:
    """Up to ``count`` points spread along a polyline, each pushed sideways by up to ``spread`` meters."""
    try:
        pts = [(float(p[0]), float(p[1])) for p in points]
    except (TypeError, IndexError, ValueError):
        raise ValueError("path must be a list of [x, y] points.")
    if len(pts) < 2:
        raise ValueError("path needs at least two points.")
    lengths = [math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(pts, pts[1:])]
    total = sum(lengths)
    if total <= 1e-9:
        raise ValueError("path points are all the same place.")
    rnd = random.Random(seed)
    placed: List[Point] = []
    for _ in range(max(count, 1) * 60):
        if len(placed) >= count:
            break
        along = rnd.uniform(0.0, total)
        for (a, b), seg in zip(zip(pts, pts[1:]), lengths):
            if along <= seg or seg == lengths[-1]:
                t = along / seg if seg > 1e-9 else 0.0
                x, y = a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t
                nx, ny = (-(b[1] - a[1]) / seg, (b[0] - a[0]) / seg) if seg > 1e-9 else (0.0, 0.0)
                side = rnd.uniform(-spread, spread)
                x, y = x + nx * side, y + ny * side
                break
            along -= seg
        if _inside_rects(x, y, avoid) or not _far_enough(x, y, placed, min_distance):
            continue
        placed.append((x, y))
    return placed


def _hash(ix: int, iy: int, seed: int) -> float:
    n = (ix * 374761393 + iy * 668265263 + seed * 1442695041) & 0xFFFFFFFF
    n = ((n ^ (n >> 13)) * 1274126177) & 0xFFFFFFFF
    return ((n ^ (n >> 16)) & 0xFFFFFF) / float(0xFFFFFF)


def value_noise(x: float, y: float, seed: int) -> float:
    """Smooth value noise in 0..1."""
    ix, iy = math.floor(x), math.floor(y)
    fx, fy = x - ix, y - iy
    sx, sy = fx * fx * (3 - 2 * fx), fy * fy * (3 - 2 * fy)
    a, b = _hash(ix, iy, seed), _hash(ix + 1, iy, seed)
    c, d = _hash(ix, iy + 1, seed), _hash(ix + 1, iy + 1, seed)
    return (a + (b - a) * sx) + ((c + (d - c) * sx) - (a + (b - a) * sx)) * sy


def height_at(x: float, y: float, size: float, height: float, roughness: float, seed: int, flat_radius: float = 0.0) -> float:
    """Terrain height at a point: fractal noise scaled to 0..height, with a flat (height 0) disc around the centre."""
    total, amp, freq, norm = 0.0, 1.0, 3.0 / max(size, 1e-6), 0.0
    for octave in range(4):
        total += value_noise(x * freq, y * freq, seed + octave * 101) * amp
        norm += amp
        amp *= max(min(roughness, 0.95), 0.05)
        freq *= 2.0
    h = (total / norm) * height
    if flat_radius > 0:
        d = math.hypot(x, y)
        edge = flat_radius * 1.6
        if d < flat_radius:
            return 0.0
        if d < edge:
            t = (d - flat_radius) / (edge - flat_radius)
            h *= t * t * (3 - 2 * t)
    return h


def height_grid(size: float, resolution: int, height: float, roughness: float, seed: int, flat_radius: float = 0.0) -> List[List[float]]:
    """(resolution + 1) x (resolution + 1) heights over a square of ``size`` meters centred on the origin."""
    step = size / resolution
    half = size / 2
    return [[height_at(-half + i * step, -half + j * step, size, height, roughness, seed, flat_radius) for i in range(resolution + 1)]
            for j in range(resolution + 1)]


def rect_of_box(lo: Sequence[float], hi: Sequence[float], margin: float = 0.0) -> Rect:
    return (float(lo[0]) - margin, float(lo[1]) - margin, float(hi[0]) + margin, float(hi[1]) + margin)


def min_distance_for(size_x: float, size_y: float, scale_max: float, given: Optional[float]) -> float:
    """Spacing to keep copies apart: the caller's value, else roughly the footprint of the biggest copy."""
    if given is not None:
        return max(float(given), 0.0)
    return max(size_x, size_y) * max(scale_max, 0.1) * 0.9
