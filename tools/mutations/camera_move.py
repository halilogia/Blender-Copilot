"""CameraMove: cinematic tool (see the description)."""

from typing import Any
from core.types import RiskLevel, ToolResult
from tools.base import BaseTool


class CameraMoveTool(BaseTool):
    """Cinematic tool `camera_move`."""

    name = "camera_move"
    description = (
        "Create or reuse the shot camera (ShotCamera, aimed by ShotTarget) and animate it with a cinematic preset around the subject: static, dolly_in, dolly_out, orbit (angle degrees), arc_left, arc_right, crane_up, crane_down, pan_left, pan_right, tilt_up, tilt_down, whip_pan, dolly_zoom (vertigo), crash_zoom_in, handheld. The subject is the named objects, or every mesh in the scene. Keyframes are exact and repeatable; the scene's frame range and fps are set to the shot, and the camera becomes the active camera. azimuth 0 is in front of the subject (models face +Y), 90 on its +X side. Then call render_image (one frame) or render_animation (the whole shot)."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "preset": {"type": "string", "enum": ["static", "dolly_in", "dolly_out", "orbit", "arc_left", "arc_right", "crane_up", "crane_down", "pan_left", "pan_right", "tilt_up", "tilt_down", "whip_pan", "dolly_zoom", "crash_zoom_in", "handheld"], "description": "Camera move preset."},
            "object_names": {"type": "array", "items": {"type": "string"}, "description": "Subject objects. Omit for every mesh in the scene."},
            "duration": {"type": "number", "description": "Shot length in seconds (0.2-60, default 4)."},
            "fps": {"type": "integer", "description": "Frames per second (8-60, default 24)."},
            "distance": {"type": "number", "description": "Camera distance from the subject in meters (default about 2.8 times its radius)."},
            "elevation": {"type": "number", "description": "Camera height angle in degrees above the horizon (default 15)."},
            "azimuth": {"type": "number", "description": "Where the camera starts around the subject in degrees; 0 = in front (default 35)."},
            "angle": {"type": "number", "description": "orbit only: how many degrees to circle (default 120, up to 360)."},
            "intensity": {"type": "number", "description": "pan, tilt, whip_pan, handheld strength multiplier (default 1)."},
            "focal_length": {"type": "number", "description": "Lens in millimeters (default 35; 24 wide, 85 portrait)."},
        },
        "required": ["preset"],
        "additionalProperties": False,
    }
    risk_level = RiskLevel.LOW

    def execute(self, adapter: Any, **kwargs) -> ToolResult:
        return adapter.camera_move(**kwargs)
