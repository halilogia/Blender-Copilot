"""Extrude a 2D outline along an axis into a solid (roofs, vehicle bodies, wings, walls) in one call."""

from typing import Any
from core.types import RiskLevel, ToolResult
from tools.base import BaseTool


class CreateExtrusionTool(BaseTool):
    """Creates a closed solid from an outline extruded along X, Y or Z."""

    name = "create_extrusion"
    description = (
        "Create a solid from a 2D outline pushed along an axis: a gable roof, a pickup body, an L-shaped wing, a ramp. "
        "profile is the outline as [u, v] points in order around it (3 to 64 points, convex or not); axis Y puts the "
        "outline in the XZ plane (u = x, v = z) and extrudes along Y, axis X uses (y, z), axis Z uses (x, y). "
        "start and end are the positions along the axis (meters). taper below 1 shrinks the far end toward the "
        "outline's centre (0.5 = half size). The result is closed with outward normals. Far less work than "
        "create_mesh with hand-built faces. Colour it with set_material, then join_objects. One undo step."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "profile": {
                "type": "array",
                "items": {"type": "array", "items": {"type": "number"}, "minItems": 2, "maxItems": 2},
                "description": "Outline as [u, v] points in order, for example a gable: [[-3,0],[3,0],[0,2]].",
            },
            "axis": {"type": "string", "enum": ["X", "Y", "Z"], "description": "Extrusion direction (default Y)."},
            "start": {"type": "number", "description": "Where the outline sits along the axis (default 0)."},
            "end": {"type": "number", "description": "Where the extrusion ends along the axis (default 1)."},
            "taper": {"type": "number", "description": "Scale of the far end, above 0 (default 1 = straight)."},
            "cap": {"type": "boolean", "description": "Close both ends (default true)."},
            "name": {"type": "string", "description": "Object name (default 'Extrusion')."},
            "location": {"type": "array", "items": {"type": "number"}, "minItems": 3, "maxItems": 3,
                         "description": "World [x, y, z] of the object origin. Default origin."},
            "rotation": {"type": "array", "items": {"type": "number"}, "minItems": 3, "maxItems": 3,
                         "description": "Euler [x, y, z] in radians."},
            "scale": {"type": "array", "items": {"type": "number"}, "minItems": 3, "maxItems": 3,
                      "description": "Scale [x, y, z]."},
            "smooth": {"type": "boolean", "description": "Smooth shading (default false = flat, good for low-poly)."},
        },
        "required": ["profile"],
        "additionalProperties": False,
    }
    risk_level = RiskLevel.LOW

    def execute(self, adapter: Any, **kwargs) -> ToolResult:
        return adapter.create_extrusion(**kwargs)
