"""Procedural material recipes as plain data (no bpy): what a chat model names is turned into a shader network by MaterialMutator.

A recipe is a texture (``noise``, ``wave``, ``brick``) driving a colour ramp (base colour) and a bump (surface relief), plus
the Principled BSDF constants. Textures use object coordinates, so nothing needs UVs; ``scale`` on the tool stretches the pattern.
Colours are linear RGB.
"""

from typing import Any, Dict, List, Tuple

PRESETS: Dict[str, Dict[str, Any]] = {
    "wood": {"about": "planks with grain and rings", "texture": "wave", "scale": (0.9, 0.9, 0.9), "detail": 4.0, "distortion": 4.0,
             "ramp": [(0.0, (0.16, 0.07, 0.025)), (0.55, (0.30, 0.14, 0.055)), (1.0, (0.45, 0.24, 0.10))],
             "roughness": 0.6, "metallic": 0.0, "bump": 0.15},
    "stone": {"about": "rough grey rock", "texture": "noise", "scale": (4.0, 4.0, 4.0), "detail": 12.0, "distortion": 0.3,
              "ramp": [(0.0, (0.10, 0.10, 0.10)), (0.5, (0.25, 0.24, 0.23)), (1.0, (0.42, 0.41, 0.39))],
              "roughness": 0.85, "metallic": 0.0, "bump": 0.6},
    "brick": {"about": "red bricks with mortar", "texture": "brick", "scale": (0.6, 0.6, 0.6), "detail": 0.0, "distortion": 0.0,
              "ramp": [(0.0, (0.30, 0.07, 0.04)), (1.0, (0.45, 0.13, 0.08))], "mortar": (0.55, 0.53, 0.5),
              "roughness": 0.8, "metallic": 0.0, "bump": 0.4},
    "metal": {"about": "brushed steel", "texture": "noise", "scale": (1.5, 80.0, 1.5), "detail": 4.0, "distortion": 0.0,
              "ramp": [(0.0, (0.35, 0.36, 0.38)), (1.0, (0.62, 0.63, 0.65))],
              "roughness": 0.35, "metallic": 1.0, "bump": 0.05},
    "gold": {"about": "polished gold", "texture": "noise", "scale": (2.0, 2.0, 2.0), "detail": 2.0, "distortion": 0.0,
             "ramp": [(0.0, (0.75, 0.52, 0.15)), (1.0, (0.95, 0.72, 0.28))],
             "roughness": 0.2, "metallic": 1.0, "bump": 0.0},
    "grass": {"about": "lawn with light and dark patches", "texture": "noise", "scale": (9.0, 9.0, 9.0), "detail": 8.0, "distortion": 0.2,
              "ramp": [(0.0, (0.025, 0.10, 0.02)), (0.5, (0.10, 0.30, 0.05)), (1.0, (0.30, 0.52, 0.10))],
              "roughness": 0.9, "metallic": 0.0, "bump": 0.3},
    "water": {"about": "smooth blue water with ripples", "texture": "noise", "scale": (6.0, 6.0, 1.5), "detail": 3.0, "distortion": 0.0,
              "ramp": [(0.0, (0.02, 0.15, 0.30)), (1.0, (0.05, 0.30, 0.48))],
              "roughness": 0.04, "metallic": 0.0, "bump": 0.12},
    "sand": {"about": "fine beige sand", "texture": "noise", "scale": (40.0, 40.0, 40.0), "detail": 6.0, "distortion": 0.0,
             "ramp": [(0.0, (0.55, 0.42, 0.25)), (1.0, (0.78, 0.65, 0.42))],
             "roughness": 0.95, "metallic": 0.0, "bump": 0.2},
    "concrete": {"about": "grey concrete", "texture": "noise", "scale": (12.0, 12.0, 12.0), "detail": 10.0, "distortion": 0.0,
                 "ramp": [(0.0, (0.28, 0.28, 0.28)), (1.0, (0.45, 0.45, 0.44))],
                 "roughness": 0.9, "metallic": 0.0, "bump": 0.25},
    "marble": {"about": "white marble with grey veins", "texture": "wave", "scale": (0.5, 0.5, 0.5), "detail": 8.0, "distortion": 9.0,
               "ramp": [(0.0, (0.62, 0.62, 0.64)), (0.35, (0.85, 0.85, 0.86)), (1.0, (0.95, 0.95, 0.95))],
               "roughness": 0.15, "metallic": 0.0, "bump": 0.0},
}


def preset_names() -> List[str]:
    return list(PRESETS)


def recipe(name: Any, scale: Any = 1.0) -> Dict[str, Any]:
    """The recipe for a preset name (case-insensitive) with ``scale`` applied; raises ValueError naming the valid presets."""
    key = str(name or "").strip().lower().replace(" ", "_")
    if key not in PRESETS:
        raise ValueError(f"Unknown material preset '{name}'. Available: {', '.join(PRESETS)}.")
    try:
        factor = float(scale if scale is not None else 1.0)
    except (TypeError, ValueError):
        raise ValueError("scale must be a number (1 = default pattern size, 2 = twice as fine, 0.5 = twice as coarse).")
    if not (0.05 <= factor <= 50.0):
        raise ValueError("scale must be between 0.05 and 50.")
    out = dict(PRESETS[key])
    out["name"] = key
    out["scale"] = tuple(v * factor for v in out["scale"])
    return out


def stops(rec: Dict[str, Any]) -> List[Tuple[float, Tuple[float, float, float]]]:
    return list(rec["ramp"])
