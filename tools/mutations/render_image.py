"""RenderImage: cinematic tool (see the description)."""

from typing import Any
from core.types import RiskLevel, ToolResult
from tools.base import BaseTool


class RenderImageTool(BaseTool):
    """Cinematic tool `render_image`."""

    name = "render_image"
    description = (
        "Render one frame of the scene through the active camera with EEVEE and save it as a PNG in the add-on's export folder (a plain file name, no folders). Returns the absolute path and the picture itself so you can check the lighting and framing. Blender is busy while it renders (a few seconds). Typical loop: set_environment, camera_move, render_image, fix, render_animation."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "filename": {"type": "string", "description": "File name without folders, such as castle_shot (default shot)."},
            "width": {"type": "integer", "description": "Pixels, 64-1920 (default 960)."},
            "height": {"type": "integer", "description": "Pixels, 64-1080 (default 540)."},
            "frame": {"type": "integer", "description": "Frame to render (default: the current frame)."},
            "samples": {"type": "integer", "description": "EEVEE samples 1-64 (default 16)."},
        },
        "required": [],
        "additionalProperties": False,
    }
    risk_level = RiskLevel.LOW

    def execute(self, adapter: Any, **kwargs) -> ToolResult:
        return adapter.render_image(**kwargs)
