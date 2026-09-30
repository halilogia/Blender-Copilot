"""GenerateThreeD: tool (see the description)."""

from typing import Any
from core.types import RiskLevel, ToolResult
from tools.base import BaseTool


class Generate3DTool(BaseTool):
    """Tool `generate_3d`."""

    name = "generate_3d"
    description = (
        "Generate a 3D model from text (and optionally a reference image) with a trained 3D generator that the USER configured (the environment variable BLENDER_COPILOT_3D_URL points at their service, for example a local Hunyuan3D or TRELLIS server; see docs/GENERATE_3D.md). The model is saved as a .glb in the export folder, imported, scaled to `height` meters and stood on the ground at the origin under one root object, ready for set_environment, camera_move and render_animation. It is one solid mesh: use it for props, scenery and static characters; for a character that walks or talks, model it from parts instead. If no generator is configured the tool says so; then use the modeling tools. Generation can take minutes and Blender waits for it."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "prompt": {"type": "string", "description": "What to generate, in a sentence or two (English works best): shape, material, style."},
            "name": {"type": "string", "description": "Name of the result (letters, digits, _ -); default made from the prompt."},
            "image_file": {"type": "string", "description": "Optional reference image in the export folder (.png or .jpg file name) for image to 3D."},
            "height": {"type": "number", "description": "Height of the result in meters (default 1)."},
            "seed": {"type": "integer", "description": "Optional seed for repeatable results."},
            "texture": {"type": "boolean", "description": "Ask the generator for textures (default true)."},
            "timeout": {"type": "number", "description": "Seconds to wait for the service (5-1800, default 300)."},
        },
        "required": [],
        "additionalProperties": False,
    }
    risk_level = RiskLevel.LOW

    def execute(self, adapter: Any, **kwargs) -> ToolResult:
        return adapter.generate_3d(**kwargs)
