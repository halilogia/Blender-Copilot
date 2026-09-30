"""CameraSettings: cinematic tool (see the description)."""

from typing import Any
from core.types import RiskLevel, ToolResult
from tools.base import BaseTool


class CameraSettingsTool(BaseTool):
    """Cinematic tool `camera_settings`."""

    name = "camera_settings"
    description = (
        "Lens effects on the shot camera made by camera_move: depth of field (f_stop 1.4-5.6 blurs the background; focus_object or focus_distance chooses what is sharp), rack focus (focus_object plus rack_focus_to: the focus glides from one object to another over the shot) and motion blur (motion_blur true, shutter about 0.5). Call it after camera_move and before rendering."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "f_stop": {"type": "number", "description": "Aperture 0.5-32; small numbers give a strong blur (1.8 portrait, 5.6 mild). Turns depth of field on."},
            "focus_object": {"type": "string", "description": "Object that stays sharp."},
            "focus_distance": {"type": "number", "description": "Sharp distance in meters (instead of focus_object)."},
            "rack_focus_to": {"type": "string", "description": "Object the focus moves to by the end of the shot; needs focus_object as the start."},
            "motion_blur": {"type": "boolean", "description": "Turn render motion blur on or off."},
            "shutter": {"type": "number", "description": "Motion blur strength, 0.01-2, default 0.5."},
        },
        "required": [],
        "additionalProperties": False,
    }
    risk_level = RiskLevel.LOW

    def execute(self, adapter: Any, **kwargs) -> ToolResult:
        return adapter.camera_settings(**kwargs)
