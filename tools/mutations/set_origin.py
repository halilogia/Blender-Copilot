"""Move an object's origin without moving its geometry in the world."""

from typing import Any
from core.types import RiskLevel, ToolResult
from tools.base import BaseTool


class SetOriginTool(BaseTool):
    """Puts the origin at the bottom centre, bounds centre, geometry centre or world origin."""

    name = "set_origin"
    description = (
        "Move the object's origin while the geometry stays where it is in the world. BOTTOM_CENTER (default) "
        "is what game props want: the model stands on its origin. Also BOUNDS_CENTER, GEOMETRY_CENTER, "
        "WORLD_ORIGIN. Not for parented objects. One undo step."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "object_name": {"type": "string", "description": "MESH object."},
            "mode": {"type": "string", "enum": ["BOTTOM_CENTER", "BOUNDS_CENTER", "GEOMETRY_CENTER", "WORLD_ORIGIN"]},
        },
        "required": ["object_name"],
        "additionalProperties": False,
    }
    risk_level = RiskLevel.LOW

    def execute(self, adapter: Any, **kwargs) -> ToolResult:
        return adapter.set_origin(**kwargs)
