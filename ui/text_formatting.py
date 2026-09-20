"""Small, Blender-independent helpers for presenting assistant text and timeline data."""

from html import unescape
import textwrap
from typing import Dict, List


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
