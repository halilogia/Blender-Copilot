"""Headless integration test: the MCP bridge running inside real Blender.

The add-on registers with the bridge enabled through environment variables; an HTTP client thread talks MCP
to it while the script's main thread pumps the bridge's main-thread executor (bpy.app.timers do not fire in
--background mode). Verifies discovery, annotations, a real mutation over MCP, gating, and a clean shutdown.
"""

import importlib.util
import json
import os
import sys
import tempfile
import threading
import urllib.error
import urllib.request

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

TOKEN = "integration-token-abc"
PORT = 6591
os.environ["BLENDER_COPILOT_MCP"] = "1"
os.environ["BLENDER_COPILOT_MCP_TOKEN"] = TOKEN
os.environ["BLENDER_COPILOT_MCP_PORT"] = str(PORT)
os.environ["BLENDER_AI_USE_MOCK_PROVIDER"] = "1"
_export = tempfile.mkdtemp(prefix="bc_export_")
os.environ["BLENDER_COPILOT_EXPORT_DIR"] = _export

import bpy  # noqa: E402


def load_extension():
    spec = importlib.util.spec_from_file_location("blender_ai_sidebar", os.path.join(PROJECT_ROOT, "__init__.py"),
                                                  submodule_search_locations=[PROJECT_ROOT])
    mod = importlib.util.module_from_spec(spec)
    sys.modules["blender_ai_sidebar"] = mod
    spec.loader.exec_module(mod)
    return mod


def rpc(method, params=None, headers=None, msg_id=1):
    body = {"jsonrpc": "2.0", "id": msg_id, "method": method}
    if params is not None:
        body["params"] = params
    req = urllib.request.Request(f"http://127.0.0.1:{PORT}/mcp", data=json.dumps(body).encode("utf-8"), method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", f"Bearer {TOKEN}")
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as err:
        return err.code, json.loads(err.read() or b"null")


def call(name, arguments=None):
    status, body = rpc("tools/call", {"name": name, "arguments": arguments or {}})
    assert status == 200, (status, body)
    return body["result"]


def run_client(results):
    try:
        status, body = rpc("server/discover")
        assert status == 200 and body["result"]["serverInfo"]["name"] == "blender-copilot", body
        assert body["result"]["supportedVersions"][0] == "2026-07-28"
        print("[PASS] server/discover")

        status, body = rpc("tools/list", headers={"MCP-Protocol-Version": "2026-07-28", "Mcp-Method": "tools/list"})
        tools = {t["name"]: t for t in body["result"]["tools"]}
        assert len(tools) >= 15, sorted(tools)
        assert "propose_plan" not in tools
        assert tools["inspect_scene"]["annotations"]["readOnlyHint"] is True
        assert tools["create_primitive"]["annotations"]["readOnlyHint"] is False
        assert tools["delete_object"]["annotations"]["destructiveHint"] is True
        assert list(tools) == sorted(tools)
        print(f"[PASS] tools/list: {len(tools)} tools, sorted, annotated")

        scene = call("inspect_scene")
        assert scene["isError"] is False, scene
        created = call("create_primitive", {"primitive_type": "CUBE", "name": "McpCube", "location": [1, 2, 3]})
        assert created["isError"] is False, created
        after = call("inspect_scene")
        text = json.dumps(after["structuredContent"])
        assert "McpCube" in text, text[:300]
        print("[PASS] create_primitive over MCP changed the live scene")

        refused = call("delete_object", {"object_name": "McpCube"})
        assert refused["isError"] is True and refused["structuredContent"]["error"]["type"] == "APPROVAL_REQUIRED", refused
        print("[PASS] delete_object is gated (APPROVAL_REQUIRED)")

        status, body = rpc("tools/list", headers={"Mcp-Method": "tools/call"})
        assert status == 400 and body["error"]["code"] == -32020
        print("[PASS] header mismatch rejected")
        results["ok"] = True
    except BaseException as exc:  # noqa: BLE001 - reported by the main thread
        results["error"] = exc


def main():
    ext = load_extension()
    ext.register()
    from bridge import control

    ctl = control.get_controller()
    assert ctl is not None and ctl.is_running(), "bridge did not autostart from the environment"
    assert ctl.server.port == PORT
    results = {}
    client = threading.Thread(target=run_client, args=(results,), daemon=True)
    client.start()
    while client.is_alive():
        ctl.executor.pump()
        client.join(0.005)
    if "error" in results:
        raise results["error"]
    assert results.get("ok"), "client did not finish"
    assert "McpCube" in bpy.data.objects
    ext.unregister()
    assert control.get_controller() is None
    print("[PASS] bridge stopped cleanly on unregister")
    print("\nALL MCP BRIDGE INTEGRATION TESTS PASSED")


if __name__ == "__main__":
    main()
