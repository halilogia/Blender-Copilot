"""Small, Blender-independent helpers for presenting assistant text and timeline data."""

from html import unescape
import textwrap
from typing import Any, Dict, List, Sequence



def clean_assistant_text(text: str) -> str:
    """Decode HTML entities and normalize line endings for UI display.

    Provider responses are plain text, but some compatible endpoints return
    entities such as ``&#x20;``. Decode only at the presentation boundary so
    the canonical conversation/history data remains unchanged.
    """
    if not text:
        return ""
    normalized = unescape(str(text)).replace("\r\n", "\n").replace("\r", "\n")
    return "\n".join(line.rstrip() for line in normalized.split("\n"))


def wrap_multiline_text(text: str, width: int = 42) -> List[str]:
    """Break text into wrapped sublines preserving explicit newlines."""
    if not text:
        return []
    result: List[str] = []
    for paragraph in str(text).split("\n"):
        if not paragraph.strip():
            result.append("")
            continue
        wrapped = textwrap.wrap(paragraph, width=width)
        if wrapped:
            result.extend(wrapped)
        else:
            result.append("")
    return result


def map_agent_status_to_ui(state: str) -> Dict[str, str]:
    """Map backend AgentState to user-facing UI label, Blender icon, and marker symbol."""
    raw = str(state or "IDLE").upper()
    mapping = {
        "IDLE": {"label": "IDLE", "icon": "CHECKMARK", "marker": "●"},
        "PROCESSING": {"label": "THINKING", "icon": "TIME", "marker": "●"},
        "EXECUTING_TOOL": {"label": "EXECUTING", "icon": "TOOL_SETTINGS", "marker": "⟳"},
        "PENDING_APPROVAL": {"label": "WAITING FOR APPROVAL", "icon": "QUESTION", "marker": "⚠"},
        "ERROR": {"label": "ERROR", "icon": "ERROR", "marker": "✕"},
    }
    return mapping.get(raw, {"label": raw, "icon": "INFO", "marker": "·"})


def format_tool_status_icon(status: str) -> str:
    """Map tool status to standard UI symbol."""
    s = str(status or "").upper()
    if s in ("OK", "DONE", "COMPLETED", "SUCCESS"):
        return "✓"
    elif s in ("FAILED", "ERROR", "FAIL"):
        return "✕"
    elif s in ("RUNNING", "EXECUTING", "PROCESSING"):
        return "⟳"
    elif s in ("CANCELLED", "ABORTED"):
        return "—"
    elif s in ("PENDING", "QUEUED"):
        return "○"
    return "·"


def format_plan_step_status(status: str) -> Dict[str, str]:
    """Map PlanStepStatus to UI symbol, Blender icon, and label."""
    s = str(status or "").upper()
    if s == "COMPLETED":
        return {"symbol": "✓", "icon": "CHECKMARK", "label": "completed"}
    elif s in ("RUNNING", "EXECUTING", "IN_PROGRESS"):
        return {"symbol": "⟳", "icon": "TIME", "label": "running"}
    elif s in ("FAILED", "ERROR"):
        return {"symbol": "!", "icon": "ERROR", "label": "failed"}
    elif s in ("CANCELLED", "ABORTED"):
        return {"symbol": "—", "icon": "CANCEL", "label": "cancelled"}
    elif s in ("SKIPPED", "BYPASSED"):
        return {"symbol": "⤼", "icon": "FORWARD", "label": "skipped"}
    elif s in ("PENDING", "QUEUED", "WAITING"):
        return {"symbol": "○", "icon": "DOT", "label": "pending"}
    return {"symbol": "·", "icon": "DOT", "label": s.lower()}


def format_plan_text_for_clipboard(title: str, status: str, steps: Sequence[Any]) -> str:
    """Format plan details and steps into clean, human-readable text for clipboard export."""
    t = str(title or "Untitled Plan").strip()
    st = str(status or "UNKNOWN").strip().lower()
    lines = [
        f"Plan: {t}",
        f"Status: {st}",
        "",
    ]
    for idx, s in enumerate(steps):
        desc = ""
        step_status = ""
        if isinstance(s, dict):
            desc = s.get("description") or s.get("tool_name") or f"Step {idx + 1}"
            step_status = s.get("status") or "pending"
        else:
            desc = getattr(s, "description", "") or getattr(s, "tool_name", "") or f"Step {idx + 1}"
            step_status = getattr(s, "status", "") or "pending"
        mapped_status = format_plan_step_status(step_status)["label"]
        lines.append(f"{idx + 1}. {desc}")
        lines.append(f"   Status: {mapped_status}")

    return "\n".join(lines).strip()


def format_tool_text_for_clipboard(tool_name: str, status: str, summary: str) -> str:
    """Format single tool execution record into clean, human-readable text for clipboard export."""
    t_name = str(tool_name or "unknown_tool").strip()
    st = str(status or "UNKNOWN").strip()
    sum_text = str(summary or "").strip()
    return f"Tool: {t_name}\nStatus: {st}\nSummary: {sum_text}".strip()

