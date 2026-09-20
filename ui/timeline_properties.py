"""Timeline presentation PropertyGroups for Blender Copilot UI."""

import bpy
from bpy.props import (
    CollectionProperty,
    StringProperty,
)
from bpy.types import PropertyGroup


class AISidebarToolItem(PropertyGroup):
    """Presentation representation of a single tool execution within a turn."""

    tool_name: StringProperty(name="Tool Name", default="")
    status: StringProperty(name="Status", default="OK")
    summary: StringProperty(name="Summary", default="")
    error_message: StringProperty(name="Error Message", default="")


class AISidebarTurnItem(PropertyGroup):
    """Presentation representation of a completed turn in the chat timeline."""

    turn_id: StringProperty(name="Turn ID", default="")
    prompt: StringProperty(name="Prompt", default="")
    status: StringProperty(name="Status", default="COMPLETED")
    final_response: StringProperty(name="Final Response", default="")
    error_message: StringProperty(name="Error Message", default="")
    tools: CollectionProperty(type=AISidebarToolItem)


class AISidebarPlanStepItem(PropertyGroup):
    """Presentation representation of an individual step in the active plan."""

    step_id: StringProperty(name="Step ID", default="")
    tool_name: StringProperty(name="Tool Name", default="")
    description: StringProperty(name="Description", default="")
    status: StringProperty(name="Status", default="PENDING")
    error_message: StringProperty(name="Error Message", default="")


TIMELINE_CLASSES = (
    AISidebarToolItem,
    AISidebarTurnItem,
    AISidebarPlanStepItem,
)



def register_timeline_properties():
    """Register timeline property groups."""
    for cls in TIMELINE_CLASSES:
        try:
            bpy.utils.register_class(cls)
        except (ValueError, RuntimeError):
            pass


def unregister_timeline_properties():
    """Unregister timeline property groups."""
    for cls in reversed(TIMELINE_CLASSES):
        try:
            bpy.utils.unregister_class(cls)
        except (ValueError, RuntimeError):
            pass
