"""Prop builders: well-proportioned low-poly props and rig-ready characters from one call (no AI, just geometry).

A chat model that has to build a house from 30 primitives makes proportion mistakes and burns time (or context). Here a
kind such as ``house`` or ``humanoid`` is a small recipe of boxes, cylinders, cones, spheres and prisms placed with proper
proportions, coloured from a palette the caller can override, bevelled and smooth shaded, standing on the ground with its
front toward +Y. Props come back as ONE object (parts joined); humanoids come back as separate parts named for
``rig_character`` (Head, Torso, ArmL, ForearmL, ArmR, ForearmR, LegL, ShinL, LegR, ShinR, EyeL, EyeR, Mouth, ...).
"""

import math
import random
from typing import Any, Dict, List, Optional, Sequence, Tuple

import bmesh
import bpy
from mathutils import Euler, Matrix, Vector

from adapter.mutators.modeling_mutator import ModelingError, ModelingMutator, as_list
from adapter.mutators.polish_mutator import PolishMutator
from adapter.mutators.undo_manager import push_undo_step
from core.prop_kinds import KIND_INFO

Part = Tuple[str, str, Tuple[float, float, float], Tuple[float, float, float], str, Tuple[float, float, float]]


def P(name: str, shape: str, center, size, color: str, rot=(0.0, 0.0, 0.0)) -> Part:
    return (name, shape, tuple(center), tuple(size), color, tuple(rot))


# color key -> (rgb, roughness, metallic, emission strength)
WOOD = ((0.55, 0.36, 0.18), 0.75, 0.0, 0.0)
WOOD_DARK = ((0.33, 0.2, 0.1), 0.8, 0.0, 0.0)
STONE = ((0.55, 0.55, 0.57), 0.9, 0.0, 0.0)
METAL = ((0.45, 0.47, 0.5), 0.35, 0.8, 0.0)
METAL_DARK = ((0.16, 0.17, 0.19), 0.45, 0.7, 0.0)
LEAF = ((0.16, 0.42, 0.18), 0.8, 0.0, 0.0)
GLASS = ((0.55, 0.75, 0.9), 0.15, 0.0, 0.0)
SKIN = ((0.87, 0.62, 0.46), 0.6, 0.0, 0.0)
WATER = ((0.15, 0.4, 0.75), 0.1, 0.0, 0.0)
GLOW = ((1.0, 0.85, 0.5), 0.3, 0.0, 6.0)
CANVAS = ((0.72, 0.68, 0.5), 0.9, 0.0, 0.0)
PLASTER = ((0.85, 0.8, 0.7), 0.9, 0.0, 0.0)
TILE = ((0.62, 0.22, 0.16), 0.8, 0.0, 0.0)
RUBBER = ((0.06, 0.06, 0.07), 0.9, 0.0, 0.0)


def _crate(H, rng):
    t = 0.12 * H
    parts = [P("Body", "box", (0, 0, H / 2), (H * 0.9, H * 0.9, H * 0.94), "wood"), P("Lid", "box", (0, 0, H - 0.03 * H), (1.05 * H, 1.05 * H, 0.06 * H), "wood_dark")]
    for sx in (-1, 1):
        for sy in (-1, 1):
            parts.append(P(f"Post{sx}{sy}", "box", (sx * (H / 2 - t / 2), sy * (H / 2 - t / 2), H / 2), (t, t, H), "wood_dark"))
    return parts, {"wood": WOOD, "wood_dark": WOOD_DARK}


def _barrel(H, rng):
    r = 0.36 * H
    parts = [P("Body", "cyl", (0, 0, H / 2), (2 * r, 2 * r, H), "wood"), P("Belly", "cyl", (0, 0, H / 2), (2.16 * r, 2.16 * r, 0.5 * H), "wood")]
    for z in (0.14, 0.5, 0.86):
        parts.append(P(f"Band{z}", "cyl", (0, 0, z * H), (2.24 * r, 2.24 * r, 0.06 * H), "metal"))
    parts.append(P("Lid", "cyl", (0, 0, H - 0.01 * H), (1.8 * r, 1.8 * r, 0.03 * H), "wood_dark"))
    return parts, {"wood": WOOD, "wood_dark": WOOD_DARK, "metal": METAL_DARK}


def _tree_pine(H, rng):
    parts = [P("Trunk", "cyl", (0, 0, 0.14 * H), (0.1 * H, 0.1 * H, 0.28 * H), "bark")]
    for i, (z, w, h) in enumerate(((0.26, 0.62, 0.34), (0.46, 0.5, 0.3), (0.66, 0.38, 0.26), (0.84, 0.24, 0.2))):
        parts.append(P(f"Tier{i}", "cone", (0, 0, (z + h / 2) * H), (w * H * 0.75, w * H * 0.75, h * H), "leaf"))
    return parts, {"bark": WOOD_DARK, "leaf": LEAF}


def _tree_round(H, rng):
    parts = [P("Trunk", "cyl", (0, 0, 0.22 * H), (0.1 * H, 0.1 * H, 0.44 * H), "bark"),
             P("Crown", "sphere", (0, 0, 0.7 * H), (0.62 * H, 0.62 * H, 0.56 * H), "leaf"),
             P("CrownSide", "sphere", (0.14 * H, 0.06 * H, 0.6 * H), (0.36 * H, 0.36 * H, 0.32 * H), "leaf"),
             P("CrownTop", "sphere", (-0.08 * H, -0.04 * H, 0.86 * H), (0.34 * H, 0.34 * H, 0.3 * H), "leaf")]
    return parts, {"bark": WOOD_DARK, "leaf": ((0.3, 0.55, 0.2), 0.8, 0.0, 0.0)}


def _rock(H, rng):
    parts = []
    for i, (x, y, s) in enumerate(((0, 0, 1.0), (0.55, 0.2, 0.55), (-0.45, 0.35, 0.42))):
        j = lambda: 1.0 + rng.uniform(-0.12, 0.12)  # noqa: E731
        w, d, h = s * H * 0.9 * j(), s * H * 0.8 * j(), s * H * 0.75 * j()
        parts.append(P(f"Rock{i}", "sphere", (x * H * 0.6, y * H * 0.6, h / 2), (w, d, h), "rock", (0, 0, rng.uniform(0, 3))))
    return parts, {"rock": STONE}


def _house(H, rng):
    W, D, wall_h, roof_h = 0.9 * H, 0.66 * H, 0.55 * H, 0.42 * H
    parts = [P("Walls", "box", (0, 0, wall_h / 2), (W, D, wall_h), "wall"),
             P("Roof", "prism", (0, 0, wall_h + roof_h / 2), (W * 1.12, D * 1.16, roof_h), "roof"),
             P("Door", "box", (-0.16 * W, D / 2 + 0.005 * H, 0.16 * H), (0.13 * H, 0.02 * H, 0.32 * H), "door"),
             P("Chimney", "box", (0.28 * W, -0.12 * D, wall_h + roof_h * 0.55), (0.1 * H, 0.1 * H, 0.26 * H), "stone")]
    for i, x in enumerate((0.22 * W, 0.36 * W)):
        parts.append(P(f"Window{i}", "box", (x, D / 2 + 0.005 * H, 0.32 * H), (0.11 * H, 0.02 * H, 0.13 * H), "glass"))
    parts.append(P("WindowSide", "box", (W / 2 + 0.005 * H, 0, 0.32 * H), (0.02 * H, 0.12 * H, 0.13 * H), "glass"))
    return parts, {"wall": PLASTER, "roof": TILE, "door": WOOD_DARK, "stone": STONE, "glass": GLASS}


def _tower(H, rng):
    w = 0.34 * H
    parts = []
    for sx in (-1, 1):
        for sy in (-1, 1):
            parts.append(P(f"Leg{sx}{sy}", "box", (sx * w / 2, sy * w / 2, 0.36 * H), (0.05 * H, 0.05 * H, 0.72 * H), "wood"))
    for z in (0.22, 0.5):
        for sx in (-1, 1):
            parts.append(P(f"BraceX{sx}{z}", "box", (sx * w / 2, 0, z * H), (0.03 * H, w, 0.03 * H), "wood"))
            parts.append(P(f"BraceY{sx}{z}", "box", (0, sx * w / 2, z * H), (w, 0.03 * H, 0.03 * H), "wood"))
    parts.append(P("Floor", "box", (0, 0, 0.73 * H), (w * 1.3, w * 1.3, 0.04 * H), "wood_dark"))
    for sx in (-1, 1):
        parts.append(P(f"RailX{sx}", "box", (sx * w * 0.62, 0, 0.82 * H), (0.025 * H, w * 1.3, 0.05 * H), "wood_dark"))
        parts.append(P(f"RailY{sx}", "box", (0, sx * w * 0.62, 0.82 * H), (w * 1.3, 0.025 * H, 0.05 * H), "wood_dark"))
    parts.append(P("Roof", "prism", (0, 0, 0.93 * H), (w * 1.6, w * 1.6, 0.14 * H), "roof"))
    for i in range(6):
        parts.append(P(f"Rung{i}", "box", (0, w / 2 + 0.03 * H, 0.06 * H + i * 0.11 * H), (0.16 * H, 0.02 * H, 0.02 * H), "wood"))
    return parts, {"wood": WOOD, "wood_dark": WOOD_DARK, "roof": TILE}


def _fence(H, rng):
    length = 3.0 * H
    parts = []
    for i in range(5):
        x = -length / 2 + i * length / 4
        parts.append(P(f"Post{i}", "box", (x, 0, H / 2), (0.1 * H, 0.1 * H, H), "wood"))
    for z in (0.4, 0.75):
        parts.append(P(f"Rail{z}", "box", (0, 0.06 * H, z * H), (length, 0.05 * H, 0.1 * H), "wood_dark"))
    return parts, {"wood": WOOD, "wood_dark": WOOD_DARK}


def _lamp(H, rng):
    parts = [P("Base", "cyl", (0, 0, 0.03 * H), (0.16 * H, 0.16 * H, 0.06 * H), "metal"),
             P("Pole", "cyl", (0, 0, H * 0.48), (0.04 * H, 0.04 * H, H * 0.92), "metal"),
             P("Arm", "box", (0.1 * H, 0, 0.94 * H), (0.22 * H, 0.03 * H, 0.03 * H), "metal"),
             P("Shade", "cone", (0.2 * H, 0, 0.95 * H), (0.18 * H, 0.18 * H, 0.08 * H), "metal"),
             P("Bulb", "sphere", (0.2 * H, 0, 0.9 * H), (0.07 * H, 0.07 * H, 0.07 * H), "glow")]
    return parts, {"metal": METAL_DARK, "glow": GLOW}


def _tent(H, rng):
    parts = [P("Canvas", "prism", (0, 0, H / 2), (1.3 * H, 1.5 * H, H), "canvas"),
             P("Door", "prism", (0, 0.752 * H, 0.3 * H), (0.42 * H, 0.02 * H, 0.6 * H), "dark")]
    for sx in (-1, 1):
        parts.append(P(f"Peg{sx}", "cyl", (sx * 0.66 * H, 0.82 * H, 0.06 * H), (0.03 * H, 0.03 * H, 0.12 * H), "wood"))
    return parts, {"canvas": CANVAS, "dark": METAL_DARK, "wood": WOOD}


def _well(H, rng):
    parts = [P("Ring", "cyl", (0, 0, 0.22 * H), (0.7 * H, 0.7 * H, 0.44 * H), "stone"),
             P("Water", "cyl", (0, 0, 0.4 * H), (0.5 * H, 0.5 * H, 0.03 * H), "water")]
    for sx in (-1, 1):
        parts.append(P(f"Post{sx}", "box", (sx * 0.32 * H, 0, 0.6 * H), (0.05 * H, 0.05 * H, 0.6 * H), "wood"))
    parts += [P("Roof", "prism", (0, 0, 0.94 * H), (0.9 * H, 0.6 * H, 0.22 * H), "roof"),
              P("Beam", "cyl", (0, 0, 0.72 * H), (0.03 * H, 0.03 * H, 0.64 * H), "wood", (0, math.pi / 2, 0)),
              P("Bucket", "cyl", (0, 0, 0.58 * H), (0.12 * H, 0.12 * H, 0.1 * H), "wood_dark")]
    return parts, {"stone": STONE, "water": WATER, "wood": WOOD, "wood_dark": WOOD_DARK, "roof": TILE}


def _car(H, rng):
    L, Wd = 2.6 * H, 1.1 * H
    parts = [P("Body", "box", (0, 0, 0.42 * H), (Wd, L, 0.42 * H), "paint"),
             P("Cabin", "box", (0, -0.1 * L, 0.72 * H), (Wd * 0.9, L * 0.45, 0.36 * H), "glass"),
             P("Roof", "box", (0, -0.1 * L, 0.91 * H), (Wd * 0.94, L * 0.42, 0.04 * H), "paint"),
             P("BumperF", "box", (0, L / 2, 0.3 * H), (Wd * 1.02, 0.06 * H, 0.1 * H), "dark"),
             P("BumperB", "box", (0, -L / 2, 0.3 * H), (Wd * 1.02, 0.06 * H, 0.1 * H), "dark"),
             P("LightL", "box", (-0.35 * Wd, L / 2 + 0.005 * H, 0.5 * H), (0.16 * H, 0.02 * H, 0.08 * H), "glow"),
             P("LightR", "box", (0.35 * Wd, L / 2 + 0.005 * H, 0.5 * H), (0.16 * H, 0.02 * H, 0.08 * H), "glow")]
    for sx in (-1, 1):
        for sy in (-1, 1):
            parts.append(P(f"Wheel{sx}{sy}", "cyl", (sx * Wd * 0.5, sy * L * 0.3, 0.2 * H), (0.4 * H, 0.4 * H, 0.16 * H), "rubber", (0, math.pi / 2, 0)))
    return parts, {"paint": ((0.75, 0.12, 0.1), 0.35, 0.3, 0.0), "glass": GLASS, "dark": METAL_DARK, "glow": GLOW, "rubber": RUBBER}


def _chest(H, rng):
    W = 1.5 * H
    parts = [P("Body", "box", (0, 0, H * 0.3), (W, 0.9 * H, 0.6 * H), "wood"),
             P("Lid", "cyl", (0, 0, 0.6 * H), (0.9 * H, 0.9 * H, W), "wood", (0, math.pi / 2, 0)),
             P("BandL", "box", (-0.32 * W, 0, 0.33 * H), (0.08 * H, 0.94 * H, 0.66 * H), "metal"),
             P("BandR", "box", (0.32 * W, 0, 0.33 * H), (0.08 * H, 0.94 * H, 0.66 * H), "metal"),
             P("Lock", "box", (0, 0.47 * H, 0.55 * H), (0.14 * H, 0.05 * H, 0.16 * H), "gold")]
    return parts, {"wood": WOOD, "metal": METAL_DARK, "gold": ((0.9, 0.7, 0.15), 0.3, 0.9, 0.0)}


def _table(H, rng):
    W = 1.6 * H
    parts = [P("Top", "box", (0, 0, H - 0.04 * H), (W, 0.9 * H, 0.08 * H), "wood")]
    for sx in (-1, 1):
        for sy in (-1, 1):
            parts.append(P(f"Leg{sx}{sy}", "box", (sx * (W / 2 - 0.06 * H), sy * (0.45 * H - 0.06 * H), H * 0.46), (0.09 * H, 0.09 * H, H * 0.92), "wood_dark"))
    return parts, {"wood": WOOD, "wood_dark": WOOD_DARK}


def _chair(H, rng):
    S = 0.5 * H
    parts = [P("Seat", "box", (0, 0, 0.5 * H), (S, S, 0.06 * H), "wood"), P("Back", "box", (0, -S / 2 + 0.03 * H, 0.78 * H), (S, 0.06 * H, 0.5 * H), "wood")]
    for sx in (-1, 1):
        for sy in (-1, 1):
            parts.append(P(f"Leg{sx}{sy}", "box", (sx * (S / 2 - 0.04 * H), sy * (S / 2 - 0.04 * H), 0.24 * H), (0.06 * H, 0.06 * H, 0.48 * H), "wood_dark"))
    return parts, {"wood": WOOD, "wood_dark": WOOD_DARK}


def _campfire(H, rng):
    parts = []
    for i in range(8):
        a = i * math.pi / 4
        parts.append(P(f"Stone{i}", "sphere", (math.cos(a) * 0.5 * H, math.sin(a) * 0.5 * H, 0.09 * H), (0.22 * H, 0.2 * H, 0.16 * H), "stone", (0, 0, a)))
    for i in range(4):
        a = i * math.pi / 2 + 0.4
        parts.append(P(f"Log{i}", "cyl", (math.cos(a) * 0.14 * H, math.sin(a) * 0.14 * H, 0.29 * H), (0.09 * H, 0.09 * H, 0.6 * H), "wood",
                       (math.sin(a) * 0.9, -math.cos(a) * 0.9, 0)))
    parts += [P("Flame", "cone", (0, 0, 0.4 * H), (0.26 * H, 0.26 * H, 0.52 * H), "fire"), P("FlameCore", "cone", (0, 0, 0.34 * H), (0.13 * H, 0.13 * H, 0.36 * H), "core")]
    return parts, {"stone": STONE, "wood": WOOD_DARK, "fire": ((1.0, 0.35, 0.05), 0.4, 0.0, 1.6), "core": ((1.0, 0.75, 0.2), 0.4, 0.0, 2.6)}


def _humanoid_parts(H, style="human"):
    """Standing figure of height H, facing +Y, T-less (arms hang), every joint a part boundary."""
    u = H / 8.0                                   # about eight heads tall
    parts = [
        P("Head", "sphere" if style == "human" else "box", (0, 0, 7.0 * u), (1.0 * u, 1.05 * u, 1.15 * u), "skin"),
        P("Torso", "box", (0, 0, 5.2 * u), (1.9 * u, 1.0 * u, 2.4 * u), "shirt"),
        P("ArmL", "box", (-1.3 * u, 0, 5.9 * u), (0.55 * u, 0.6 * u, 1.05 * u), "shirt"),
        P("ForearmL", "box", (-1.3 * u, 0, 4.85 * u), (0.5 * u, 0.55 * u, 1.05 * u), "skin"),
        P("ArmR", "box", (1.3 * u, 0, 5.9 * u), (0.55 * u, 0.6 * u, 1.05 * u), "shirt"),
        P("ForearmR", "box", (1.3 * u, 0, 4.85 * u), (0.5 * u, 0.55 * u, 1.05 * u), "skin"),
        P("LegL", "box", (-0.5 * u, 0, 3.05 * u), (0.85 * u, 0.9 * u, 1.9 * u), "pants"),
        P("ShinL", "box", (-0.5 * u, 0, 1.2 * u), (0.75 * u, 0.85 * u, 1.75 * u), "pants"),
        P("LegR", "box", (0.5 * u, 0, 3.05 * u), (0.85 * u, 0.9 * u, 1.9 * u), "pants"),
        P("ShinR", "box", (0.5 * u, 0, 1.2 * u), (0.75 * u, 0.85 * u, 1.75 * u), "pants"),
        P("BootL", "box", (-0.5 * u, 0.15 * u, 0.18 * u), (0.8 * u, 1.15 * u, 0.36 * u), "shoes"),
        P("BootR", "box", (0.5 * u, 0.15 * u, 0.18 * u), (0.8 * u, 1.15 * u, 0.36 * u), "shoes"),
        P("EyeL", "box", (-0.22 * u, 0.5 * u, 7.1 * u), (0.16 * u, 0.06 * u, 0.16 * u), "eye"),
        P("EyeR", "box", (0.22 * u, 0.5 * u, 7.1 * u), (0.16 * u, 0.06 * u, 0.16 * u), "eye"),
        P("Mouth", "box", (0, 0.52 * u, 6.7 * u), (0.34 * u, 0.05 * u, 0.09 * u), "mouth"),
    ]
    if style == "human":
        parts.append(P("Hair", "sphere", (0, -0.06 * u, 7.3 * u), (1.08 * u, 1.08 * u, 0.8 * u), "hair"))
    else:
        parts += [P("Antenna", "cyl", (0, 0, 7.85 * u), (0.08 * u, 0.08 * u, 0.5 * u), "metal"),
                  P("AntennaTip", "sphere", (0, 0, 8.15 * u), (0.22 * u, 0.22 * u, 0.22 * u), "glow"),
                  P("Panel", "box", (0, 0.52 * u, 5.4 * u), (1.0 * u, 0.05 * u, 0.9 * u), "glow")]
    return parts


HUMAN_COLORS = {"skin": SKIN, "shirt": ((0.25, 0.4, 0.7), 0.7, 0.0, 0.0), "pants": ((0.18, 0.2, 0.3), 0.8, 0.0, 0.0),
                "shoes": ((0.12, 0.08, 0.06), 0.8, 0.0, 0.0), "eye": ((0.05, 0.05, 0.08), 0.3, 0.0, 0.0),
                "mouth": ((0.35, 0.08, 0.08), 0.5, 0.0, 0.0), "hair": ((0.2, 0.12, 0.06), 0.8, 0.0, 0.0)}
ROBOT_COLORS = {"skin": ((0.75, 0.78, 0.82), 0.4, 0.6, 0.0), "shirt": ((0.3, 0.55, 0.85), 0.4, 0.5, 0.0), "pants": ((0.35, 0.37, 0.42), 0.45, 0.6, 0.0),
                "shoes": ((0.9, 0.55, 0.15), 0.5, 0.3, 0.0), "eye": ((0.5, 0.95, 1.0), 0.2, 0.0, 3.0), "mouth": ((0.15, 0.15, 0.2), 0.5, 0.0, 0.0),
                "metal": METAL, "glow": ((1.0, 0.55, 0.15), 0.3, 0.0, 3.0)}


def _humanoid(H, rng):
    return _humanoid_parts(H, "human"), dict(HUMAN_COLORS)


def _robot(H, rng):
    return _humanoid_parts(H, "robot"), dict(ROBOT_COLORS)


BUILDERS = {"crate": _crate, "barrel": _barrel, "tree_pine": _tree_pine, "tree_round": _tree_round, "rock": _rock, "house": _house,
            "tower": _tower, "fence": _fence, "lamp": _lamp, "tent": _tent, "well": _well, "car": _car, "chest": _chest,
            "table": _table, "chair": _chair, "campfire": _campfire, "humanoid": _humanoid, "robot": _robot}
# kind -> (builder, default height in meters, one line, rigged?)
KINDS: Dict[str, Tuple[Any, float, str, bool]] = {k: (BUILDERS[k], *KIND_INFO[k]) for k in KIND_INFO}


def kind_help() -> str:
    return "; ".join(f"{k} ({v[2]})" for k, v in KINDS.items())


def _shape_mesh(shape: str, size, rot, center, seed_segments: int = 14):
    bm = bmesh.new()
    if shape == "box":
        bmesh.ops.create_cube(bm, size=1.0)
    elif shape == "cyl":
        bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=seed_segments, radius1=0.5, radius2=0.5, depth=1.0)
    elif shape == "cone":
        bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=seed_segments, radius1=0.5, radius2=0.0, depth=1.0)
    elif shape == "sphere":
        bmesh.ops.create_uvsphere(bm, u_segments=10, v_segments=6, radius=0.5)
    elif shape == "prism":                      # triangle profile in X and Z, extruded along Y
        v = [bm.verts.new(c) for c in ((-0.5, -0.5, -0.5), (0.5, -0.5, -0.5), (0.0, -0.5, 0.5),
                                       (-0.5, 0.5, -0.5), (0.5, 0.5, -0.5), (0.0, 0.5, 0.5))]
        bm.faces.new((v[0], v[2], v[1]))
        bm.faces.new((v[3], v[4], v[5]))
        bm.faces.new((v[0], v[1], v[4], v[3]))
        bm.faces.new((v[1], v[2], v[5], v[4]))
        bm.faces.new((v[2], v[0], v[3], v[5]))
        bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    else:
        bm.free()
        raise ModelingError(f"unknown shape {shape}")
    for vert in bm.verts:
        vert.co = Vector((vert.co.x * size[0], vert.co.y * size[1], vert.co.z * size[2]))
    if any(abs(r) > 1e-9 for r in rot):
        rotation = Euler(rot, "XYZ").to_matrix()
        for vert in bm.verts:
            vert.co = rotation @ vert.co
    for vert in bm.verts:
        vert.co += Vector(center)
    return bm


def _material(name: str, spec) -> "bpy.types.Material":
    (rgb, rough, metal, emit) = spec
    mat = bpy.data.materials.get(name)
    if mat is None:
        mat = bpy.data.materials.new(name)
    mat.diffuse_color = (rgb[0], rgb[1], rgb[2], 1.0)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    bsdf = nodes.get("Principled BSDF")
    if bsdf is None:
        for node in list(nodes):
            nodes.remove(node)
        bsdf = nodes.new("ShaderNodeBsdfPrincipled")
        out = nodes.new("ShaderNodeOutputMaterial")
        mat.node_tree.links.new(bsdf.outputs[0], out.inputs[0])
    bsdf.inputs["Base Color"].default_value = (rgb[0], rgb[1], rgb[2], 1.0)
    bsdf.inputs["Roughness"].default_value = rough
    bsdf.inputs["Metallic"].default_value = metal
    try:
        if emit > 0:
            bsdf.inputs["Emission Color"].default_value = (rgb[0], rgb[1], rgb[2], 1.0)
            bsdf.inputs["Emission Strength"].default_value = emit
        else:
            bsdf.inputs["Emission Strength"].default_value = 0.0
    except KeyError:
        pass
    return mat


class _OneUndoStep:
    """Joining and polishing inside create_prop must not leave their own undo steps: one prop, one Ctrl+Z."""

    def __enter__(self):
        import adapter.mutators.modeling_mutator as mm
        import adapter.mutators.polish_mutator as pm
        self.modules = (mm, pm)
        self.saved = [m.push_undo_step for m in self.modules]
        for m in self.modules:
            m.push_undo_step = lambda *a, **k: None
        return self

    def __exit__(self, *exc):
        for m, fn in zip(self.modules, self.saved):
            m.push_undo_step = fn
        return False


class PropMutator:
    """Build a prop or a character from a recipe."""

    @classmethod
    def create_prop(cls, kind: str, name: Any = None, size: Any = None, colors: Any = None, location: Any = None,
                    seed: Any = 1, polish: Any = True) -> Dict[str, Any]:
        key = str(kind or "").strip().lower()
        if key not in KINDS:
            raise ModelingError(f"kind must be one of: {kind_help()}.")
        builder, default_h, about, rigged = KINDS[key]
        try:
            height = float(size) if size is not None else default_h
            rng = random.Random(int(seed))
        except (TypeError, ValueError):
            raise ModelingError("size must be a number of meters and seed a whole number.")
        if not (0.05 <= height <= 200.0):
            raise ModelingError("size must be between 0.05 and 200 meters.")
        where = Vector((0.0, 0.0, 0.0))
        if location is not None:
            location = as_list(location)
            if not isinstance(location, list) or len(location) != 3:
                raise ModelingError("location must be [x, y, z].")
            try:
                where = Vector([float(v) for v in location])
            except (TypeError, ValueError):
                raise ModelingError("location must be numbers.")
        parts, palette = builder(height, rng)
        override = {}
        if colors is not None:
            if isinstance(colors, dict) and len(colors) == 1 and isinstance(next(iter(colors.values())), dict):
                colors = next(iter(colors.values()))
            if not isinstance(colors, dict):
                raise ModelingError(f"colors must map a color name to [r, g, b]; names for {key}: {', '.join(palette)}.")
            for cname, rgb in colors.items():
                if cname not in palette:
                    raise ModelingError(f"'{cname}' is not a color of {key}. Colors: {', '.join(palette)}.")
                rgb = as_list(rgb)
                if not isinstance(rgb, list) or len(rgb) < 3:
                    raise ModelingError(f"color '{cname}' must be [r, g, b] with values 0 to 1.")
                try:
                    triple = tuple(max(0.0, min(1.0, float(v))) for v in rgb[:3])
                except (TypeError, ValueError):
                    raise ModelingError(f"color '{cname}' must be numbers.")
                base = palette[cname]
                override[cname] = (triple, base[1], base[2], base[3])
        palette = {**palette, **override}
        label = str(name).strip() if name else key
        collection = bpy.context.scene.collection
        made: List["bpy.types.Object"] = []
        for pname, shape, center, psize, color, rot in parts:
            bm = _shape_mesh(shape, psize, rot, center)
            mesh = bpy.data.meshes.new(pname)
            bm.to_mesh(mesh)
            bm.free()
            mesh.update()
            obj = bpy.data.objects.new(pname, mesh)
            obj.location = where
            obj.data.materials.append(_material(f"{key}_{color}", palette[color]))
            collection.objects.link(obj)
            made.append(obj)
        names = [o.name for o in made]
        note = None
        if not rigged:
            with _OneUndoStep():
                res = ModelingMutator.join_objects(object_names=names, target_name=names[0], new_name=label)
                final = res["object_name"]
                if polish:
                    try:
                        PolishMutator.polish_model(object_names=[final], bevel_angle=50.0)
                    except ModelingError as err:
                        note = f"not polished: {err}"
            names = [final]
        depsgraph = bpy.context.evaluated_depsgraph_get()
        tris, lo, hi = 0, Vector((1e9, 1e9, 1e9)), Vector((-1e9, -1e9, -1e9))
        for name_ in names:
            o = bpy.data.objects[name_]
            ev = o.evaluated_get(depsgraph)
            mesh = ev.to_mesh()
            mesh.calc_loop_triangles()
            tris += len(mesh.loop_triangles)
            ev.to_mesh_clear()
            for c in o.bound_box:
                w = o.matrix_world @ Vector(c)
                lo = Vector((min(lo.x, w.x), min(lo.y, w.y), min(lo.z, w.z)))
                hi = Vector((max(hi.x, w.x), max(hi.y, w.y), max(hi.z, w.z)))
        if rigged and polish:
            with _OneUndoStep():
                try:
                    PolishMutator.polish_model(object_names=names, bevel_angle=50.0)
                except ModelingError as err:
                    note = f"not polished: {err}"
        push_undo_step(f"AI: Create {key}")
        out = {"kind": key, "about": about, "objects": names, "parts": len(parts), "triangle_count": tris,
               "height_m": round(hi.z - lo.z, 3), "width_m": round(hi.x - lo.x, 3), "depth_m": round(hi.y - lo.y, 3),
               "colors": sorted(palette), "rigged_ready": rigged, "front": "+Y"}
        if rigged:
            out["next"] = "rig_character(name=..., object_names=<these objects>), then animate_character or animate_sequence"
        if note:
            out["note"] = note
        return out
