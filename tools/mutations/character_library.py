"""CharacterLibrary: tool (see the description)."""

from typing import Any
from core.types import RiskLevel, ToolResult
from tools.base import BaseTool


class CharacterLibraryTool(BaseTool):
    """Tool `character_library`."""

    name = "character_library"
    description = (
        "Keep characters between scenes and shots. action save writes a rigged character (rig and parts, materials included) to the library in the export folder; load brings a saved one back into the scene at a location, ready for animate_character; list shows the saved names. The same character then appears in every shot with the same look, which is how you keep a character consistent."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["list", "save", "load"], "description": "list (default), save or load."},
            "name": {"type": "string", "description": "Library name for save and load, such as Soldier (letters, digits, _ -)."},
            "rig": {"type": "string", "description": "save: the rig to store, such as Soldier_Rig."},
            "location": {"type": "array", "items": {"type": "number"}, "description": "load: where to place it, [x, y, z] (default the origin)."},
        },
        "required": [],
        "additionalProperties": False,
    }
    risk_level = RiskLevel.LOW

    def execute(self, adapter: Any, **kwargs) -> ToolResult:
        return adapter.character_library(**kwargs)
