"""Model QA mutator (read only): measure meshes with bmesh and let core.model_qa judge the numbers."""

from typing import Any, Dict, List, Optional

import bmesh
import bpy
from mathutils import Vector

from adapter.mutators.cinema_mutator import _scene_meshes
from adapter.mutators.modeling_mutator import ModelingError, as_list
from core.model_qa import DEFAULT_TRIANGLE_BUDGET, verdict

DOUBLE_DISTANCE = 1e-5
DEGENERATE_AREA = 1e-10


def _uses_image_texture(obj: "bpy.types.Object") -> bool:
    for slot in obj.material_slots:
        tree = getattr(slot.material, "node_tree", None) if slot.material else None
        if tree and any(n.type == "TEX_IMAGE" for n in tree.nodes):
            return True
    return False


def _origin_outside(obj: "bpy.types.Object") -> bool:
    corners = [Vector(c) for c in obj.bound_box]
    for axis in range(3):
        lo, hi = min(c[axis] for c in corners), max(c[axis] for c in corners)
        slack = max(hi - lo, 1e-3) * 0.1
        if not (lo - slack <= 0.0 <= hi + slack):
            return True
    return False


def measure(obj: "bpy.types.Object") -> Dict[str, Any]:
    """Statistics of the mesh as it would export (modifiers applied)."""
    depsgraph = bpy.context.evaluated_depsgraph_get()
    evaluated = obj.evaluated_get(depsgraph)
    mesh = evaluated.to_mesh()
    bm = bmesh.new()
    try:
        bm.from_mesh(mesh)
        bm.edges.ensure_lookup_table()
        nonmanifold = sum(1 for e in bm.edges if len(e.link_faces) > 2 or len(e.link_faces) == 0)
        boundary = sum(1 for e in bm.edges if len(e.link_faces) == 1)
        closed = bool(bm.faces) and nonmanifold == 0 and boundary == 0
        volume = float(bm.calc_volume(signed=True)) if closed else 0.0
        tris = sum(max(len(f.verts) - 2, 0) for f in bm.faces)
        degenerate = sum(1 for f in bm.faces if f.calc_area() < DEGENERATE_AREA)
        doubles = len(bmesh.ops.find_doubles(bm, verts=bm.verts, dist=DOUBLE_DISTANCE)["targetmap"]) if bm.verts else 0
        loose = sum(1 for v in bm.verts if not v.link_edges)
        faces = len(bm.faces)
    finally:
        bm.free()
        evaluated.to_mesh_clear()
    world = [obj.matrix_world @ Vector(c) for c in obj.bound_box]
    return {
        "name": obj.name, "tris": tris, "faces": faces, "nonmanifold_edges": nonmanifold, "boundary_edges": boundary,
        "closed": closed, "signed_volume": volume, "degenerate_faces": degenerate, "duplicate_verts": doubles,
        "loose_verts": loose, "scale": tuple(float(s) for s in obj.scale), "origin_outside": _origin_outside(obj),
        "has_material": any(s.material for s in obj.material_slots), "uses_image_texture": _uses_image_texture(obj),
        "uv_layers": len(obj.data.uv_layers), "z_min": min(p.z for p in world), "z_max": max(p.z for p in world),
        "bbox_min": tuple(min(p[i] for p in world) for i in range(3)), "bbox_max": tuple(max(p[i] for p in world) for i in range(3)),
    }


class ModelQaMutator:
    @classmethod
    def check_model(cls, object_names: Any = None, max_triangles: Any = DEFAULT_TRIANGLE_BUDGET) -> Dict[str, Any]:
        """Measure the named objects (a parent stands for its parts) or every mesh in the scene except helpers."""
        try:
            budget = int(max_triangles)
        except (TypeError, ValueError):
            raise ModelingError("max_triangles must be a whole number between 100 and 1000000.")
        if not (100 <= budget <= 1_000_000):
            raise ModelingError("max_triangles must be between 100 and 1000000.")
        objs = [o for o in _scene_meshes(as_list(object_names) if object_names else None) if o.type == "MESH"]
        if not objs:
            raise ModelingError("There is no mesh to check. Model something first, or name the subject in object_names.")
        stats: List[Dict[str, Any]] = [measure(o) for o in objs]
        result = verdict(stats, budget)
        biggest = sorted(stats, key=lambda s: -s["tris"])[:5]
        result.update({"triangle_budget": budget, "heaviest": [{"name": s["name"], "triangles": s["tris"]} for s in biggest],
                       "checked": [s["name"] for s in stats][:24]})
        return result
