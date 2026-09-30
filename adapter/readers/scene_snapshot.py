"""Scene snapshot: a small dict describing the scene by meaning (see core.scene_diff). Read only."""

from typing import Any, Dict, List

import bpy


def _round(values) -> List[float]:
    return [round(float(v), 4) for v in values]


def _object_entry(obj: "bpy.types.Object") -> Dict[str, Any]:
    entry: Dict[str, Any] = {
        "type": obj.type,
        "location": _round(obj.location),
        "rotation": _round(obj.rotation_euler),
        "scale": _round(obj.scale),
        "parent": obj.parent.name if obj.parent else None,
        "hidden": bool(obj.hide_viewport or obj.hide_render),
        "materials": [s.material.name if s.material else None for s in obj.material_slots],
        "modifiers": [m.name for m in obj.modifiers],
        "collections": sorted(c.name for c in obj.users_collection),
        "data": {},
    }
    if obj.type == "MESH" and obj.data is not None:
        entry["data"] = {"vertices": len(obj.data.vertices), "faces": len(obj.data.polygons)}
    elif obj.type == "LIGHT" and obj.data is not None:
        entry["data"] = {"light": obj.data.type, "energy": round(float(obj.data.energy), 3)}
    elif obj.type == "CAMERA" and obj.data is not None:
        entry["data"] = {"lens": round(float(obj.data.lens), 3)}
    if obj.animation_data and obj.animation_data.action:
        entry["data"] = {**entry["data"], "action": obj.animation_data.action.name}
    return entry


def take() -> Dict[str, Any]:
    """Objects of the current scene, all material and collection names, and a few scene settings."""
    scn = bpy.context.scene
    render = scn.render
    return {
        "objects": {o.name: _object_entry(o) for o in scn.objects},
        "materials": sorted(m.name for m in bpy.data.materials),
        "collections": sorted(c.name for c in bpy.data.collections),
        "scene": {
            "camera": scn.camera.name if scn.camera else None,
            "frame_start": scn.frame_start, "frame_end": scn.frame_end,
            "resolution": [render.resolution_x, render.resolution_y],
            "engine": render.engine,
            "world": scn.world.name if scn.world else None,
        },
    }
