"""Modal operator managing events, input trapping, and draw lifecycle for the GPU HUD."""

import bpy
from bpy.types import Operator

from .state import overlay_state
from .renderer import draw_overlay_hud
from .menu import digest_turns
from ..text_formatting import clean_assistant_text
from core.logging_utils import get_logger

_active_modal_operator = None
_logger = get_logger("gpu_overlay")


class AISIDEBAR_OT_viewport_hud(Operator):
    """Toggle the in-viewport floating AI HUD (Alt+Space)."""

    bl_idname = "ai_sidebar.viewport_hud"
    bl_label = "Blender AI HUD"
    bl_description = "Toggle in-viewport floating AI HUD"

    _draw_handler = None
    _timer = None

    @classmethod
    def poll(cls, context):
        return context.area and context.area.type == "VIEW_3D"

    def invoke(self, context, event):
        global _active_modal_operator

        # If already running, toggle off cleanly
        if overlay_state.is_open:
            self.cleanup(context)
            return {"FINISHED"}

        overlay_state.is_open = True
        _active_modal_operator = self

        # 1. Register draw handler on 3D Viewport
        self._draw_handler = bpy.types.SpaceView3D.draw_handler_add(
            draw_overlay_hud, (context,), "WINDOW", "POST_PIXEL"
        )

        # 2. Start animation/sync timer
        wm = context.window_manager
        self._timer = wm.event_timer_add(0.03, window=context.window)

        # 3. Add modal handler
        wm.modal_handler_add(self)

        # Force redraw
        self.tag_redraw_view3d(context)
        return {"RUNNING_MODAL"}

    def cleanup(self, context):
        """Remove draw handler, timer, and reset overlay state."""
        global _active_modal_operator
        overlay_state.is_open = False
        _active_modal_operator = None

        if self._draw_handler is not None:
            try:
                bpy.types.SpaceView3D.draw_handler_remove(self._draw_handler, "WINDOW")
            except Exception:
                pass
            self._draw_handler = None

        if self._timer is not None:
            try:
                context.window_manager.event_timer_remove(self._timer)
            except Exception:
                pass
            self._timer = None

        self.tag_redraw_view3d(context)

    @staticmethod
    def tag_redraw_view3d(context):
        """Safely tag 3D Viewport for redraw."""
        try:
            if context and context.area and context.area.type == "VIEW_3D":
                context.area.tag_redraw()
            elif context and context.screen:
                for a in context.screen.areas:
                    if a.type == "VIEW_3D":
                        a.tag_redraw()
        except Exception:
            _logger.exception("HUD redraw failed")

    def modal(self, context, event):
        if not overlay_state.is_open:
            self.cleanup(context)
            return {"FINISHED"}

        # ---------------------------------------------------------------------
        # 1. Periodic Timer (Blink & Agent Sync)
        # ---------------------------------------------------------------------
        if event.type == "TIMER":
            state_changed = overlay_state.update_blink()

            # Sync with AgentRuntime
            try:
                from ... import get_runtime
                runtime = get_runtime()
                if runtime:
                    snapshot = runtime.snapshot() if hasattr(runtime, "snapshot") else None
                    runtime_state = snapshot.state if snapshot else runtime.current_state.value
                    is_proc = runtime_state in ("PROCESSING", "EXECUTING_TOOL")
                    if is_proc != overlay_state.is_processing:
                        overlay_state.is_processing = is_proc
                        state_changed = True

                    overlay_state.status_text = runtime_state
                    last_response = snapshot.last_response_text if snapshot else (
                        runtime.last_result.final_text if runtime.last_result else ""
                    )
                    last_response = clean_assistant_text(last_response)
                    if last_response:
                        if overlay_state.last_response_text != last_response:
                            overlay_state.last_response_text = last_response
                            state_changed = True

                    live_text = snapshot.streaming_text if snapshot else getattr(runtime, "streaming_text", "")
                    live_text = clean_assistant_text(live_text)
                    if overlay_state.streaming_response_text != live_text:
                        overlay_state.streaming_response_text = live_text
                        state_changed = True

                    task_plan = snapshot.last_plan_summary if snapshot else getattr(runtime, "last_plan_summary", None)
                    if overlay_state.task_plan != task_plan:
                        overlay_state.task_plan = task_plan
                        state_changed = True

                    queued_prompts = [
                        {"queue_id": item.queue_id, "prompt": item.prompt}
                        for item in getattr(runtime, "queued_prompts", [])
                    ]
                    if overlay_state.queued_prompts != queued_prompts:
                        overlay_state.queued_prompts = queued_prompts
                        state_changed = True

                    # Sync pending approval (plan review takes precedence as batch card)
                    plan_review = getattr(runtime, "pending_plan_review", None)
                    if plan_review is not None:
                        try:
                            appr_dict = plan_review.hud_summary()
                        except Exception:
                            _logger.exception("Plan review HUD serialization failed")
                            appr_dict = {
                                "kind": "plan",
                                "approval_id": plan_review.approval_id,
                                "title": plan_review.title,
                                "description": plan_review.description,
                                "steps_total": plan_review.steps_total,
                                "overall_risk": plan_review.overall_risk.value,
                            }
                        if overlay_state.pending_approval != appr_dict:
                            overlay_state.pending_approval = appr_dict
                            state_changed = True
                    else:
                        pending = getattr(runtime, "pending_approval", None)
                        if pending:
                            appr_dict = {
                                "approval_id": pending.approval_id,
                                "description": pending.human_readable_description,
                                "risk_level": pending.risk_level.value if hasattr(pending.risk_level, "value") else str(pending.risk_level),
                                "tool_name": pending.tool_name,
                            }
                            if overlay_state.pending_approval != appr_dict:
                                overlay_state.pending_approval = appr_dict
                                state_changed = True
                        elif overlay_state.pending_approval is not None:
                            overlay_state.pending_approval = None
                            state_changed = True
            except Exception:
                _logger.exception("HUD timer synchronization failed")
                overlay_state.status_text = "ERROR"
                overlay_state.is_processing = False
                state_changed = True

            if self.sync_extras(context):
                state_changed = True
            if overlay_state.toast and not overlay_state.active_toast():
                overlay_state.toast = ""
                state_changed = True

            if state_changed:
                self.tag_redraw_view3d(context)
            return {"PASS_THROUGH"}

        # ---------------------------------------------------------------------
        # 2. Mouse Move & Hover Detection
        # ---------------------------------------------------------------------
        if event.type == "MOUSEMOVE":
            hit = overlay_state.hit_test(event.mouse_region_x, event.mouse_region_y)
            if hit != overlay_state.hover_element:
                overlay_state.hover_element = hit
                self.tag_redraw_view3d(context)

            # If mouse is inside bar, swallow event to protect 3D scene underneath
            if hit is not None:
                return {"RUNNING_MODAL"}
            return {"PASS_THROUGH"}

        # ---------------------------------------------------------------------
        # 2b. Wheel and the rest of the pointer: nothing under the HUD may leak to the 3D view
        # ---------------------------------------------------------------------
        if event.type in ("WHEELUPMOUSE", "WHEELDOWNMOUSE"):
            if overlay_state.hit_test(event.mouse_region_x, event.mouse_region_y) is None:
                return {"PASS_THROUGH"}  # over the viewport: normal zoom
            if overlay_state.scroll_response(-3 if event.type == "WHEELUPMOUSE" else 3):
                self.tag_redraw_view3d(context)
            return {"RUNNING_MODAL"}
        if event.type in ("RIGHTMOUSE", "MIDDLEMOUSE") or (event.type == "LEFTMOUSE" and event.value != "PRESS"):
            if overlay_state.hit_test(event.mouse_region_x, event.mouse_region_y) is not None:
                return {"RUNNING_MODAL"}  # releases and right/middle clicks on the HUD are swallowed
            return {"PASS_THROUGH"}

        # ---------------------------------------------------------------------
        # 3. Mouse Clicks
        # ---------------------------------------------------------------------
        if event.type == "LEFTMOUSE" and event.value == "PRESS":
            hit = overlay_state.hit_test(event.mouse_region_x, event.mouse_region_y)
            if hit == "approve":
                if overlay_state.pending_approval:
                    appr_id = overlay_state.pending_approval["approval_id"]
                    self.approve_pending_action(appr_id)
                    self.tag_redraw_view3d(context)
                    return {"RUNNING_MODAL"}
            elif hit == "reject":
                if overlay_state.pending_approval:
                    appr_id = overlay_state.pending_approval["approval_id"]
                    self.reject_pending_action(appr_id)
                    self.tag_redraw_view3d(context)
                    return {"RUNNING_MODAL"}
            elif hit == "send":
                self.submit_current_prompt()
                self.tag_redraw_view3d(context)
                return {"RUNNING_MODAL"}
            elif hit == "cancel":
                self.cancel_current_turn()
                self.tag_redraw_view3d(context)
                return {"RUNNING_MODAL"}
            elif hit == "copy_response":
                response = overlay_state.streaming_response_text or overlay_state.last_response_text
                if response:
                    context.window_manager.clipboard = response
                    overlay_state.status_text = "COPIED"
                    self.tag_redraw_view3d(context)
                return {"RUNNING_MODAL"}
            elif hit is not None and hit not in ("input", "bar", "approval_card"):
                self.dispatch_action(context, hit)
                self.tag_redraw_view3d(context)
                return {"RUNNING_MODAL"}
            elif hit in ("input", "bar", "approval_card"):
                # Focus prompt
                self.tag_redraw_view3d(context)
                return {"RUNNING_MODAL"}

            # Clicked outside bar: pass through to viewport
            return {"PASS_THROUGH"}

        # ---------------------------------------------------------------------
        # 4. Keyboard Controls
        # ---------------------------------------------------------------------
        if event.value == "PRESS":
            # A settings field being edited owns the keyboard (so Y/N/Enter do not approve or send).
            if overlay_state.settings_editor is not None:
                self.edit_setting_key(context, event)
                self.tag_redraw_view3d(context)
                return {"RUNNING_MODAL"}

            # If approval card is awaiting decision, intercept quick approval/rejection keys
            if overlay_state.pending_approval:
                appr_id = overlay_state.pending_approval["approval_id"]
                if event.type in ("Y", "A"):
                    self.approve_pending_action(appr_id)
                    self.tag_redraw_view3d(context)
                    return {"RUNNING_MODAL"}
                elif event.type in ("N", "R"):
                    self.reject_pending_action(appr_id)
                    self.tag_redraw_view3d(context)
                    return {"RUNNING_MODAL"}
                elif event.type == "ESC":
                    self.reject_pending_action(appr_id)
                    self.tag_redraw_view3d(context)
                    return {"RUNNING_MODAL"}
                elif event.type == "RET" and not overlay_state.prompt_text:
                    self.approve_pending_action(appr_id)
                    self.tag_redraw_view3d(context)
                    return {"RUNNING_MODAL"}

            # Esc: close drawer, clear input, or close the HUD
            if event.type == "ESC":
                if overlay_state.panel:
                    overlay_state.panel = None
                    self.tag_redraw_view3d(context)
                    return {"RUNNING_MODAL"}
                if overlay_state.prompt_text:
                    overlay_state.reset_input()
                    self.tag_redraw_view3d(context)
                    return {"RUNNING_MODAL"}
                else:
                    self.cleanup(context)
                    return {"FINISHED"}

            # Enter: Submit or Newline
            if event.type == "RET":
                if event.shift:
                    overlay_state.insert_text("\n")
                    self.tag_redraw_view3d(context)
                    return {"RUNNING_MODAL"}
                else:
                    self.submit_current_prompt()
                    self.tag_redraw_view3d(context)
                    return {"RUNNING_MODAL"}

            # Backspace & Delete
            if event.type in ("BACKSPACE", "BACK_SPACE"):
                if event.ctrl:
                    overlay_state.delete_word_backward()
                else:
                    overlay_state.delete_backward()
                self.tag_redraw_view3d(context)
                return {"RUNNING_MODAL"}

            if event.type in ("DEL", "DELETE"):
                overlay_state.delete_forward()
                self.tag_redraw_view3d(context)
                return {"RUNNING_MODAL"}

            # Cursor Navigation
            if event.type == "LEFT_ARROW":
                overlay_state.move_cursor_left()
                self.tag_redraw_view3d(context)
                return {"RUNNING_MODAL"}

            if event.type == "RIGHT_ARROW":
                overlay_state.move_cursor_right()
                self.tag_redraw_view3d(context)
                return {"RUNNING_MODAL"}

            if event.type == "HOME":
                overlay_state.move_cursor_home()
                self.tag_redraw_view3d(context)
                return {"RUNNING_MODAL"}

            if event.type == "END":
                overlay_state.move_cursor_end()
                self.tag_redraw_view3d(context)
                return {"RUNNING_MODAL"}

            # Clipboard Paste (Ctrl + V)
            if event.type == "V" and event.ctrl:
                clip = context.window_manager.clipboard
                if clip:
                    overlay_state.insert_text(clip)
                    self.tag_redraw_view3d(context)
                return {"RUNNING_MODAL"}

            # Standard Text Character Input (includes Turkish & Unicode)
            if event.unicode:
                overlay_state.insert_text(event.unicode)
                self.tag_redraw_view3d(context)
                return {"RUNNING_MODAL"}

            # Trap all other keys while HUD is open so Blender viewport shortcuts aren't fired accidentally
            return {"RUNNING_MODAL"}

        return {"PASS_THROUGH"}

    # ------------------------------------------------------------------
    # Sidebar feature parity: extra state and actions
    # ------------------------------------------------------------------
    @staticmethod
    def sync_extras(context) -> bool:
        """Mirror history, task undo count, MCP bridge and model info; True if anything changed."""
        changed = False

        def put(name, value):
            nonlocal changed
            if getattr(overlay_state, name) != value:
                setattr(overlay_state, name, value)
                changed = True

        try:
            props = getattr(context.window_manager, "ai_sidebar", None)
            if props is not None:
                put("history", digest_turns(list(props.timeline)))
                put("plan_title", str(getattr(props, "plan_title", "") or ""))
                running = [t.tool_name for t in props.active_tools if str(t.status).upper() in ("RUNNING", "EXECUTING")]
                put("active_tool_name", running[-1] if running else None)
        except Exception:
            _logger.exception("HUD history sync failed")

        # The connection test finishes on a worker thread; redraw when its result lands.
        test_sig = (overlay_state.settings_test["state"], overlay_state.settings_test["msg"])
        if getattr(overlay_state, "_test_sig", None) != test_sig:
            overlay_state._test_sig = test_sig
            changed = True

        try:
            from ... import get_runtime
            runtime = get_runtime()
            steps = runtime.task_open_steps() if runtime is not None else 0
            put("task_open_steps", steps if not overlay_state.is_processing else 0)
        except Exception:
            _logger.exception("HUD task sync failed")

        try:
            from bridge import control
            from bridge.settings import mask_token
            ctl = control.get_controller()
            if ctl is None:
                mcp = {"available": False, "running": False, "endpoint": "", "token": "", "allow_gated": False}
            else:
                running = bool(ctl.is_running())
                mcp = {
                    "available": True,
                    "running": running,
                    "endpoint": ctl.server.endpoint() if running else "",
                    "token": mask_token(ctl.settings.token) if running else "",
                    "allow_gated": bool(ctl.settings.allow_gated),
                }
            put("mcp", mcp)
        except Exception:
            _logger.exception("HUD MCP sync failed")

        try:
            from ..preferences import get_addon_package
            from core.logging_utils import get_log_path
            put("log_path", get_log_path())
            prefs = context.preferences.addons[get_addon_package()].preferences
            put("model_label", f"{prefs.model} · {prefs.provider}")
        except (KeyError, AttributeError) as exc:
            # Add-on loaded outside the extension system (tests): no preferences entry to show.
            _logger.debug("HUD model label unavailable: %s", exc)
        return changed

    # ------------------------------------------------------------------
    # Settings drawer: edits go to the add-on preferences (same store the N-panel used)
    # ------------------------------------------------------------------
    @staticmethod
    def _prefs(context):
        from ..preferences import get_addon_package
        return context.preferences.addons[get_addon_package()].preferences

    @staticmethod
    def load_settings_snapshot(context) -> bool:
        """Copy the add-on preferences into the HUD; False when the add-on has no preferences entry."""
        try:
            prefs = AISIDEBAR_OT_viewport_hud._prefs(context)
        except (KeyError, AttributeError) as exc:
            _logger.debug("HUD settings unavailable: %s", exc)
            return False
        overlay_state.settings_values = {
            "provider": prefs.provider, "base_url": prefs.base_url, "model": prefs.model,
            "api_key": prefs.api_key, "timeout": int(prefs.timeout_seconds),
        }
        overlay_state.online_access = bool(getattr(bpy.app, "online_access", True))
        return True

    @staticmethod
    def commit_setting(context, field: str, value) -> None:
        """Write one field to the preferences (their update callback saves and re-syncs the provider)."""
        prefs = AISIDEBAR_OT_viewport_hud._prefs(context)
        setattr(prefs, "timeout_seconds" if field == "timeout" else field, value)
        overlay_state.settings_values[field] = value
        overlay_state.settings_test = {"state": "idle", "msg": ""}

    @staticmethod
    def finish_setting_edit(context, apply: bool) -> None:
        editor = overlay_state.settings_editor
        overlay_state.settings_editor = None
        if editor is None or not apply:
            return
        text = editor.text.strip()
        if editor.field == "base_url" and not text:
            return  # an empty URL would only be replaced by the default; keep the old value
        AISIDEBAR_OT_viewport_hud.commit_setting(context, editor.field, text)

    @staticmethod
    def edit_setting_key(context, event) -> None:
        """Keyboard handling while a settings field is being typed into."""
        editor = overlay_state.settings_editor
        if event.type == "ESC":
            AISIDEBAR_OT_viewport_hud.finish_setting_edit(context, apply=False)
        elif event.type in ("RET", "NUMPAD_ENTER"):
            AISIDEBAR_OT_viewport_hud.finish_setting_edit(context, apply=True)
        elif event.type in ("BACKSPACE", "BACK_SPACE"):
            editor.backspace(word=bool(event.ctrl))
        elif event.type == "V" and event.ctrl:
            editor.insert(context.window_manager.clipboard or "")
        elif event.unicode:
            editor.insert(event.unicode)

    @staticmethod
    def start_connection_test(context) -> None:
        """Probe the endpoint on a worker thread so Blender never waits on the network."""
        import threading
        from .settings import run_connection_test
        v = dict(overlay_state.settings_values)
        online = overlay_state.online_access
        overlay_state.settings_test = {"state": "running", "msg": ""}

        def work():
            try:
                ok, msg = run_connection_test(v["provider"], v["base_url"], v["api_key"],
                                              float(v["timeout"]), online)
            except Exception as exc:  # the probe must report, never raise into the thread machinery
                _logger.warning("HUD connection test crashed: %s", type(exc).__name__)
                ok, msg = False, f"Test failed: {type(exc).__name__}"
            overlay_state.settings_test = {"state": "ok" if ok else "fail", "msg": msg}

        threading.Thread(target=work, name="hud-connection-test", daemon=True).start()

    @staticmethod
    def start_agy_verify(context) -> None:
        """`agy --print ok` on a worker thread; result goes to the settings status line."""
        import threading
        from agent.agy_cli_provider import verify_login
        overlay_state.settings_test = {"state": "running", "msg": ""}

        def work():
            try:
                state, msg = verify_login()
            except Exception as exc:  # report instead of dying silently in the thread
                _logger.warning("agy verify crashed: %s", type(exc).__name__)
                state, msg = "needs_login", f"Check failed: {type(exc).__name__}"
            overlay_state.settings_test = {"state": "ok" if state == "ok" else "fail", "msg": msg}

        threading.Thread(target=work, name="hud-agy-verify", daemon=True).start()

    @staticmethod
    def dispatch_setting(context, key: str) -> None:
        """Clicks inside the settings drawer."""
        from .settings import next_provider, step_timeout
        ops = bpy.ops.ai_sidebar
        field = key[len("set:"):]
        editor = overlay_state.settings_editor
        if editor is not None and field != editor.field:
            AISIDEBAR_OT_viewport_hud.finish_setting_edit(context, apply=True)
        v = overlay_state.settings_values
        if field == "provider":
            AISIDEBAR_OT_viewport_hud.commit_setting(context, "provider", next_provider(v.get("provider", "")))
        elif field in ("base_url", "model", "api_key"):
            from .settings import FieldEditor
            overlay_state.settings_editor = FieldEditor(field, str(v.get(field, "")))
        elif field in ("timeout:-", "timeout:+"):
            delta = -15 if field.endswith("-") else 15
            AISIDEBAR_OT_viewport_hud.commit_setting(context, "timeout", step_timeout(v.get("timeout", 30), delta))
        elif field == "test":
            AISIDEBAR_OT_viewport_hud.start_connection_test(context)
        elif field == "agy_login":
            from agent.agy_cli_provider import launch_login
            ok, msg = launch_login()
            overlay_state.settings_test = {"state": "ok" if ok else "fail", "msg": msg}
        elif field == "agy_verify":
            AISIDEBAR_OT_viewport_hud.start_agy_verify(context)
        elif field == "save":
            ops.save_preferences()
            overlay_state.set_toast("Settings saved")
        elif field == "reload":
            ops.reload_preferences()
            AISIDEBAR_OT_viewport_hud.load_settings_snapshot(context)
            overlay_state.set_toast("Settings reloaded")
        elif field == "prefs":
            from ..preferences import get_addon_package
            bpy.ops.preferences.addon_show(module=get_addon_package())

    @staticmethod
    def dispatch_action(context, key: str) -> None:
        """Run the existing operator behind a clickable HUD region."""
        ops = bpy.ops.ai_sidebar
        try:
            if key.startswith("set:"):
                AISIDEBAR_OT_viewport_hud.dispatch_setting(context, key)
            elif key == "pill:menu":
                overlay_state.toggle_panel("menu")
            elif key == "pill:history":
                overlay_state.toggle_panel("history")
            elif key == "panel_bg":
                pass
            elif key == "task:changes":
                ops.task_changes("INVOKE_DEFAULT")
            elif key == "task:undo":
                ops.task_undo("INVOKE_DEFAULT")
            elif key == "plan:copy":
                ops.copy_plan()
                overlay_state.set_toast("Plan copied")
            elif key == "menu:mcp_toggle":
                if overlay_state.mcp.get("running"):
                    ops.mcp_stop()
                    overlay_state.set_toast("MCP stopped")
                else:
                    ops.mcp_start()
                    overlay_state.set_toast("MCP started")
            elif key == "menu:mcp_copy":
                ops.mcp_copy_command()
                overlay_state.set_toast("Command copied")
            elif key == "menu:mcp_gated":
                ops.mcp_toggle_gated()
            elif key == "menu:clear":
                ops.clear_history()
                overlay_state.last_prompt_text = ""
                overlay_state.last_response_text = ""
                overlay_state.streaming_response_text = ""
                overlay_state.task_plan = None
                overlay_state.history = []
                overlay_state.panel = None
                overlay_state.set_toast("History cleared")
            elif key == "menu:logpath":
                ops.copy_diagnostic_log_path()
                overlay_state.set_toast("Log path copied")
            elif key == "menu:updates":
                ops.check_updates()
                from .. import operators
                overlay_state.set_toast(operators.get_last_update_message() or "Update check done", 5.0)
            elif key == "menu:settings":
                if AISIDEBAR_OT_viewport_hud.load_settings_snapshot(context):
                    overlay_state.settings_test = {"state": "idle", "msg": ""}
                    overlay_state.panel = "settings"
                else:
                    overlay_state.set_toast("Settings unavailable: add-on not installed")
            elif key.startswith("hist:copy:"):
                ops.copy_turn_response(turn_id=key[len("hist:copy:"):])
                overlay_state.set_toast("Response copied")
            elif key.startswith("hist:tool:"):
                turn_id, idx = key[len("hist:tool:"):].rsplit(":", 1)
                turn = next((t for t in overlay_state.history if t["turn_id"] == turn_id), None)
                tool = turn["tools"][int(idx)] if turn else None
                if tool:
                    ops.copy_tool_details(
                        tool_name=tool["tool_name"], status=tool["status"], summary=tool["summary"]
                    )
                    overlay_state.set_toast("Tool copied")
        except Exception as exc:
            _logger.exception("HUD action failed: %s", key)
            overlay_state.set_toast(f"Failed: {str(exc).splitlines()[0][:48]}")

    def submit_current_prompt(self):
        """Submit the prompt to AgentRuntime."""
        prompt = overlay_state.prompt_text.strip()
        if not prompt:
            return
        try:
            from ... import get_runtime
            runtime = get_runtime()
            if runtime:
                # Keep the submitted user turn visible after the input buffer
                # is cleared, so a failed/slow request is not mistaken for a
                # click that never reached the runtime.
                # Keep the active turn's user card stable. A prompt submitted
                # while another turn is running appears in the separate FIFO
                # queue card instead of replacing the active card.
                if runtime.current_turn_id is None:
                    overlay_state.last_prompt_text = prompt
                overlay_state.reset_input()
                overlay_state.is_processing = True
                overlay_state.status_text = "PROCESSING"
                overlay_state.response_scroll = 0
                overlay_state.last_response_text = ""
                overlay_state.streaming_response_text = ""
                overlay_state.task_plan = None
                runtime.submit_prompt(prompt)
        except Exception as exc:
            _logger.exception("HUD prompt submission failed")
            overlay_state.is_processing = False
            overlay_state.status_text = "ERROR"
            overlay_state.last_response_text = f"Error: {exc}"

    def cancel_current_turn(self):
        """Cancel active agent operation."""
        try:
            from ... import get_runtime
            runtime = get_runtime()
            if runtime:
                runtime.cancel_current_turn()
                overlay_state.pending_approval = None
                overlay_state.is_processing = False
                overlay_state.status_text = "IDLE"
        except Exception as exc:
            _logger.exception("HUD turn cancellation failed")
            overlay_state.is_processing = False
            overlay_state.status_text = "ERROR"
            overlay_state.last_response_text = f"Cancel failed: {exc}"

    def approve_pending_action(self, approval_id: str):
        """Approve the pending action on the active agent runtime."""
        try:
            from ... import get_runtime
            runtime = get_runtime()
            if runtime:
                if approval_id.startswith("plan_") and hasattr(runtime, "approve_plan"):
                    try:
                        runtime.approve_plan(approval_id)
                    except Exception:
                        runtime.approve(approval_id)
                else:
                    runtime.approve(approval_id)
                overlay_state.pending_approval = None
        except Exception as exc:
            _logger.exception("HUD approval failed for %s", approval_id)
            overlay_state.status_text = "ERROR"
            overlay_state.last_response_text = f"Approval failed: {exc}"

    def reject_pending_action(self, approval_id: str):
        """Reject the pending action on the active agent runtime."""
        try:
            from ... import get_runtime
            runtime = get_runtime()
            if runtime:
                if approval_id.startswith("plan_") and hasattr(runtime, "reject_plan"):
                    try:
                        runtime.reject_plan(approval_id)
                    except Exception:
                        runtime.reject(approval_id)
                else:
                    runtime.reject(approval_id)
                overlay_state.pending_approval = None
        except Exception as exc:
            _logger.exception("HUD rejection failed for %s", approval_id)
            overlay_state.status_text = "ERROR"
            overlay_state.last_response_text = f"Rejection failed: {exc}"


CLASSES = (
    AISIDEBAR_OT_viewport_hud,
)


def register_modal():
    for cls in CLASSES:
        try:
            bpy.utils.register_class(cls)
        except (ValueError, RuntimeError):
            pass


def unregister_modal():
    global _active_modal_operator
    if _active_modal_operator:
        try:
            _active_modal_operator.cleanup(bpy.context)
        except Exception:
            pass
    for cls in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(cls)
        except (ValueError, RuntimeError):
            pass
