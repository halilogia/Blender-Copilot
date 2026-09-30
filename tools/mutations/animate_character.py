"""AnimateCharacter: character tool (see the description)."""

from typing import Any
from core.types import RiskLevel, ToolResult
from tools.base import BaseTool


class AnimateCharacterTool(BaseTool):
    """Character tool `animate_character`."""

    name = "animate_character"
    description = (
        "Animate a rigged character with a motion preset: idle, walk, run, aim (arms forward as if holding a rifle), wave, jump. Keyframes the rotations of its parts and the movement of the rig; sets the scene's frame range and fps. walk and run travel forward (+Y, or the heading you give); pass distance to choose how far, otherwise the natural speed for its height is used. Then call camera_move with follow=true so the camera keeps the character in frame, and render_animation."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "rig": {"type": "string", "description": "The rig name returned by rig_character, such as Soldier_Rig."},
            "preset": {"type": "string", "enum": ["idle", "walk", "run", "aim", "wave", "jump"], "description": "Motion preset."},
            "duration": {"type": "number", "description": "Seconds (0.2-60, default 3)."},
            "fps": {"type": "integer", "description": "Frames per second (8-60, default 24)."},
            "distance": {"type": "number", "description": "walk and run: meters travelled over the whole motion (default: natural speed)."},
            "intensity": {"type": "number", "description": "Swing size multiplier (default 1)."},
            "heading": {"type": "number", "description": "Direction in degrees: 0 walks toward +Y, 90 toward -X, -90 toward +X, 180 toward -Y."},
        },
        "required": ["rig", "preset"],
        "additionalProperties": False,
    }
    risk_level = RiskLevel.LOW

    def execute(self, adapter: Any, **kwargs) -> ToolResult:
        return adapter.animate_character(**kwargs)
