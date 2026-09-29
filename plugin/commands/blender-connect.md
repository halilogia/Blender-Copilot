---
description: Connect Claude Code to Blender Copilot's MCP bridge (running Blender window, or a headless Blender started for you).
---

Connect this Claude Code session to Blender Copilot's MCP bridge.

Ask the user which way they want, unless they already said:

**A. Their open Blender window (recommended when they model by hand too).**
1. In Blender: 3D Viewport → N sidebar → "Blender - Copilot" tab → "MCP bridge (Claude Code)" panel → **Start MCP bridge**, then **Copy Claude Code connect command**.
2. Ask them to paste the copied command here, or run it themselves. It looks like `claude mcp add --transport http blender http://127.0.0.1:<port>/mcp --header "Authorization: Bearer <token>"`. If they paste it, run it. Never print the full token back (show only its first 6 characters).

**B. A headless Blender (no window; good for automated asset jobs).**
1. Find the add-on folder (the repository root that contains `tools/serve_mcp_headless.py`) and Blender 5.2's executable.
2. Start it in the background: `"<blender.exe>" --background --python "<addon>/tools/serve_mcp_headless.py" -- --port 6592 --export-dir "<folder for .glb files>"`. Add `--allow-gated` only if the user agrees that delete_object may run without asking.
3. It prints `MCP_READY` and writes the endpoint and token to `<temp>/blender_copilot_mcp.json`. Read that file and run `claude mcp add --transport http --scope local blender <endpoint> --header "Authorization: Bearer <token>"`. Stop the server later by creating `<temp>/blender_copilot_mcp.stop`.

Then tell the user: restart Claude Code once so the `blender` tools load, keep Blender running, and start with `inspect_scene`. The `blender-game-assets` skill explains the modeling workflow and `blender-to-godot` the hand-over to Godot.
