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
from core.lipsync import speech_seconds
from core.motion_paths import FACE_ROLES, PRESETS, ROLES, motion_samples

RIG_SUFFIX = "_Rig"
KEYWORDS = {                       # order matters: "forearm" contains "arm", so lower limbs are tested first
    "forearm": ("forearm", "lowerarm", "lower_arm", "elbow"),
    "shin": ("shin", "calf", "lowerleg", "lower_leg", "knee"),
    "eye": ("eye", "pupil"),
    "mouth": ("mouth", "lips", "jaw", "teeth"),
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
        if "brow" in low:                    # eyebrows follow the head like any accessory
            continue
        for kind, words in KEYWORDS.items():
            if any(w in low for w in words):
                role = kind if kind in ("head", "torso", "mouth") else f"{kind}_{_side(obj.name, cx, mid_x)}"
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
            if role in FACE_ROLES:                # eyes and mouth change scale about their own centre
                pivots[role] = Vector((cx, cy, (blo.z + bhi.z) / 2))
            else:
                pivots[role] = Vector((cx, cy, blo.z if role in ("head", "torso") else bhi.z))
        # extras follow the role part whose centre is closest
        centres = {r: (sum(_world_bounds(o), Vector()) / 2) for r, o in roles.items() if r not in FACE_ROLES}
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
        for role in FACE_ROLES:                  # eyes and mouth ride on the head
            if role in roles:
                _parent_keep(roles[role], roles.get("head") or roles["torso"])
        # extras attached to a part that has since been parented keep their world position (parent inverse was taken
        # before, so refresh it now that the parent's own matrix is final)
        bpy.context.view_layer.update()
        for extra in extras:
            keep = extra.matrix_world.copy()
            _parent_keep(extra, roles[attach[extra.name]])
            extra.matrix_world = keep
        rig["character_roles"] = json.dumps({r: o.name for r, o in roles.items()})
        rig["rest_scales"] = json.dumps({r: list(o.scale) for r, o in roles.items()})
        rig["character_height"] = height
        rig["rest_location"] = list(rig.location)
        push_undo_step(f"AI: Rig character {name}")
        return {"rig": rig.name, "roles": {r: o.name for r, o in roles.items()}, "attached": attach,
                "height": round(height, 3), "location": [round(v, 3) for v in rig.location],
                "presets": sorted(PRESETS)}

    @classmethod
    def animate_character(cls, rig: str, preset: str, duration: Any = None, fps: int = 24, distance: Any = None,
                          intensity: float = 1.0, heading: float = 0.0, text: Any = None) -> Dict[str, Any]:
        key = str(preset or "").strip().lower()
        if key not in PRESETS:
            raise ModelingError(f"preset must be one of {sorted(PRESETS)}.")
        rig_obj = bpy.data.objects.get(str(rig or "").strip())
        if rig_obj is None or "character_roles" not in rig_obj:
            raise ModelingError(f"'{rig}' is not a rig made by rig_character.")
        speaking = bool(text) and key == "talk"
        if duration is None:                       # a spoken line lasts as long as it takes to say it
            duration = min(60.0, speech_seconds(str(text)) + 0.6) if speaking else 3.0
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
        samples = motion_samples(key, frames, rate, height, float(intensity), float(distance) if distance is not None else None,
                                 text=str(text) if speaking else None)

        _clear_animation(list(roles.values()) + [rig_obj])
        rest_scales = json.loads(rig_obj.get("rest_scales", "{}"))
        for role, obj in roles.items():
            if role in rest_scales:
                obj.scale = tuple(rest_scales[role])
        start = Vector(rig_obj.get("rest_location", list(rig_obj.location)))
        cls._key_segment(rig_obj, roles, rest_scales, samples, 1, start, yaw)
        scn = bpy.context.scene
        scn.render.fps = rate
        scn.frame_start, scn.frame_end = 1, frames
        scn.frame_set(1)
        last = samples[-1]["root"]
        push_undo_step(f"AI: Animate {rig_obj.name} {key}")
        return {"rig": rig_obj.name, "preset": key, "about": PRESETS[key], "frames": frames, "fps": rate,
                "seconds": round(frames / rate, 2), "frame_range": [1, frames], "animated_parts": sorted(roles),
                "travel_m": round(math.hypot(last[0], last[1]), 3), "heading": float(heading),
                "face": [r for r in FACE_ROLES if r in roles], "lip_sync": speaking}

    @classmethod
    def _key_segment(cls, rig_obj, roles, rest_scales, samples, first: int, start: Vector, yaw: float) -> Vector:
        """Keyframe one motion segment beginning at frame ``first``; returns where the rig stands at its end."""
        cos_y, sin_y = math.cos(yaw), math.sin(yaw)
        rig_obj.rotation_euler = (0.0, 0.0, yaw)
        for i, sample in enumerate(samples):
            frame = first + i
            dx, dy, dz = sample["root"]
            rig_obj.location = (start.x + dx * cos_y - dy * sin_y, start.y + dx * sin_y + dy * cos_y, start.z + dz)
            rig_obj.keyframe_insert("location", frame=frame)
            rig_obj.keyframe_insert("rotation_euler", frame=frame)
            for role, obj in roles.items():
                obj.rotation_euler = Euler(sample["rot"][role], "XYZ")
                obj.keyframe_insert("rotation_euler", frame=frame)
            for role in FACE_ROLES:
                if role in roles:
                    base = rest_scales.get(role, [1.0, 1.0, 1.0])
                    roles[role].scale = tuple(b * m for b, m in zip(base, sample["scale"][role]))
                    roles[role].keyframe_insert("scale", frame=frame)
        last = samples[-1]["root"]
        return Vector((start.x + last[0] * cos_y - last[1] * sin_y, start.y + last[0] * sin_y + last[1] * cos_y, start.z))

    SEGMENT_KEYS = {"preset", "duration", "distance", "intensity", "heading", "text"}
    MAX_SEQUENCE_FRAMES = 1800

    @classmethod
    def animate_sequence(cls, rig: str, segments: Any, fps: int = 24, blend_seconds: float = 0.3) -> Dict[str, Any]:
        """Act a scene: several motions one after another on one timeline (walk, then wave, then talk ...).

        Each segment is {preset, duration?, distance?, intensity?, heading?, text?}. The character moves on from where the
        previous segment ended and keeps its heading unless a segment gives a new one; between segments a short blend lets
        the pose glide instead of jumping.
        """
        segments = as_list(segments)
        if not isinstance(segments, list) or not (1 <= len(segments) <= 12):
            raise ModelingError("segments must be a list of 1 to 12 objects such as {\"preset\": \"walk\", \"duration\": 3}.")
        rig_obj = bpy.data.objects.get(str(rig or "").strip())
        if rig_obj is None or "character_roles" not in rig_obj:
            raise ModelingError(f"'{rig}' is not a rig made by rig_character.")
        try:
            rate, blend = int(fps), float(blend_seconds)
        except (TypeError, ValueError):
            raise ModelingError("fps and blend_seconds must be numbers.")
        if not (8 <= rate <= 60):
            raise ModelingError("fps must be between 8 and 60.")
        if not (0.0 <= blend <= 1.5):
            raise ModelingError("blend_seconds must be between 0 and 1.5.")
        blend_frames = int(round(blend * rate))
        height = float(rig_obj.get("character_height", 1.8))
        plan = []
        heading = 0.0
        for n, seg in enumerate(segments, 1):
            if not isinstance(seg, dict):
                raise ModelingError(f"segment {n} must be an object such as {{\"preset\": \"walk\"}}.")
            extra = set(seg) - cls.SEGMENT_KEYS
            if extra:
                raise ModelingError(f"segment {n}: unknown keys {sorted(extra)}. Allowed: {sorted(cls.SEGMENT_KEYS)}.")
            key = str(seg.get("preset") or "").strip().lower()
            if key not in PRESETS:
                raise ModelingError(f"segment {n}: preset must be one of {sorted(PRESETS)}.")
            text = seg.get("text")
            speaking = bool(text) and key == "talk"
            duration = seg.get("duration")
            if duration is None:
                duration = min(60.0, speech_seconds(str(text)) + 0.6) if speaking else 3.0
            try:
                seconds = float(duration)
                if seg.get("heading") is not None:
                    heading = float(seg["heading"])
                intensity = float(seg.get("intensity", 1.0))
                distance = float(seg["distance"]) if seg.get("distance") is not None else None
            except (TypeError, ValueError):
                raise ModelingError(f"segment {n}: duration, distance, intensity and heading must be numbers.")
            if not (0.2 <= seconds <= 60.0):
                raise ModelingError(f"segment {n}: duration must be between 0.2 and 60 seconds.")
            plan.append((key, frame_count(seconds, rate), heading, intensity, distance, str(text) if speaking else None))
        total = sum(p[1] for p in plan) + blend_frames * (len(plan) - 1)
        if total > cls.MAX_SEQUENCE_FRAMES:
            raise ModelingError(f"The sequence would be {total} frames; the limit is {cls.MAX_SEQUENCE_FRAMES}.")

        roles = {r: bpy.data.objects.get(n) for r, n in json.loads(rig_obj["character_roles"]).items()}
        roles = {r: o for r, o in roles.items() if o is not None}
        _clear_animation(list(roles.values()) + [rig_obj])
        rest_scales = json.loads(rig_obj.get("rest_scales", "{}"))
        for role, obj in roles.items():
            if role in rest_scales:
                obj.scale = tuple(rest_scales[role])
        position = Vector(rig_obj.get("rest_location", list(rig_obj.location)))
        first, timeline = 1, []
        for key, frames, head, intensity, distance, text in plan:
            samples = motion_samples(key, frames, rate, height, intensity, distance, text=text)
            position = cls._key_segment(rig_obj, roles, rest_scales, samples, first, position, math.radians(head))
            timeline.append({"preset": key, "start_frame": first, "end_frame": first + frames - 1, "heading": head})
            first += frames + blend_frames
        end_frame = timeline[-1]["end_frame"]
        scn = bpy.context.scene
        scn.render.fps = rate
        scn.frame_start, scn.frame_end = 1, end_frame
        scn.frame_set(1)
        push_undo_step(f"AI: Animate sequence {rig_obj.name}")
        return {"rig": rig_obj.name, "frames": end_frame, "fps": rate, "seconds": round(end_frame / rate, 2),
                "frame_range": [1, end_frame], "timeline": timeline,
                "end_position": [round(v, 3) for v in position],
                "note": "film a part of it with camera_move start_frame, or all of it with duration equal to seconds"}

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
