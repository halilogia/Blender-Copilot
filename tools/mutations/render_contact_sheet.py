"""RenderContactSheet: cinematic tool (see the description)."""

from typing import Any
from core.types import RiskLevel, ToolResult
from tools.base import BaseTool


class RenderContactSheetTool(BaseTool):
    """Cinematic tool `render_contact_sheet`."""

    name = "render_contact_sheet"
    description = (
        "Render 2 to 9 evenly spaced frames of the current shot into ONE picture (a grid) and return it, so you can check the whole move, the framing and the light in a single call before the full render_animation. Small tiles, quick."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "filename": {"type": "string", "description": "File name without folders (default sheet)."},
            "frames": {"type": "integer", "description": "Number of frames, 2-9 (default 4)."},
            "width": {"type": "integer", "description": "Tile width, 64-960 (default 480)."},
            "height": {"type": "integer", "description": "Tile height, 64-540 (default 270)."},
            "samples": {"type": "integer", "description": "EEVEE samples (default 8)."},
        },
        "required": [],
        "additionalProperties": False,
    }
    risk_level = RiskLevel.LOW

    def execute(self, adapter: Any, **kwargs) -> ToolResult:
        return adapter.render_contact_sheet(**kwargs)
