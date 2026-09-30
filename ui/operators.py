"""Blender operators for AI Sidebar user interactions."""

import bpy
from bpy.props import StringProperty
from bpy.types import Operator
from core.logging_utils import get_logger



_logger = get_logger("operators")


class AISIDEBAR_OT_send_prompt(Operator):
    """Submit prompt to the autonomous AI agent runtime."""

    bl_idname = "ai_sidebar.send_prompt"
    bl_label = "Send"
    bl_description = "Submit natural language prompt to AI agent"

    @classmethod
    def poll(cls, context):
        props = getattr(context.window_manager, "ai_sidebar", None)
        if not props or not props.prompt_input.strip():
            return False
        # Active submissions are accepted and become visible FIFO queue rows.
        return props.agent_status in ("IDLE", "ERROR", "PROCESSING", "EXECUTING_TOOL", "PENDING_APPROVAL")

    def execute(self, context):
        from .. import get_runtime

        runtime = get_runtime()
        if runtime is None:
            self.report({"ERROR"}, "AI Sidebar Agent Runtime is not active.")
            return {"CANCELLED"}

        props = context.window_manager.ai_sidebar
        prompt = props.prompt_input.strip()
        if not prompt:
            return {"CANCELLED"}

        # Clear input field immediately and dispatch turn
        props.prompt_input = ""
        props.live_streaming_text = ""
        props.agent_status = "PROCESSING"
        props.current_action = "Thinking..."

        try:
            runtime.submit_prompt(prompt)
            return {"FINISHED"}
        except Exception as exc:
            _logger.exception("Sidebar prompt submission failed")
            props.agent_status = "ERROR"
            props.current_action = "Error encountered"
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}


class AISIDEBAR_OT_cancel_turn(Operator):
    """Cancel the active agent operation."""

    bl_idname = "ai_sidebar.cancel_turn"
    bl_label = "Cancel"
    bl_description = "Cancel currently executing agent turn"

    @classmethod
    def poll(cls, context):
        props = getattr(context.window_manager, "ai_sidebar", None)
        return props is not None and props.agent_status in ("PROCESSING", "EXECUTING_TOOL")

    def execute(self, context):
        from .. import get_runtime

        runtime = get_runtime()
        if runtime is not None:
            try:
                runtime.cancel_current_turn()
            except Exception as exc:
                _logger.exception("Sidebar turn cancellation failed")
                self.report({"ERROR"}, str(exc))
                return {"CANCELLED"}
        props = getattr(context.window_manager, "ai_sidebar", None)
        if props:
            props.agent_status = "IDLE"
            props.current_action = "Cancelled"
            props.live_streaming_text = ""
        return {"FINISHED"}


class AISIDEBAR_OT_clear_history(Operator):
    """Clear conversation turns and tool history from the session."""

    bl_idname = "ai_sidebar.clear_history"
    bl_label = "Clear History"
    bl_description = "Clear current session history"

    def execute(self, context):
        from .. import get_runtime

        props = getattr(context.window_manager, "ai_sidebar", None)
        if props:
            props.history.clear()
            props.history_index = -1
            props.live_streaming_text = ""

        runtime = get_runtime()
        if runtime is not None:
            runtime.clear_history()

        return {"FINISHED"}


class AISIDEBAR_OT_copy_diagnostic_log_path(Operator):
    """Copy the local diagnostic log path so errors can be inspected quickly."""

    bl_idname = "ai_sidebar.copy_diagnostic_log_path"
    bl_label = "Copy Diagnostic Log Path"
    bl_description = "Copy the Blender - Copilot diagnostic log path"

    def execute(self, context):
        from core.logging_utils import get_log_path

        context.window_manager.clipboard = get_log_path()
        self.report({"INFO"}, "Diagnostic log path copied to clipboard.")
        return {"FINISHED"}


class AISIDEBAR_OT_approve_action(Operator):
    """Approve the active pending tool action."""

    bl_idname = "ai_sidebar.approve_action"
    bl_label = "Approve Action"
    bl_description = "Approve execution of currently pending tool action"

    approval_id: bpy.props.StringProperty(name="Approval ID", default="")

    @classmethod
    def poll(cls, context):
        from .. import get_runtime
        runtime = get_runtime()
        if runtime is None:
            return False
        return runtime.pending_approval is not None or getattr(runtime, "pending_plan_review", None) is not None

    def execute(self, context):
        from .. import get_runtime
        runtime = get_runtime()
        if not runtime:
            self.report({"WARNING"}, "No action is currently pending approval.")
            return {"CANCELLED"}
        target_id = self.approval_id
        if not target_id:
            if getattr(runtime, "pending_plan_review", None) is not None:
                target_id = runtime.pending_plan_review.approval_id
            elif runtime.pending_approval is not None:
                target_id = runtime.pending_approval.approval_id
        if not target_id:
            self.report({"WARNING"}, "No action is currently pending approval.")
            return {"CANCELLED"}
        try:
            if target_id.startswith("plan_") and hasattr(runtime, "approve_plan"):
                try:
                    runtime.approve_plan(target_id)
                except Exception:
                    runtime.approve(target_id)
            else:
                runtime.approve(target_id)
            return {"FINISHED"}
        except Exception as exc:
            _logger.exception("Sidebar approval failed for %s", target_id)
            self.report({"ERROR"}, f"Approval failed: {str(exc)}")
            return {"CANCELLED"}


class AISIDEBAR_OT_reject_action(Operator):
    """Reject the active pending tool action."""

    bl_idname = "ai_sidebar.reject_action"
    bl_label = "Reject Action"
    bl_description = "Reject execution of currently pending tool action"

    approval_id: bpy.props.StringProperty(name="Approval ID", default="")

    @classmethod
    def poll(cls, context):
        from .. import get_runtime
        runtime = get_runtime()
        if runtime is None:
            return False
        return runtime.pending_approval is not None or getattr(runtime, "pending_plan_review", None) is not None

    def execute(self, context):
        from .. import get_runtime
        runtime = get_runtime()
        if not runtime:
            self.report({"WARNING"}, "No action is currently pending approval.")
            return {"CANCELLED"}

        target_id = self.approval_id
        if not target_id:
            if getattr(runtime, "pending_plan_review", None) is not None:
                target_id = runtime.pending_plan_review.approval_id
            elif runtime.pending_approval is not None:
                target_id = runtime.pending_approval.approval_id
        if not target_id:
            self.report({"WARNING"}, "No action is currently pending approval.")
            return {"CANCELLED"}
        try:
            if target_id.startswith("plan_") and hasattr(runtime, "reject_plan"):
                try:
                    runtime.reject_plan(target_id)
                except Exception:
                    runtime.reject(target_id)
            else:
                runtime.reject(target_id)
            return {"FINISHED"}
        except Exception as exc:
            _logger.exception("Sidebar rejection failed for %s", target_id)
            self.report({"ERROR"}, f"Rejection failed: {str(exc)}")
            return {"CANCELLED"}


_last_copied_text: str = ""


def get_last_copied_text() -> str:
    """Return the text most recently copied by an AI Sidebar copy operator."""
    return _last_copied_text


class AISIDEBAR_OT_copy_turn_response(Operator):
    """Copy assistant response of a timeline turn to clipboard."""

    bl_idname = "ai_sidebar.copy_turn_response"
    bl_label = "Copy Response"
    bl_description = "Copy assistant response to clipboard"

    turn_id: StringProperty(name="Turn ID", default="")

    def execute(self, context):
        props = getattr(context.window_manager, "ai_sidebar", None)
        if not props:
            self.report({"ERROR"}, "AI Sidebar properties not available.")
            return {"CANCELLED"}

        text_to_copy = ""
        # 1. Search in timeline turns
        for turn in getattr(props, "timeline", []):
            if turn.turn_id == self.turn_id:
                text_to_copy = turn.final_response
                break

        # 2. If not found and target matches active turn
        if not text_to_copy and self.turn_id == getattr(props, "active_turn_id", ""):
            text_to_copy = getattr(props, "active_streaming_response", "")

        # 3. Fallback to latest timeline turn if turn_id omitted
        if not text_to_copy and not self.turn_id and len(props.timeline) > 0:
            text_to_copy = props.timeline[-1].final_response

        if not text_to_copy:
            self.report({"WARNING"}, "No response text found to copy.")
            return {"CANCELLED"}

        global _last_copied_text
        _last_copied_text = text_to_copy
        if hasattr(props, "last_copied_text"):
            props.last_copied_text = text_to_copy
        context.window_manager.clipboard = text_to_copy
        self.report({"INFO"}, "Response copied to clipboard.")
        return {"FINISHED"}


class AISIDEBAR_OT_copy_plan(Operator):
    """Copy structured plan and step statuses to clipboard."""

    bl_idname = "ai_sidebar.copy_plan"
    bl_label = "Copy Plan"
    bl_description = "Copy plan details and steps to clipboard"

    def execute(self, context):
        props = getattr(context.window_manager, "ai_sidebar", None)
        if not props or not getattr(props, "plan_title", ""):
            self.report({"WARNING"}, "No active plan found to copy.")
            return {"CANCELLED"}

        from .text_formatting import format_plan_text_for_clipboard

        steps = list(getattr(props, "plan_steps", []))
        text = format_plan_text_for_clipboard(
            title=props.plan_title,
            status=props.plan_status,
            steps=steps,
        )
        global _last_copied_text
        _last_copied_text = text
        if hasattr(props, "last_copied_text"):
            props.last_copied_text = text
        context.window_manager.clipboard = text
        self.report({"INFO"}, "Plan copied to clipboard.")
        return {"FINISHED"}


class AISIDEBAR_OT_copy_tool_details(Operator):
    """Copy tool execution details to clipboard."""

    bl_idname = "ai_sidebar.copy_tool_details"
    bl_label = "Copy Tool Details"
    bl_description = "Copy tool execution details to clipboard"

    tool_name: StringProperty(name="Tool Name", default="")
    status: StringProperty(name="Status", default="OK")
    summary: StringProperty(name="Summary", default="")

    def execute(self, context):
        props = getattr(context.window_manager, "ai_sidebar", None)
        from .text_formatting import format_tool_text_for_clipboard

        text = format_tool_text_for_clipboard(
            tool_name=self.tool_name,
            status=self.status,
            summary=self.summary,
        )
        global _last_copied_text
        _last_copied_text = text
        if props and hasattr(props, "last_copied_text"):
            props.last_copied_text = text
        context.window_manager.clipboard = text

        self.report({"INFO"}, f"Tool '{self.tool_name or 'tool'}' details copied.")
        return {"FINISHED"}



class AISIDEBAR_OT_check_updates(Operator):
    """Check GitHub for a newer release (check-only, never downloads)."""

    bl_idname = "ai_sidebar.check_updates"
    bl_label = "Check for Updates"
    bl_description = "Check GitHub releases for a newer Blender Copilot version"

    def execute(self, context):
        from core.update_check import check_for_updates
        from core.config import is_network_allowed
        import bpy as _bpy

        from .. import get_runtime  # noqa: F401 (keeps import pattern consistent)
        try:
            from ..blender_manifest import __version__ as _v  # type: ignore
            current = _v
        except Exception:
            try:
                current = context.preferences.addons[__package__.split(".")[0]].bl_info.get("version", (1, 0, 0))
                current = ".".join(str(x) for x in current)
            except Exception:
                current = "1.0.0"
        online = getattr(_bpy.app, "online_access", True)
        allowed, reason = is_network_allowed("https://api.github.com", online)
        if not allowed:
            self.report({"WARNING"}, reason)
            return {"CANCELLED"}
        status = check_for_updates(current)
        if status.error:
            self.report({"WARNING"}, f"Update check failed: {status.error}")
            return {"CANCELLED"}
        if status.update_available:
            self.report({"INFO"}, f"Update available: {status.latest} (current {status.current}).")
        else:
            self.report({"INFO"}, f"Up to date ({status.current}).")
        return {"FINISHED"}


class AISIDEBAR_OT_task_changes(Operator):
    """Show what the last AI task changed in the scene."""

    bl_idname = "ai_sidebar.task_changes"
    bl_label = "What did the AI change?"
    bl_description = "List the objects, materials and settings the last AI task added, removed or changed"

    lines: StringProperty(default="", options={"SKIP_SAVE"})

    def invoke(self, context, event):
        from .. import get_runtime

        runtime = get_runtime()
        report = runtime.task_changes() if runtime is not None else {"changes": []}
        self.lines = "\n".join(report["changes"][:30]) or "Nothing changed yet."
        return context.window_manager.invoke_props_dialog(self, width=520)

    def draw(self, context):
        col = self.layout.column(align=True)
        for line in self.lines.split("\n"):
            col.label(text=line)

    def execute(self, context):
        return {"FINISHED"}


class AISIDEBAR_OT_task_undo(Operator):
    """Take back everything the last AI task did (one undo for the whole task)."""

    bl_idname = "ai_sidebar.task_undo"
    bl_label = "Undo AI task"
    bl_description = "Undo every step of the last AI task at once and check that the scene is back as it was"

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        from .. import get_runtime

        runtime = get_runtime()
        result = runtime.task_undo() if runtime is not None else {"rolled_back": False, "reason": "The agent is not running."}
        if result.get("rolled_back"):
            self.report({"INFO"}, f"AI task undone ({result['undo_steps_done']} steps), scene verified.")
        else:
            note = result.get("reason") or result.get("note") or "Could not undo the task completely."
            self.report({"WARNING"}, note)
        return {"FINISHED"}


CLASSES = (
    AISIDEBAR_OT_task_changes,
    AISIDEBAR_OT_task_undo,
    AISIDEBAR_OT_send_prompt,
    AISIDEBAR_OT_cancel_turn,
    AISIDEBAR_OT_clear_history,
    AISIDEBAR_OT_copy_diagnostic_log_path,
    AISIDEBAR_OT_approve_action,
    AISIDEBAR_OT_reject_action,
    AISIDEBAR_OT_copy_turn_response,
    AISIDEBAR_OT_copy_plan,
    AISIDEBAR_OT_copy_tool_details,
    AISIDEBAR_OT_check_updates,
)



def register_operators():
    """Register operator classes."""
    for cls in CLASSES:
        try:
            bpy.utils.register_class(cls)
        except (ValueError, RuntimeError):
            pass


def unregister_operators():
    """Unregister operator classes."""
    for cls in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(cls)
        except (RuntimeError, ValueError):
            pass
