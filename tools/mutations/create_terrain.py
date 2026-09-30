"""CreateTerrain: world tool (see the description)."""

from typing import Any
from core.types import RiskLevel, ToolResult
from tools.base import BaseTool


class CreateTerrainTool(BaseTool):
    """World tool `create_terrain`."""

    name = "create_terrain"
    description = (
        "Create a hilly terrain mesh: a square grid of `resolution` quads per side over `size` meters, hills up to `height` "
        "meters from fractal noise (roughness 0.05 smooth rolling hills, 0.95 jagged), centred on x=0, y=0, the lowest "
        "ground at z=0. `flat_radius` keeps a flat disc around the centre for buildings. Same seed, same terrain. Give it a "
        "material (set_material preset grass, sand or stone), then scatter trees or rocks onto it with scatter ground=<its "
        "name>. 48 quads is plenty for 40 m; keep resolution under ~100 for a game."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Object name (default Terrain)."},
            "size": {"type": "number", "description": "Side length in meters, 2-2000 (default 40)."},
            "resolution": {"type": "integer", "description": "Quads per side, 4-160 (default 48)."},
            "height": {"type": "number", "description": "Highest hill in meters (default 4)."},
            "roughness": {"type": "number", "description": "0.05-0.95 (default 0.5)."},
            "seed": {"type": "integer", "description": "Random seed (default 1)."},
            "flat_radius": {"type": "number", "description": "Radius of the flat disc around the centre in meters (default 0)."},
            "location": {"type": "array", "items": {"type": "number"}, "description": "[x, y, z] of the terrain centre (default the origin)."},
        },
        "required": [],
        "additionalProperties": False,
    }
    risk_level = RiskLevel.LOW

    def execute(self, adapter: Any, **kwargs) -> ToolResult:
        return adapter.create_terrain(**kwargs)
