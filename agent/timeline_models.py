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
