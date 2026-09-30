"""EnableTools: loads a pack of tools on demand (see the description)."""

from typing import Any
from core.tool_packs import ABOUT, PACKS, valid_packs
from core.types import RiskLevel, ToolResult
from tools.base import BaseTool


class EnableToolsTool(BaseTool):
    """Loads the film or character tools into this conversation."""

    name = "enable_tools"
    description = (
        "Load more tools when you need them. Packs: film (light, camera moves, render, colour looks, video editing, music) and "
        "characters (rig a character made of parts and animate it: walk, talk, expressions, scenes). They load by themselves when "
        "the request mentions video, camera, characters and so on; call this if you need them anyway."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "packs": {"type": "array", "items": {"type": "string", "enum": ["film", "characters"]},
                      "description": "Packs to load."},
        },
        "required": ["packs"],
        "additionalProperties": False,
    }
    risk_level = RiskLevel.READ_ONLY

    def execute(self, adapter: Any, **kwargs) -> ToolResult:
        wanted = kwargs.get("packs")
        if isinstance(wanted, str):
            wanted = [wanted]
        if not isinstance(wanted, list) or not wanted:
            return ToolResult.fail(self.name, "INVALID_ARGUMENT", "packs must be a list such as [\"film\"].")
        good = valid_packs(str(w).strip().lower() for w in wanted)
        if not good:
            return ToolResult.fail(self.name, "INVALID_ARGUMENT", f"Unknown pack. Packs: {', '.join(PACKS)}.")
        return ToolResult.ok(self.name, {"enabled": good, "tools": [n for p in good for n in PACKS[p]],
                                         "about": {p: ABOUT[p] for p in good},
                                         "note": "these tools are available from your next step"})
