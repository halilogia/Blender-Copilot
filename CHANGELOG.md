# Changelog — Blender - Copilot

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Added
- `scripts/model_report.py` and `docs/MODELS.md`: which chat model drives Blender Copilot, from the stored benchmark runs (finished, calls, tool errors, minutes) and three standard tasks (`bench-model-check`, `bench-baked-bench`, `bench-terrain-forest`, same prompt for every model). First numbers: DeepSeek V4 Flash, Gemini Pro agent and Space Bunny Alpha all finished all three; Gemini needed the fewest calls, Space Bunny 141 calls for the terrain scene.

---

## [1.17.0] - 2026-09-30

### Added
- **World pack** (loads from words such as terrain, hill, forest, scatter, trees, village, or `enable_tools`):
  - `create_terrain`: a hilly grid mesh (`size`, `resolution`, `height`, `roughness`, `seed`, `flat_radius` for a flat disc around the centre), deterministic for a seed.
  - `scatter`: many linked copies of an object (or a group of objects) in one call, inside an `area` (rectangle or circle) or along a `path` with `spread`; random scale and rotation, never closer than `min_distance`, never inside the footprint of `avoid` objects, standing on a `ground` object (cast straight down at that object alone) or on `ground_z`; up to 500 copies, same seed same layout, one undo step, copies in their own collection. Copies share the mesh, so a glTF export keeps them as instances.
- Pure logic in `core/scatter_points.py` (seeded sampling, noise, height grid), tests in `tests/unit/test_scatter_points.py` and `tests/integration/test_world_tools.py`.

---

## [1.16.0] - 2026-09-30

### Added
- **Deeper `mesh_edit`** (no new tool, eight new operations): `FLIP_NORMALS`, `DELETE_FACES`, `DISSOLVE_PLANAR` (angle; cleans up after a boolean), `LOOP_CUT` (axis, cuts 1-8), `KNIFE_PLANE` (axis, position, keep both / above / below; the cut is capped and closed), `BRIDGE_FACES` (two selected faces removed and joined by a tunnel), `SEPARATE` (loose parts or material into objects), `APPLY_MODIFIERS` (bakes bevel, boolean, mirror into the mesh).
- Face selectors can also pick by `material` (name or slot), `min_area` / `max_area` and `near` (+ `radius`), combined with the normal direction; all given conditions must hold.
- Tests: `tests/integration/test_mesh_edit_pack.py` (flipped normals are found by `check_model` and fixed, loop cut vertex count and positions, knife plane leaves a closed mesh, bridge face count, separate, apply modifiers, selectors, errors, undo).

---

## [1.15.0] - 2026-09-30

### Added
- **Textures pack** (loads from words such as uv, unwrap, texture, bake, glb, godot, unity, or `enable_tools`): `unwrap_uv` (smart project or cube project, replaces the active UV map, reports coverage of the 0-1 square and whether it lies inside) and `bake_material` (paints the look of a procedural `set_material` preset into an image over the UV map and gives the object one image-textured material). A glTF export keeps only the flat base colour of a procedural material; after `bake_material` the `.glb` carries a real texture (tested by reading the exported file). Flat-colour objects are left alone. Unwraps by itself when the mesh has no UVs; Cycles settings are restored; one undo step each.
- Tests: `tests/integration/test_texture_tools.py` (UV in bounds, baked image is brown and grainy, the .glb has images and a base colour texture, undo, errors), pack keyword tests.

### Changed
- `check_model` names `unwrap_uv` for a texture without UVs; skills and the Godot sidebar skill no longer say that presets are lost in glTF.

---

## [1.14.0] - 2026-09-30

### Added
- **`check_model`** (read only, core tool): checks a model with numbers, the modelling counterpart of `check_shot`: non-manifold edges, faces pointing inward, doubled and loose vertices, zero-area faces, unapplied scale, a pivot outside the object, no material, a texture without UVs, the model sunk into the ground, two objects in the same space, and the triangle count against a budget (`max_triangles`, default 3000). Returns `ok` (false only for FAIL findings), issues with severity and the tool call that fixes each. Pure logic in `core/model_qa.py`, measurements in `adapter/mutators/model_qa_mutator.py`.
- Tests: `tests/unit/test_model_qa.py`, `tests/integration/test_model_qa.py` (all ready-made props pass; every defect is found and the suggested tool removes it).

### Changed
- Roadmap rewritten: the core (modelling, materials, verification) comes first and the film side is frozen; README and roadmap test counts corrected.

---

## [1.13.0] - 2026-09-30

### Added
- **`set_material` presets**: `preset` builds a procedural material in one call: wood, stone, brick, metal (brushed), gold, grass, water, sand, concrete, marble. Texture, colour variation and relief from shader nodes in object coordinates (no image files, no UVs); `scale` makes the pattern finer or coarser; explicit `roughness`, `metallic`, `base_color` still apply on top; a second preset replaces the first. Recipes are plain data in `core/material_presets.py`.
- Fixed: with the sky presets, everything below the horizon was near black, so the edge of a small ground plane opened onto a dark blue void in every demo; it now shows the ground colour.
- Tests: `tests/unit/test_material_presets.py`, `tests/integration/test_material_presets.py` (every preset renders with visible texture and the expected hue).

---

## [1.12.0] - 2026-09-30

### Added
- **`check_shot`** (read only, film pack): checks the current shot with numbers, for a few frames of it: where the subject sits (cut off, too small, too big, off centre, behind the camera) and how bright the picture is (too dark, mostly black, too bright, blown out). Each issue names the frames and the tool call that fixes it. For models that cannot look at pictures or misread them. Pure logic in `core/shot_qa.py`.
- `fit_distance`: `camera_move` places the camera from the real projection (lens, aspect, direction) so the whole subject fits; a cube seen from a corner is no longer cut off.

### Fixed
- **`set_look` colour grades were never applied** in Blender 5.2 (the colour balance node changed its menu and sockets): looks now use Offset/Power/Slope and really tint the picture (test measures it).
- `studio` light preset was blown out: dimmer sky, sun and ground.

---

## [1.11.0] - 2026-09-30

### Added
- **`create_prop`**: ready-made, proportioned, coloured, bevelled and smooth-shaded low-poly props in one call, standing on the ground with the front toward +Y: crate, barrel, tree_pine, tree_round, rock, house, tower, fence, lamp, tent, well, car, chest, table, chair, campfire. `humanoid` and `robot` come as separate parts named for `rig_character` (Head, Torso, arms with forearms, legs with shins, boots, eyes, mouth, hair or antenna). `size`, `location`, `colors` (by name, the result lists the names), `seed`, `polish`; one undo step. Pure geometry, no AI.
- Skills, agent prompt and MCP instructions say to start with `create_prop`; the agent prompt is shorter than before (about 4,400 characters).
- Tests: `tests/integration/test_prop_tools.py` (all 18 kinds stand on the ground at the right height under a triangle budget, colours, seed, undo, humanoids rig and act, errors, wrapped lists). A free model (DeepSeek V4 Flash) built a village with a rigged walking person and filmed it in 18 tool calls.

### Fixed
- Tool arguments from weak models are repaired instead of ending the turn: text after the object, truncated output (missing brackets, cut strings), trailing commas, Python-style `True`, `None` and single quotes (`lenient_json_loads`, `tests/unit/test_lenient_json.py`); hopeless JSON is still reported.

---

## [1.10.0] - 2026-09-30

### Added
- **Tool packs** (`core/tool_packs.py`, `enable_tools`): the in-Blender agent sends the film tools (light, camera, render, edit, music) and the character tools (rig, animate) only when the conversation needs them. They load by themselves from the request's words (English and Turkish; a character request also loads the film pack) or when the model calls `enable_tools`. A plain modeling request now costs about 5,800 tokens of tool descriptions instead of about 11,000; the full set is unchanged over MCP, where clients handle long tool lists themselves.
- Tests: `tests/unit/test_tool_packs.py` and `tests/unit/test_runtime_packs.py` (what is sent, keyword loading, `enable_tools`, size); a free model (DeepSeek V4 Flash) made a crate with the core tools only and a film shot with the film pack loaded from the request alone.

---

## [1.9.1] - 2026-09-30

### Removed
- `generate_3d` (added in 1.8.0), its mock server, its contract document and its test: the project works with chat models only and does not hook in a trained 3D generator. The manifest network reason is back to LLM provider access and the local MCP bridge.

---

## [1.9.0] - 2026-09-30

### Added
- **`animate_sequence`**: act a scene on one timeline: up to 12 segments (`preset`, `duration`, `distance`, `intensity`, `heading`, `text`), the character carries on from where the last one ended, a segment with a new heading turns it, a blend (default 0.3 s) glides between poses; the result lists the start and end frame of each segment.
- **Demo proof for every feature**, run end to end by a free chat model (DeepSeek V4 Flash through 9router): depth of field with rack focus, slow motion, crossfade and a composed soundtrack in `edit_video`, and an acting scene (walk, wave, talk) filmed in continuous shots.
- Tests: `tests/integration/test_character_tools.py` Test 8 (timeline, position and heading carried over, glide, lip sync in the last segment, errors, wrapped lists).

---

## [1.8.0] - 2026-09-30

### Added
- **`generate_3d`**: text or image to 3D through a trained generator the user configures. `BLENDER_COPILOT_3D_URL` (and optional `BLENDER_COPILOT_3D_KEY`) point at a service that follows a small contract (JSON request with prompt, optional image, seed and texture; answer as `.glb` bytes, `glb_base64` or `glb_url`); the URL comes only from the environment, the network rules of the add-on apply, files over 80 MB are refused. The model is saved in the export folder, imported, scaled to a height and stood on the ground under one root object. See `docs/GENERATE_3D.md` and `scripts/mock_3d_server.py` (a stand-in that serves demo models).
- **Shot continuity**: `camera_move` `start_frame`, and `render_shots` `continuous` (default true): each shot carries on where the previous one stopped in the characters' animation, so a spoken line or a walk continues across shots.
- Manifest network reason mentions the optional 3D generator; MCP render and generate calls get a long wait window.
- Tests: `tests/integration/test_generate_tools.py` (mock generator: binary, base64 and URL answers, auth, image to 3D, errors, scaling and grounding, undo), shot continuity in the character tests.

---

## [1.7.0] - 2026-09-30

### Added
- **Faces**: optional `eye_l`, `eye_r` and `mouth` parts (small boxes on the head, found by name; brows become head accessories). Every animation blinks; new presets `talk` (lip sync), `happy`, `surprised`, `angry` change scale and pose.
- **Lip sync from text** (`core/lipsync.py`): `animate_character(preset="talk", text=...)` opens the mouth with vowels, closes it on consonants and pauses (English and Turkish); the duration follows the line.
- **Soundtrack** (`core/soundtrack.py`, `make_soundtrack`): procedural mood beds as WAV (calm, tense, epic, playful, night, synthwave), no downloads. `edit_video` `soundtrack` and `music_volume`, `render_shots` `music`: the bed is composed to the film's length and muxed into the MP4 as AAC.
- **50 camera presets** (was 38): eyes_in, mouth_in, lazy_susan, incline, road_rush, glam, spiral_in/out, fisheye, telephoto, rise_reveal, crane_over.
- Tests: expressions and lip sync (15), soundtrack (5), camera presets (8), faces (integration), audio in the edited MP4.

### Notes
- Everything here is driven by chat models, so quality depends on the model; the tools stay strict and forgiving so weaker models still finish.

---

## [1.6.0] - 2026-09-30

### Added
- **Bent limbs**: optional `forearm_l/r` and `shin_l/r` parts (found by names such as forearm, lowerarm, shin, calf; parented to the upper limb with the pivot at the elbow or knee). Walk and run fold the knees and bend the elbows, wave swings the forearm from the elbow, aim and jump use them too.
- **`character_library`**: `save` stores a rigged character (rig, parts, materials) as a .blend in the export folder, `load` brings it into any scene at a location (names remapped, animation cleared, ready for `animate_character`), `list` shows the saved ones.
- **`polish_model`**: bevels hard corners and shades smooth with sharp edges kept (bevel in meters or about 4 percent of the smallest side, 3 segments, angles adjustable).
- Skills: `blender-character-animation` (lower limbs, library) and `blender-game-assets` (a polish step); agent prompt and MCP instructions mention them.
- Tests: motion unit tests for knees and elbows, integration tests for bent limbs and the library (a fresh scene gets the character back and walks), `tests/integration/test_polish_tools.py`.

### Fixed
- Ground colours of the `day` preset were too bright; exposure and sun retuned.

---

## [1.5.1] - 2026-09-30

### Fixed
- **Batches of tool calls with an approval in the middle**: when a model sent several tool calls in one message and one needed approval, the calls after it never got a result, and strict providers rejected the next request ("Tool results are missing for tool calls ..."; seen with DeepSeek V4 Flash through 9router). After approve or reject each skipped call now gets a `NOT_EXECUTED` result so the model can repeat it.
- Lists that weak models wrap or quote (`{"item": [...]}`, a JSON string, one bare name) are unwrapped for object names, vertices, faces, clips and shot lists; numbers sent as strings are accepted.
- `render_shots` explains that a shot without `environment` or `look` keeps the previous one (a free model left the whole film in night light).

### Verified
- 748 unit tests, 30 headless Blender suites; a free model (DeepSeek V4 Flash) and Space Bunny make shots and a three-shot film through 9router.

---

## [1.5.0] - 2026-09-30

### Added
- **38 camera presets** (was 16): dolly_left/right, super_dolly_in/out, dolly_zoom_out, rapid_zoom_in/out, crash_zoom_out, yoyo_zoom, jib_up/down, aerial_pullback, fpv_drone, bullet_time, dutch_angle and barrel_roll (camera roll through the target's Z axis), snorricam (follows automatically), hero_cam, overhead, robo_arm, hyperlapse, orbit_360.
- **`set_look`**: colour grade and glow for renders through a compositor node group (cinematic, noir, vintage, warm, cold, vivid, neon_glow, dreamy, natural to remove; `strength`).
- **`camera_settings`**: depth of field (`f_stop`, `focus_object`, `focus_distance`), rack focus (`rack_focus_to`, keyframed) and motion blur.
- **`render_contact_sheet`**: several frames of the shot in one picture, returned as an image.
- **`edit_video`**: joins clips from the export folder with cut, crossfade or wipe and per-clip speed (slow motion, fast forward) in Blender's video editor (a throw-away scene, no ffmpeg command line).
- **`render_shots`**: a shot list (preset, duration, environment, look, ...) rendered and joined into one MP4 in one call.
- **Environments**: `day`, `sunset`, `dawn` and `foggy` added; the sun presets use a physical sky gradient; tone mapping is highlight-safe (Khronos PBR Neutral); night and neon retuned.
- Tests: 12 more camera unit tests, `tests/integration/test_film_tools.py` (sky, grading measured on real renders, lens, contact sheet, edit and shot list).

### Fixed
- The ground plane material had no shader in Blender 5 (an empty node tree), so ground colours were ignored and grounds looked white.
- Presets rendered blown out (day, golden hour) or black (foggy with a world volume, removed) or neon-white; all retuned and checked on rendered pictures.

---

## [1.4.0] - 2026-09-30

### Added
- **Character motion** (LOW risk, one undo step each, no armature or skinning): `rig_character` (a character built from separate parts named head, torso, arm_l, arm_r, leg_l, leg_r plus accessories: pivots go to the joints, accessories attach to the nearest part, everything hangs under `<name>_Rig`) and `animate_character` (idle, walk, run, aim, wave, jump; `distance`, `heading`, `intensity`; math in `core/motion_paths.py`).
- `camera_move` `follow`: the camera keeps its framing on a moving subject (a walking character); named objects stand for their children (a rig for its parts).
- `export_gltf` `animations`: a glb with the hierarchy and its keyframes (recenter off) for a game engine.
- Skill `blender-character-animation`; character rules in the in-Blender agent prompt and the MCP instructions.
- Tests: `tests/unit/test_motion_paths.py` (10), `tests/integration/test_character_tools.py` (rig, pivots and hierarchy, keyframes, heading, follow, animated glb read back).
- Demo bench: character shots (`shot-soldier-walk`, `shot-robot-wave`, `shot-knight-run`, `shot-soldier-aim`, `shot-zombie-walk`) by chat models through 9router.

### Fixed
- `camera_move` default distance now fits the whole subject in a 16:9 frame (tall subjects such as a standing soldier were cropped at the top); the subject is measured at the first frame of the shot.

---

## [1.3.0] - 2026-09-30

### Added
- **Cinematic tools** (chat-model driven, no Python, LOW risk, files only in the export folder): `set_environment` (studio, golden_hour, overcast, night, neon: world, sun, ground, Standard tone mapping), `camera_move` (16 keyframed presets around the subject: static, dolly_in/out, orbit, arc_left/right, crane_up/down, pan_left/right, tilt_up/down, whip_pan, dolly_zoom, crash_zoom_in, handheld; math in `core/camera_paths.py`), `render_image` (EEVEE PNG returned as an image) and `render_animation` (H.264 MP4 or PNG sequence plus a preview frame; at most 480 frames and 1920x1080; Blender 5 `media_type = "VIDEO"`).
- Skill `blender-cinematic-shot` in the Claude Code plugin; the in-Blender agent's system prompt has a cinematic protocol; MCP render calls get a 600 s window.
- Tests: `tests/unit/test_camera_paths.py` (13) and `tests/integration/test_cinema_tools.py` (a real PNG and MP4 are written and checked, settings restored, undo).
- Demo bench shots: `scripts/demo_bench_mcp.py --shots` (model, light, move, MP4) with the add-on's own agent through 9router; `demos/` shows them with a video link.
- Research: `docs/HIGGSFIELD.md` (gap analysis of a Higgsfield-style workflow).

### Fixed
- The viewport image store kept only 10 pictures; an agent that captured or rendered more lost older ones and the run ended with `IMAGE_NOT_FOUND`. It now keeps 48.
- Provider HTTP errors show up to 600 characters of the response body.

---

## [1.2.0] - 2026-09-30

### Added
- **MCP bridge** (`bridge/`): local MCP server so Claude Code and other agents can use Blender Copilot's tools. Loopback only, bearer token, browser `Origin` refused, off by default; speaks MCP 2026-07-28 (`server/discover`, `_meta` version, `resultType`, cacheable `tools/list`, `structuredContent`, header checks) and the older `initialize` handshake; tool `annotations`; ANSI/control characters scrubbed from results; `capture_viewport` returned as an MCP image. MEDIUM+ risk tools (`delete_object`) are refused unless the user allows gated tools. N-panel section "MCP bridge (Claude Code)" and `tools/serve_mcp_headless.py` for headless use. See `docs/MCP.md`.
- **Modeling tools without Python** (no exec/eval): `create_mesh`, `mesh_edit` (extrude / inset / bevel / subdivide / taper faces picked by normal), `join_objects`, `parent_object`, `apply_transform`, `set_origin`, `add_shape_modifier` (MIRROR, ARRAY, SOLIDIFY, DECIMATE, TRIANGULATE), `frame_view`, `export_gltf` (writes a `.glb`, recenters the prop at the origin); primitives CYLINDER, CONE, ICOSPHERE, TORUS.
- **Claude Code plugin** (`plugin/`, marketplace in `.claude-plugin/`): skills `blender-game-assets` (with tested recipes: crate, barrel, tree, rock, sandbags, rifle, soldier) and `blender-to-godot`, plus `/blender-connect`.
- Manifest: `files` permission and updated `network` text; build excludes the plugin, demos, scripts and archives folders.
- **In-Blender agent, modeling readiness**: the system prompt has a modeling protocol; tool rounds per prompt come from `BLENDER_AI_MAX_TOOL_ROUNDS` (default 100, was a fixed 5); opt-in `BLENDER_AI_CONTINUE_ON_TOOL_ERROR=1` returns a failed call to the model instead of ending the turn; provider HTTP errors now show the start of the response body.
- **Demo bench and library**: `scripts/demo_bench_mcp.py` (Claude Code over MCP, or the add-on's own agent through 9router with `--via 9router`), `scripts/agent_run_headless.py`, `demo_history.py`, `demo_promote.py`, and `demos/` (33 props with chats, views and measurements).

### Fixed
- `set_material` with `object_name` and `material_name` and no property just assigns the existing material to the slot.
- `mesh_edit` accepts vectors that models wrap or stringify (`{"item": [0, 0, 1]}`, `"0, 0, 1"`); the schema and error text show the accepted forms.
- `capture_viewport` derives its view and projection matrices from the viewport parameters (`RegionView3D.view_matrix` is stale in background mode, so `frame_view` had no effect on captures).

### Verified
- Pure-Python unit suites `test_mcp_bridge` (protocol, gating, executor, real loopback HTTP) and `test_mcp_settings`; headless Blender suites `test_mcp_bridge_blender.py` and `test_modeling_tools.py` (a real `.glb` is written and read back); full master runner 27/27 suites.

---

## [1.1.0] - 2026-09-27

### Added
- **Vision completion (A1–A3)**:
  - `capture_viewport` cost guard: optional `max_side` downscale (pure-Python nearest-neighbor, `downscaled` metadata).
  - Native Anthropic Messages provider (`agent/anthropic_provider.py`): `/v1/messages`, `x-api-key`, SSE `content_block_delta` -> shared `ToolCallAccumulator`; `Config.provider` + `BLENDER_AI_PROVIDER` + Preferences dropdown.
  - Stdlib local embedding (`agent/local_embed.py`): hashed trigram+token TF (dim 256), cosine `top_k` + `LocalIndex`, Turkish tokenizer.
- **Auto-update (B, check-only)**:
  - `core/update_check.py` (parse/compare/fold errors) strictly via `HttpClient.get()`/`get_json()`; `ai_sidebar.check_updates` operator gated by `online_access`.
- **Asset browser (C, local)**:
  - `agent/asset_index.py` (scan `.blend/.glb/.obj/.fbx`, traversal guard, substring + embedding search); `import_asset` tool (`LOW` risk, main-thread, `push_undo_step`); `ChangeVerifier` `import` rule.
- **Transport**: `HttpClient.get()` + `get_json()` with identical TLS/timeout/cancel discipline (network stays isolated in `http_client`).

### Fixed
- `.blend` asset append datablock-name fallback in `BlenderAdapter.import_asset()`: tries caller `name` then file stem, returns `ASSET_NOT_FOUND` instead of a false-positive success when nothing is appended.

### Verified
- 682 pure-Python unit tests passing (`python tests/run_unit_tests.py` OK, hardening green).
- New unit suites: `test_anthropic_provider`, `test_local_embed`, `test_update_check`, `test_asset_browser`.
- New headless suites (Blender 5.2.2 LTS): `test_asset_import.py` (6/6), `test_anthropic_roundtrip.py` — master runner 25/25 SUITES PASS.
- Pending: live GUI pass (moved to v1.2).

## [1.0.0] - 2026-09-14

### Added
- First public release checkpoint for Blender AI Copilot.
- FIFO prompt queue with ordered HUD/N-Panel visibility.
- Shared `RuntimeSnapshot` projection for consistent UI state.
- Stateless `EventRouter` boundary preserving AgentRuntime lifecycle ownership.
- Project-local diagnostic log override through `BLENDER_AI_LOG_DIR`.
- Multiline GPU HUD input with automatic wrapping, long-token splitting, and cursor positioning.
- Presentation-layer assistant text cleanup for HTML entities such as `&#x20;`.
- English and Turkish README documentation.

### Verified
- 618 pure-Python unit tests passing.
- 23 Blender integration test files maintained for Blender-runtime verification.
- Existing SSE keep-alive completion, cancellation, approval, plan execution, queue, and verification paths remain covered.

## [0.9.0] - 2026-09-14

### Added
- **M9: Advanced Agentic Blender Operations**:
  - **Turn-Level Repair Budget Guard**: `_current_plan_repairs` counter and `max_plan_repairs = 1` guard terminating infinite LLM repair iterations with `MAX_PLAN_REPAIRS_EXCEEDED`.
  - **Agentic Prompt Protocol**: Updated `ContextBuilder` system instructions to guide model reasoning on inspect -> propose_plan -> approval -> PlanExecutor -> verify -> feedback -> repair.
  - **Camera Semantic Tool (`create_camera`)**: Safe Data API camera creation and manipulation (location, rotation, lens focal length, active scene camera assignment, undo integration, and deterministic `ChangeVerifier` rule).
  - **Light Semantic Tool (`create_light`)**: Safe Data API lighting tool supporting `POINT`, `SUN`, `SPOT`, and `AREA` light types, location, rotation, energy wattage, color tint, undo integration, and deterministic `ChangeVerifier` rule.
  - **Core Geometry Quality (`set_shading` & `add_modifier`)**:
    - `set_shading`: Direct polygon-level `SMOOTH` and `FLAT` shading via Data API without operator context dependencies.
    - `add_modifier`: Data API geometry modifiers supporting `BEVEL` (width, segments), `SUBSURF` (levels), and `BOOLEAN` (DIFFERENCE, UNION, target object existence checks).
  - **Object Duplication Tool (`duplicate_object`)**:
    - Data API object and independent datablock cloning with material slot preservation.
    - Deterministic fail-closed name collision handling (fails if specified name already exists, `{source}_copy_{n}` if omitted).
    - Source object immutability, optional transform application, undo integration, and deterministic `ChangeVerifier` rule.
  - **End-to-End Agentic Acceptance Suite**:
    - Headless Blender integration test proving full multi-round agentic loop on real scene: prompt -> inspect -> plan -> approval -> execution -> verification -> final response.
    - Live Blender verification of mesh geometry, modifier state, shading, material BSDF, active camera, and light.
    - Verified plan self-repair loop on step failure without recreating already-successful mutations.

---

## [Unreleased] - M4.2 High-Level Plan Review

### Added
- **M4.2: Structured Plans, Validation, Execution, Batch Approval**:
  - Frozen `Plan` / `PlanStep` models with validated-snapshot immutability.
  - Strict `PlanValidator`: unknown-tool, argument schema, dependency, cycle and `propose_plan`-nesting rejection; deterministic topological order.
  - `propose_plan` meta-tool for declarative plan intake (no scene mutation).
  - `PlanExecutor` orchestration layer over existing ToolDispatcher plus semantic verification and explicit visual-verification hooks; fail-fast step execution with `PlanExecutionSummary`.
  - `PlanReview` single batch-approval gate: no step executes before approval; approve runs immutable plan once; reject runs zero mutations; single-use, stale-turn/cancellation protected.
  - Approved plan suppresses per-step re-approval; standalone tool approval path unchanged.
  - Risk derived from registry/tool metadata; LLM `overall_risk` ignored.

---

## [0.7.0] - 2026-09-13

### Added
- **M7 Task 3: Visual Scene Verification**:
  - `VisualVerifier` (`agent/visual_verifier.py`) evaluating viewport state against high-level natural language prompt intent.
  - Hierarchical verification: deterministic RNA semantic verification (`ChangeVerifier`) is authoritative; visual verification is skipped if semantic verification fails.
  - Deterministic structured output format (`PASS`, `FAIL`, `UNCERTAIN` + concise rationale).
  - Fault-tolerant `VisualResultParser` handling malformed JSON, markdown fences, unrecognized status values, or empty strings gracefully without unhandled exceptions.
  - Read-only semantic tool `visual_verify` (`tools/read_only/visual_verify.py`) registered in `ToolRegistry` (`RiskLevel.READ_ONLY`).
  - Safe failure policy: `FAIL` and `UNCERTAIN` report visual discrepancies without triggering automatic mutation rollbacks.
  - Strict thread isolation: viewport capture and screenshot resolution remain on Blender main thread; worker thread handles HTTP/JSON/SSE.
  - Zero raw image bytes or base64 strings in history logs or serialized results (`to_dict()`).
  - Automatic post-mutation visual verification wired into `AgentRuntime._execute_and_verify` when visual confirmation is requested by user prompt or runtime expectation.
  - Added unit test suite `tests/unit/test_visual_verifier.py` (unit tests expanded to 375 tests).
  - Added Blender headless integration suite `tests/integration/test_visual_verification_integration.py` (master suite expanded to 17 suites).
- **M7 Task 2: Multimodal Provider Integration**:
  - `ChatMessage` and `ProviderRequestContext` updated to support in-memory image attachments (`image_id` and `images: Mapping[str, bytes]`).
  - `ContextBuilder.build` resolves raw PNG bytes on the main thread via `adapter.get_viewport_screenshot(image_id)` before worker task dispatch.
  - Background worker thread isolation: worker strictly handles HTTP/JSON/SSE off the main thread without touching `bpy` or `gpu`.
  - `OpenAIRequestMapper` maps messages with images into OpenAI-compatible `image_url` data URIs (`data:image/png;base64,...`) entirely in memory.
  - In-memory privacy: zero temporary PNG files written to disk; raw image bytes and base64 strings excluded from history logs and message serialization.
  - Deterministic capability gate: `supports_multimodal=False` deterministically yields `PROVIDER_UNSUPPORTED` / `MultimodalUnsupportedError`.
  - Added `tests/unit/test_multimodal_provider.py` (unit tests expanded to 335 tests).
  - Added `tests/integration/test_multimodal_integration.py` (master Blender integration test suite expanded to 16 suites).
- **M7 Task 1: Viewport Screenshot Capture Primitive**:
  - `capture_viewport` read-only semantic tool (`RiskLevel.READ_ONLY`) in `tools/read_only/capture_viewport.py`.
  - `ViewportReader` in `adapter/readers/viewport_reader.py`:
    - Resolves active 3D Viewport in Blender context and fallback screens.
    - Offscreen GPU framebuffer rendering via `gpu.types.GPUOffScreen` with `do_color_management=True`.
    - Pure Python in-memory PNG encoder (`encode_png_rgba`) using `zlib` and `struct` (zero external dependencies).
    - Bounded in-memory LRU cache (max 10 images) mapping `image_id` to raw PNG bytes.
    - Zero filesystem writes, zero scene contamination (objects, meshes, materials, images, and selection unchanged).
  - Main-thread execution enforcement (`ThreadSafetyViolationError` on cross-thread calls).
  - Clean metadata contract preventing conversation log and history pollution.
  - Added `tests/unit/test_capture_viewport.py` (unit tests expanded to 320 tests).
  - Added `tests/integration/test_viewport_capture.py` (master Blender integration test suite expanded to 15 suites).

---

## [0.6.0] - 2026-09-13

### Added
- **M6: Materials & Shader Tools**:
  - `set_material`: Mutates Principled BSDF shader socket properties (`base_color`, `metallic`, `roughness`, `emission_color`, `emission_strength`, `alpha`).
  - `assign_material`: Binds existing or newly created materials to object material slots with automatic slot expansion.
  - Normalization & clamping: 3-element RGB automatically converted to 4-element RGBA; out-of-range scalars/colors clamped safely to [0, 1].
  - Deterministic material verification in `ChangeVerifier` and `build_change_set_from_result`.
  - Partial verification support: modifying a single property verifies without failing on untouched default sockets.
  - Lossless shader undo/redo: all material mutations record atomic undo steps via `push_undo_step()`.
  - Headless integration test suite (`tests/integration/test_material_mutations.py`) validating all 10 acceptance scenarios including genuine RNA divergence detection (`test_04_real_verification_fail`).

---

## [0.5.0] - 2026-09-13

### Added
- **M5: Deterministic Mutation Verification & Change Sets**:
  - `ChangeSet` immutable data model capturing `operation`, `target_name`, `before`, `expected_after`, and `actual_after`.
  - Pure Python `ChangeVerifier` engine (100% standard library, zero `bpy` dependencies).
  - `build_change_set_from_result` mapper deriving expected states directly from tool call parameters.
  - Floating point and rotational epsilon tolerances (`EPSILON=1e-3`, Euler circular wrapping in `[-pi, pi]`).
  - Verification integration in `AgentRuntime._execute_and_verify`.
  - Structured failure handling: divergence produces `VERIFICATION_FAILED` error code, detailed property mismatches, and safe turn termination.
  - Headless integration test suite (`tests/integration/test_verification_integration.py`).

---

## [0.4.0] - 2026-09-13

### Added
- **M4.1: Deterministic Approval Gate**:
  - `ApprovalPolicy` providing central risk-based execution gating (`READ_ONLY`/`LOW` auto-approve; `MEDIUM`/`HIGH`/`CRITICAL` require explicit user confirmation).
  - Pure Python immutable `PendingApproval` container with cryptographic UUID tokens (`approval_id`), frozen `tool_call` parameters, and human-readable descriptions.
  - Runtime execution interception in `AgentRuntime`: even if the LLM provider directly emits destructive tool calls without conversational confirmation, execution is deterministically trapped in `AgentState.PENDING_APPROVAL`.
  - `runtime.approve(approval_id)`: Dispatches tool exactly once and invalidates token against duplicate execution.
  - `runtime.reject(approval_id)`: Guarantees tool is never dispatched, producing controlled `USER_REJECTED` outcome returned to conversation.
  - Cancellation safety: `cancel_current_turn()` immediately invalidates pending approvals.
- **Viewport GPU Overlay Approval Card**:
  - In-viewport floating card with amber warning styling (`⚠ Confirm Action`), object action descriptions, and risk badge.
  - Interactive `[ Reject (N) ]` and `[ Approve (Y) ]` buttons with hover feedback.
  - Full keyboard shortcut support: `Y` / `A` / `Enter` to approve, `N` / `R` / `Esc` to reject.
  - Fixed Blender input event handling for `BACK_SPACE` key and added `Ctrl+Backspace` word deletion support.
- **Verification & Testing**:
  - Added `tests/unit/test_approval_gate.py` verifying all 12 approval security invariants (unit test suite expanded to 252 tests).
  - Added `tests/integration/test_approval_integration.py` confirming live object deletion and rejection semantics under headless Blender (integration test suite expanded to 12 suites).
  - Full manual validation completed on real Blender GUI with live 9Router LLM provider.

---

## [0.3.0] - 2026-09-13

### Added
- **M3.1: Safe Mutation & Undo Foundation**:
  - `create_primitive`: Generates `CUBE`, `SPHERE`, or `PLANE` with deterministic names and dimensions via Data API.
  - `transform_object`: Translates, rotates, and scales existing objects in absolute or relative coordinates.
  - `delete_object`: Safely unlinks and purges targeted objects by exact name with `ObjectNotFoundError` fail-safes.
  - Atomic Undo: Integrated `push_undo_step()` into all mutation mutators, enabling lossless `Ctrl+Z` / `Ctrl+Shift+Z` native Blender undo operations.
  - Strict thread-safety guards ensuring all scene mutations execute exclusively on Blender's main thread.
- **In-Viewport Native GPU HUD (M2.9)**:
  - Floating HUD drawn directly in the 3D Viewport via Blender `gpu` and `blf` APIs (Higgsfield-inspired floating bar, ~0 MB added binary size).
  - Text editing buffer, cursor blink, Turkish and Unicode input support, responsive layout, and `Alt+Space` modal toggle operator.
- **Production Provider Wiring**:
  - Connected production addon initialization to live `OpenAICompatibleProvider` driven by user preferences (`base_url`, `model`, `api_key`).

---

## [0.2.0] - 2026-09-07

### Added
- **OpenAI-Compatible Streaming Provider Engine**:
  - Pure Python `HttpClient` using `urllib.request` with streaming bytes reading, auth header hygiene, and instant cancellation support.
  - Pure Python `SSEParser` adhering to W3C EventSource standard, supporting arbitrary chunk fragmentation, UTF-8 boundary handling, LF/CRLF line endings, and `[DONE]` sentinels.
  - Pure Python `ToolCallAccumulator` reassembling streaming fragmented tool-call deltas into validated `ToolCall` instances.
  - `OpenAICompatibleProvider` connecting to standard `/v1/chat/completions` endpoints.
  - `ContextBuilder` mapping internal `Conversation` and registered tools to OpenAI function schemas with context character safety cap (`MAX_CONTEXT_CHARS=15000`).
- **Full AgentRuntime Tool Round-Trip (M2.7)**:
  - User Prompt -> LLM streaming -> `tool_calls` -> Main Thread `ToolDispatcher` -> `ToolResult` -> `Conversation` -> 2nd LLM call -> Final Assistant Response.
  - Multi-round sequential tool execution within a single user turn.
  - Loop safety guard (`max_tool_rounds` / `MAX_TOOL_ROUNDS_EXCEEDED`).
  - Stale turn rejection and clean in-flight cancellation without residual tool executions.
  - Dual execution modes: async event-driven (`submit_prompt`) and synchronous (`run`).
- **Addon Preferences & Configuration Management (M2.1)**:
  - Native Preferences UI in Blender for `Base URL`, `Model`, `API Key`, and `Timeout`.
  - Password subtype masking for API keys in UI.
  - Atomic, restricted-permission configuration persistence (`config.json`).
  - Support for environment variable overrides (`OPENAI_BASE_URL`, `BLENDER_AI_API_KEY`, etc.).
- **Tests & Verification**:
  - Pure Python unit test count increased to 221 tests.
  - Blender headless integration test suites expanded to 9 suites, including live Blender datablock round-trip verification (`test_provider_roundtrip.py`).
  - Added live endpoint test harness (`tests/manual/test_live_openai_endpoint.py`) targeting local 9Router (`http://localhost:20128/v1`).

---

## [0.1.0] - 2026-09-07

### Added
- **5 Non-Destructive Grounding Tools**:
  - `inspect_scene`: Scene hierarchy, camera, render settings, object counts.
  - `inspect_selection`: Current selection and active object transform.
  - `inspect_object`: Object metadata, transform matrices, modifier stack, material slots.
  - `inspect_material`: Principled BSDF shader parameters and material slots.
  - `inspect_mesh`: Topology diagnostics, vertex/edge/face counts, UV channel detection, world-space bounding box.
- **Thread-Safe Asynchronous Boundary**:
  - Main thread / background worker isolation (`AgentWorker`).
  - `ThreadSafeEventQueue` with bounded batch draining.
  - `BlenderAdapter` main-thread safety guard (`ThreadSafetyViolationError`).
  - `TimerBridge` consuming events via `bpy.app.timers`.
- **State Machine & Runtime Lifecycle**:
  - `AgentStateMachine` with deterministic transitions (`IDLE`, `PROCESSING`, `EXECUTING_TOOL`, `ERROR`).
  - Turn metrics tracking (`t_submitted`, `t_first_event`, `t_tools_duration`, `t_completed`).
  - In-flight cancellation and graceful unregistration handling.
- **Native Blender 5.2 Interface**:
  - 3D Viewport sidebar N-Panel (`VIEW_3D` -> `AI Copilot`).
  - Custom `UIList` displaying user prompts, tool executions, and assistant responses.
  - Prompt submission, cancel, and clear history operators.
  - Blender 5.2 extension manifest (`blender_manifest.toml`).
