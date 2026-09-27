"""Import a local library asset into the scene (v1.1 C)."""

from typing import Any
from core.types import RiskLevel, ToolResult
from tools.base import BaseTool


class ImportAssetTool(BaseTool):
    """Imports a .blend/.glb/.obj/.fbx asset from the configured library."""

    name = "import_asset"
    description = (
        "Import a local asset file (relative to the configured asset library) "
        "into the current Blender scene. Returns imported object name."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Library-relative asset path (e.g. 'props/chair.blend').",
            },
            "name": {
                "type": "string",
                "description": "Optional target object name override.",
            },
        },
        "required": ["path"],
        "additionalProperties": False,
    }
    risk_level = RiskLevel.LOW

    def execute(self, adapter: Any, **kwargs) -> ToolResult:
        path = kwargs.get("path", "")
        name = kwargs.get("name", None)
        if not isinstance(path, str) or not path.strip():
            return ToolResult.fail(self.name, "INVALID_ARGUMENT", "Asset 'path' must be non-empty.")
        if ".." in path.replace("\\", "/").split("/"):
            return ToolResult.fail(self.name, "INVALID_ARGUMENT", "Path traversal '..' is not allowed.")
        try:
            if name:
                return adapter.import_asset(path=path.strip(), name=name)
            return adapter.import_asset(path=path.strip())
        except TypeError:
            return ToolResult.fail(self.name, "ADAPTER_INTERNAL_ERROR", "Adapter lacks import_asset().")
