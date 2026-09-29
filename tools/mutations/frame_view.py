"""Frame the 3D viewport on objects from a chosen direction so capture_viewport shows what you built."""

from typing import Any
from core.types import RiskLevel, ToolResult
from tools.base import BaseTool


class FrameViewTool(BaseTool):
    """Points the viewport at objects (or the whole scene) from FRONT, BACK, LEFT, RIGHT, TOP or ISO."""

    name = "frame_view"
    description = (
        "Aim the 3D viewport at the named objects (default: every mesh) from a direction (FRONT, BACK, LEFT, RIGHT, "
        "TOP, ISO) so the next capture_viewport shows your model instead of an empty default view. Optional "
        "shading (SOLID, MATERIAL, WIREFRAME) and overlays=false for a clean grid-free picture. Changes only the "
        "editor view, never the scene data. Typical loop: build, frame_view ISO, capture_viewport, fix, frame_view FRONT."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "object_names": {"type": "array", "items": {"type": "string"},
                             "description": "Objects to frame. Omit for all mesh objects."},
            "direction": {"type": "string", "enum": ["ISO", "FRONT", "BACK", "LEFT", "RIGHT", "TOP"],
                          "description": "Viewing direction (default ISO)."},
            "shading": {"type": "string", "enum": ["SOLID", "MATERIAL", "WIREFRAME"], "description": "Viewport shading."},
            "overlays": {"type": "boolean", "description": "Show grid, gizmos and outlines (default true)."},
        },
        "additionalProperties": False,
    }
    risk_level = RiskLevel.LOW

    def execute(self, adapter: Any, **kwargs) -> ToolResult:
        return adapter.frame_view(**kwargs)
