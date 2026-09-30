"""SetLook: cinematic tool (see the description)."""

from typing import Any
from core.types import RiskLevel, ToolResult
from tools.base import BaseTool


class SetLookTool(BaseTool):
    """Cinematic tool `set_look`."""

    name = "set_look"
    description = (
        "Colour-grade and add glow to everything you render afterwards (render_image, render_animation, render_contact_sheet); the viewport is not affected. Looks: natural (removes the grade), cinematic (teal shadows, warm highlights), noir (black and white, hard contrast), vintage (warm and faded), warm, cold, vivid (strong colour), neon_glow (bright parts bloom), dreamy (soft haze). strength 0-2 (default 1) fades the look in or out. Calling it again replaces the previous look."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "preset": {"type": "string", "enum": ["natural", "cinematic", "noir", "vintage", "warm", "cold", "vivid", "neon_glow", "dreamy"], "description": "Look preset (default cinematic)."},
            "strength": {"type": "number", "description": "0 to 2, default 1."},
        },
        "required": [],
        "additionalProperties": False,
    }
    risk_level = RiskLevel.LOW

    def execute(self, adapter: Any, **kwargs) -> ToolResult:
        return adapter.set_look(**kwargs)
