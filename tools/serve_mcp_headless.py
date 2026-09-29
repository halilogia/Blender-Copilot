"""Serve the Blender Copilot MCP bridge from a headless Blender (no window): for agents, CI and overnight jobs.

    blender --background --python tools/serve_mcp_headless.py -- [--port 6592] [--token T]
                                                                  [--export-dir DIR] [--allow-gated] [--seconds N]

It registers the add-on, starts the bridge and serves MCP until ``--seconds`` pass or the stop file appears
(``<temp>/blender_copilot_mcp.stop``). The connection details go to ``<temp>/blender_copilot_mcp.json``
(owner-only file; it holds the token). Then, for Claude Code:

    claude mcp add --transport http blender http://127.0.0.1:<port>/mcp --header "Authorization: Bearer <token>"
"""

import importlib.util
import json
import os
import secrets
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def parse_args(argv):
    args = {"port": 6592, "token": "", "export_dir": "", "allow_gated": False, "seconds": None}
    it = iter(argv)
    for arg in it:
        if arg == "--port":
            args["port"] = int(next(it))
        elif arg == "--token":
            args["token"] = next(it)
        elif arg == "--export-dir":
            args["export_dir"] = next(it)
        elif arg == "--allow-gated":
            args["allow_gated"] = True
        elif arg == "--seconds":
            args["seconds"] = float(next(it))
    return args


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    args = parse_args(argv)
    token = args["token"] or secrets.token_hex(24)
    os.environ["BLENDER_COPILOT_MCP"] = "1"
    os.environ["BLENDER_COPILOT_MCP_PORT"] = str(args["port"])
    os.environ["BLENDER_COPILOT_MCP_TOKEN"] = token
    os.environ["BLENDER_AI_USE_MOCK_PROVIDER"] = "1"
    if args["allow_gated"]:
        os.environ["BLENDER_COPILOT_MCP_ALLOW_GATED"] = "1"
    if args["export_dir"]:
        os.environ["BLENDER_COPILOT_EXPORT_DIR"] = args["export_dir"]

    spec = importlib.util.spec_from_file_location("blender_ai_sidebar", ROOT / "__init__.py", submodule_search_locations=[str(ROOT)])
    ext = importlib.util.module_from_spec(spec)
    sys.modules["blender_ai_sidebar"] = ext
    spec.loader.exec_module(ext)
    ext.register()

    from bridge import control

    ctl = control.get_controller()
    if ctl is None or not ctl.is_running():
        print("MCP_FAILED the bridge did not start", flush=True)
        sys.exit(1)
    temp = Path(tempfile.gettempdir())
    info_path = temp / "blender_copilot_mcp.json"
    stop_path = temp / "blender_copilot_mcp.stop"
    if stop_path.exists():
        stop_path.unlink()
    info = {"endpoint": ctl.server.endpoint(), "port": ctl.server.port, "token": token,
            "export_dir": ctl.settings.export_dir, "pid": os.getpid()}
    info_path.write_text(json.dumps(info, indent=2), encoding="utf-8")
    try:
        os.chmod(info_path, 0o600)
    except OSError:
        pass
    print(f"MCP_READY {ctl.server.endpoint()} (details in {info_path}; stop by creating {stop_path})", flush=True)
    try:
        ctl.run_headless(seconds=args["seconds"], stop_file=stop_path)
    finally:
        ext.unregister()
        if info_path.exists():
            info_path.unlink()
        print("MCP_STOPPED", flush=True)


if __name__ == "__main__":
    main()
