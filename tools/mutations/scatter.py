"""Scatter: world tool (see the description)."""

from typing import Any
from core.types import RiskLevel, ToolResult
from tools.base import BaseTool


class ScatterTool(BaseTool):
    """World tool `scatter`."""

    name = "scatter"
    description = (
        "Place many copies of an object (a tree, a rock, a fence post ...) in one call instead of calling create_prop dozens "
        "of times: inside an `area` ({\"center\": [x, y], \"size\": [w, d]} or {\"center\": [x, y], \"radius\": r}) or along "
        "a `path` ([[x, y], ...] with `spread` meters to each side, for a tree-lined road). Copies are linked (they share the "
        "mesh: cheap, and a glTF export keeps them as instances), random in scale (scale_range, default [0.8, 1.2]) and "
        "rotation, never closer than min_distance (default about the object's footprint) and never inside the boxes of "
        "`avoid` objects (keep trees out of the house). With ground=<terrain name> every copy stands on the terrain surface; "
        "otherwise on z=ground_z. Same seed, same layout. The original stays where it is (hide or move it). One object, or a "
        "list of objects that belong together (they are copied as a group). Up to 500 copies; keep triangles_total in mind."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "source": {"description": "Object name to copy, or a list of names that form one thing (unparented, standing on its own origin)."},
            "count": {"type": "integer", "description": "How many copies, 1-500 (default 20). Fewer are placed if they do not fit."},
            "area": {"type": "object", "description": "{\"center\": [x, y], \"size\": [width, depth]} or {\"center\": [x, y], \"radius\": r}. Give area or path."},
            "path": {"type": "array", "items": {"type": "array", "items": {"type": "number"}}, "description": "Polyline [[x, y], [x, y], ...] (at least 2 points). Give area or path."},
            "spread": {"type": "number", "description": "Path only: copies are pushed up to this many meters sideways (default 2)."},
            "min_distance": {"type": "number", "description": "Smallest gap between copies in meters (default about the footprint of the largest copy)."},
            "scale_range": {"type": "array", "items": {"type": "number"}, "description": "[min, max] random scale (default [0.8, 1.2])."},
            "random_rotation": {"type": "boolean", "description": "Random turn around Z (default true)."},
            "seed": {"type": "integer", "description": "Random seed (default 1)."},
            "ground": {"type": "string", "description": "Terrain or ground object the copies stand on (found by looking straight down)."},
            "ground_z": {"type": "number", "description": "Height to stand on when there is no ground object (default 0)."},
            "avoid": {"type": "array", "items": {"type": "string"}, "description": "Objects to keep clear (their footprint plus half a meter)."},
            "name": {"type": "string", "description": "Name of the collection that holds the copies."},
        },
        "required": ["source"],
        "additionalProperties": False,
    }
    risk_level = RiskLevel.LOW

    def execute(self, adapter: Any, **kwargs) -> ToolResult:
        return adapter.scatter(**kwargs)
