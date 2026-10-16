"""Character shading layers for set_material as plain data (no bpy): validated here, built into nodes by MaterialMutator.

Each layer adds one look on top of the Principled BSDF instead of replacing it:
``subsurface`` (light glowing through soft material), ``coat`` (a clear glossy varnish), ``thin_film`` (soap-bubble
iridescence, in nanometres), ``gradient_colors`` (base colour running bottom to top over the object's bounds, or along
``gradient_axis``) and ``rim_colors`` (a Fresnel rim: the silhouette glows, first colour at the very edge).
Colours are linear RGB in 0-1.
"""

import math
from typing import Any, Dict, List, Optional, Tuple

LAYER_KEYS = ("subsurface", "coat", "coat_roughness", "thin_film", "gradient_colors", "gradient_axis", "rim_colors", "rim_strength")
# "diagonal" runs from the bottom of the -X side to the top of the +X side
AXES = {"z": (0.0, 0.0, 1.0), "x": (1.0, 0.0, 0.0), "y": (0.0, 1.0, 0.0), "diagonal": (0.5, 0.0, 0.866)}
MAX_STOPS = 4
MAX_RIM_STRENGTH = 20.0
MAX_THIN_FILM = 2000.0


def _unit(value: Any, name: str) -> float:
    try:
        f = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{name} must be a number between 0 and 1.")
    if math.isnan(f) or not (0.0 <= f <= 1.0):
        raise ValueError(f"{name} must be between 0 and 1.")
    return f


def _colors(value: Any, name: str) -> List[Tuple[float, float, float]]:
    if not isinstance(value, (list, tuple)) or not (2 <= len(value) <= MAX_STOPS):
        raise ValueError(f"{name} must be a list of 2 to {MAX_STOPS} colours, each [r, g, b] in 0-1.")
    out = []
    for c in value:
        if not isinstance(c, (list, tuple)) or len(c) not in (3, 4):
            raise ValueError(f"{name}: every colour must be [r, g, b] in 0-1, got {c!r}.")
        out.append(tuple(_unit(v, name) for v in c[:3]))
    return out


def normalize_layers(**kwargs: Any) -> Dict[str, Any]:
    """The given layer arguments, validated; ``{}`` when none is set. Raises ValueError with the allowed range."""
    given = {k: v for k, v in kwargs.items() if k in LAYER_KEYS and v is not None}
    out: Dict[str, Any] = {}
    for key in ("subsurface", "coat", "coat_roughness"):
        if key in given:
            out[key] = _unit(given[key], key)
    if "thin_film" in given:
        try:
            nm = float(given["thin_film"])
        except (TypeError, ValueError):
            raise ValueError(f"thin_film is a thickness in nanometres, 0-{MAX_THIN_FILM:.0f} (300-700 shows colours).")
        if math.isnan(nm) or not (0.0 <= nm <= MAX_THIN_FILM):
            raise ValueError(f"thin_film must be between 0 and {MAX_THIN_FILM:.0f} nanometres.")
        out["thin_film"] = nm
    if "gradient_colors" in given:
        out["gradient_colors"] = _colors(given["gradient_colors"], "gradient_colors")
        axis = str(given.get("gradient_axis") or "z").strip().lower()
        if axis not in AXES:
            raise ValueError(f"gradient_axis must be one of {list(AXES)}.")
        out["gradient_axis"] = axis
    elif "gradient_axis" in given:
        raise ValueError("gradient_axis needs gradient_colors.")
    if "rim_colors" in given:
        out["rim_colors"] = _colors(given["rim_colors"], "rim_colors")
        strength = given.get("rim_strength", 2.0)
        try:
            s = float(strength)
        except (TypeError, ValueError):
            raise ValueError(f"rim_strength must be a number between 0 and {MAX_RIM_STRENGTH:.0f}.")
        if math.isnan(s) or not (0.0 <= s <= MAX_RIM_STRENGTH):
            raise ValueError(f"rim_strength must be between 0 and {MAX_RIM_STRENGTH:.0f}.")
        out["rim_strength"] = s
    elif "rim_strength" in given:
        raise ValueError("rim_strength needs rim_colors.")
    return out


def even_stops(colors: List[Tuple[float, float, float]], start: float = 0.0, end: float = 1.0) -> List[Tuple[float, Tuple[float, float, float]]]:
    """Colour ramp stops spread evenly from ``start`` to ``end``."""
    n = len(colors)
    return [(start + (end - start) * i / (n - 1), c) for i, c in enumerate(colors)]


def axis_vector(axis: Optional[str]) -> Tuple[float, float, float]:
    return AXES[str(axis or "z").lower()]
