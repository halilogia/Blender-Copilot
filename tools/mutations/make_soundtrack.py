"""MakeSoundtrack: tool (see the description)."""

from typing import Any
from core.types import RiskLevel, ToolResult
from tools.base import BaseTool


class MakeSoundtrackTool(BaseTool):
    """Tool `make_soundtrack`."""

    name = "make_soundtrack"
    description = (
        "Compose a background music bed as a WAV file in the export folder, procedurally (no downloads). Moods: calm (warm pads), tense (drone and heartbeat), epic (driving bass and drums), playful (bouncy plucks), night (deep pad and bells), synthwave (pulsing bass and kick). Fades in and out. Then pass the file name as soundtrack to edit_video, or skip this step and give render_shots a music mood."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "mood": {"type": "string", "enum": ["calm", "tense", "epic", "playful", "night", "synthwave"], "description": "Music mood (default calm)."},
            "seconds": {"type": "number", "description": "Length in seconds, 1-90 (default 20); make it as long as the film."},
            "filename": {"type": "string", "description": "File name without folders or extension (default music_<mood>)."},
            "seed": {"type": "integer", "description": "Different seeds give different variations (default 1)."},
        },
        "required": [],
        "additionalProperties": False,
    }
    risk_level = RiskLevel.LOW

    def execute(self, adapter: Any, **kwargs) -> ToolResult:
        return adapter.make_soundtrack(**kwargs)
