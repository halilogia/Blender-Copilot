"""N-Panel section and operators for the MCP bridge (start / stop, connect command, gated-tool switch)."""

import bpy
from bpy.types import Operator, Panel

from bridge import control
from bridge.settings import mask_token


class AISIDEBAR_OT_mcp_start(Operator):
    bl_idname = "ai_sidebar.mcp_start"
    bl_label = "Start MCP bridge"
    bl_description = "Let Claude Code or another MCP client use Blender Copilot's tools on this machine"

    def execute(self, context):
        ctl = control.get_controller()
        if ctl is None:
            self.report({"ERROR"}, "Add-on is not registered.")
            return {"CANCELLED"}
        try:
            ctl.update_settings(enabled=True)
            ctl.start()
        except OSError as exc:
            self.report({"ERROR"}, f"Could not start the bridge: {exc}")
            return {"CANCELLED"}
        self.report({"INFO"}, f"MCP bridge listening on {ctl.server.endpoint()}")
        return {"FINISHED"}


class AISIDEBAR_OT_mcp_stop(Operator):
    bl_idname = "ai_sidebar.mcp_stop"
    bl_label = "Stop MCP bridge"

    def execute(self, context):
        ctl = control.get_controller()
        if ctl is not None:
            ctl.update_settings(enabled=False)
            ctl.stop()
        return {"FINISHED"}


class AISIDEBAR_OT_mcp_copy_command(Operator):
    bl_idname = "ai_sidebar.mcp_copy_command"
    bl_label = "Copy Claude Code connect command"

    def execute(self, context):
        ctl = control.get_controller()
        if ctl is None or not ctl.is_running():
            self.report({"WARNING"}, "Start the MCP bridge first.")
            return {"CANCELLED"}
        context.window_manager.clipboard = ctl.server.claude_add_command()
        self.report({"INFO"}, "Connect command copied (it contains the secret token).")
        return {"FINISHED"}


class AISIDEBAR_OT_mcp_toggle_gated(Operator):
    bl_idname = "ai_sidebar.mcp_toggle_gated"
    bl_label = "Allow gated tools"
    bl_description = "When on, MCP clients may run MEDIUM+ risk tools (delete_object) without an approval card"

    def execute(self, context):
        ctl = control.get_controller()
        if ctl is not None:
            ctl.update_settings(allow_gated=not ctl.settings.allow_gated)
        return {"FINISHED"}


class AISIDEBAR_PT_mcp_panel(Panel):
    bl_label = "MCP bridge (Claude Code)"
    bl_idname = "AISIDEBAR_PT_mcp_panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Blender - Copilot"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        layout = self.layout
        ctl = control.get_controller()
        if ctl is None:
            layout.label(text="Add-on is not registered.", icon="ERROR")
            return
        box = layout.box()
        if ctl.is_running():
            box.label(text=f"Listening on 127.0.0.1:{ctl.server.port}", icon="CHECKMARK")
            box.label(text=f"Token: {mask_token(ctl.settings.token)}")
            layout.operator("ai_sidebar.mcp_copy_command", icon="COPYDOWN")
            layout.operator("ai_sidebar.mcp_stop", icon="PAUSE")
        else:
            box.label(text="Stopped (nothing listens).", icon="X")
            layout.operator("ai_sidebar.mcp_start", icon="PLAY")
        row = layout.row()
        row.operator("ai_sidebar.mcp_toggle_gated",
                     text="Gated tools: allowed" if ctl.settings.allow_gated else "Gated tools: ask me",
                     icon="LOCKED" if not ctl.settings.allow_gated else "UNLOCKED")
        layout.label(text=f"Exports: {ctl.settings.export_dir}")


CLASSES = (
    AISIDEBAR_OT_mcp_start,
    AISIDEBAR_OT_mcp_stop,
    AISIDEBAR_OT_mcp_copy_command,
    AISIDEBAR_OT_mcp_toggle_gated,
    AISIDEBAR_PT_mcp_panel,
)


def register_mcp_ui():
    for cls in CLASSES:
        try:
            bpy.utils.register_class(cls)
        except (ValueError, RuntimeError):
            pass


def unregister_mcp_ui():
    for cls in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(cls)
        except (ValueError, RuntimeError):
            pass
