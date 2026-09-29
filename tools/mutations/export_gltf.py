"""Export objects as a .glb into the configured export folder."""

from typing import Any
from core.types import RiskLevel, ToolResult
from tools.base import BaseTool


class ExportGltfTool(BaseTool):
    """Writes selected objects to a binary glTF file that Godot, Unity and Unreal import directly."""

    name = "export_gltf"
    description = (
        "Export the named objects as one binary glTF (.glb) file in the add-on's export folder (a plain file "
        "name only: no folders; the folder is set in the add-on, and the result returns the absolute path). "
        "Y-up by default (Godot, Unity), modifiers applied, materials included. Returns triangle count; more "
        "than ~3000 triangles is heavy for a small prop. Then copy the file under the game project "
        "(Godot: res://assets/) and call sync_project there."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "object_names": {"type": "array", "items": {"type": "string"},
                             "description": "Objects to export (children are exported only if listed)."},
            "filename": {"type": "string", "description": "File name such as crate.glb (letters, digits, _ - .)."},
            "apply_modifiers": {"type": "boolean", "description": "Apply modifiers (default true)."},
            "include_materials": {"type": "boolean", "description": "Export materials (default true)."},
            "y_up": {"type": "boolean", "description": "Convert to Y-up (default true)."},
            "recenter": {"type": "boolean",
                         "description": "Export as if the first object's origin were at (0, 0, 0) (default true). Without it the file "
                                        "keeps the object's position in the Blender scene and the prop appears offset in the game."},
        },
        "required": ["object_names", "filename"],
        "additionalProperties": False,
    }
    risk_level = RiskLevel.LOW

    def execute(self, adapter: Any, **kwargs) -> ToolResult:
        return adapter.export_gltf(**kwargs)
