"""Headless integration tests for v1.1 Track A2: AgentRuntime + Anthropic native
provider + live tool round-trip inside Blender.

Verifies inside live headless Blender:
USER
  -> AgentRuntime
  -> AnthropicCompatibleProvider (POST /v1/messages against local fake server)
  -> tool_use (inspect_scene) reassembled via shared ToolCallAccumulator
  -> ToolDispatcher (real bpy execution on Blender main thread)
  -> ToolResult -> Conversation
  -> 2nd provider call (tool_result) -> FINAL text synthesis

Zero external network dependencies. Runs against local ephemeral HTTP fake server
speaking the Anthropic Messages SSE dialect.
"""

import http.server
import json
import os
import sys
import threading
import time

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import bpy  # noqa: F401 (ensures Blender runtime context)
import importlib.util

init_path = os.path.join(PROJECT_ROOT, "__init__.py")
spec = importlib.util.spec_from_file_location(
    "blender_ai_sidebar",
    init_path,
    submodule_search_locations=[PROJECT_ROOT],
)
blender_ai_sidebar = importlib.util.module_from_spec(spec)
sys.modules["blender_ai_sidebar"] = blender_ai_sidebar
spec.loader.exec_module(blender_ai_sidebar)

from adapter.blender_adapter import BlenderAdapter
from agent.anthropic_provider import AnthropicCompatibleProvider
from agent.dispatcher import ToolDispatcher
from agent.runtime import AgentRuntime
from agent.state_machine import AgentState
from core.config import Config
from core.event_queue import ThreadSafeEventQueue
from tools.read_only.inspect_scene import InspectSceneTool
from ui.timer_bridge import TimerBridge


# -----------------------------------------------------------------------------
# Local Fake Anthropic Messages Server for Blender Headless Testing
# -----------------------------------------------------------------------------

class FakeAnthropicHandler(http.server.BaseHTTPRequestHandler):
    """Responds with Anthropic Messages SSE events for an inspect_scene round-trip."""

    request_history = []
    header_history = []
    lock = threading.Lock()

    def log_message(self, format, *args):
        pass

    def do_POST(self):
        assert self.path.endswith("/messages"), f"Unexpected path: {self.path}"
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length) if length > 0 else b""
        req = json.loads(raw.decode("utf-8")) if raw else {}

        with self.lock:
            FakeAnthropicHandler.request_history.append(req)
            FakeAnthropicHandler.header_history.append(dict(self.headers))

        messages = req.get("messages", [])
        # Tool result received? -> final text synthesis.
        got_tool_result = any(
            isinstance(m.get("content"), list)
            and any(isinstance(b, dict) and b.get("type") == "tool_result" for b in m["content"])
            for m in messages
            if isinstance(m, dict)
        )
        if got_tool_result:
            n_objects = 0
            for m in messages:
                for b in (m.get("content") or []):
                    if isinstance(b, dict) and b.get("type") == "tool_result":
                        try:
                            payload = json.loads(b.get("content", "{}"))
                            n_objects = payload.get("counts", {}).get("total", 0)
                        except Exception:
                            pass
            text = f"Sahne Anthropic ile incelendi. Toplam {n_objects} nesne mevcut."
            self._send_sse([
                ("message_start", {"type": "message_start",
                                   "message": {"id": "msg_final", "usage": {"input_tokens": 5}}}),
                ("content_block_delta", {"type": "content_block_delta", "index": 0,
                                         "delta": {"type": "text_delta", "text": text}}),
                ("message_delta", {"type": "message_delta",
                                   "delta": {"stop_reason": "end_turn"},
                                   "usage": {"output_tokens": 4}}),
                ("message_stop", {"type": "message_stop"}),
            ])
            return

        # First turn: user asks in Turkish -> tool_use inspect_scene.
        user_text = ""
        for m in messages:
            if m.get("role") == "user":
                c = m.get("content")
                user_text += c if isinstance(c, str) else json.dumps(c)
        if "Sahneyi incele" in user_text:
            self._send_sse([
                ("message_start", {"type": "message_start", "message": {"id": "msg_1"}}),
                ("content_block_start", {"type": "content_block_start", "index": 0,
                                         "content_block": {"type": "tool_use", "id": "toolu_b3d_01",
                                                           "name": "inspect_scene"}}),
                ("content_block_delta", {"type": "content_block_delta", "index": 0,
                                         "delta": {"type": "input_json_delta",
                                                   "partial_json": "{}"}}),
                ("message_delta", {"type": "message_delta",
                                   "delta": {"stop_reason": "tool_use"}}),
                ("message_stop", {"type": "message_stop"}),
            ])
        else:
            self._send_sse([
                ("message_start", {"type": "message_start", "message": {"id": "msg_x"}}),
                ("content_block_delta", {"type": "content_block_delta", "index": 0,
                                         "delta": {"type": "text_delta",
                                                   "text": "Anthropic hazir."}}),
                ("message_delta", {"type": "message_delta",
                                   "delta": {"stop_reason": "end_turn"}}),
                ("message_stop", {"type": "message_stop"}),
            ])

    def _send_sse(self, events):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        for etype, payload in events:
            self.wfile.write(f"event: {etype}\ndata: {json.dumps(payload)}\n\n".encode("utf-8"))
            self.wfile.flush()


def pump_timer_until_idle(bridge: TimerBridge, runtime: AgentRuntime, timeout: float = 5.0) -> bool:
    """Pump timer ticks on the Blender main thread until the agent reaches IDLE or times out."""
    start = time.perf_counter()
    while time.perf_counter() - start < timeout:
        bridge.tick()
        if runtime.current_state in (AgentState.IDLE, AgentState.ERROR) and runtime.current_turn_id is None:
            return True
        time.sleep(0.01)
    return False


def run_tests():
    print("\n=== STARTING v1.1 ANTHROPIC ROUND-TRIP HEADLESS INTEGRATION TEST ===")

    server = http.server.HTTPServer(("127.0.0.1", 0), FakeAnthropicHandler)
    port = server.server_port
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    try:
        registry = __import__("tools.registry", fromlist=["ToolRegistry"]).ToolRegistry()
        registry.register(InspectSceneTool())

        adapter = BlenderAdapter()
        dispatcher = ToolDispatcher(registry=registry, adapter=adapter)

        config = Config(
            base_url=f"http://127.0.0.1:{port}/v1",
            model="claude-b3d-test",
            api_key="b3d-anthropic-key",
            timeout_seconds=5.0,
            provider="anthropic",
        )
        provider = AnthropicCompatibleProvider(config=config)

        queue = ThreadSafeEventQueue()
        runtime = AgentRuntime(provider=provider, dispatcher=dispatcher, event_queue=queue)
        bridge = TimerBridge(runtime=runtime, event_queue=queue)

        # ---------------------------------------------------------------------
        # TEST 1: Anthropic tool_use round-trip (inspect_scene on live scene)
        # ---------------------------------------------------------------------
        print("Running Test 1: Anthropic inspect_scene round-trip...")
        FakeAnthropicHandler.request_history.clear()
        FakeAnthropicHandler.header_history.clear()

        runtime.submit_prompt("Sahneyi incele")
        assert runtime.current_state == AgentState.PROCESSING

        done = pump_timer_until_idle(bridge, runtime, timeout=5.0)
        assert done, "Timeout waiting for Test 1 to complete"
        assert runtime.current_state == AgentState.IDLE
        assert runtime.last_result is not None

        # Real tool executed on live Blender scene
        assert len(runtime.last_result.tool_results) == 1
        tr = runtime.last_result.tool_results[0]
        assert tr.success is True
        assert tr.tool == "inspect_scene"
        assert tr.data["scene_name"] == "Scene"
        assert tr.data["counts"]["total"] >= 3

        # tool_use reassembly produced the right call (recorded in conversation;
        # provider.last_tool_calls reflects only the final text-only turn)
        assistant_calls = [tc for m in runtime.conversation.messages
                           if m.role.value == "assistant" and m.tool_calls
                           for tc in m.tool_calls]
        assert len(assistant_calls) == 1
        assert assistant_calls[0].tool_name == "inspect_scene"
        assert assistant_calls[0].arguments == {}

        # Final synthesis used the real tool result
        assert "Sahne Anthropic ile incelendi" in runtime.last_result.final_text
        assert str(tr.data["counts"]["total"]) in runtime.last_result.final_text

        # Exactly 2 Messages API requests
        assert len(FakeAnthropicHandler.request_history) == 2
        for body in FakeAnthropicHandler.request_history:
            assert body["model"] == "claude-b3d-test"
            assert "system" in body

        # Native auth + version headers (case-insensitive)
        low = {k.lower(): v for k, v in FakeAnthropicHandler.header_history[0].items()}
        assert low.get("x-api-key") == "b3d-anthropic-key"
        assert low.get("anthropic-version") == "2023-06-01"

        runtime.conversation.validate_sequence()
        print("[PASS] Test 1: Anthropic inspect_scene round-trip verified.")

        # ---------------------------------------------------------------------
        # TEST 2: Cleanup and shutdown
        # ---------------------------------------------------------------------
        runtime.shutdown()
        print("[PASS] Test 2: Clean runtime shutdown verified.")

        print("=== v1.1 ANTHROPIC ROUND-TRIP TEST COMPLETED SUCCESSFULLY ===\n")

    finally:
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    try:
        run_tests()
    except Exception as exc:
        import traceback
        traceback.print_exc()
        sys.exit(1)
