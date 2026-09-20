"""UI state properties for Blender AI Sidebar."""

import bpy
from bpy.props import (
    BoolProperty,
    CollectionProperty,
    IntProperty,
    PointerProperty,
    StringProperty,
)
from bpy.types import PropertyGroup

from .timeline_properties import (
    AISidebarToolItem,
    AISidebarTurnItem,
    register_timeline_properties,
    unregister_timeline_properties,
)


class AISidebarHistoryItem(PropertyGroup):
    """Lightweight UI representation of a history event for UIList rendering."""

    item_id: StringProperty(name="Item ID", default="")
    turn_id: StringProperty(name="Turn ID", default="")
    kind: StringProperty(name="Kind", default="SYSTEM")
    title: StringProperty(name="Title", default="")
    status: StringProperty(name="Status", default="OK")
    summary: StringProperty(name="Summary", default="")


class AISidebarUIProperties(PropertyGroup):
    """Session/runtime-level properties for AI Sidebar UI state (not saved in .blend)."""

    prompt_input: StringProperty(
        name="Prompt",
        description="Enter natural language command or grounding test prompt",
        default="",
    )

    agent_status: StringProperty(
        name="Status",
        description="Current agent lifecycle state (IDLE, PROCESSING, EXECUTING_TOOL, ERROR)",
        default="IDLE",
    )

    current_action: StringProperty(
        name="Action",
        description="Current activity description",
        default="Ready",
    )

    last_result_summary: StringProperty(
        name="Summary",
        description="Summary of the last executed grounding tool",
        default="Ready",
    )

    history: CollectionProperty(type=AISidebarHistoryItem)

    history_index: IntProperty(
        name="History Index",
        description="Currently selected history item index",
        default=-1,
    )

    queued_count: IntProperty(
        name="Queued Prompts",
        description="Number of user prompts waiting behind the active turn",
        default=0,
        min=0,
    )

    ui_mode: bpy.props.EnumProperty(
        name="UI Mode",
        description="Current AI floating UI state",
        items=[
            ("CLOSED", "Closed", "No floating panel active"),
            ("COMMAND_BAR", "Command Bar", "Floating AI command input bar"),
            ("CONVERSATION", "Conversation", "Active conversation and tool drawer"),
        ],
        default="CLOSED",
    )

    live_streaming_text: StringProperty(
        name="Live Stream",
        description="Accumulated streaming response for active turn",
        default="",
    )

    # -------------------------------------------------------------------------
    # V2 Agent Timeline Presentation Properties
    # -------------------------------------------------------------------------
    has_active_turn: BoolProperty(
        name="Has Active Turn",
        description="True while a turn is in-flight and streaming/executing",
        default=False,
    )

    active_turn_id: StringProperty(
        name="Active Turn ID",
        default="",
    )

    active_prompt: StringProperty(
        name="Active Prompt",
        default="",
    )

    active_streaming_response: StringProperty(
        name="Active Streaming Response",
        default="",
    )

    active_status: StringProperty(
        name="Active Status",
        default="RUNNING",
    )

    active_error: StringProperty(
        name="Active Error",
        default="",
    )

    active_tools: CollectionProperty(type=AISidebarToolItem)

    timeline: CollectionProperty(type=AISidebarTurnItem)

    timeline_index: IntProperty(
        name="Timeline Index",
        default=-1,
    )

    plan_title: StringProperty(
        name="Plan Title",
        default="",
    )

    plan_status: StringProperty(
        name="Plan Status",
        default="",
    )

    plan_steps_summary: StringProperty(
        name="Plan Steps Summary",
        default="",
    )


CLASSES = (
    AISidebarHistoryItem,
    AISidebarUIProperties,
)


def register_properties():
    """Register property groups and window manager pointer."""
    register_timeline_properties()
    for cls in CLASSES:
        try:
            bpy.utils.register_class(cls)
        except (ValueError, RuntimeError):
            pass
    if not hasattr(bpy.types.WindowManager, "ai_sidebar"):
        bpy.types.WindowManager.ai_sidebar = PointerProperty(type=AISidebarUIProperties)


def unregister_properties():
    """Unregister property groups and window manager pointer."""
    try:
        wm = getattr(bpy.context, "window_manager", None)
        if wm and hasattr(wm, "ai_sidebar"):
            wm.ai_sidebar.history.clear()
            wm.ai_sidebar.history_index = -1
            wm.ai_sidebar.active_tools.clear()
            wm.ai_sidebar.timeline.clear()
            wm.ai_sidebar.timeline_index = -1
            wm.ai_sidebar.agent_status = "IDLE"
            wm.ai_sidebar.current_action = "Ready"
            wm.ai_sidebar.prompt_input = ""
            wm.ai_sidebar.queued_count = 0
            wm.ai_sidebar.has_active_turn = False
    except Exception:
        pass
    if hasattr(bpy.types.WindowManager, "ai_sidebar"):
        del bpy.types.WindowManager.ai_sidebar
    for cls in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(cls)
        except (ValueError, RuntimeError):
            pass
    unregister_timeline_properties()
