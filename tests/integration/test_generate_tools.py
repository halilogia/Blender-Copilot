"""Headless integration test for generate_3d in real Blender 5.2 against a mock 3D generator (a local HTTP server that
follows the contract in docs/GENERATE_3D.md): binary, base64 and URL answers, auth, errors, import, scaling."""

import base64
import http.server
import json
import os
import sys
import tempfile
import threading
from pathlib import Path

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

from adapter.blender_adapter import BlenderAdapter  # noqa: E402
from adapter.mutators.undo_manager import perform_undo, push_undo_step  # noqa: E402

SEEN = []
GLB = {"bytes": b""}


class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def _send(self, code, body, ctype):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/files/x.glb":
            self._send(200, GLB["bytes"], "model/gltf-binary")
        else:
            self._send(404, b"nope", "text/plain")

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        payload = json.loads(self.rfile.read(length) or b"{}")
        SEEN.append({"path": self.path, "auth": self.headers.get("Authorization"), "payload": payload,
                     "accept": self.headers.get("Accept")})
        port = self.server.server_port
        if self.path == "/glb":
            self._send(200, GLB["bytes"], "model/gltf-binary")
        elif self.path == "/b64":
            self._send(200, json.dumps({"glb_base64": base64.b64encode(GLB["bytes"]).decode()}).encode(), "application/json")
        elif self.path == "/url":
            self._send(200, json.dumps({"glb_url": f"http://127.0.0.1:{port}/files/x.glb"}).encode(), "application/json")
        elif self.path == "/err500":
            self._send(500, b'{"error": "GPU out of memory"}', "application/json")
        elif self.path == "/errjson":
            self._send(200, b'{"error": "prompt refused"}', "application/json")
        elif self.path == "/junk":
            self._send(200, b"hello there", "text/plain")
        elif self.path == "/notglb":
            self._send(200, json.dumps({"glb_base64": base64.b64encode(b"not a glb at all").decode()}).encode(), "application/json")
        elif self.path == "/empty":
            self._send(200, b"{}", "application/json")
        else:
            self._send(404, b"nope", "text/plain")


def fresh():
    bpy.ops.wm.read_homefile(use_empty=True)
    bpy.context.preferences.edit.use_global_undo = True
    adapter = BlenderAdapter()
    push_undo_step("Baseline")
    return adapter


def make_glb(tmp):
    """A small two-part model 2 units tall, off centre and floating, so scaling and grounding are visible."""
    adapter = fresh()
    assert adapter.create_primitive("CUBE", name="Base", size=1.0, location=[4, 5, 3], scale=[1, 1, 1]).success
    assert adapter.create_primitive("CONE", name="Top", size=1.0, location=[4, 5, 4.0], scale=[1, 1, 1]).success
    adapter.export_dir = tmp
    res = adapter.export_gltf(object_names=["Base", "Top"], filename="mock.glb", recenter=False)
    assert res.success, res.error
    return Path(res.data["path"]).read_bytes()


def world_box(root_name):
    root = bpy.data.objects[root_name]
    pts = []
    for o in [root] + list(root.children_recursive):
        if o.type == "MESH":
            pts += [o.matrix_world @ Vector(c) for c in o.bound_box]
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    return lo, hi


def main():
    server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_port}"
    with tempfile.TemporaryDirectory() as tmp:
        GLB["bytes"] = make_glb(tmp)
        assert GLB["bytes"][:4] == b"glTF"
        adapter = fresh()
        adapter.export_dir = tmp
        os.environ.pop("BLENDER_COPILOT_3D_URL", None)
        os.environ.pop("BLENDER_COPILOT_3D_KEY", None)

        print("Test 1: not configured -> a clear message...")
        res = adapter.generate_3d(prompt="a small tree")
        assert not res.success and "BLENDER_COPILOT_3D_URL" in res.error.message, res
        os.environ["BLENDER_COPILOT_3D_URL"] = "ftp://nope"
        res = adapter.generate_3d(prompt="a small tree")
        assert not res.success and "http" in res.error.message, res
        print("[PASS] Test 1")

        print("Test 2: binary answer is imported, scaled to height and put on the ground...")
        os.environ["BLENDER_COPILOT_3D_URL"] = base + "/glb"
        os.environ["BLENDER_COPILOT_3D_KEY"] = "secret-key"
        res = adapter.generate_3d(prompt="a stylised pine tree, low poly", name="pine", height=3.0, seed=7)
        assert res.success, res.error
        d = res.data
        assert d["root"] == "pine" and d["height_m"] == 3.0 and d["triangle_count"] > 10, d
        lo, hi = world_box("pine")
        assert abs((hi.z - lo.z) - 3.0) < 0.02, (lo, hi)
        assert abs(lo.z) < 0.02 and abs((lo.x + hi.x) / 2) < 0.02 and abs((lo.y + hi.y) / 2) < 0.02, (lo, hi)
        assert (Path(tmp) / "pine.glb").exists() and d["bytes"] == len(GLB["bytes"])
        seen = SEEN[-1]
        assert seen["auth"] == "Bearer secret-key" and seen["payload"]["prompt"].startswith("a stylised pine")
        assert seen["payload"]["seed"] == 7 and seen["payload"]["texture"] is True and "model/gltf-binary" in seen["accept"]
        assert perform_undo() and "pine" not in bpy.data.objects, "one undo step removes the model"
        print("[PASS] Test 2")

        print("Test 3: base64 and URL answers, image to 3D, unique names...")
        adapter = fresh()
        adapter.export_dir = tmp
        os.environ["BLENDER_COPILOT_3D_URL"] = base + "/b64"
        a = adapter.generate_3d(prompt="a lamp", name="lamp", height=1.5)
        assert a.success, a.error
        os.environ["BLENDER_COPILOT_3D_URL"] = base + "/url"
        (Path(tmp) / "ref.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 32)
        b = adapter.generate_3d(prompt="a lamp", name="lamp", height=1.5, image_file="ref.png")
        assert b.success, b.error
        assert a.data["root"] != b.data["root"], "a second model with the same name gets its own root"
        assert base64.b64decode(SEEN[-1]["payload"]["image_base64"])[:4] == b"\x89PNG"
        os.environ["BLENDER_COPILOT_3D_KEY"] = ""
        adapter.generate_3d(prompt="x")
        assert SEEN[-1]["auth"] is None, "no key, no Authorization header"
        print("[PASS] Test 3")

        print("Test 4: errors from the service and bad input are reported...")
        for path, needle in (("/err500", "500"), ("/errjson", "prompt refused"), ("/junk", "neither"),
                             ("/notglb", "not a binary glTF"), ("/empty", "glb_base64 or glb_url"), ("/missing", "404")):
            os.environ["BLENDER_COPILOT_3D_URL"] = base + path
            res = adapter.generate_3d(prompt="thing")
            assert not res.success and res.error.type == "INVALID_ARGUMENT" and needle in res.error.message, (path, res)
        os.environ["BLENDER_COPILOT_3D_URL"] = base + "/glb"
        for bad in (dict(), dict(prompt="x" * 900), dict(prompt="x", height=0), dict(prompt="x", height="tall"),
                    dict(prompt="x", timeout=1), dict(prompt="x", image_file="../ref.png"), dict(prompt="x", image_file="none.png"),
                    dict(prompt="x", seed="s"), dict(prompt="x", name="a/b")):
            res = adapter.generate_3d(**bad)
            assert not res.success and res.error.type == "INVALID_ARGUMENT", (bad, res)
        os.environ["BLENDER_COPILOT_3D_URL"] = "http://127.0.0.1:9/none"
        res = adapter.generate_3d(prompt="thing", timeout=5)
        assert not res.success and "Cannot reach" in res.error.message, res
        print("[PASS] Test 4")
    server.shutdown()
    print("\nALL GENERATE TOOL INTEGRATION TESTS PASSED")


if __name__ == "__main__":
    main()
