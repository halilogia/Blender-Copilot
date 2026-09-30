"""CheckModel: modelling QA tool (see the description)."""

from typing import Any
from core.types import RiskLevel, ToolResult
from tools.base import BaseTool


class CheckModelTool(BaseTool):
    """Modelling tool `check_model`."""

    name = "check_model"
    description = (
        "Check a model with numbers instead of eyes, the way check_shot checks a shot: surface problems (edges shared by 3+ "
        "faces, faces pointing inward, doubled or loose vertices, zero-area faces), unapplied scale, a pivot outside the "
        "object, no material, a texture without UVs, the model sunk into the ground, two objects in the same space, and the "
        "triangle count against a budget. Returns ok (false only for FAIL findings), issues with severity FAIL or WARN, the "
        "objects concerned and the tool call that fixes each. Cheap and read only: call it after building or editing a model "
        "and before export_gltf, fix the FAIL items and the cheap WARN items, and repeat until ok."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "object_names": {"type": "array", "items": {"type": "string"},
                             "description": "The model (a parent stands for its parts). Omit for every mesh in the scene except helper objects."},
            "max_triangles": {"type": "integer", "description": "Triangle budget for the whole model (default 3000, a small game prop; 100-1000000)."},
        },
        "required": [],
        "additionalProperties": False,
    }
    risk_level = RiskLevel.READ_ONLY

    def execute(self, adapter: Any, **kwargs) -> ToolResult:
        return adapter.check_model(**kwargs)
