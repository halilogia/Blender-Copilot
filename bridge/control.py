"""Starts and stops the MCP bridge inside Blender (or in a headless script).

The only Blender-aware part of the bridge: it registers a ``bpy.app.timers`` callback that pumps the
main-thread executor. Headless scripts call ``run_headless`` instead (no timers run in --background).
"""

import time
from pathlib import Path
from typing import Any, Callable, Optional

from bridge import protocol
from bridge.http_server import BridgeServer
from bridge.main_thread import MainThreadExecutor
from bridge.settings import BridgeSettings, ensure_token, load_settings, save_settings
from bridge.tool_host import INSTRUCTIONS, RegistryToolHost

PUMP_INTERVAL = 0.02
VERSION = "1.2.0"


class BridgeController:
    def __init__(self, registry: Any, adapter: Any, settings_path: Path, version: str = VERSION):
        self.registry = registry
        self.adapter = adapter
        self.settings_path = Path(settings_path)
        self.version = version
        self.settings: BridgeSettings = load_settings(self.settings_path)
        self.executor = MainThreadExecutor()
        self.server: Optional[BridgeServer] = None
        self._timer_ref: Optional[Callable[[], Optional[float]]] = None
        self.apply_settings_to_adapter()

    # -- settings ---------------------------------------------------------
    def apply_settings_to_adapter(self) -> None:
        try:
            self.adapter.export_dir = self.settings.export_dir
        except Exception:
            pass

    def update_settings(self, **changes: Any) -> None:
        for key, value in changes.items():
            if hasattr(self.settings, key):
                setattr(self.settings, key, value)
        save_settings(self.settings, self.settings_path)
        self.apply_settings_to_adapter()

    # -- lifecycle --------------------------------------------------------
    def is_running(self) -> bool:
        return self.server is not None and self.server.is_running()

    def start(self, port: Optional[int] = None) -> BridgeServer:
        if self.is_running():
            return self.server  # type: ignore[return-value]
        ensure_token(self.settings)
        host = RegistryToolHost(
            self.registry, self.adapter, submit=self.executor.submit,
            allow_gated=lambda: self.settings.allow_gated,
        )
        mcp = protocol.McpProtocol(host, server_version=self.version, instructions=INSTRUCTIONS)
        self.server = BridgeServer(mcp, self.settings.token, self.settings.port if port is None else port)
        self.settings.port = self.server.start()
        save_settings(self.settings, self.settings_path)
        self._register_timer()
        return self.server

    def stop(self) -> None:
        self._unregister_timer()
        if self.server is not None:
            self.server.stop()
            self.server = None

    def maybe_autostart(self) -> bool:
        if self.settings.enabled and not self.is_running():
            self.start()
            return True
        return False

    # -- main-thread pump -------------------------------------------------
    def _register_timer(self) -> None:
        try:
            import bpy
        except ImportError:
            return
        if not hasattr(bpy.app, "timers"):
            return

        def _tick() -> Optional[float]:
            self.executor.pump()
            return PUMP_INTERVAL if self.is_running() else None

        self._timer_ref = _tick
        if not bpy.app.timers.is_registered(_tick):
            bpy.app.timers.register(_tick, persistent=True)

    def _unregister_timer(self) -> None:
        if self._timer_ref is None:
            return
        try:
            import bpy
            if bpy.app.timers.is_registered(self._timer_ref):
                bpy.app.timers.unregister(self._timer_ref)
        except Exception:
            pass
        self._timer_ref = None

    def run_headless(self, seconds: Optional[float] = None, stop_file: Optional[Path] = None) -> None:
        """Serve requests from the main thread of a ``blender --background`` script until time is up or
        ``stop_file`` appears. bpy.app.timers do not fire in background mode, so this loop is the pump."""
        deadline = None if seconds is None else time.time() + seconds
        while (deadline is None or time.time() < deadline) and not (stop_file and Path(stop_file).exists()):
            self.executor.pump()
            time.sleep(0.005)


_controller: Optional[BridgeController] = None


def get_controller() -> Optional[BridgeController]:
    return _controller


def attach(registry: Any, adapter: Any, settings_path: Path, version: str = VERSION) -> BridgeController:
    """Create (or replace) the global controller. Does not start listening unless settings/env say so."""
    global _controller
    if _controller is not None:
        _controller.stop()
    _controller = BridgeController(registry, adapter, settings_path, version)
    _controller.maybe_autostart()
    return _controller


def detach() -> None:
    global _controller
    if _controller is not None:
        _controller.stop()
        _controller = None
