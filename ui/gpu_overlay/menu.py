"""Pure description of the HUD menu drawer and history digest (no bpy, unit-testable)."""

from typing import Any, Dict, List, Tuple

# (action key, label). The key is dispatched by modal.dispatch_action.
MenuItem = Tuple[str, str]


def menu_items(mcp: Dict[str, Any], task_open_steps: int) -> List[MenuItem]:
    """Buttons shown in the menu drawer, in drawing order (two per row)."""
    items: List[MenuItem] = []
    if mcp.get("available"):
        items.append(("menu:mcp_toggle", "Stop MCP bridge" if mcp.get("running") else "Start MCP bridge"))
        if mcp.get("running"):
            items.append(("menu:mcp_copy", "Copy connect command"))
        items.append((
            "menu:mcp_gated",
            "Gated tools: allowed" if mcp.get("allow_gated") else "Gated tools: ask me",
        ))
    if task_open_steps > 0:
        items.append(("task:changes", "What changed?"))
        items.append(("task:undo", f"Undo AI task ({task_open_steps})"))
    items.append(("menu:clear", "Clear history"))
    items.append(("menu:logpath", "Copy log path"))
    items.append(("menu:updates", "Check for updates"))
    items.append(("menu:settings", "Settings"))
    return items


def mcp_summary(mcp: Dict[str, Any]) -> str:
    """One status line for the MCP bridge."""
    if not mcp.get("available"):
        return "MCP bridge unavailable"
    if mcp.get("running"):
        token = f" · token {mcp['token']}" if mcp.get("token") else ""
        return f"MCP listening on {mcp.get('endpoint', '')}{token}"
    return "MCP bridge stopped"


def digest_turns(turns: List[Any], limit: int = 15) -> List[Dict[str, Any]]:
    """Plain-dict copy of timeline turns (Blender property groups or objects) for drawing."""
    out: List[Dict[str, Any]] = []
    for turn in list(turns)[-limit:]:
        tools = [
            {
                "tool_name": getattr(t, "tool_name", ""),
                "status": getattr(t, "status", ""),
                "summary": getattr(t, "summary", ""),
            }
            for t in getattr(turn, "tools", [])
        ]
        out.append({
            "turn_id": getattr(turn, "turn_id", ""),
            "prompt": getattr(turn, "prompt", ""),
            "response": getattr(turn, "final_response", ""),
            "status": getattr(turn, "status", ""),
            "error": getattr(turn, "error_message", ""),
            "tools": tools,
        })
    return out
