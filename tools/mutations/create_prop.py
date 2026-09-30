"""CreateProp: tool (see the description)."""

from typing import Any
from core.prop_kinds import KIND_INFO
from core.types import RiskLevel, ToolResult
from tools.base import BaseTool


class CreatePropTool(BaseTool):
    """Tool `create_prop`."""

    name = "create_prop"
    description = (
        "Build a well-proportioned low-poly prop or a rig-ready character in ONE call instead of dozens of primitives: "
        + "; ".join(f"{k} ({v[1]})" for k, v in KIND_INFO.items())
        + ". Props come back as one bevelled, smooth object standing on the ground at `location`, front toward +Y, coloured "
        "from a palette you can override with `colors`. humanoid and robot come back as separate parts named for rig_character "
        "(Head, Torso, ArmL, ForearmL, ..., EyeL, EyeR, Mouth): pass the returned objects to rig_character, then animate. "
        "Use it first; add or change parts with the modeling tools afterwards."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "kind": {"type": "string", "enum": list(KIND_INFO), "description": "What to build."},
            "name": {"type": "string", "description": "Name of the object (props); default the kind."},
            "size": {"type": "number", "description": "Height in meters (default depends on the kind: crate 1, house 3, person 1.8)."},
            "colors": {"type": "object", "description": "Override colors by name, each [r, g, b] in 0-1, for example {\"roof\": [0.2, 0.3, 0.7]}. The result lists the color names of the kind."},
            "location": {"type": "array", "items": {"type": "number"}, "description": "[x, y, z] of the base center (default the origin)."},
            "seed": {"type": "integer", "description": "Variation for organic kinds such as rock."},
            "polish": {"type": "boolean", "description": "Bevel and smooth shade the result (default true)."},
        },
        "required": ["kind"],
        "additionalProperties": False,
    }
    risk_level = RiskLevel.LOW

    def execute(self, adapter: Any, **kwargs) -> ToolResult:
        return adapter.create_prop(**kwargs)
