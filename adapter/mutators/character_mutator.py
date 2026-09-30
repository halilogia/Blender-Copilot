"""Character mutators: rig a character built from separate parts and animate it with motion presets.

No armature and no skinning: the character is a hierarchy of the parts the agent modelled (head, torso, arms, legs,
plus accessories such as helmet, boots or gun that follow the part they sit on). ``rig_character`` puts each part's
pivot at its joint and parents everything under an Empty ``<name>_Rig``; ``animate_character`` keyframes rotations of the
parts and the movement of the rig. Blocky low-poly characters need nothing more, and the result exports to glTF with
animations. Motion math lives in ``core.motion_paths``.
"""

import json
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import bpy
from mathutils import Euler, Matrix, Vector

from adapter.mutators.modeling_mutator import ModelingError, as_list, _unique_mesh
from adapter.mutators.undo_manager import push_undo_step
from core.camera_paths import frame_count
from core.motion_paths import PRESETS, ROLES, motion_samples

RIG_SUFFIX = "_Rig"
KEYWORDS = {                       # order matters: "forearm" contains "arm", so lower limbs are tested first
    "forearm": ("forearm", "lowerarm", "lower_arm", "elbow"),
    "shin": ("shin", "calf", "lowerleg", "lower_leg", "knee"),
    "head": ("head", "skull", "face"),
    "torso": ("torso", "chest", "spine", "body", "trunk"),
    "arm": ("arm", "shoulder"),
    "leg": ("leg", "thigh"),
}
LEFT_MARKS = ("left", "_l", "-l", ".l", "l_")
RIGHT_MARKS = ("right", "_r", "-r", ".r", "r_")


def _world_bounds(obj: "bpy.types.Object"):
    pts = [obj.matrix_world @ Vector(c) for c in obj.bound_box]
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    return lo, hi


def _mesh_objects(names: Any, what: str = "object_names") -> List["bpy.types.Object"]:
    names = as_list(names)
    if not isinstance(names, list) or not names:
        raise ModelingError(f"{what} must be a non-empty list of mesh object names.")
    objs = []
    for n in names:
        obj = bpy.data.objects.get(str(n).strip())
        if obj is None:
            raise ModelingError(f"Object '{n}' not found.")
        if obj.type != "MESH":
            raise ModelingError(f"Object '{n}' is a {obj.type}, not a MESH.")
        objs.append(obj)
    return objs


def _side(name: str, center_x: float, mid_x: float) -> str:
    low = name.lower()
    if any(m in low for m in LEFT_MARKS) or low.endswith("l") and low[-2:-1] in ("_", "-", "."):
        return "l"
    if any(m in low for m in RIGHT_MARKS) or low.endswith("r") and low[-2:-1] in ("_", "-", "."):
        return "r"
    # the character faces +Y, so its right side is +X
    return "r" if center_x >= mid_x else "l"


def _detect_roles(objs: Sequence["bpy.types.Object"]) -> Dict[str, "bpy.types.Object"]:
    los_his = {o.name: _world_bounds(o) for o in objs}
    mid_x = sum((lo.x + hi.x) / 2 for lo, hi in los_his.values()) / len(objs)
    roles: Dict[str, "bpy.types.Object"] = {}
    for obj in objs:
        low = obj.name.lower()
        lo, hi = los_his[obj.name]
        cx = (lo.x + hi.x) / 2
        for kind, words in KEYWORDS.items():
            if any(w in low for w in words):
                role = kind if kind in ("head", "torso") else f"{kind}_{_side(obj.name, cx, mid_x)}"
                # a taller/larger piece wins when two objects claim one role
                if role not in roles or (hi - lo).length > (_world_bounds(roles[role])[1] - _world_bounds(roles[role])[0]).length:
                    roles[role] = obj
                break
    return roles


def _set_pivot(obj: "bpy.types.Object", world_point: Vector) -> None:
    """Move the object's origin to a world point without moving its geometry."""
    if obj.parent is not None:
        keep = obj.matrix_world.copy()
        obj.parent = None
        obj.matrix_world = keep
    mesh = _unique_mesh(obj)
    local = obj.matrix_world.inverted() @ world_point
    mesh.transform(Matrix.Translation(-local))
    mesh.update()
    obj.matrix_world.translation = obj.matrix_world @ local
    obj.location = obj.matrix_world.translation
    bpy.context.view_layer.update()


def _parent_keep(child: "bpy.types.Object", parent: "bpy.types.Object") -> None:
    child.parent = parent
    child.matrix_parent_inverse = parent.matrix_world.inverted()


def _clear_animation(objs: Sequence["bpy.types.Object"]) -> None:
    for obj in objs:
        obj.animation_data_clear()
        obj.rotation_mode = "XYZ"
        obj.rotation_euler = (0.0, 0.0, 0.0)


def _vec(value: Any):
    if isinstance(value, dict) and len(value) == 1:
        value = next(iter(value.values()))
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        raise ModelingError("location must be [x, y, z].")
    try:
        return [float(v) for v in value]
    except (TypeError, ValueError):
        raise ModelingError("location must be numbers.")


class CharacterMutator:
    """Rig and motion operations for characters made of separate parts."""

    @classmethod
    def rig_character(cls, name: str, object_names: Any, parts: Any = None) -> Dict[str, Any]:
        rig_name = f"{str(name or '').strip()}{RIG_SUFFIX}"
        if not str(name or "").strip():
            raise ModelingError("name must be a non-empty character name, for example Soldier.")
        if bpy.data.objects.get(rig_name) is not None:
            raise ModelingError(f"'{rig_name}' already exists; choose another name or delete that rig first.")
        objs = _mesh_objects(object_names)
        if parts is not None:
            if not isinstance(parts, dict):
                raise ModelingError("parts must map a role to an object name, for example {\"torso\": \"Body\"}.")
            roles = {}
            for role, obj_name in parts.items():
                if role not in ROLES:
                    raise ModelingError(f"Unknown role '{role}'. Roles: {', '.join(ROLES)}.")
                obj = bpy.data.objects.get(str(obj_name).strip())
                if obj is None or obj.type != "MESH":
                    raise ModelingError(f"parts['{role}']: '{obj_name}' is not a mesh object in the scene.")
                roles[role] = obj
                if obj not in objs:
                    objs.append(obj)
        else:
            roles = _detect_roles(objs)
        if "torso" not in roles or len(roles) < 3:
            raise ModelingError("Could not find the parts. Name them with head, torso (or body), arm_l/arm_r (or left/right arm) "
                                f"and leg_l/leg_r, or pass parts={{role: object}}. Found: {sorted(roles) or 'nothing'} in {[o.name for o in objs]}.")

        lo = Vector((min(_world_bounds(o)[0].x for o in objs), min(_world_bounds(o)[0].y for o in objs), min(_world_bounds(o)[0].z for o in objs)))
        hi = Vector((max(_world_bounds(o)[1].x for o in objs), max(_world_bounds(o)[1].y for o in objs), max(_world_bounds(o)[1].z for o in objs)))
        height = max(hi.z - lo.z, 0.05)
        role_objs = set(roles.values())
        extras = [o for o in objs if o not in role_objs]

        # pivots first (this changes origins only), measured on the untouched bounds
        pivots: Dict[str, Vector] = {}
        for role, obj in roles.items():
            blo, bhi = _world_bounds(obj)
            cx, cy = (blo.x + bhi.x) / 2, (blo.y + bhi.y) / 2
            pivots[role] = Vector((cx, cy, blo.z if role in ("head", "torso") else bhi.z))
        # extras follow the role part whose centre is closest
        centres = {r: (sum(_world_bounds(o), Vector()) / 2) for r, o in roles.items()}
        attach: Dict[str, str] = {}
        for extra in extras:
            ec = sum(_world_bounds(extra), Vector()) / 2
            best = min(centres, key=lambda r: (centres[r] - ec).length)
            attach[extra.name] = best
        for role, obj in roles.items():
            _set_pivot(obj, pivots[role])

        rig = bpy.data.objects.new(rig_name, None)
        rig.empty_display_type = "PLAIN_AXES"
        rig.empty_display_size = max(height * 0.25, 0.1)
        rig.location = ((lo.x + hi.x) / 2, (lo.y + hi.y) / 2, lo.z)
        bpy.context.scene.collection.objects.link(rig)
        bpy.context.view_layer.update()
        for extra in extras:
            _parent_keep(extra, roles[attach[extra.name]])
        _parent_keep(roles["torso"], rig)
        for role in ("head", "arm_l", "arm_r"):
            if role in roles:
                _parent_keep(roles[role], roles["torso"])
        for role in ("leg_l", "leg_r"):
            if role in roles:
                _parent_keep(roles[role], rig)
        # lower limbs hang from their upper limb (elbow and knee joints); without one they hang from the body
        for lower, upper, fallback in (("forearm_l", "arm_l", "torso"), ("forearm_r", "arm_r", "torso"),
                                       ("shin_l", "leg_l", None), ("shin_r", "leg_r", None)):
            if lower in roles:
                parent = roles.get(upper) or (roles[fallback] if fallback else rig)
                _parent_keep(roles[lower], parent)
        # extras attached to a part that has since been parented keep their world position (parent inverse was taken
        # before, so refresh it now that the parent's own matrix is final)
        bpy.context.view_layer.update()
        for extra in extras:
            keep = extra.matrix_world.copy()
            _parent_keep(extra, roles[attach[extra.name]])
            extra.matrix_world = keep
        rig["character_roles"] = json.dumps({r: o.name for r, o in roles.items()})
        rig["character_height"] = height
        rig["rest_location"] = list(rig.location)
        push_undo_step(f"AI: Rig character {name}")
        return {"rig": rig.name, "roles": {r: o.name for r, o in roles.items()}, "attached": attach,
                "height": round(height, 3), "location": [round(v, 3) for v in rig.location],
                "presets": sorted(PRESETS)}

    @classmethod
    def animate_character(cls, rig: str, preset: str, duration: float = 3.0, fps: int = 24, distance: Any = None,
                          intensity: float = 1.0, heading: float = 0.0) -> Dict[str, Any]:
        key = str(preset or "").strip().lower()
        if key not in PRESETS:
            raise ModelingError(f"preset must be one of {sorted(PRESETS)}.")
        rig_obj = bpy.data.objects.get(str(rig or "").strip())
        if rig_obj is None or "character_roles" not in rig_obj:
            raise ModelingError(f"'{rig}' is not a rig made by rig_character.")
        try:
            seconds, rate, yaw = float(duration), int(fps), math.radians(float(heading))
        except (TypeError, ValueError):
            raise ModelingError("duration, fps and heading must be numbers.")
        if not (0.2 <= seconds <= 60.0):
            raise ModelingError("duration must be between 0.2 and 60 seconds.")
        if not (8 <= rate <= 60):
            raise ModelingError("fps must be between 8 and 60.")
        roles = {r: bpy.data.objects.get(n) for r, n in json.loads(rig_obj["character_roles"]).items()}
        roles = {r: o for r, o in roles.items() if o is not None}
        height = float(rig_obj.get("character_height", 1.8))
        frames = frame_count(seconds, rate)
        samples = motion_samples(key, frames, rate, height, float(intensity), float(distance) if distance is not None else None)

        _clear_animation(list(roles.values()) + [rig_obj])
        start = Vector(rig_obj.get("rest_location", list(rig_obj.location)))
        cos_y, sin_y = math.cos(yaw), math.sin(yaw)
        rig_obj.rotation_euler = (0.0, 0.0, yaw)
        for i, sample in enumerate(samples):
            frame = 1 + i
            dx, dy, dz = sample["root"]
            rig_obj.location = (start.x + dx * cos_y - dy * sin_y, start.y + dx * sin_y + dy * cos_y, start.z + dz)
            rig_obj.keyframe_insert("location", frame=frame)
            rig_obj.keyframe_insert("rotation_euler", frame=frame)
            for role, obj in roles.items():
                obj.rotation_euler = Euler(sample["rot"][role], "XYZ")
                obj.keyframe_insert("rotation_euler", frame=frame)
        scn = bpy.context.scene
        scn.render.fps = rate
        scn.frame_start, scn.frame_end = 1, frames
        scn.frame_set(1)
        last = samples[-1]["root"]
        push_undo_step(f"AI: Animate {rig_obj.name} {key}")
        return {"rig": rig_obj.name, "preset": key, "about": PRESETS[key], "frames": frames, "fps": rate,
                "seconds": round(frames / rate, 2), "frame_range": [1, frames], "animated_parts": sorted(roles),
                "travel_m": round(math.hypot(last[0], last[1]), 3), "heading": float(heading)}

    # ------------------------------------------------------------------ library
    LIBRARY_DIR = "characters"

    @classmethod
    def character_library(cls, export_dir: str, action: str = "list", name: Any = None, rig: Any = None,
                          location: Any = None) -> Dict[str, Any]:
        """Save a rigged character to a .blend in the export folder, list saved ones, or bring one back into the scene.

        The same character can then appear in any later scene or shot with the same look and the same rig.
        """
        import re

        kind = str(action or "list").strip().lower()
        if kind not in ("list", "save", "load"):
            raise ModelingError("action must be list, save or load.")
        folder = Path(export_dir).expanduser() / cls.LIBRARY_DIR
        if kind == "list":
            files = sorted(folder.glob("*.blend")) if folder.exists() else []
            return {"characters": [f.stem for f in files], "folder": str(folder)}
        stem = str(name or "").strip()
        if not re.match(r"^[A-Za-z0-9][A-Za-z0-9_\-]{0,60}$", stem):
            raise ModelingError("name must be a plain name (letters, digits, _ -), no folders.")
        path = folder / f"{stem}.blend"
        if kind == "save":
            rig_obj = bpy.data.objects.get(str(rig or "").strip())
            if rig_obj is None or "character_roles" not in rig_obj:
                raise ModelingError(f"'{rig}' is not a rig made by rig_character.")
            parts = [rig_obj] + list(rig_obj.children_recursive)
            folder.mkdir(parents=True, exist_ok=True)
            bpy.data.libraries.write(str(path), set(parts), fake_user=True)
            return {"saved": stem, "path": str(path), "objects": len(parts), "rig": rig_obj.name,
                    "bytes": path.stat().st_size}
        # load
        if not path.exists():
            have = sorted(f.stem for f in folder.glob("*.blend")) if folder.exists() else []
            raise ModelingError(f"No saved character '{stem}'. Saved: {have or 'none'}.")
        where = Vector((0.0, 0.0, 0.0))
        if location is not None:
            where = Vector(_vec(location))
        with bpy.data.libraries.load(str(path), link=False) as (src, dst):
            original = list(src.objects)
            dst.objects = original
        loaded = [o for o in dst.objects if o is not None]
        mapping = {old: obj.name for old, obj in zip(original, dst.objects) if obj is not None}
        rig_obj = next((o for o in loaded if "character_roles" in o), None)
        if rig_obj is None:
            for obj in loaded:
                bpy.data.objects.remove(obj, do_unlink=True)
            raise ModelingError(f"'{stem}' has no rig inside.")
        for obj in loaded:
            bpy.context.scene.collection.objects.link(obj)
        roles = json.loads(rig_obj["character_roles"])
        rig_obj["character_roles"] = json.dumps({role: mapping.get(n, n) for role, n in roles.items()})
        _clear_animation(loaded)
        rig_obj.location = where
        rig_obj["rest_location"] = list(rig_obj.location)
        bpy.context.view_layer.update()
        push_undo_step(f"AI: Load character {stem}")
        return {"loaded": stem, "rig": rig_obj.name, "roles": json.loads(rig_obj["character_roles"]),
                "objects": len(loaded), "location": [round(v, 3) for v in rig_obj.location],
                "height": round(float(rig_obj.get("character_height", 0.0)), 3)}
