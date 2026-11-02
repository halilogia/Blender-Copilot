"""Compile high-level AssetSpec intermediate representation (IR) into a complete 3D asset."""

from typing import Any
from core.types import RiskLevel, ToolResult
from tools.base import BaseTool


class CreateFromSpecTool(BaseTool):
    """Compiles a high-level parametric AssetSpec into a complete, mathematically coupled 3D asset."""

    name = "create_from_spec"
    description = (
        "Compile a complete 3D asset from a high-level AssetSpec intermediate representation (IR). "
        "Allows language models to generate complex vehicles, props, and structures with mathematically "
        "guaranteed ground alignment (Z=0), coupled wheel/chassis/cabin proportions, pre-calculated sockets, "
        "and material slots without coordinate guessing or mesh intersection bugs. Produces Godot-compatible "
        "hierarchy and collision metadata in one atomic undo step."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "spec": {
                "type": "object",
                "description": (
                    "AssetSpec dictionary containing: asset_id, family ('vehicle', 'prop', 'structure', etc.), "
                    "recipe ('offroad_scout', 'sedan', 'truck', 'crate', 'barrel', etc.), dimensions ({length, width, height}), "
                    "parameters ({wheelbase_ratio, track_width_ratio, wheel_radius, etc.}), features ({roof_rack, bull_bar, etc.}), "
                    "materials ({body, tires, trim, etc.}), and export ({collision, triangle_budget, format})."
                ),
            },
            "name": {
                "type": "string",
                "description": "Optional name prefix for generated objects (default is asset_id).",
            },
        },
        "required": ["spec"],
        "additionalProperties": False,
    }
    risk_level = RiskLevel.LOW

    def execute(self, adapter: Any, **kwargs) -> ToolResult:
        return adapter.create_from_spec(**kwargs)
