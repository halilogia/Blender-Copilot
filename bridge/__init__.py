"""MCP bridge: lets external agents (Claude Code, Codex) use Blender Copilot's tools.

Layers (only main_thread.py's pump and control.py touch Blender):
  protocol.py     MCP / JSON-RPC handling (spec 2026-07-28 plus the older initialize handshake)
  tool_host.py    exposes the ToolRegistry with approval gating and MCP annotations
  http_server.py  token-protected loopback HTTP endpoint (POST /mcp)
  main_thread.py  runs tool calls on Blender's main thread (bpy is not thread safe)
  control.py      start / stop from preferences, environment or headless scripts
"""
