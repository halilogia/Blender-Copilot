"""Create a mesh object from explicit vertices and faces (build any shape without Python)."""

from typing import Any
from core.types import RiskLevel, ToolResult
from tools.base import BaseTool


class CreateMeshTool(BaseTool):
    """Creates a new mesh object from vertex positions and face index lists."""

    name = "create_mesh"
    description = (
        "Create a new mesh object from your own geometry: vertices as [x, y, z] points (meters, +Z up) and "
        "faces as lists of 3 to 8 vertex indices (counter-clockwise seen from outside, so normals point out). "
        "Use it for shapes the primitives cannot make: a rifle body, a house with a roof, a low-poly tree. "
        "Limits: 20000 vertices and 40000 faces per call. Build a prop from several meshes, then join_objects. "
        "Returns triangle count and dimensions. One undo step."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Object name (default 'Mesh')."},
            "vertices": {
                "type": "array",
                "items": {"type": "array", "items": {"type": "number"}, "minItems": 3, "maxItems": 3},
                "description": "List of [x, y, z] positions.",
            },
            "faces": {
                "type": "array",
                "items": {"type": "array", "items": {"type": "integer"}, "minItems": 3, "maxItems": 8},
                "description": "List of faces; each face is a list of vertex indices.",
            },
            "location": {"type": "array", "items": {"type": "number"}, "minItems": 3, "maxItems": 3,
                         "description": "World [x, y, z]. Default origin."},
            "rotation": {"type": "array", "items": {"type": "number"}, "minItems": 3, "maxItems": 3,
                         "description": "Euler [x, y, z] in radians."},
            "scale": {"type": "array", "items": {"type": "number"}, "minItems": 3, "maxItems": 3,
                      "description": "Scale [x, y, z]."},
            "smooth": {"type": "boolean", "description": "Smooth shading (default false = flat, good for low-poly)."},
        },
        "required": ["vertices", "faces"],
        "additionalProperties": False,
    }
    risk_level = RiskLevel.LOW

    def execute(self, adapter: Any, **kwargs) -> ToolResult:
        return adapter.create_mesh(**kwargs)
