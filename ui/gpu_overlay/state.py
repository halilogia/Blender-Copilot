"""State container for Blender AI Sidebar In-Viewport GPU Overlay."""

import time
from typing import Optional, Tuple, List, Dict, Any


class GPUOverlayState:
    """Manages input buffer, layout bounding boxes, cursor, and animation state."""

    def __init__(self):
        self.is_open: bool = False
        self.prompt_text: str = ""
        self.cursor_pos: int = 0
        self.cursor_visible: bool = True
        self.last_blink_time: float = time.time()
        self.blink_interval: float = 0.5  # 500ms

        # Bounding boxes (x, y, w, h) in viewport region pixel coordinates
        self.bar_rect: Tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)
        self.input_rect: Tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)
        self.send_btn_rect: Tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)
        self.cancel_btn_rect: Tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)

        # Hover states
        self.hover_element: Optional[str] = None  # 'send', 'cancel', 'input', None

        # Display caches
        self.status_text: str = "Ready"
        self.is_processing: bool = False
        self.active_tool_name: Optional[str] = None
        self.last_prompt_text: str = ""
        self.last_response_text: str = ""
        self.streaming_response_text: str = ""
        self.response_copy_btn_rect: Tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)
        self.task_plan: Optional[Dict[str, Any]] = None
        self.queued_prompts: List[Dict[str, Any]] = []

        # Approval Card Bounding Boxes and State
        self.pending_approval: Optional[Dict[str, Any]] = None
        self.approval_card_rect: Tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)
        self.reject_btn_rect: Tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)
        self.approve_btn_rect: Tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)

        # Generic clickable regions rebuilt on every draw: action key -> rect.
        # Later entries are drawn on top, so hit testing walks them in reverse.
        self.buttons: Dict[str, Tuple[float, float, float, float]] = {}

        # Which drawer sits above the prompt bar: None (conversation), "menu" or "history".
        self.panel: Optional[str] = None

        # Cached runtime data mirrored by the modal timer (see modal.sync_extras).
        self.history: List[Dict[str, Any]] = []
        self.task_open_steps: int = 0
        self.plan_title: str = ""
        self.mcp: Dict[str, Any] = {"available": False, "running": False, "endpoint": "", "token": "", "allow_gated": False}
        self.model_label: str = ""
        self.log_path: str = ""

        # Response drawer scrolling (wheel): first visible line, and the largest valid value.
        self.response_scroll: int = 0
        self.response_max_scroll: int = 0

        # Settings drawer: snapshot of the add-on preferences, the field being typed into,
        # and the last connection-test result ({"state": idle|running|ok|fail, "msg": str}).
        self.settings_values: Dict[str, Any] = {}
        self.settings_editor: Any = None
        self.settings_test: Dict[str, str] = {"state": "idle", "msg": ""}
        self.online_access: bool = True

        # Short confirmation text ("Copied") shown in the status pill for a moment.
        self.toast: str = ""
        self.toast_until: float = 0.0

    def set_toast(self, text: str, seconds: float = 2.5) -> None:
        """Show a short confirmation in the status pill."""
        self.toast = text
        self.toast_until = time.time() + seconds

    def active_toast(self) -> str:
        """Return the toast text while it is still fresh, else an empty string."""
        if self.toast and time.time() < self.toast_until:
            return self.toast
        return ""

    def scroll_response(self, lines: int) -> bool:
        """Move the response view by `lines` (positive = down). True when the view moved."""
        new = max(0, min(self.response_max_scroll, self.response_scroll + lines))
        moved = new != self.response_scroll
        self.response_scroll = new
        return moved

    def toggle_panel(self, name: str) -> None:
        """Open the named drawer, or close it when it is already open."""
        self.panel = None if self.panel == name else name
        self.settings_editor = None  # never keep typing into a field of a drawer that closed

    def reset_input(self) -> None:
        """Clear prompt input buffer and reset cursor."""
        self.prompt_text = ""
        self.cursor_pos = 0
        self.cursor_visible = True
        self.last_blink_time = time.time()

    def update_blink(self) -> bool:
        """Toggle cursor visibility based on timer; returns True if state changed."""
        now = time.time()
        if now - self.last_blink_time >= self.blink_interval:
            self.cursor_visible = not self.cursor_visible
            self.last_blink_time = now
            return True
        return False

    def insert_text(self, text: str) -> None:
        """Insert arbitrary text at the current cursor position."""
        if not text:
            return
        left = self.prompt_text[:self.cursor_pos]
        right = self.prompt_text[self.cursor_pos:]
        self.prompt_text = left + text + right
        self.cursor_pos += len(text)
        self.cursor_visible = True
        self.last_blink_time = time.time()

    def delete_backward(self) -> None:
        """Delete one character before the cursor (Backspace)."""
        if self.cursor_pos > 0:
            left = self.prompt_text[:self.cursor_pos - 1]
            right = self.prompt_text[self.cursor_pos:]
            self.prompt_text = left + right
            self.cursor_pos -= 1
            self.cursor_visible = True
            self.last_blink_time = time.time()

    def delete_word_backward(self) -> None:
        """Delete one word before cursor (Ctrl+Backspace)."""
        if self.cursor_pos > 0:
            left = self.prompt_text[:self.cursor_pos].rstrip()
            last_space = left.rfind(" ")
            new_pos = last_space + 1 if last_space != -1 else 0
            right = self.prompt_text[self.cursor_pos:]
            self.prompt_text = self.prompt_text[:new_pos] + right
            self.cursor_pos = new_pos
            self.cursor_visible = True
            self.last_blink_time = time.time()

    def delete_forward(self) -> None:
        """Delete one character after the cursor (Delete)."""
        if self.cursor_pos < len(self.prompt_text):
            left = self.prompt_text[:self.cursor_pos]
            right = self.prompt_text[self.cursor_pos + 1:]
            self.prompt_text = left + right
            self.cursor_visible = True
            self.last_blink_time = time.time()

    def move_cursor_left(self) -> None:
        """Move cursor one character to the left."""
        if self.cursor_pos > 0:
            self.cursor_pos -= 1
            self.cursor_visible = True
            self.last_blink_time = time.time()

    def move_cursor_right(self) -> None:
        """Move cursor one character to the right."""
        if self.cursor_pos < len(self.prompt_text):
            self.cursor_pos += 1
            self.cursor_visible = True
            self.last_blink_time = time.time()

    def move_cursor_home(self) -> None:
        """Move cursor to the start of the line."""
        self.cursor_pos = 0
        self.cursor_visible = True
        self.last_blink_time = time.time()

    def move_cursor_end(self) -> None:
        """Move cursor to the end of the line."""
        self.cursor_pos = len(self.prompt_text)
        self.cursor_visible = True
        self.last_blink_time = time.time()

    @staticmethod
    def _inside(rect: Tuple[float, float, float, float], px: float, py: float) -> bool:
        """Point-in-rect that ignores unused (zero-size) rects, which would otherwise match (0, 0)."""
        x, y, w, h = rect
        return w > 0 and h > 0 and x <= px <= x + w and y <= py <= y + h

    def hit_test(self, px: float, py: float) -> Optional[str]:
        """Determine which UI element (if any) contains the point (px, py)."""
        # Check Approval Card elements if pending approval is active
        if self.pending_approval:
            if self._inside(self.approve_btn_rect, px, py):
                return "approve"

            if self._inside(self.reject_btn_rect, px, py):
                return "reject"

            if self._inside(self.approval_card_rect, px, py):
                return "approval_card"

        for key in reversed(list(self.buttons)):
            if self._inside(self.buttons[key], px, py):
                return key

        if self._inside(self.response_copy_btn_rect, px, py):
            return "copy_response"

        bx, by, bw, bh = self.bar_rect
        if not (bx <= px <= bx + bw and by <= py <= by + bh):
            return None

        # Check send / cancel button
        if self._inside(self.send_btn_rect, px, py):
            return "send"

        if self._inside(self.cancel_btn_rect, px, py):
            return "cancel"

        if self._inside(self.input_rect, px, py):
            return "input"

        return "bar"


# Global singleton instance
overlay_state = GPUOverlayState()
