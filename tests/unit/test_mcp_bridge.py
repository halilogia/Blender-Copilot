"""Unit tests for the MCP bridge: protocol, tool host gating, main-thread executor and the loopback HTTP server.

Pure Python. Zero Blender (bpy) dependencies.
"""

import base64
import json
import threading
import time
import unittest
import urllib.error
import urllib.request

from bridge import protocol
from bridge.http_server import BridgeServer
from bridge.main_thread import MainThreadExecutor
from bridge.tool_host import RegistryToolHost
from core.types import RiskLevel, ToolResult
from tools.base import BaseTool
from tools.registry import ToolRegistry


class _ReadTool(BaseTool):
    name = "zeta_read"
    description = "read"
    input_schema = {"type": "object", "properties": {}}
    risk_level = RiskLevel.READ_ONLY

    def execute(self, adapter, **kwargs):
        return ToolResult.ok(self.name, {"echo": "ansi \x1b[31mred\x1b[0m\x07 ok"})


class _MakeTool(BaseTool):
    name = "alpha_make"
    description = "make"
    input_schema = {"type": "object", "properties": {"n": {"type": "integer"}}, "required": ["n"], "additionalProperties": False}
    risk_level = RiskLevel.LOW

    def execute(self, adapter, **kwargs):
        return ToolResult.ok(self.name, {"n": kwargs["n"]})


class _DeleteTool(BaseTool):
    name = "mid_delete"
    description = "delete"
    input_schema = {"type": "object", "properties": {}}
    risk_level = RiskLevel.MEDIUM

    def execute(self, adapter, **kwargs):
        return ToolResult.ok(self.name, {"deleted": True})


class _ShotTool(BaseTool):
    name = "shot"
    description = "shot"
    input_schema = {"type": "object", "properties": {}}
    risk_level = RiskLevel.READ_ONLY

    def execute(self, adapter, **kwargs):
        return ToolResult.ok(self.name, {"image_id": "vp_1", "width": 4})


class _Adapter:
    def get_image_bytes(self, image_id):
        return b"\x89PNGfake" if image_id == "vp_1" else None


def _host(allow_gated=False):
    registry = ToolRegistry()
    for tool in (_ReadTool(), _MakeTool(), _DeleteTool(), _ShotTool()):
        registry.register(tool)
    return RegistryToolHost(registry, _Adapter(), submit=lambda fn, timeout=60.0: fn(), allow_gated=lambda: allow_gated)


def _rpc(method, params=None, msg_id=1):
    msg = {"jsonrpc": "2.0", "method": method}
    if msg_id is not None:
        msg["id"] = msg_id
    if params is not None:
        msg["params"] = params
    return msg


class TestProtocol(unittest.TestCase):
    def setUp(self):
        self.mcp = protocol.McpProtocol(_host(), server_version="1.2.3", instructions="hello")

    def test_discover_lists_versions_and_identity(self):
        res = self.mcp.handle(_rpc("server/discover"))["result"]
        self.assertEqual(res["supportedVersions"][0], "2026-07-28")
        self.assertEqual(res["resultType"], "complete")
        self.assertEqual(res["serverInfo"], {"name": "blender-copilot", "version": "1.2.3"})
        self.assertEqual(res["instructions"], "hello")

    def test_initialize_negotiates_supported_or_falls_back(self):
        ok = self.mcp.handle(_rpc("initialize", {"protocolVersion": "2025-11-25"}))["result"]
        self.assertEqual(ok["protocolVersion"], "2025-11-25")
        fallback = self.mcp.handle(_rpc("initialize", {"protocolVersion": "2099-01-01"}))["result"]
        self.assertEqual(fallback["protocolVersion"], protocol.DEFAULT_PROTOCOL_VERSION)

    def test_notification_has_no_reply_and_bad_requests_error(self):
        self.assertIsNone(self.mcp.handle(_rpc("notifications/initialized", msg_id=None)))
        self.assertEqual(self.mcp.handle([_rpc("ping")])["error"]["code"], protocol.ERR_INVALID_REQUEST)
        self.assertEqual(self.mcp.handle({"id": 1, "method": "ping"})["error"]["code"], protocol.ERR_INVALID_REQUEST)
        self.assertEqual(self.mcp.handle(_rpc("resources/list"))["error"]["code"], protocol.ERR_METHOD_NOT_FOUND)

    def test_unsupported_meta_version_is_rejected_with_supported_list(self):
        reply = self.mcp.handle(_rpc("tools/list", {"_meta": {protocol.META_VERSION: "2099-01-01"}}))
        self.assertEqual(reply["error"]["code"], protocol.ERR_UNSUPPORTED_VERSION)
        self.assertIn("2026-07-28", reply["error"]["data"]["supported"])

    def test_tools_list_is_sorted_annotated_and_cacheable(self):
        res = self.mcp.handle(_rpc("tools/list", {"_meta": {protocol.META_VERSION: "2026-07-28"}}))["result"]
        names = [t["name"] for t in res["tools"]]
        self.assertEqual(names, sorted(names))
        self.assertGreater(res["ttlMs"], 0)
        self.assertEqual(res["cacheScope"], "private")
        by_name = {t["name"]: t for t in res["tools"]}
        self.assertTrue(by_name["zeta_read"]["annotations"]["readOnlyHint"])
        self.assertFalse(by_name["alpha_make"]["annotations"]["readOnlyHint"])
        self.assertFalse(by_name["alpha_make"]["annotations"]["destructiveHint"])
        self.assertTrue(by_name["mid_delete"]["annotations"]["destructiveHint"])

    def test_tools_call_success_scrubs_text_and_carries_structured_content(self):
        res = self.mcp.handle(_rpc("tools/call", {"name": "zeta_read", "arguments": {}}))["result"]
        self.assertFalse(res["isError"])
        self.assertEqual(res["structuredContent"]["data"]["echo"], "ansi red ok")
        self.assertNotIn("\x1b", res["content"][0]["text"])
        self.assertEqual(res["resultType"], "complete")

    def test_tools_call_unknown_tool_and_schema_errors(self):
        self.assertEqual(self.mcp.handle(_rpc("tools/call", {"name": "nope"}))["error"]["code"], protocol.ERR_INVALID_PARAMS)
        missing = self.mcp.handle(_rpc("tools/call", {"name": "alpha_make", "arguments": {}}))["result"]
        self.assertTrue(missing["isError"])
        self.assertEqual(missing["structuredContent"]["error"]["type"], "INVALID_ARGUMENT")

    def test_screenshot_becomes_an_image_block(self):
        res = self.mcp.handle(_rpc("tools/call", {"name": "shot", "arguments": {}}))["result"]
        kinds = [c["type"] for c in res["content"]]
        self.assertEqual(kinds, ["text", "image"])
        self.assertEqual(base64.b64decode(res["content"][1]["data"]), b"\x89PNGfake")
        self.assertNotIn("image_base64", res["structuredContent"]["data"])

    def test_header_validation(self):
        call = _rpc("tools/call", {"name": "alpha_make"})
        self.assertIsNone(protocol.validate_headers(call, {"mcp-method": "tools/call", "mcp-name": "alpha_make", "mcp-protocol-version": "2026-07-28"}))
        self.assertEqual(protocol.validate_headers(_rpc("tools/list"), {"mcp-method": "tools/call"})["error"]["code"], protocol.ERR_HEADER_MISMATCH)
        self.assertEqual(protocol.validate_headers(call, {"mcp-name": "other"})["error"]["code"], protocol.ERR_HEADER_MISMATCH)
        self.assertEqual(protocol.validate_headers(call, {"mcp-protocol-version": "1999-01-01"})["error"]["code"], protocol.ERR_UNSUPPORTED_VERSION)
        self.assertIsNone(protocol.validate_headers(call, {}))


class TestGating(unittest.TestCase):
    def test_gated_tool_is_refused_unless_allowed(self):
        refused = _host(False).call_tool("mid_delete", {})
        self.assertFalse(refused["success"])
        self.assertEqual(refused["error"]["type"], "APPROVAL_REQUIRED")
        self.assertTrue(_host(True).call_tool("mid_delete", {})["success"])

    def test_excluded_tool_is_hidden(self):
        registry = ToolRegistry()
        registry.register(_ReadTool())
        host = RegistryToolHost(registry, _Adapter(), submit=lambda fn, timeout=60.0: fn(), exclude={"zeta_read"})
        self.assertFalse(host.has_tool("zeta_read"))
        self.assertEqual(host.list_tools(), [])

    def test_timeout_and_bridge_errors_are_reported_not_raised(self):
        registry = ToolRegistry()
        registry.register(_ReadTool())

        def slow(fn, timeout=60.0):
            raise TimeoutError("late")

        res = RegistryToolHost(registry, _Adapter(), submit=slow).call_tool("zeta_read", {})
        self.assertEqual(res["error"]["type"], "TIMEOUT")

        def boom(fn, timeout=60.0):
            raise RuntimeError("x")

        res = RegistryToolHost(registry, _Adapter(), submit=boom).call_tool("zeta_read", {})
        self.assertEqual(res["error"]["type"], "BRIDGE_ERROR")


class TestMainThreadExecutor(unittest.TestCase):
    def test_worker_thread_call_runs_on_the_pumping_thread(self):
        executor = MainThreadExecutor()
        seen = {}

        def worker():
            seen["value"] = executor.submit(lambda: threading.current_thread().name, timeout=5)

        t = threading.Thread(target=worker)
        t.start()
        deadline = time.time() + 5
        while t.is_alive() and time.time() < deadline:
            executor.pump()
            time.sleep(0.005)
        t.join()
        self.assertEqual(seen["value"], threading.current_thread().name)

    def test_exceptions_propagate_and_timeouts_abandon_the_call(self):
        executor = MainThreadExecutor()
        errors = []

        def worker():
            try:
                executor.submit(lambda: 1 / 0, timeout=5)
            except ZeroDivisionError as exc:
                errors.append(exc)

        t = threading.Thread(target=worker)
        t.start()
        while t.is_alive():
            executor.pump()
            time.sleep(0.005)
        t.join()
        self.assertEqual(len(errors), 1)

        ran = []
        late = threading.Thread(target=lambda: self.assertRaises(TimeoutError, executor.submit, lambda: ran.append(1), 0.05))
        late.start()
        late.join()
        executor.pump()
        self.assertEqual(ran, [])

    def test_main_thread_submit_runs_inline(self):
        self.assertEqual(MainThreadExecutor().submit(lambda: 7), 7)


class TestHttpServer(unittest.TestCase):
    TOKEN = "secret-token-123"

    def setUp(self):
        self.executor = MainThreadExecutor()
        registry = ToolRegistry()
        registry.register(_MakeTool())
        host = RegistryToolHost(registry, _Adapter(), submit=self.executor.submit)
        self.server = BridgeServer(protocol.McpProtocol(host, "9.9.9"), self.TOKEN, 0)
        self.port = self.server.start()
        self._stop = threading.Event()
        self._pump = threading.Thread(target=self._loop, daemon=True)
        self._pump.start()

    def tearDown(self):
        self._stop.set()
        self._pump.join(2)
        self.server.stop()

    def _loop(self):
        # The test thread is the "main thread" of this executor; pump from a helper that impersonates it.
        while not self._stop.is_set():
            self.executor.pump()
            time.sleep(0.005)

    def _post(self, body, headers=None, path="/mcp", method="POST"):
        data = body if isinstance(body, bytes) else json.dumps(body).encode("utf-8")
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}{path}", data=data if method == "POST" else None, method=method)
        req.add_header("Content-Type", "application/json")
        for k, v in (headers if headers is not None else {"Authorization": f"Bearer {self.TOKEN}"}).items():
            req.add_header(k, v)
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                raw = resp.read()
                return resp.status, (json.loads(raw) if raw else None)
        except urllib.error.HTTPError as err:
            raw = err.read()
            return err.code, (json.loads(raw) if raw else None)

    def test_auth_origin_method_and_path(self):
        self.assertEqual(self._post(_rpc("ping"), headers={})[0], 401)
        self.assertEqual(self._post(_rpc("ping"), headers={"Authorization": "Bearer wrong"})[0], 401)
        self.assertEqual(self._post(_rpc("ping"), headers={"Authorization": f"Bearer {self.TOKEN}", "Origin": "http://evil"})[0], 403)
        self.assertEqual(self._post(_rpc("ping"), path="/other")[0], 404)
        self.assertEqual(self._post(b"", method="GET")[0], 405)
        self.assertEqual(self._post(b"{not json")[0], 400)

    def test_happy_path_notification_and_header_mismatch(self):
        status, body = self._post(_rpc("server/discover"))
        self.assertEqual(status, 200)
        self.assertEqual(body["result"]["serverInfo"]["version"], "9.9.9")
        self.assertEqual(self._post(_rpc("notifications/initialized", msg_id=None))[0], 202)
        mismatch = {"Authorization": f"Bearer {self.TOKEN}", "Mcp-Method": "tools/call"}
        status, body = self._post(_rpc("tools/list"), headers=mismatch)
        self.assertEqual(status, 400)
        self.assertEqual(body["error"]["code"], protocol.ERR_HEADER_MISMATCH)

    def test_tool_call_runs_through_the_main_thread_executor(self):
        status, body = self._post(_rpc("tools/call", {"name": "alpha_make", "arguments": {"n": 5}}))
        self.assertEqual(status, 200)
        self.assertEqual(body["result"]["structuredContent"]["data"]["n"], 5)

    def test_start_requires_a_token(self):
        with self.assertRaises(ValueError):
            BridgeServer(protocol.McpProtocol(_host()), "", 0)

    def test_claude_command_shape(self):
        cmd = self.server.claude_add_command()
        self.assertIn("claude mcp add --transport http blender", cmd)
        self.assertIn(f":{self.port}/mcp", cmd)
        self.assertIn(self.TOKEN, cmd)


if __name__ == "__main__":
    unittest.main()
