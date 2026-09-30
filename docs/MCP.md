# MCP bridge and modeling tools

Blender Copilot can be driven by external agents (Claude Code, Codex, any MCP client) through a local MCP server, and it can model game assets without running arbitrary Python. Türkçe özet en altta.

## What you get

- **An MCP bridge** inside Blender (or a headless Blender): the same tools the in-Blender agent uses, exposed over MCP with the same safety rules.
- **Modeling tools** that go beyond primitives, all allow-listed and undoable: `create_mesh`, `mesh_edit`, `join_objects`, `parent_object`, `apply_transform`, `set_origin`, `add_shape_modifier`, `frame_view`, `export_gltf`.
- **Cinematic tools** to direct a film from chat: `set_environment` (9 lights), `camera_move` (38 moves), `camera_settings`, `set_look`, `render_image`, `render_contact_sheet`, `render_animation` (MP4), `edit_video`, `render_shots`.
- **Character tools**: `rig_character`, `animate_character` (idle, walk, run, aim, wave, jump), camera `follow`, animated glb export.
- **A Claude Code plugin** with four skills (`blender-game-assets`, `blender-to-godot`, `blender-cinematic-shot`, `blender-character-animation`) and `/blender-connect`.

## Security model

- Listens on **127.0.0.1 only**, and only when you start it. Off by default.
- Every request needs `Authorization: Bearer <token>` (constant-time comparison). Requests carrying an `Origin` header (browsers) are refused. Only `POST /mcp`, bodies up to 4 MB.
- **No arbitrary code.** There is no exec/eval tool. Modeling is done with bounded, validated operations (vertex and face limits, allow-listed mesh operations, file names without folders).
- **Approval gate stays.** Tools with risk MEDIUM or higher (`delete_object`, boolean modifiers) are refused over MCP with `APPROVAL_REQUIRED` unless you switch on **Gated tools: allowed** in the panel (or `--allow-gated` / `BLENDER_COPILOT_MCP_ALLOW_GATED=1` for headless jobs).
- Files are written only by `export_gltf`, into the export folder you configure, as `<name>.glb`.
- Every mutation is one Ctrl+Z step; tool calls run on Blender's main thread through a queue (bpy is not thread safe).

## Start it

### In Blender (window open)

3D Viewport → N sidebar → **Blender - Copilot** tab → **MCP bridge (Claude Code)** → **Start MCP bridge** → **Copy Claude Code connect command**, then run the copied command in a terminal:

```bash
claude mcp add --transport http blender http://127.0.0.1:6590/mcp --header "Authorization: Bearer <token>"
```

The port and a generated token are stored in `mcp_bridge.json` next to the add-on configuration (owner-only file). Set `BLENDER_COPILOT_MCP=1` to start the bridge whenever the add-on registers.

### Headless (no window: automation, CI, overnight jobs)

```bash
blender --background --python tools/serve_mcp_headless.py -- --port 6592 --export-dir D:/assets/exports
```

It prints `MCP_READY <endpoint>` and writes the endpoint and token to `<temp>/blender_copilot_mcp.json`; create `<temp>/blender_copilot_mcp.stop` to shut it down. Options: `--token`, `--allow-gated`, `--seconds`.

### With the Claude Code plugin

```bash
claude plugin marketplace add halilogia/Blender-Copilot && claude plugin install blender-copilot@blender-copilot
```

Then `/blender-connect` in Claude Code explains and performs the connection for either mode.

## Settings and environment

| Variable | Meaning |
|---|---|
| `BLENDER_COPILOT_MCP=1` | start the bridge on add-on registration |
| `BLENDER_COPILOT_MCP_PORT` | port (1024-65535, default 6590) |
| `BLENDER_COPILOT_MCP_TOKEN` | bearer token (otherwise generated once and stored) |
| `BLENDER_COPILOT_MCP_ALLOW_GATED=1` | run MEDIUM+ risk tools without an in-Blender approval |
| `BLENDER_COPILOT_EXPORT_DIR` | folder `export_gltf` writes into (default `Documents/BlenderCopilot/exports`) |

## Tools

Read-only: `inspect_scene`, `inspect_selection`, `inspect_object`, `inspect_material`, `inspect_mesh`, `capture_viewport` (returns the PNG as an MCP image), `visual_verify`.

Scene and modeling (risk LOW, one undo step each): `create_primitive` (CUBE, SPHERE, PLANE, CYLINDER, CONE, ICOSPHERE, TORUS), `create_mesh`, `mesh_edit` (EXTRUDE_FACES, INSET_FACES, BEVEL_EDGES, SUBDIVIDE, TRIANGULATE, RECALC_NORMALS, MERGE_BY_DISTANCE, SCALE_TO_HEIGHT_TAPER; faces picked by normal direction), `add_modifier` (BEVEL, SUBSURF; BOOLEAN is gated), `add_shape_modifier` (MIRROR, ARRAY, SOLIDIFY, DECIMATE, TRIANGULATE), `set_material`, `assign_material`, `set_shading`, `transform_object`, `duplicate_object`, `parent_object`, `join_objects`, `apply_transform`, `set_origin`, `create_camera`, `create_light`, `import_asset`, `frame_view` (aims the viewport so `capture_viewport` shows the model), `export_gltf` (writes a `.glb`; `recenter` puts the prop at the origin so a game engine does not place it where it was modelled).

Cinematic (risk LOW, files only in the export folder): `set_environment` (studio, day, golden_hour, sunset, dawn, overcast, foggy, night, neon: world with a physical sky gradient for the sun presets, sun, ground, highlight-safe tone mapping), `camera_move` (38 presets keyframed around the subject: dolly in, out, left, right, super; orbit, arc, orbit_360, crane, jib, pan, tilt, whip_pan, dolly_zoom both ways, crash, rapid and yoyo zooms, handheld, fpv_drone, hyperlapse, robo_arm, bullet_time, aerial_pullback, overhead, hero_cam, snorricam, dutch_angle, barrel_roll ...), `camera_settings` (depth of field, rack focus, motion blur), `set_look` (compositor colour grade and glow: cinematic, noir, vintage, warm, cold, vivid, neon_glow, dreamy), `render_contact_sheet` (several frames of the shot in one picture), `edit_video` (join clips with cut, crossfade or wipe, slow motion and fast forward, through Blender's video editor), `render_shots` (a shot list rendered and joined into one film in one call), `render_image` (one EEVEE frame as PNG, returned as an image), `render_animation` (the shot as H.264 MP4 or a PNG sequence, plus a preview frame; at most 480 frames and 1920x1080; renders keep Blender busy, about 0.1 s per frame at 960x540). The skill `blender-cinematic-shot` explains the workflow. See [HIGGSFIELD.md](HIGGSFIELD.md) for why.

Characters (risk LOW, one undo step each): `rig_character` (a character built from separate parts named head, torso, arm_l, arm_r, leg_l, leg_r plus accessories: pivots go to the joints, accessories attach to the nearest part, everything hangs under `<name>_Rig`; no armature, no skinning), `animate_character` (idle, walk, run, aim, wave, jump; `distance`, `heading`, `intensity`), `camera_move` with `follow: true` (the camera keeps its framing on a moving subject), and `export_gltf` with `animations: true` (a glb with the hierarchy and its keyframes, for a game engine). The skill `blender-character-animation` explains the workflow.

Gated (MEDIUM+): `delete_object`.

Every tool has MCP `annotations` (`readOnlyHint`, `destructiveHint`, `idempotentHint`, `openWorldHint`, `title`) so clients can skip approval prompts for tools that only observe.

## Protocol

MCP **2026-07-28** (stateless requests, `server/discover`, `_meta` protocol version, `resultType`, cacheable `tools/list` with `ttlMs` and `cacheScope`, `structuredContent`, `Mcp-Method` / `Mcp-Name` / `MCP-Protocol-Version` header checks with `-32020` and `-32022` errors) and the older `initialize` handshake (2025-03-26 to 2025-11-25). ANSI colour codes and control characters are stripped from results so clients can always parse them.

## Blender to Godot in one session

Run two MCP servers in Claude Code: `blender` (this bridge) and `godot` ([Godot AI Sidebar](https://github.com/halilogia/Godot-AI-Sidebar)). Model and export a prop with the Blender tools, copy the `.glb` under `res://assets/models/`, call the Godot tool `sync_project`, instantiate the model in the game, and check it with the Godot runtime screenshot. The `blender-to-godot` skill spells out every step, including collision shapes and scale.

## Verified with a real Claude Code client

A fresh `claude -p` process connected through `--mcp-config` (HTTP, bearer token) to a headless Blender, was asked for "a low-poly wooden water bucket, verify it in the viewport, export bucket.glb" and used only the tools above: 40 calls (`create_primitive`, `mesh_edit`, `set_material`, `frame_view`, `capture_viewport` ...), noticed from its own viewport captures that the sides were straight and the bands hidden, rebuilt the body, then joined, set the origin and exported a 1,204-triangle `.glb` and reported honestly what it left behind. It worked without any client-specific handling.

## Demo bench

`scripts/demo_bench_mcp.py` gives a fresh Claude Code agent one short prompt ("model a low-poly barrel") and only the `blender` MCP server, then keeps everything in `archives/bench-runs/<date>-<name>/` (git-ignored): the prompt, the raw and readable chat, every viewport capture the agent made, four final views (`sheet.png`), the `.glb` and `result.json` (calls, triangles, size, time). `scripts/demo_history.py` builds `archives/history/index.html` (zoom, chat links, "demos'a koy" picks) and `scripts/demo_promote.py <run>` copies the best runs into the tracked [`demos/`](../demos/README.md) library.

Two agents were benchmarked with the same tools. **Claude Code** (`claude-opus-5-5`) drives the bridge over MCP (24 demos). The **add-on's own in-Blender agent** runs headless through an OpenAI-compatible gateway, here 9router: `python scripts/demo_bench_mcp.py --via 9router --model ag/claude-sonnet-4-6 --only crate` (also tried: `gemini-pro-agent`, `openrouter/space-bunny-alpha`; the cheap `a` combo stopped before exporting). For that agent the run script sets `BLENDER_AI_CONTINUE_ON_TOOL_ERROR=1` (a failed call goes back to the model), the default 100 tool rounds apply (`BLENDER_AI_MAX_TOOL_ROUNDS`), and up to two follow-up messages ask it to finish and export, like a user would. The `Ajan` column of [`demos/README.md`](../demos/README.md) says which agent made each model. `--shots` (or `--only shot-castle-orbit`) runs the cinematic prompts instead: the agent models, lights, moves the camera and renders an MP4 (`shot-*` demos, four frames of the video in `sheet.png`).

## Tests

```bash
python tests/run_unit_tests.py                                   # protocol, gating, executor, HTTP server, settings
blender --background --python tests/integration/test_mcp_bridge_blender.py   # the bridge inside real Blender, over HTTP
blender --background --python tests/integration/test_modeling_tools.py       # all modeling tools, a real .glb, undo, threads
```

## Türkçe özet

Blender Copilot artık yerel bir MCP sunucusu açabiliyor: Claude Code gibi dış ajanlar Blender'ı 127.0.0.1 üzerinden, token korumalı ve **rastgele Python çalıştırmadan** kullanır. Yeni modelleme araçları (`create_mesh`, `mesh_edit`, `join_objects`, `parent_object`, `apply_transform`, `set_origin`, `add_shape_modifier`, `frame_view`, `export_gltf`) düşük poligonlu oyun varlıklarını yapıp `.glb` olarak dışa aktarır. Silme gibi riskli işlemler varsayılan olarak reddedilir. Kurulum: panelde **Start MCP bridge**, ya da başsız `blender --background --python tools/serve_mcp_headless.py`. Claude Code eklentisi: `claude plugin marketplace add halilogia/Blender-Copilot && claude plugin install blender-copilot@blender-copilot`.
