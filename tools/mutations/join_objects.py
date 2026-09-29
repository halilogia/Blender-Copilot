"""Join several mesh objects into one."""

from typing import Any
from core.types import RiskLevel, ToolResult
from tools.base import BaseTool


class JoinObjectsTool(BaseTool):
    """Merges mesh objects into a single object (materials are kept)."""

    name = "join_objects"
    description = (
        "Join mesh objects into one mesh: the target keeps its name, transform and origin; the other objects are "
        "merged into it and disappear. Use it to turn the parts of a prop (body, barrel, stock) into a single "
        "asset before export_gltf. Optionally rename the result. One undo step."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "object_names": {"type": "array", "items": {"type": "string"},
                             "description": "Names of the objects to merge (the target may be included)."},
            "target_name": {"type": "string", "description": "Object that receives the others."},
            "new_name": {"type": "string", "description": "Optional new name for the joined object."},
        },
        "required": ["object_names", "target_name"],
        "additionalProperties": False,
    }
    risk_level = RiskLevel.LOW

    def execute(self, adapter: Any, **kwargs) -> ToolResult:
        return adapter.join_objects(**kwargs)
