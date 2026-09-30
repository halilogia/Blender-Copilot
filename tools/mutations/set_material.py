"""Set or update Principled BSDF shader properties on an object slot or material."""

from typing import Any
from core.types import RiskLevel, ToolResult
from tools.base import BaseTool


class SetMaterialTool(BaseTool):
    """Sets Principled BSDF shader properties on a Blender material or object slot."""

    name = "set_material"
    description = (
        "Set or update Principled BSDF shader properties (base_color, metallic, roughness, "
        "emission_color, emission_strength, alpha) on a Blender material or object slot. "
        "Creates material if missing. `preset` builds a procedural material in one call (wood, stone, brick, metal, gold, grass, "
        "water, sand, concrete, marble): texture, colour variation and relief, no image files or UVs needed; `scale` makes the "
        "pattern finer (2) or coarser (0.5); base_color/roughness/metallic given as well are applied on top. Every modification "
        "records an atomic undo point."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "object_name": {
                "type": "string",
                "description": "Optional target object name whose material slot will be modified.",
            },
            "material_name": {
                "type": "string",
                "description": "Optional target material name in bpy.data.materials.",
            },
            "slot_index": {
                "type": "integer",
                "default": 0,
                "description": "Zero-indexed material slot on the object. Defaults to 0.",
            },
            "base_color": {
                "type": "array",
                "items": {"type": "number"},
                "minItems": 3,
                "maxItems": 4,
                "description": "Base color as [R, G, B] or [R, G, B, A] in range [0.0, 1.0].",
            },
            "metallic": {
                "type": "number",
                "description": "Metallic factor in range [0.0, 1.0].",
            },
            "roughness": {
                "type": "number",
                "description": "Roughness factor in range [0.0, 1.0].",
            },
            "emission_color": {
                "type": "array",
                "items": {"type": "number"},
                "minItems": 3,
                "maxItems": 4,
                "description": "Emission color as [R, G, B] or [R, G, B, A] in range [0.0, 1.0].",
            },
            "emission_strength": {
                "type": "number",
                "description": "Emission strength factor (>= 0.0).",
            },
            "alpha": {
                "type": "number",
                "description": "Alpha transparency factor in range [0.0, 1.0].",
            },
            "preset": {
                "type": "string",
                "description": "Procedural material: wood, stone, brick, metal, gold, grass, water, sand, concrete, marble.",
            },
            "scale": {
                "type": "number",
                "description": "With preset: pattern size, 1 = default, 2 = twice as fine, 0.5 = twice as coarse (0.05-50).",
            },
        },
        "required": [],
        "additionalProperties": False,
    }
    risk_level = RiskLevel.LOW

    def execute(self, adapter: Any, **kwargs) -> ToolResult:
        """Execute material property mutation via adapter."""
        object_name = kwargs.get("object_name")
        material_name = kwargs.get("material_name")
        slot_index = kwargs.get("slot_index", 0)
        base_color = kwargs.get("base_color")
        metallic = kwargs.get("metallic")
        roughness = kwargs.get("roughness")
        emission_color = kwargs.get("emission_color")
        emission_strength = kwargs.get("emission_strength")
        alpha = kwargs.get("alpha")

        return adapter.set_material(
            object_name=object_name,
            material_name=material_name,
            slot_index=slot_index,
            base_color=base_color,
            metallic=metallic,
            roughness=roughness,
            emission_color=emission_color,
            emission_strength=emission_strength,
            alpha=alpha,
            preset=kwargs.get("preset"),
            scale=kwargs.get("scale"),
        )
