"""3D Viewport N-Panel: a thin launcher for the Alt+Space GPU HUD (the primary interface)."""

import bpy
from bpy.types import Panel

from .text_formatting import map_agent_status_to_ui


class AISIDEBAR_PT_main_panel(Panel):
    """Secondary entry point. Every feature lives in the HUD (ui/gpu_overlay)."""

    bl_label = "Blender - Copilot"
    bl_idname = "AISIDEBAR_PT_main_panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Blender - Copilot"

    def draw(self, context):
        layout = self.layout
        props = getattr(context.window_manager, "ai_sidebar", None)

        if not props:
            layout.label(text="Blender - Copilot properties not initialized.", icon="ERROR")
            return

        status_info = map_agent_status_to_ui(props.agent_status)
        status_row = layout.row(align=True)
        status_row.label(text=f"AGENT: {status_info['label']}", icon=status_info["icon"])
        queued = getattr(props, "queued_count", 0)
        if queued > 0:
            status_row.label(text=f"({queued} queued)", icon="TIME")

        hud_row = layout.row(align=True)
        hud_row.scale_y = 1.4
        hud_row.operator("ai_sidebar.viewport_hud", text="Open AI HUD", icon="WINDOW")
        layout.label(text="Shortcut: Alt+Space in the 3D viewport")

        # Pending approvals stay answerable here even when the HUD is closed.
        if props.agent_status == "PENDING_APPROVAL":
            approval_box = layout.box()
            approval_box.label(text="Human approval required", icon="QUESTION")
            appr_row = approval_box.row(align=True)
            appr_row.scale_y = 1.3
            appr_row.operator("ai_sidebar.approve_action", text="Approve", icon="CHECKMARK")
            appr_row.operator("ai_sidebar.reject_action", text="Reject", icon="X")


CLASSES = (
    AISIDEBAR_PT_main_panel,
)


def register_panels():
    """Register panel classes."""
    for cls in CLASSES:
        try:
            bpy.utils.register_class(cls)
        except (ValueError, RuntimeError):
            pass


def unregister_panels():
    """Unregister panel classes."""
    for cls in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(cls)
        except (ValueError, RuntimeError):
            pass
