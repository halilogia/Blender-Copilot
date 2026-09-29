"""Parent one object to another (or clear the parent)."""

from typing import Any
from core.types import RiskLevel, ToolResult
from tools.base import BaseTool


class ParentObjectTool(BaseTool):
    """Sets or clears an object's parent while keeping its world position."""

    name = "parent_object"
    description = (
        "Make child_name a child of parent_name (world position kept unless keep_transform is false). "
        "Pass parent_name 'NONE' to unparent. Use it to group parts that must move together, for example "
        "a turret on a tank body, before export_gltf. One undo step."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "child_name": {"type": "string", "description": "Object to parent."},
            "parent_name": {"type": "string", "description": "New parent, or 'NONE' to clear."},
            "keep_transform": {"type": "boolean", "description": "Keep the world transform (default true)."},
        },
        "required": ["child_name", "parent_name"],
        "additionalProperties": False,
    }
    risk_level = RiskLevel.LOW

    def execute(self, adapter: Any, **kwargs) -> ToolResult:
        return adapter.parent_object(**kwargs)
