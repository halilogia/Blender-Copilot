"""3D Viewport N-Panel native Agent Chat Timeline for Blender Copilot."""

import bpy
from bpy.types import Panel

from core.logging_utils import get_log_path
from .text_formatting import (
    format_plan_step_status,
    format_tool_status_icon,
    map_agent_status_to_ui,
    wrap_multiline_text,
)



class AISIDEBAR_PT_main_panel(Panel):
    """Native N-Panel Agent Chat Timeline and control interface."""

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

        # ---------------------------------------------------------------------
        # 1. Agent Status Bar
        # ---------------------------------------------------------------------
        status_info = map_agent_status_to_ui(props.agent_status)
        status_box = layout.box()
        status_row = status_box.row(align=True)
        status_row.label(
            text=f"AGENT: {status_info['label']}",
            icon=status_info["icon"],
        )
        queued = getattr(props, "queued_count", 0)
        if queued > 0:
            status_row.label(text=f"({queued} queued)", icon="TIME")

        # ---------------------------------------------------------------------
        # 2. Prompt Input & Primary Action
        # ---------------------------------------------------------------------
        input_box = layout.box()
        input_box.prop(props, "prompt_input", text="", placeholder="Type prompt...")

        btn_row = input_box.row(align=True)
        is_processing = props.agent_status in ("PROCESSING", "EXECUTING_TOOL")
        send_btn = btn_row.operator("ai_sidebar.send_prompt", text="Send", icon="PLAY")
        if is_processing:
            btn_row.operator("ai_sidebar.cancel_turn", text="Cancel", icon="CANCEL")

        # In-Viewport HUD launcher shortcut
        hud_row = layout.row(align=True)
        hud_row.scale_y = 1.1
        hud_row.operator("ai_sidebar.viewport_hud", text="✦ Open AI HUD (Alt+Space)", icon="WINDOW")

        layout.separator()

        # ---------------------------------------------------------------------
        # 3. Plan Card (if active or last executed plan exists)
        # ---------------------------------------------------------------------
        plan_title = getattr(props, "plan_title", "")
        if plan_title:
            plan_box = layout.box()
            plan_header = plan_box.row(align=True)
            plan_status = getattr(props, "plan_status", "")
            icon = "CHECKMARK" if plan_status in ("COMPLETED", "APPROVED") else "TIME"
            plan_header.label(text=f"PLAN: {plan_title}", icon=icon)
            summary = getattr(props, "plan_steps_summary", "")
            if summary:
                plan_header.label(text=f"({summary})")
            copy_p_btn = plan_header.operator("ai_sidebar.copy_plan", text="Copy Plan", icon="COPYDOWN")

            # Step-by-step checklist
            plan_steps = list(getattr(props, "plan_steps", []))
            if plan_steps:
                steps_col = plan_box.column(align=True)
                for step in plan_steps:
                    s_row = steps_col.row(align=True)
                    s_info = format_plan_step_status(step.status)
                    desc = step.description or step.tool_name
                    s_row.label(text=f" {s_info['symbol']} {desc}", icon=s_info["icon"])
                    if step.status and step.status.upper() not in ("COMPLETED", "PENDING"):
                        s_row.label(text=f"[{step.status}]")


        # ---------------------------------------------------------------------
        # 4. CURRENT ACTIVE TURN (In-Flight Streaming / Tool Execution)
        # ---------------------------------------------------------------------
        if getattr(props, "has_active_turn", False):
            active_box = layout.box()
            active_header = active_box.row(align=True)
            active_header.label(text="CURRENT TURN", icon="TIME")
            active_header.label(text=props.active_status)

            # User prompt
            if props.active_prompt:
                p_col = active_box.column(align=True)
                p_col.label(text="YOU", icon="USER")
                self._draw_multiline(p_col, props.active_prompt)

            # Live streaming response
            if props.active_streaming_response:
                active_box.separator()
                a_hdr = active_box.row(align=True)
                a_hdr.label(text="ASSISTANT (streaming)", icon="COMMUNITY")
                copy_act = a_hdr.operator("ai_sidebar.copy_turn_response", text="Copy", icon="COPYDOWN")
                copy_act.turn_id = getattr(props, "active_turn_id", "")
                a_col = active_box.column(align=True)
                self._draw_multiline(a_col, props.active_streaming_response)


            # Active tools in-flight
            if len(props.active_tools) > 0:
                active_box.separator()
                active_box.label(text="TOOLS", icon="TOOL_SETTINGS")
                for tool in props.active_tools:
                    t_row = active_box.row(align=True)
                    icon_str = format_tool_status_icon(tool.status)
                    t_row.label(text=f" {icon_str} {tool.tool_name}")
                    if tool.summary:
                        s_col = active_box.column(align=True)
                        s_col.label(text=f"    {tool.summary}")

            # Active error if any
            if props.active_error:
                active_box.separator()
                err_col = active_box.column(align=True)
                err_col.label(text="ERROR", icon="ERROR")
                self._draw_multiline(err_col, props.active_error)

        # ---------------------------------------------------------------------
        # 5. CHAT TIMELINE (Completed Conversation Turns)
        # ---------------------------------------------------------------------
        timeline_turns = list(getattr(props, "timeline", []))
        timeline_box = layout.box()
        tl_header = timeline_box.row(align=True)
        tl_header.label(text=f"CHAT TIMELINE ({len(timeline_turns)})", icon="TEXT")

        if not timeline_turns and not getattr(props, "has_active_turn", False):
            timeline_box.label(text="No conversation yet.", icon="INFO")
        else:
            # Render turns in chronological order (newest turns visible)
            for turn in timeline_turns:
                turn_box = timeline_box.box()

                # User Prompt Block
                p_col = turn_box.column(align=True)
                p_col.label(text="YOU", icon="USER")
                self._draw_multiline(p_col, turn.prompt)

                # Tool Execution Checklist Block
                if len(turn.tools) > 0:
                    turn_box.separator()
                    tools_header = turn_box.row(align=True)
                    tools_header.label(text="TOOLS", icon="TOOL_SETTINGS")
                    for tool in turn.tools:
                        t_row = turn_box.row(align=True)
                        icon_str = format_tool_status_icon(tool.status)
                        t_row.label(text=f" {icon_str} {tool.tool_name}")
                        copy_t = t_row.operator("ai_sidebar.copy_tool_details", text="", icon="COPYDOWN")
                        copy_t.tool_name = tool.tool_name
                        copy_t.status = tool.status
                        copy_t.summary = tool.summary
                        if tool.summary:
                            s_col = turn_box.column(align=True)
                            s_col.label(text=f"    {tool.summary}")


                # Assistant Final Response Block
                if turn.final_response:
                    turn_box.separator()
                    a_hdr = turn_box.row(align=True)
                    a_hdr.label(text="ASSISTANT", icon="CHECKMARK")
                    copy_resp = a_hdr.operator("ai_sidebar.copy_turn_response", text="Copy", icon="COPYDOWN")
                    copy_resp.turn_id = turn.turn_id
                    a_col = turn_box.column(align=True)
                    self._draw_multiline(a_col, turn.final_response)


                # Error Message Block if failed
                if turn.error_message:
                    turn_box.separator()
                    e_col = turn_box.column(align=True)
                    e_col.label(text="ERROR", icon="ERROR")
                    self._draw_multiline(e_col, turn.error_message)

                # Turn status footer
                status_row = turn_box.row(align=True)
                status_row.scale_y = 0.8
                status_icon = "CHECKMARK" if turn.status == "COMPLETED" else ("CANCEL" if turn.status == "CANCELLED" else "ERROR")
                status_row.label(text=f"{turn.status}", icon=status_icon)

        # ---------------------------------------------------------------------
        # 6. Approval Actions Gate (When human approval is requested)
        # ---------------------------------------------------------------------
        if props.agent_status == "PENDING_APPROVAL":
            approval_box = layout.box()
            approval_box.label(text="⚠ Human Approval Required", icon="QUESTION")
            appr_row = approval_box.row(align=True)
            appr_row.scale_y = 1.3
            appr_row.operator("ai_sidebar.approve_action", text="Approve", icon="CHECKMARK")
            appr_row.operator("ai_sidebar.reject_action", text="Reject", icon="X")

        # ---------------------------------------------------------------------
        # 7. Actions & Diagnostics
        # ---------------------------------------------------------------------
        diag_box = layout.box()
        diag_header = diag_box.row(align=True)
        diag_header.label(text="Diagnostics & Controls", icon="INFO")
        if timeline_turns or getattr(props, "history", []):
            diag_header.operator("ai_sidebar.clear_history", text="Clear", icon="TRASH")

        diag_row = diag_box.row(align=True)
        diag_row.scale_y = 0.9
        diag_row.label(text="Log: " + get_log_path())
        diag_row.operator("ai_sidebar.copy_diagnostic_log_path", text="", icon="COPYDOWN")

    @staticmethod
    def _draw_multiline(col, text: str, width: int = 42) -> None:
        """Helper to draw wrapped text sublines inside a layout column."""
        if not text:
            return
        lines = wrap_multiline_text(text, width=width)
        for line in lines:
            if not line:
                col.separator()
            else:
                col.label(text=line)


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
