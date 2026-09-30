"""EditVideo: cinematic tool (see the description)."""

from typing import Any
from core.types import RiskLevel, ToolResult
from tools.base import BaseTool


class EditVideoTool(BaseTool):
    """Cinematic tool `edit_video`."""

    name = "edit_video"
    description = (
        "Join rendered clips (MP4 files in the export folder) into one film with transitions and speed changes, using Blender's video editor. clips: names such as shot1.mp4, or objects {\"file\": \"shot1.mp4\", \"speed\": 0.5} (0.5 slow motion, 2 fast forward). transition: cut, crossfade or wipe, transition_seconds 0.1-3. All clips should share one size and frame rate (render them with the same width, height and fps)."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "filename": {"type": "string", "description": "Result name without extension (default film)."},
            "clips": {"type": "array", "items": {"description": "Clip file name like shot1.mp4, or an object {file, speed}."}, "description": "1 to 12 clips, in order."},
            "transition": {"type": "string", "enum": ["cut", "crossfade", "wipe"], "description": "Transition between clips (default cut)."},
            "transition_seconds": {"type": "number", "description": "Length of each transition, 0.1-3 (default 0.5)."},
            "soundtrack": {"type": "string", "description": "Audio file in the export folder to lay under the film (make one with make_soundtrack); trimmed to the film, AAC in the MP4."},
            "music_volume": {"type": "number", "description": "Music volume 0.05-1 (default 0.6)."},
        },
        "required": ["clips"],
        "additionalProperties": False,
    }
    risk_level = RiskLevel.LOW

    def execute(self, adapter: Any, **kwargs) -> ToolResult:
        return adapter.edit_video(**kwargs)
