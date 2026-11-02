"""Attach an object to a predefined socket or local offset on target_object without coordinate guesswork."""

from typing import Any
from core.types import RiskLevel, ToolResult
from tools.base import BaseTool


class PlaceOnSocketTool(BaseTool):
    """Snaps an object to a target object's socket with exact transform coupling and parenting."""

    name = "place_on_socket"
    description = (
        "Attach an object to a predefined socket or local offset on target_object. Eliminates floating or intersecting "
        "secondary parts (wheels on wheel hubs, turrets on chassis, spoilers on trunks, lids on crates, lights on bumpers) "
        "by snapping them directly to mathematically exact socket points. Automatically sets parent hierarchy and "
        "local parent inverse matrix so parts follow cleanly in game engines. One undo step."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "object_name": {
                "type": "string",
                "description": "Name of the object to move and attach.",
            },
            "target_object": {
                "type": "string",
                "description": "Name of the target parent object holding the socket.",
            },
            "socket_name": {
                "type": "string",
                "description": "Name of the socket on target_object (e.g. 'socket_wheel_fl', 'socket_roof', 'socket_lid').",
            },
            "socket_location": {
                "type": "array",
                "items": {"type": "number"},
                "minItems": 3,
                "maxItems": 3,
                "description": "Local [x, y, z] coordinate relative to target_object if not using a named socket.",
            },
            "relative_rotation": {
                "type": "array",
                "items": {"type": "number"},
                "minItems": 3,
                "maxItems": 3,
                "description": "Euler rotation [rx, ry, rz] to apply relative to the socket orientation.",
            },
            "relative_scale": {
                "type": "array",
                "items": {"type": "number"},
                "minItems": 3,
                "maxItems": 3,
                "description": "Scale [sx, sy, sz] to apply to the attached object.",
            },
            "parent": {
                "type": "boolean",
                "description": "Whether to parent object_name to target_object (default true).",
            },
        },
        "required": ["object_name", "target_object"],
        "additionalProperties": False,
    }
    risk_level = RiskLevel.LOW

    def execute(self, adapter: Any, **kwargs) -> ToolResult:
        return adapter.place_on_socket(**kwargs)
