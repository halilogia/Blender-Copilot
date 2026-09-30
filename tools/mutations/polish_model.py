"""PolishModel: tool (see the description)."""

from typing import Any
from core.types import RiskLevel, ToolResult
from tools.base import BaseTool


class PolishModelTool(BaseTool):
    """Tool `polish_model`."""

    name = "polish_model"
    description = (
        "Make blocky models look finished: bevels the hard edges (soft highlights along every corner) and shades smooth with sharp edges kept. Run it on the parts of a prop or a character once the shapes are right, before colouring or joining is fine either way; skip it for tiny parts you want razor sharp. bevel is in meters (default about 4 percent of the smallest side), segments 1-4 (default 3: round enough to shade smooth), bevel_angle is the smallest corner angle that gets a bevel (default 30), smooth_angle the angle above which an edge stays sharp (default 45). It adds faces, so mind the triangle budget."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "object_names": {"type": "array", "items": {"type": "string"}, "description": "Mesh objects to polish."},
            "bevel": {"type": "number", "description": "Bevel width in meters (default: about 4 percent of the smallest side, 2 mm to 5 cm)."},
            "segments": {"type": "integer", "description": "Bevel segments 1-4 (default 3)."},
            "bevel_angle": {"type": "number", "description": "Only corners sharper than this many degrees are bevelled (default 30)."},
            "smooth_angle": {"type": "number", "description": "Edges sharper than this many degrees stay sharp when shading smooth (default 45)."},
        },
        "required": ["object_names"],
        "additionalProperties": False,
    }
    risk_level = RiskLevel.LOW

    def execute(self, adapter: Any, **kwargs) -> ToolResult:
        return adapter.polish_model(**kwargs)
