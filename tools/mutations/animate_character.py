"""AnimateCharacter: character tool (see the description)."""

from typing import Any
from core.motion_paths import PRESETS
from core.types import RiskLevel, ToolResult
from tools.base import BaseTool


class AnimateCharacterTool(BaseTool):
    """Character tool `animate_character`."""

    name = "animate_character"
    description = (
        "Animate a rigged character with a motion preset: idle, walk, run, aim (arms forward as if holding a rifle), wave, jump, "
        "and expressions: talk (the mouth follows `text`: lip sync, plus nods and a hand gesture), happy, surprised, angry. "
        "Keyframes the rotations of its parts, the scale of eyes and mouth (blinks in every preset) and the movement of the rig; "
        "sets the scene's frame range and fps. walk and run travel forward (+Y, or the heading you give); pass distance to "
        "choose how far, otherwise the natural speed for its height is used. For talk pass the words in `text` and leave "
        "duration out: it lasts as long as the line takes to say. Faces need parts named eye_l, eye_r and mouth (small boxes "
        "on the head, the mouth thin) before rig_character. Then call camera_move with follow=true when it moves, and "
        "render_animation."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "rig": {"type": "string", "description": "The rig name returned by rig_character, such as Soldier_Rig."},
            "preset": {"type": "string", "enum": list(PRESETS), "description": "Motion or expression preset."},
            "duration": {"type": "number", "description": "Seconds (0.2-60, default 3; for talk with text: the time to say it)."},
            "fps": {"type": "integer", "description": "Frames per second (8-60, default 24)."},
            "distance": {"type": "number", "description": "walk and run: meters travelled over the whole motion (default: natural speed)."},
            "intensity": {"type": "number", "description": "Swing size multiplier (default 1)."},
            "heading": {"type": "number", "description": "Direction in degrees: 0 walks toward +Y, 90 toward -X, -90 toward +X, 180 toward -Y."},
            "text": {"type": "string", "description": "talk only: the spoken line; the mouth opens and closes with its vowels, consonants and pauses."},
        },
        "required": ["rig", "preset"],
        "additionalProperties": False,
    }
    risk_level = RiskLevel.LOW

    def execute(self, adapter: Any, **kwargs) -> ToolResult:
        return adapter.animate_character(**kwargs)
