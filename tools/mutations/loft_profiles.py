"""Loft cross-section profile rings into a watertight solid (bodies, hulls, fuselages, columns) in one call."""

from typing import Any
from core.types import RiskLevel, ToolResult
from tools.base import BaseTool


class LoftProfilesTool(BaseTool):
    """Creates a solid by bridging N >= 2 profile rings with quad strips."""

    name = "loft_profiles"
    description = (
        "Loft N >= 2 cross-section profile rings into a single watertight solid: car bodies, airplane fuselages, "
        "boat hulls, bottles, columns, vases, and organic transitions. All profile rings must have the same number "
        "of points (3 to 64 points per ring). Rings can be 3D points [[x, y, z], ...] or 2D outline points [[u, v], ...] "
        "distributed along an axis ('X', 'Y', 'Z') via heights=[h0, h1, ...]. End caps are closed with outward "
        "normals. One undo step."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "profiles": {
                "type": "array",
                "items": {
                    "type": "array",
                    "items": {
                        "type": "array",
                        "items": {"type": "number"},
                        "minItems": 2,
                        "maxItems": 3,
                    },
                    "minItems": 3,
                },
                "minItems": 2,
                "description": "List of at least 2 profile rings, each having the same number of points.",
            },
            "heights": {
                "type": "array",
                "items": {"type": "number"},
                "description": "Positions along axis for 2D profile rings [u, v]. Must match the number of profiles.",
            },
            "axis": {
                "type": "string",
                "enum": ["X", "Y", "Z"],
                "description": "Extrusion axis when using 2D profile rings (default 'Z').",
            },
            "cap": {
                "type": "boolean",
                "description": "Whether to close the start and end rings with caps (default true).",
            },
            "name": {
                "type": "string",
                "description": "Object name (default 'Loft').",
            },
            "location": {
                "type": "array",
                "items": {"type": "number"},
                "minItems": 3,
                "maxItems": 3,
                "description": "World [x, y, z] location of the object origin.",
            },
            "rotation": {
                "type": "array",
                "items": {"type": "number"},
                "minItems": 3,
                "maxItems": 3,
                "description": "Euler [x, y, z] rotation in radians.",
            },
            "scale": {
                "type": "array",
                "items": {"type": "number"},
                "minItems": 3,
                "maxItems": 3,
                "description": "Scale [x, y, z].",
            },
            "smooth": {
                "type": "boolean",
                "description": "Smooth shading (default false = flat).",
            },
        },
        "required": ["profiles"],
        "additionalProperties": False,
    }
    risk_level = RiskLevel.LOW

    def execute(self, adapter: Any, **kwargs) -> ToolResult:
        return adapter.loft_profiles(**kwargs)
