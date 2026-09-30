"""SetEnvironment: cinematic tool (see the description)."""

from typing import Any
from core.types import RiskLevel, ToolResult
from tools.base import BaseTool


class SetEnvironmentTool(BaseTool):
    """Cinematic tool `set_environment`."""

    name = "set_environment"
    description = (
        "Set the scene's lighting and background from a preset so renders look designed, not black or washed out. Presets: studio (neutral backdrop, soft key light), golden_hour (low warm sun), overcast (grey sky, soft light), night (dark blue with cold moon light), neon (dark with a magenta and a cyan light). Creates a world, a sun light called AI_Sun and, by default, a ground plane called AI_Ground under the models. Calling it again replaces the previous setup. Call it before camera_move and render_image / render_animation."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "preset": {"type": "string", "enum": ["studio", "golden_hour", "overcast", "night", "neon"], "description": "Lighting preset (default studio)."},
            "ground": {"type": "boolean", "description": "Add a ground plane under the models (default true)."},
            "ground_color": {"type": "array", "items": {"type": "number"}, "description": "Optional ground colour [r, g, b] in 0-1."},
            "ground_size": {"type": "number", "description": "Ground plane size in meters (default about 10 times the subject)."},
        },
        "required": [],
        "additionalProperties": False,
    }
    risk_level = RiskLevel.LOW

    def execute(self, adapter: Any, **kwargs) -> ToolResult:
        return adapter.set_environment(**kwargs)
