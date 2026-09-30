"""Edit an existing mesh with allow-listed operations (no arbitrary Python)."""

from typing import Any
from core.types import RiskLevel, ToolResult
from tools.base import BaseTool


class MeshEditTool(BaseTool):
    """Extrude, inset, bevel, subdivide, taper ... faces picked by their normal direction."""

    name = "mesh_edit"
    description = (
        "Edit a mesh object with one allow-listed operation. Faces are picked by the direction their normal "
        "points in the object's local space: faces = {'direction': '+Z', 'threshold': 0.9} selects the top faces "
        "(directions +X -X +Y -Y +Z -Z or a [x, y, z] vector; threshold is the minimum dot product, default 0.9; "
        "omit faces for all faces). Operations: EXTRUDE_FACES (distance along the average normal, meters), "
        "INSET_FACES (thickness, depth), BEVEL_EDGES (width, segments 1-8, optional sharp_angle in degrees to bevel "
        "only hard edges), SUBDIVIDE (cuts 1-4), TRIANGULATE, RECALC_NORMALS, MERGE_BY_DISTANCE (merge_distance), "
        "SCALE_TO_HEIGHT_TAPER (top_scale: X/Y scale at the top relative to the bottom, e.g. 0.5 for a chimney). "
        "More operations: FLIP_NORMALS and DELETE_FACES (selected faces), DISSOLVE_PLANAR (angle degrees, default 5: "
        "removes edges between nearly flat faces, cleans up after a boolean), LOOP_CUT (axis X/Y/Z, cuts 1-8: evenly spaced "
        "cuts across that local axis, then EXTRUDE or INSET the new faces), KNIFE_PLANE (axis, position in local "
        "coordinates, keep both/above/below: cuts at a plane and, with above or below, removes the other side and caps it), "
        "BRIDGE_FACES (faces and faces_b select two faces, both removed and joined by a tunnel, for example a handle "
        "or a doorway), SEPARATE (by loose or material: splits the mesh into objects) and APPLY_MODIFIERS (bakes bevel, "
        "boolean, mirror ... into the mesh so it can be edited and exported). A selector can also carry material "
        "(name or slot index), min_area, max_area, and near ([x, y, z] with radius, default 0.25) to pick one face among "
        "parallel ones; all given conditions must hold. "
        "Typical use: a crate = CUBE, INSET_FACES on all faces, EXTRUDE_FACES -0.03; a wall = CUBE scaled, BEVEL_EDGES. "
        "One undo step."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "object_name": {"type": "string", "description": "Name of the MESH object to edit."},
            "operation": {
                "type": "string",
                "enum": ["EXTRUDE_FACES", "INSET_FACES", "BEVEL_EDGES", "SUBDIVIDE", "TRIANGULATE",
                         "RECALC_NORMALS", "MERGE_BY_DISTANCE", "SCALE_TO_HEIGHT_TAPER", "FLIP_NORMALS", "DELETE_FACES",
                         "DISSOLVE_PLANAR", "LOOP_CUT", "KNIFE_PLANE", "BRIDGE_FACES", "SEPARATE", "APPLY_MODIFIERS"],
            },
            "faces": {
                "type": "object",
                "description": "Face selector: {'direction': '+Z' or [x, y, z], 'threshold': 0.9, 'material': name or index, 'min_area', 'max_area', 'near': [x, y, z], 'radius'}. Omit for all faces.",
                "properties": {"direction": {"description": "Axis string \"+Z\" (also +X -X +Y -Y -Z) or an [x, y, z] array of three numbers, e.g. [0, 0, 1]."}, "threshold": {"type": "number"},
                               "material": {"description": "Material name or slot index."}, "min_area": {"type": "number"}, "max_area": {"type": "number"},
                               "near": {"description": "[x, y, z] local point: faces whose centre is within radius."}, "radius": {"type": "number"}},
            },
            "faces_b": {
                "type": "object",
                "description": "BRIDGE_FACES: selector of the second face (same fields as faces).",
            },
            "axis": {"type": "string", "enum": ["X", "Y", "Z"], "description": "LOOP_CUT / KNIFE_PLANE: the local axis the cut runs across."},
            "position": {"type": "number", "description": "KNIFE_PLANE: local coordinate of the cutting plane along the axis."},
            "keep": {"type": "string", "enum": ["both", "above", "below"], "description": "KNIFE_PLANE: which side stays (default both); the cut is capped."},
            "angle": {"type": "number", "description": "DISSOLVE_PLANAR: faces flatter than this angle in degrees merge (default 5)."},
            "by": {"type": "string", "enum": ["loose", "material"], "description": "SEPARATE: split by disconnected parts (default) or by material."},
            "distance": {"type": "number", "description": "EXTRUDE_FACES: distance along the normal (negative digs in)."},
            "thickness": {"type": "number", "description": "INSET_FACES: inset width (>0)."},
            "depth": {"type": "number", "description": "INSET_FACES: depth of the inset (negative sinks it)."},
            "width": {"type": "number", "description": "BEVEL_EDGES: bevel width (>0)."},
            "segments": {"type": "integer", "description": "BEVEL_EDGES: segments (1-8)."},
            "sharp_angle": {"type": "number", "description": "BEVEL_EDGES: only edges sharper than this angle in degrees."},
            "cuts": {"type": "integer", "description": "SUBDIVIDE: cuts per edge (1-4); LOOP_CUT: number of cuts (1-8)."},
            "merge_distance": {"type": "number", "description": "MERGE_BY_DISTANCE: merge vertices closer than this."},
            "top_scale": {"type": "number", "description": "SCALE_TO_HEIGHT_TAPER: X/Y scale at the top (bottom stays 1)."},
        },
        "required": ["object_name", "operation"],
        "additionalProperties": False,
    }
    risk_level = RiskLevel.LOW

    def execute(self, adapter: Any, **kwargs) -> ToolResult:
        return adapter.mesh_edit(**kwargs)
