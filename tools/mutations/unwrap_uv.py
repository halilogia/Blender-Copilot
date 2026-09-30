"""UnwrapUv: texturing tool (see the description)."""

from typing import Any
from core.types import RiskLevel, ToolResult
from tools.base import BaseTool


class UnwrapUvTool(BaseTool):
    """Texturing tool `unwrap_uv`."""

    name = "unwrap_uv"
    description = (
        "Give meshes a UV map (the flattened surface a texture is painted on), replacing the active one. method smart "
        "(default): islands are cut where faces turn more than angle_limit degrees, then packed into the 0-1 square with "
        "a margin; cube: six projections, good for boxes. Returns per object the UV coverage of the square and whether "
        "everything lies inside it. Needed before an image texture; bake_material does it by itself when a mesh has no UVs."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "object_names": {"type": "array", "items": {"type": "string"},
                             "description": "The model (a parent stands for its parts). Omit for every mesh in the scene except helper objects."},
            "method": {"type": "string", "enum": ["smart", "cube"], "description": "smart (default) or cube."},
            "angle_limit": {"type": "number", "description": "Smart only: degrees between neighbouring faces where an island is cut (1-89, default 66)."},
            "margin": {"type": "number", "description": "Gap between islands as a share of the square (0-0.5, default 0.02)."},
        },
        "required": [],
        "additionalProperties": False,
    }
    risk_level = RiskLevel.LOW

    def execute(self, adapter: Any, **kwargs) -> ToolResult:
        return adapter.unwrap_uv(**kwargs)
