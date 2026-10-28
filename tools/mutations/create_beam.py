"""A straight bar between two points: beams, braces, poles, axles, wheels, pipes."""

from typing import Any
from core.types import RiskLevel, ToolResult
from tools.base import BaseTool


class CreateBeamTool(BaseTool):
    """Creates a box or cylinder bar from one point to another, optionally tapered."""

    name = "create_beam"
    description = (
        "Create a straight bar from start to end (world [x, y, z], meters): a leg, a diagonal brace, a pole, a rail, "
        "a wheel (a short fat CYLINDER) or a pipe. shape BOX has a rectangular section (width x thickness), shape "
        "CYLINDER a round or elliptic one (segments around it, default 12). end_width and end_thickness taper the far "
        "end, for example a tower leg that narrows toward the top. up is the direction the thickness is measured "
        "against (default +Z), so a flat board can lie in a chosen plane. The bar is closed with outward normals. "
        "Build lattices and frames from many beams, then join_objects. One undo step."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "start": {"type": "array", "items": {"type": "number"}, "minItems": 3, "maxItems": 3,
                      "description": "World [x, y, z] of one end."},
            "end": {"type": "array", "items": {"type": "number"}, "minItems": 3, "maxItems": 3,
                    "description": "World [x, y, z] of the other end."},
            "width": {"type": "number", "description": "Section width in meters (default 0.1)."},
            "thickness": {"type": "number", "description": "Section thickness in meters (default = width)."},
            "shape": {"type": "string", "enum": ["BOX", "CYLINDER"], "description": "Section shape (default BOX)."},
            "segments": {"type": "integer", "minimum": 3, "maximum": 48,
                         "description": "Sides around a CYLINDER (default 12)."},
            "end_width": {"type": "number", "description": "Width at the end point, for a taper (default = width)."},
            "end_thickness": {"type": "number", "description": "Thickness at the end point (default = thickness)."},
            "up": {"type": "array", "items": {"type": "number"}, "minItems": 3, "maxItems": 3,
                   "description": "Reference direction for the section (default [0, 0, 1])."},
            "name": {"type": "string", "description": "Object name (default 'Beam')."},
            "smooth": {"type": "boolean", "description": "Smooth shading (default false)."},
        },
        "required": ["start", "end"],
        "additionalProperties": False,
    }
    risk_level = RiskLevel.LOW

    def execute(self, adapter: Any, **kwargs) -> ToolResult:
        return adapter.create_beam(**kwargs)
