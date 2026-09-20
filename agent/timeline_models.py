"""Timeline presentation models for Blender Copilot V2 Agent UI.

Pure Python. Zero Blender (bpy) dependencies.
Defines immutable presentation projections for active in-flight turns,
completed timeline turns, and tool execution views.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional, Sequence, Tuple


class TimelineTurnStatus(str, Enum):
    """Presentation lifecycle status of a turn in the chat timeline."""

    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


@dataclass(frozen=True)
class ToolExecutionView:
    """Lightweight, immutable presentation view of a single tool execution.

    Contains only the presentation-level information needed by the UI:
    name, display status, human-readable summary, optional error, and call_id.
    """

    tool_name: str
    status: str
    summary: str
    call_id: Optional[str] = None
    error_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize tool execution view to a dictionary."""
        return {
            "call_id": self.call_id,
            "error_message": self.error_message,
            "status": self.status,
            "summary": self.summary,
            "tool_name": self.tool_name,
        }


@dataclass(frozen=True)
class ActiveTurnView:
    """Immutable presentation view of the active in-flight turn currently processing or streaming.

    Represents the active turn bubble before it transitions to a finalized TimelineTurn.
    """

    turn_id: str
    prompt: str
    streaming_response: str = ""
    status: TimelineTurnStatus = TimelineTurnStatus.RUNNING
    tool_executions: Tuple[ToolExecutionView, ...] = ()
    error_message: Optional[str] = None

    def __post_init__(self) -> None:
        if isinstance(self.status, str) and not isinstance(self.status, TimelineTurnStatus):
            try:
                object.__setattr__(self, "status", TimelineTurnStatus(self.status))
            except ValueError:
                pass
        if not isinstance(self.tool_executions, tuple):
            object.__setattr__(self, "tool_executions", tuple(self.tool_executions))

    def to_dict(self) -> Dict[str, Any]:
        """Serialize active turn view to a dictionary."""
        return {
            "error_message": self.error_message,
            "prompt": self.prompt,
            "status": self.status.value if isinstance(self.status, TimelineTurnStatus) else str(self.status),
            "streaming_response": self.streaming_response,
            "tool_executions": [t.to_dict() for t in self.tool_executions],
            "turn_id": self.turn_id,
        }


@dataclass(frozen=True)
class TimelineTurn:
    """Immutable presentation view of a completed or finalized conversation turn.

    Represents a discrete turn in the persistent chat timeline.

    Design Note on Plan Integration:
    A dedicated 'plan' field is intentionally not coupled here in V2.1.1.
    PlanExecutionSummary from agent.plan_models will be introduced into
    the timeline/card presentation layer in Milestone V2.2 to prevent
    premature coupling between basic timeline models and execution plans.
    """

    turn_id: str
    prompt: str
    status: TimelineTurnStatus
    final_response: str = ""
    tool_executions: Tuple[ToolExecutionView, ...] = ()
    error_message: Optional[str] = None

    def __post_init__(self) -> None:
        if isinstance(self.status, str) and not isinstance(self.status, TimelineTurnStatus):
            try:
                object.__setattr__(self, "status", TimelineTurnStatus(self.status))
            except ValueError:
                pass
        if not isinstance(self.tool_executions, tuple):
            object.__setattr__(self, "tool_executions", tuple(self.tool_executions))

    def to_dict(self) -> Dict[str, Any]:
        """Serialize timeline turn to a dictionary."""
        return {
            "error_message": self.error_message,
            "final_response": self.final_response,
            "prompt": self.prompt,
            "status": self.status.value if isinstance(self.status, TimelineTurnStatus) else str(self.status),
            "tool_executions": [t.to_dict() for t in self.tool_executions],
            "turn_id": self.turn_id,
        }


def _parse_tool_execution(item: Any) -> ToolExecutionView:
    title = str(getattr(item, "title", "") or "")
    if title.startswith("Tool: "):
        tool_name = title[6:].split()[0]
    else:
        tool_name = title or "unknown_tool"

    status = str(getattr(item, "status", "OK") or "OK")
    summary = str(getattr(item, "summary", "") or "")
    detail = str(getattr(item, "detail", "") or "")
    error_msg = detail if status in ("FAILED", "ERROR", "FAIL") else None

    return ToolExecutionView(
        tool_name=tool_name,
        status=status,
        summary=summary or title,
        call_id=getattr(item, "call_id", None),
        error_message=error_msg,
    )


def build_timeline_projection(
    history_items: Sequence[Any],
    current_turn_id: Optional[str] = None,
    current_prompt: str = "",
    streaming_text: str = "",
) -> Tuple[Tuple[TimelineTurn, ...], Optional[ActiveTurnView]]:
    """Project RuntimeHistory items into immutable timeline turns and active turn view.

    Guarantees:
    - Pure read-only projection (zero mutation of history items).
    - Preserves chronological order of turns and tool executions.
    - Strict deduplication: active turn is excluded from completed timeline.
    - Queued items (not yet started) are not treated as completed turns.
    """
    ordered_turn_ids: list[str] = []
    items_by_turn: dict[str, list[Any]] = {}

    for it in history_items:
        tid = getattr(it, "turn_id", None)
        if not tid:
            continue
        if tid not in items_by_turn:
            items_by_turn[tid] = []
            ordered_turn_ids.append(tid)
        items_by_turn[tid].append(it)

    # 1. Build ActiveTurnView if current_turn_id is in-flight
    active_turn: Optional[ActiveTurnView] = None
    if current_turn_id:
        active_items = items_by_turn.get(current_turn_id, [])
        user_item = next((it for it in active_items if getattr(it, "kind", "") == "USER"), None)
        prompt = current_prompt or (
            getattr(user_item, "summary", "") or getattr(user_item, "title", "")
            if user_item
            else ""
        )

        tool_views = tuple(
            _parse_tool_execution(it)
            for it in active_items
            if getattr(it, "kind", "") == "TOOL"
        )

        err_item = next((it for it in active_items if getattr(it, "kind", "") == "ERROR"), None)
        err_msg = (
            getattr(err_item, "summary", "") or getattr(err_item, "detail", "")
            if err_item
            else None
        )

        active_turn = ActiveTurnView(
            turn_id=current_turn_id,
            prompt=prompt,
            streaming_response=streaming_text or "",
            status=TimelineTurnStatus.RUNNING,
            tool_executions=tool_views,
            error_message=err_msg,
        )

    # 2. Build completed TimelineTurn list (excluding active turn and unstarted queued items)
    timeline_turns: list[TimelineTurn] = []
    for tid in ordered_turn_ids:
        if current_turn_id and tid == current_turn_id:
            # Active turn is projected into active_turn; never duplicate into timeline
            continue

        turn_items = items_by_turn[tid]
        user_item = next((it for it in turn_items if getattr(it, "kind", "") == "USER"), None)

        # Skip prompts that only exist in history as queued items and have not executed
        if user_item and getattr(user_item, "status", "") == "QUEUED" and len(turn_items) == 1:
            continue

        prompt = (
            getattr(user_item, "summary", "") or getattr(user_item, "title", "")
            if user_item
            else ""
        )

        asst_item = next((it for it in turn_items if getattr(it, "kind", "") == "ASSISTANT"), None)
        final_resp = (
            getattr(asst_item, "detail", "") or getattr(asst_item, "summary", "")
            if asst_item
            else ""
        )

        tool_views = tuple(
            _parse_tool_execution(it)
            for it in turn_items
            if getattr(it, "kind", "") == "TOOL"
        )

        err_item = next((it for it in turn_items if getattr(it, "kind", "") == "ERROR"), None)
        has_failed_tool = any(t.status in ("FAILED", "ERROR", "FAIL") for t in tool_views)

        if err_item:
            status = TimelineTurnStatus.FAILED
            err_msg = getattr(err_item, "summary", "") or getattr(err_item, "detail", "")
        elif has_failed_tool:
            status = TimelineTurnStatus.FAILED
            failed_tool = next(t for t in tool_views if t.status in ("FAILED", "ERROR", "FAIL"))
            err_msg = failed_tool.error_message or failed_tool.summary
        elif user_item and getattr(user_item, "status", "") == "CANCELLED":
            status = TimelineTurnStatus.CANCELLED
            err_msg = None
        else:
            status = TimelineTurnStatus.COMPLETED
            err_msg = None

        timeline_turns.append(
            TimelineTurn(
                turn_id=tid,
                prompt=prompt,
                status=status,
                final_response=final_resp,
                tool_executions=tool_views,
                error_message=err_msg,
            )
        )

    return tuple(timeline_turns), active_turn

