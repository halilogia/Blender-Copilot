"""TaskReport: what the current AI task changed in the scene (see the description)."""

from typing import Any
from core.types import RiskLevel, ToolResult
from tools.base import BaseTool


class TaskReportTool(BaseTool):
    """Read-only tool `task_report`."""

    name = "task_report"
    description = (
        "Report what the current task has changed in the scene, by meaning instead of by tool calls: objects added, removed "
        "and changed (transform, parent, materials, modifiers, mesh size), new materials and collections, scene settings, "
        "and how many undo steps the task took. The task is everything since the last task_report (or since the user's message). "
        "Call it at the end of a piece of work to check that the scene holds what you meant to build and nothing else (a forgotten "
        "helper object, an accidental move), then fix what is off. With close false the task stays open."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "close": {"type": "boolean", "description": "true (default): the next tool starts a new task; false: keep counting."},
        },
        "required": [],
        "additionalProperties": False,
    }
    risk_level = RiskLevel.READ_ONLY

    def execute(self, adapter: Any, **kwargs) -> ToolResult:
        return adapter.task_report(**kwargs)
