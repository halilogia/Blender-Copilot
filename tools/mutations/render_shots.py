"""RenderShots: cinematic tool (see the description)."""

from typing import Any
from core.types import RiskLevel, ToolResult
from tools.base import BaseTool


class RenderShotsTool(BaseTool):
    """Cinematic tool `render_shots`."""

    name = "render_shots"
    description = (
        "Render a whole shot list into ONE film in a single call: for every shot it sets the environment and look (if given), makes the camera move and renders it, then joins the shots with transitions. Build the models first (rig and animate characters first if they move). shots: up to 8 objects with preset (a camera_move preset) and optional duration, object_names, environment (a set_environment preset), look (a set_look preset), azimuth, elevation, distance, focal_length, follow, intensity, angle, fps. Example: [{\"preset\": \"dolly_in\", \"duration\": 3, \"environment\": \"sunset\"}, {\"preset\": \"orbit\", \"duration\": 4, \"look\": \"cinematic\"}]. If a shot has no environment or look the previous one stays, so set them on each shot that changes. Total at most 75 seconds. Blender is busy while it renders."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "filename": {"type": "string", "description": "Result name without extension (default film)."},
            "shots": {"type": "array", "items": {"type": "object", "description": "One shot: preset, duration, object_names, environment, look, azimuth, elevation, distance, focal_length, follow, intensity, angle, fps."}, "description": "1 to 8 shots, in order."},
            "transition": {"type": "string", "enum": ["cut", "crossfade", "wipe"], "description": "Transition between shots (default crossfade)."},
            "transition_seconds": {"type": "number", "description": "Length of each transition (default 0.5)."},
            "continuous": {"type": "boolean", "description": "true (default): each shot carries on where the previous one stopped in the characters' animation (a spoken line or a walk continues across shots); false: every shot starts at frame 1."},
            "music": {"type": "string", "description": "Add music: a mood (calm, tense, epic, playful, night, synthwave) composed to the film's length, or an audio file name in the export folder."},
            "music_volume": {"type": "number", "description": "Music volume 0.05-1 (default 0.6)."},
            "width": {"type": "integer", "description": "Pixels, 64-1920 (default 960)."},
            "height": {"type": "integer", "description": "Pixels, 64-1080 (default 540)."},
            "samples": {"type": "integer", "description": "EEVEE samples (default 12)."},
        },
        "required": ["shots"],
        "additionalProperties": False,
    }
    risk_level = RiskLevel.LOW

    def execute(self, adapter: Any, **kwargs) -> ToolResult:
        return adapter.render_shots(**kwargs)
