"""Main-thread timer consumer bridging bpy.app.timers with AgentRuntime.

Drains ThreadSafeEventQueue on the main thread, dispatches events to runtime,
updates WindowManager UI properties, and tags 3D Viewport areas for redraw.
"""

from typing import Optional
import bpy

from core.event_queue import ThreadSafeEventQueue
from agent.runtime import AgentRuntime
from core.logging_utils import get_logger
from .text_formatting import clean_assistant_text


_logger = get_logger("timer_bridge")


class TimerBridge:
    """Bridges Blender's main-thread timer loop with the asynchronous AgentRuntime."""

    def __init__(
        self,
        runtime: AgentRuntime,
        event_queue: ThreadSafeEventQueue,
        poll_interval: float = 0.02,
        max_events_per_tick: int = 10,
        max_tick_seconds: float = 0.005,
    ):
        self.runtime = runtime
        self.event_queue = event_queue
        self.poll_interval = poll_interval
        self.max_events_per_tick = max_events_per_tick
        self.max_tick_seconds = max_tick_seconds
        self._is_active = False
        # Store persistent bound method reference because bound method creation produces new objects
        self._callback_ref = self._timer_callback

    @property
    def is_active(self) -> bool:
        """Check if timer bridge is actively running."""
        return self._is_active

    def register(self) -> bool:
        """Register timer callback in bpy.app.timers."""
        if self._is_active:
            return False

        self._is_active = True
        if hasattr(bpy.app, "timers") and not bpy.app.timers.is_registered(self._callback_ref):
            bpy.app.timers.register(self._callback_ref, persistent=True)
        return True

    def unregister(self) -> bool:
        """Unregister timer callback from bpy.app.timers."""
        self._is_active = False
        if hasattr(bpy.app, "timers") and bpy.app.timers.is_registered(self._callback_ref):
            try:
                bpy.app.timers.unregister(self._callback_ref)
            except ValueError:
                pass
        return True

    def tick(self) -> int:
        """Process one bounded batch of queued events on the main thread.

        Can be called directly by headless tests or automatically by bpy.app.timers.

        Returns:
            Number of events processed in this tick.
        """
        events = self.event_queue.drain_batch(
            max_items=self.max_events_per_tick,
            max_time_sec=self.max_tick_seconds,
        )

        state_changed = False
        for event in events:
            old_state = self.runtime.current_state
            self.runtime.process_event(event)
            if self.runtime.current_state != old_state:
                state_changed = True

        # A completed/cancelled turn clears current_turn_id during event
        # processing. Start the oldest queued user message only after all
        # events in this tick have been applied to main-thread state.
        if hasattr(self.runtime, "pump_prompt_queue"):
            queued_turn = self.runtime.pump_prompt_queue()
            if queued_turn:
                state_changed = True

        # Sync runtime state to Blender UI WindowManager properties
        self._sync_ui_properties()

        # Tag 3D Viewport areas for redraw if state changed or events arrived
        self.tag_redraw_view3d()

        return len(events) + (1 if state_changed and not events else 0)

    def _timer_callback(self) -> Optional[float]:
        """Internal callback invoked by Blender's main event loop."""
        if not self._is_active:
            return None

        try:
            self.tick()
        except Exception:
            _logger.exception("TimerBridge callback failed")
        return self.poll_interval

    def _sync_ui_properties(self) -> None:
        """Update WindowManager session properties on the main thread."""
        try:
            wm = getattr(bpy.context, "window_manager", None)
            if not wm or not hasattr(wm, "ai_sidebar"):
                return

            props = wm.ai_sidebar
            snapshot = self.runtime.snapshot() if hasattr(self.runtime, "snapshot") else None
            state = self.runtime.current_state
            props.agent_status = snapshot.state if snapshot else state.value

            # 1. Action description
            if state.value == "IDLE":
                props.current_action = "Ready"
            elif state.value == "PROCESSING":
                props.current_action = "Thinking..."
            elif state.value == "PENDING_APPROVAL":
                pending = getattr(self.runtime, "pending_approval", None)
                props.current_action = f"Approval Required: {pending.tool_name}" if pending else "Approval Required"
            elif state.value == "EXECUTING_TOOL":
                props.current_action = "Running tool..."
            elif state.value == "ERROR":
                props.current_action = "Error encountered"

            # 2. Last result summary
            if snapshot and snapshot.last_response_text:
                props.last_result_summary = clean_assistant_text(snapshot.last_response_text)[:120]
            elif self.runtime.last_result:
                props.last_result_summary = clean_assistant_text(self.runtime.last_result.final_text)[:120]
            props.live_streaming_text = snapshot.streaming_text if snapshot else getattr(self.runtime, "streaming_text", "")
            if hasattr(props, "queued_count"):
                props.queued_count = snapshot.queued_count if snapshot else len(getattr(self.runtime, "queued_prompts", []))

            # 3. Synchronize history items from RuntimeHistory to UIList collection
            if hasattr(self.runtime, "history"):
                py_items = self.runtime.history.items
                if len(props.history) > len(py_items) or (
                    len(props.history) > 0 and len(py_items) > 0 and props.history[0].item_id != py_items[0].item_id
                ):
                    props.history.clear()
                    props.history_index = -1

                if len(py_items) == 0 and len(props.history) > 0:
                    props.history.clear()
                    props.history_index = -1
                elif len(props.history) < len(py_items):
                    was_at_end = (props.history_index == len(props.history) - 1) or (props.history_index == -1)
                    while len(props.history) < len(py_items):
                        idx = len(props.history)
                        src = py_items[idx]
                        dst = props.history.add()
                        dst.item_id = src.item_id
                        dst.turn_id = src.turn_id
                        dst.kind = src.kind
                        dst.title = src.title
                        dst.status = src.status
                        dst.summary = src.summary
                    if was_at_end:
                        props.history_index = len(props.history) - 1

                # Existing entries can change QUEUED -> RUNNING -> terminal;
                # keep the Blender collection synchronized instead of only
                # appending new rows.
                for idx, src in enumerate(py_items):
                    if idx >= len(props.history):
                        break
                    dst = props.history[idx]
                    dst.item_id = src.item_id
                    dst.turn_id = src.turn_id
                    dst.kind = src.kind
                    dst.title = src.title
                    dst.status = src.status
                    dst.summary = src.summary

            # 4. Synchronize V2 Timeline and Active Turn presentation
            if snapshot:
                # Active in-flight turn
                if snapshot.active_turn is not None:
                    active = snapshot.active_turn
                    props.has_active_turn = True
                    props.active_turn_id = active.turn_id
                    props.active_prompt = active.prompt
                    props.active_streaming_response = clean_assistant_text(active.streaming_response)
                    props.active_status = active.status.value if hasattr(active.status, "value") else str(active.status)
                    props.active_error = active.error_message or ""
                    self._sync_tool_collection(props.active_tools, active.tool_executions)
                else:
                    props.has_active_turn = False
                    props.active_turn_id = ""
                    props.active_prompt = ""
                    props.active_streaming_response = ""
                    props.active_status = ""
                    props.active_error = ""
                    if len(props.active_tools) > 0:
                        props.active_tools.clear()

                # Completed timeline turns (up to last 15 turns for performance)
                if hasattr(snapshot, "timeline"):
                    recent_turns = list(snapshot.timeline[-15:])
                    if len(props.timeline) > len(recent_turns) or (
                        len(props.timeline) > 0 and len(recent_turns) > 0 and props.timeline[0].turn_id != recent_turns[0].turn_id
                    ):
                        props.timeline.clear()
                    while len(props.timeline) < len(recent_turns):
                        props.timeline.add()
                    for idx, src_turn in enumerate(recent_turns):
                        dst_turn = props.timeline[idx]
                        dst_turn.turn_id = src_turn.turn_id
                        dst_turn.prompt = src_turn.prompt
                        dst_turn.status = src_turn.status.value if hasattr(src_turn.status, "value") else str(src_turn.status)
                        dst_turn.final_response = clean_assistant_text(src_turn.final_response)
                        dst_turn.error_message = src_turn.error_message or ""
                        self._sync_tool_collection(dst_turn.tools, src_turn.tool_executions)

                # Plan summary projection
                if snapshot.last_plan_summary:
                    props.plan_title = str(snapshot.last_plan_summary.get("title", "") or "")
                    props.plan_status = str(snapshot.last_plan_summary.get("status", "") or "")
                    steps = snapshot.last_plan_summary.get("step_results") or []
                    total = snapshot.last_plan_summary.get("steps_total", 0)
                    props.plan_steps_summary = f"{len(steps)}/{total} steps" if total else f"{len(steps)} steps"
                else:
                    props.plan_title = ""
                    props.plan_status = ""
                    props.plan_steps_summary = ""
        except Exception:
            _logger.exception("Failed to synchronize Blender UI properties")


    @staticmethod
    def _sync_tool_collection(dst_coll, src_tools) -> None:
        """Synchronize a collection property of tools with lightweight tool view objects."""
        if len(dst_coll) > len(src_tools):
            dst_coll.clear()
        while len(dst_coll) < len(src_tools):
            dst_coll.add()
        for i, t in enumerate(src_tools):
            item = dst_coll[i]
            item.tool_name = t.tool_name
            item.status = t.status
            item.summary = t.summary
            item.error_message = t.error_message or ""

    @staticmethod
    def tag_redraw_view3d() -> None:
        """Safely tag all visible 3D Viewports for redraw on the main thread."""
        try:
            wm = getattr(bpy.context, "window_manager", None)
            if not wm:
                return
            for window in wm.windows:
                screen = window.screen
                if not screen:
                    continue
                for area in screen.areas:
                    if area.type == "VIEW_3D":
                        area.tag_redraw()
        except Exception:
            _logger.exception("Failed to tag 3D Viewport areas for redraw")
