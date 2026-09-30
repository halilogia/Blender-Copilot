"""A stand-in 3D generator for trying the generate_3d pipeline without a GPU.

    python scripts/mock_3d_server.py --port 8765
    # then, before starting Blender:
    set BLENDER_COPILOT_3D_URL=http://127.0.0.1:8765/generate

It follows the contract in docs/GENERATE_3D.md but generates nothing: it returns the ready-made .glb from ``demos/`` whose
name appears in the prompt (tree, house, castle, barrel, crate, tank, well, lamp ...), or a random one. Use it to check the
whole chain (import, scale, light, camera, render) and replace it with a real generator later.
"""

import argparse
import json
import random
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

DEMOS = Path(__file__).resolve().parent.parent / "demos"


def pick(prompt: str) -> Path:
    files = {p.parent.name.split("-")[0]: p for p in DEMOS.glob("*/*.glb")}
    low = prompt.lower()
    for word, path in sorted(files.items(), key=lambda kv: -len(kv[0])):
        if word in low:
            return path
    return random.choice(list(files.values()))


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_POST(self):
        size = int(self.headers.get("Content-Length", 0))
        try:
            payload = json.loads(self.rfile.read(size) or b"{}")
        except ValueError:
            payload = {}
        glb = pick(str(payload.get("prompt", ""))).read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "model/gltf-binary")
        self.send_header("Content-Length", str(len(glb)))
        self.end_headers()
        self.wfile.write(glb)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", type=int, default=8765)
    args = ap.parse_args()
    print(f"mock 3D generator on http://127.0.0.1:{args.port}/generate ({len(list(DEMOS.glob('*/*.glb')))} models to serve)")
    HTTPServer(("127.0.0.1", args.port), Handler).serve_forever()
