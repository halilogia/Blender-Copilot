"""RenderContactSheet: cinematic tool (see the description)."""

from typing import Any
from core.types import RiskLevel, ToolResult
from tools.base import BaseTool


class RenderContactSheetTool(BaseTool):
    """Cinematic tool `render_contact_sheet`."""

    name = "render_contact_sheet"
    description = (
        "Render 2 to 16 evenly spaced frames of the current shot into ONE picture (a grid) and return it, so you can check the whole move, the framing and the light in a single call before the full render_animation. Small tiles, quick. "
        "With transparent and columns = frames it is a game sprite strip (for a loop, end the frame range one step before the start pose)."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "filename": {"type": "string", "description": "File name without folders (default sheet)."},
            "frames": {"type": "integer", "description": "Number of frames, 2-16 (default 4)."},
            "width": {"type": "integer", "description": "Tile width, 64-960 (default 480)."},
            "height": {"type": "integer", "description": "Tile height, 64-540 (default 270)."},
            "samples": {"type": "integer", "description": "EEVEE samples (default 8)."},
            "transparent": {"type": "boolean", "description": "Transparent background instead of the world (RGBA PNG, default false)."},
            "columns": {"type": "integer", "description": "Tiles per row, 1-frames (default about a square grid; frames = one row)."},
        },
        "required": [],
        "additionalProperties": False,
    }
    risk_level = RiskLevel.LOW

    def execute(self, adapter: Any, **kwargs) -> ToolResult:
        return adapter.render_contact_sheet(**kwargs)
