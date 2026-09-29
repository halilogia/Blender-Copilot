"""Bake an object's rotation / scale (and optionally location) into its mesh."""

from typing import Any
from core.types import RiskLevel, ToolResult
from tools.base import BaseTool


class ApplyTransformTool(BaseTool):
    """Applies transforms so exported geometry has rotation 0 and scale 1 (what game engines expect)."""

    name = "apply_transform"
    description = (
        "Apply an object's rotation and scale (and optionally location) into its mesh data, leaving rotation 0, "
        "scale 1. Do this before export_gltf when you scaled or rotated objects to shape them, otherwise the game "
        "engine sees odd scales. Not for parented objects. One undo step."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "object_name": {"type": "string", "description": "MESH object to apply."},
            "location": {"type": "boolean", "description": "Also bake the location (default false)."},
            "rotation": {"type": "boolean", "description": "Bake the rotation (default true)."},
            "scale": {"type": "boolean", "description": "Bake the scale (default true)."},
        },
        "required": ["object_name"],
        "additionalProperties": False,
    }
    risk_level = RiskLevel.LOW

    def execute(self, adapter: Any, **kwargs) -> ToolResult:
        return adapter.apply_transform(**kwargs)
