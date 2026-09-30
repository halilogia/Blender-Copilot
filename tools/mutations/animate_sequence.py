"""AnimateSequence: character tool (see the description)."""

from typing import Any
from core.types import RiskLevel, ToolResult
from tools.base import BaseTool


class AnimateSequenceTool(BaseTool):
    """Character tool `animate_sequence`."""

    name = "animate_sequence"
    description = (
        "Act a scene: several motions one after another on one timeline, for example walk 4 m, then wave, then talk a line. segments is a list of up to 12 objects {preset, duration, distance, intensity, heading, text}; presets are those of animate_character (idle, walk, run, aim, wave, jump, talk, happy, surprised, angry). The character carries on from where the previous segment ended and keeps its heading unless a segment gives a new one (a turn); between segments a short blend lets the pose glide. A talk segment with text lasts as long as the line. Replaces any earlier animation of the rig. The result lists the start and end frame of every segment; film all of it (camera_move duration equal to the seconds, follow true if it walks) or one segment with camera_move start_frame. Use animate_character for a single motion."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "rig": {"type": "string", "description": "The rig name returned by rig_character, such as Soldier_Rig."},
            "segments": {"type": "array", "items": {"type": "object", "description": "One motion: preset, duration (seconds), distance (walk and run), intensity, heading (degrees), text (talk)."}, "description": "1 to 12 segments, in order."},
            "fps": {"type": "integer", "description": "Frames per second (8-60, default 24)."},
            "blend_seconds": {"type": "number", "description": "Glide between segments, 0-1.5 seconds (default 0.3)."},
        },
        "required": ["rig", "segments"],
        "additionalProperties": False,
    }
    risk_level = RiskLevel.LOW

    def execute(self, adapter: Any, **kwargs) -> ToolResult:
        return adapter.animate_sequence(**kwargs)
