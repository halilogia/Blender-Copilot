"""CheckShot: cinematic tool (see the description)."""

from typing import Any
from core.types import RiskLevel, ToolResult
from tools.base import BaseTool


class CheckShotTool(BaseTool):
    """Cinematic tool `check_shot`."""

    name = "check_shot"
    description = (
        "Check the current shot with numbers instead of eyes: for a few frames of it, where the subject sits in the frame "
        "(cut off at an edge, too small, too big, off centre, behind the camera) and how bright the picture is (too dark, "
        "mostly black, too bright, blown out). Returns ok, a list of issues with the frames they appear in, and for each "
        "issue the tool change that fixes it. Cheap: call it after camera_move and set_environment and before "
        "render_animation, and repeat until ok. Works even if you cannot look at images."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "object_names": {"type": "array", "items": {"type": "string"}, "description": "The subject (a rig stands for its parts). Omit for every mesh in the scene except ground and helpers."},
            "samples": {"type": "integer", "description": "How many frames of the shot to check, 1-6 (default 3: start, middle, end)."},
            "render": {"type": "boolean", "description": "Also render small pictures to measure brightness (default true; false checks only the framing)."},
        },
        "required": [],
        "additionalProperties": False,
    }
    risk_level = RiskLevel.READ_ONLY

    def execute(self, adapter: Any, **kwargs) -> ToolResult:
        return adapter.check_shot(**kwargs)
