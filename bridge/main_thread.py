"""Runs callables on Blender's main thread (bpy is not thread safe).

HTTP handler threads call ``submit``; Blender's main thread drains the queue with ``pump`` (registered as a
``bpy.app.timers`` callback by control.py; headless scripts call it in a loop). Zero Blender dependencies.
"""

import queue
import threading
from typing import Any, Callable, Optional


class MainThreadExecutor:
    def __init__(self, main_thread: Optional[threading.Thread] = None):
        self._queue: "queue.Queue" = queue.Queue()
        self._main = main_thread or threading.main_thread()

    def submit(self, fn: Callable[[], Any], timeout: float = 60.0) -> Any:
        """Run ``fn`` on the main thread and return its value (re-raises its exception)."""
        if threading.current_thread() is self._main:
            return fn()
        done = threading.Event()
        box: dict = {}
        self._queue.put((fn, done, box))
        if not done.wait(timeout):
            box["abandoned"] = True
            raise TimeoutError(f"main thread did not run the call within {timeout} s")
        if "exc" in box:
            raise box["exc"]
        return box.get("value")

    def pump(self, max_items: int = 8) -> int:
        """Run queued calls (main thread only). Returns how many ran."""
        ran = 0
        while ran < max_items:
            try:
                fn, done, box = self._queue.get_nowait()
            except queue.Empty:
                break
            if not box.get("abandoned"):
                try:
                    box["value"] = fn()
                except BaseException as exc:  # noqa: BLE001 - handed back to the waiting thread
                    box["exc"] = exc
            done.set()
            ran += 1
        return ran

    def pending(self) -> int:
        return self._queue.qsize()
