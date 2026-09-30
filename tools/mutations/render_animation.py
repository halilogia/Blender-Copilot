"""RenderAnimation: cinematic tool (see the description)."""

from typing import Any
from core.types import RiskLevel, ToolResult
from tools.base import BaseTool


class RenderAnimationTool(BaseTool):
    """Cinematic tool `render_animation`."""

    name = "render_animation"
    description = (
        "Render the whole shot (the scene's frame range, set by camera_move) with EEVEE into the add-on's export folder: an MP4 (H.264) or a numbered PNG sequence. Returns the absolute path, frame count, render time and a preview picture of the middle frame. At most 480 frames and 1920x1080. Blender is busy while it renders (about a tenth of a second per frame at 960x540)."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "filename": {"type": "string", "description": "File name without folders and extension, such as castle_orbit (default shot)."},
            "width": {"type": "integer", "description": "Pixels, 64-1920 (default 960)."},
            "height": {"type": "integer", "description": "Pixels, 64-1080 (default 540)."},
            "start_frame": {"type": "integer", "description": "First frame (default: scene start)."},
            "end_frame": {"type": "integer", "description": "Last frame (default: scene end)."},
            "format": {"type": "string", "enum": ["mp4", "png"], "description": "mp4 video (default) or png image sequence."},
            "samples": {"type": "integer", "description": "EEVEE samples 1-64 (default 12)."},
        },
        "required": [],
        "additionalProperties": False,
    }
    risk_level = RiskLevel.LOW

    def execute(self, adapter: Any, **kwargs) -> ToolResult:
        return adapter.render_animation(**kwargs)
