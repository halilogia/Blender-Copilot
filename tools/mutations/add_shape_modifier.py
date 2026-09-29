"""Add a shape-building modifier (MIRROR, ARRAY, SOLIDIFY, DECIMATE, TRIANGULATE) to a mesh object."""

from typing import Any
from core.types import RiskLevel, ToolResult
from tools.base import BaseTool


class AddShapeModifierTool(BaseTool):
    """Non-destructive modifiers that build game props quickly (add_modifier keeps BEVEL, SUBSURF, BOOLEAN)."""

    name = "add_shape_modifier"
    description = (
        "Add a non-destructive shape modifier to a mesh object: MIRROR (axes ['X'], model half a prop, get the "
        "symmetric whole), ARRAY (count 2-64, relative_offset [1, 0, 0] in object widths: fences, stairs, "
        "railings), SOLIDIFY (thickness in meters: turn a plane into a wall or plate), DECIMATE (ratio 0.02-1.0: "
        "cut the triangle count to a budget), TRIANGULATE. The result reports evaluated_triangle_count. "
        "export_gltf applies modifiers by default. One undo step."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Name of the MESH object."},
            "modifier_type": {"type": "string", "enum": ["MIRROR", "ARRAY", "SOLIDIFY", "DECIMATE", "TRIANGULATE"]},
            "axes": {"type": "array", "items": {"type": "string", "enum": ["X", "Y", "Z"]},
                     "description": "MIRROR: axes to mirror over (default ['X'])."},
            "count": {"type": "integer", "description": "ARRAY: number of copies including the original (2-64)."},
            "relative_offset": {"type": "array", "items": {"type": "number"}, "minItems": 3, "maxItems": 3,
                                "description": "ARRAY: offset per copy in object widths, default [1, 0, 0]."},
            "thickness": {"type": "number", "description": "SOLIDIFY: thickness in meters (non-zero)."},
            "ratio": {"type": "number", "description": "DECIMATE: fraction of triangles to keep (0.02-1.0)."},
            "modifier_name": {"type": "string", "description": "Optional name in the modifier stack."},
        },
        "required": ["name", "modifier_type"],
        "additionalProperties": False,
    }
    risk_level = RiskLevel.LOW

    def execute(self, adapter: Any, **kwargs) -> ToolResult:
        return adapter.add_shape_modifier(**kwargs)
