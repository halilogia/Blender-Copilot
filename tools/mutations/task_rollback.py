"""TaskRollback: take back the whole current AI task (see the description)."""

from typing import Any
from core.types import RiskLevel, ToolResult
from tools.base import BaseTool


class TaskRollbackTool(BaseTool):
    """Tool `task_rollback`: one call undoes everything the task did."""

    name = "task_rollback"
    description = (
        "Undo the whole current task in one step (every change since the last task_report or since the user's message) and "
        "check by comparison that the scene is exactly as it was before. Use it when a piece of work went wrong beyond a "
        "quick fix and you want a clean start, instead of deleting things one by one. Needs the user's approval. The result "
        "lists what was undone and any difference that remains (manual edits by the user cannot be undone this way)."
    )
    input_schema = {"type": "object", "properties": {}, "required": [], "additionalProperties": False}
    risk_level = RiskLevel.MEDIUM

    def execute(self, adapter: Any, **kwargs) -> ToolResult:
        return adapter.task_rollback(**kwargs)
