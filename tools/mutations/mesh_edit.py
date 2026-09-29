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
                         "RECALC_NORMALS", "MERGE_BY_DISTANCE", "SCALE_TO_HEIGHT_TAPER"],
            },
            "faces": {
                "type": "object",
                "description": "Face selector: {'direction': '+Z' or [x, y, z], 'threshold': 0.9}. Omit for all faces.",
                "properties": {"direction": {}, "threshold": {"type": "number"}},
            },
            "distance": {"type": "number", "description": "EXTRUDE_FACES: distance along the normal (negative digs in)."},
            "thickness": {"type": "number", "description": "INSET_FACES: inset width (>0)."},
            "depth": {"type": "number", "description": "INSET_FACES: depth of the inset (negative sinks it)."},
            "width": {"type": "number", "description": "BEVEL_EDGES: bevel width (>0)."},
            "segments": {"type": "integer", "description": "BEVEL_EDGES: segments (1-8)."},
            "sharp_angle": {"type": "number", "description": "BEVEL_EDGES: only edges sharper than this angle in degrees."},
            "cuts": {"type": "integer", "description": "SUBDIVIDE: cuts per edge (1-4)."},
            "merge_distance": {"type": "number", "description": "MERGE_BY_DISTANCE: merge vertices closer than this."},
            "top_scale": {"type": "number", "description": "SCALE_TO_HEIGHT_TAPER: X/Y scale at the top (bottom stays 1)."},
        },
        "required": ["object_name", "operation"],
        "additionalProperties": False,
    }
    risk_level = RiskLevel.LOW

    def execute(self, adapter: Any, **kwargs) -> ToolResult:
        return adapter.mesh_edit(**kwargs)
