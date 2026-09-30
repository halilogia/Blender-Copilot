"""CameraMove: cinematic tool (see the description)."""

from typing import Any
from core.camera_paths import PRESETS
from core.types import RiskLevel, ToolResult
from tools.base import BaseTool


class CameraMoveTool(BaseTool):
    """Cinematic tool `camera_move`."""

    name = "camera_move"
    description = (
        "Create or reuse the shot camera (ShotCamera, aimed by ShotTarget) and animate it with a cinematic preset around "
        "the subject. Presets: " + ", ".join(PRESETS) + " (names say what they do; orbit takes angle, dolly_zoom keeps the "
        "subject size, snorricam and follow track a moving subject). "
        "The subject is the named objects (a rig stands for its parts), or every mesh in the scene. Keyframes are exact and "
        "repeatable; the scene's frame range and fps are set to the shot, and the camera becomes the active camera. "
        "azimuth 0 is in front of the subject (models face +Y), 90 on its +X side. Use follow=true for a moving subject. "
        "Then call render_image (one frame) or render_animation (the whole shot). For depth of field or motion blur call "
        "camera_settings."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "preset": {"type": "string", "enum": list(PRESETS), "description": "Camera move preset."},
            "object_names": {"type": "array", "items": {"type": "string"}, "description": "Subject objects. Omit for every mesh in the scene."},
            "duration": {"type": "number", "description": "Shot length in seconds (0.2-60, default 4)."},
            "fps": {"type": "integer", "description": "Frames per second (8-60, default 24)."},
            "distance": {"type": "number", "description": "Camera distance from the subject in meters (default: fits the whole subject in a 16:9 frame)."},
            "elevation": {"type": "number", "description": "Camera height angle in degrees above the horizon (default 15)."},
            "azimuth": {"type": "number", "description": "Where the camera starts around the subject in degrees; 0 = in front (default 35)."},
            "angle": {"type": "number", "description": "orbit only: how many degrees to circle (default 120, up to 360)."},
            "intensity": {"type": "number", "description": "Strength multiplier for pan, tilt, whip_pan, handheld, dolly_left/right, jib, dutch_angle (default 1)."},
            "focal_length": {"type": "number", "description": "Lens in millimeters (default 35; 24 wide, 85 portrait)."},
            "follow": {"type": "boolean", "description": "Keep the same framing while the subject moves (a walking character): the camera keeps its offset to the subject frame by frame. Set the subject's animation first (animate_character), pass the rig as object_names."},
        },
        "required": ["preset"],
        "additionalProperties": False,
    }
    risk_level = RiskLevel.LOW

    def execute(self, adapter: Any, **kwargs) -> ToolResult:
        return adapter.camera_move(**kwargs)
