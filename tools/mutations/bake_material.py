"""BakeMaterial: texturing tool (see the description)."""

from typing import Any
from core.types import RiskLevel, ToolResult
from tools.base import BaseTool


class BakeMaterialTool(BaseTool):
    """Texturing tool `bake_material`."""

    name = "bake_material"
    description = (
        "Paint the look of a procedural material (set_material preset: wood, brick, stone, grass ...) into an image over the "
        "object's UV map and give the object one material that uses that image. A game engine cannot read Blender's shader "
        "nodes: without this a glTF export keeps only the flat base colour, with it the .glb carries a real texture. Unwraps "
        "the mesh first if it has no UVs. Objects with flat colours only are left alone (they export fine). Bake per object "
        "after joining its parts, then export_gltf. The object gets one material: roughness and metallic of its first material are kept for the whole object, so a metal part joined to wood loses its shine (bake metal objects separately, or keep flat colours for them)."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "object_name": {"type": "string", "description": "The mesh object to bake (its mesh must not be shared with another object)."},
            "resolution": {"type": "integer", "description": "Texture size in pixels, 64-4096 (default 1024; 512 is enough for a small prop)."},
            "samples": {"type": "integer", "description": "Bake quality, 1-128 (default 4; procedural colours need few)."},
        },
        "required": ["object_name"],
        "additionalProperties": False,
    }
    risk_level = RiskLevel.LOW

    def execute(self, adapter: Any, **kwargs) -> ToolResult:
        return adapter.bake_material(**kwargs)
