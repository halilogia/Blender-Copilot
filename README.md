# Blender - Copilot — v1.18.0

> Autonomous Grounding Copilot & AI Agent inside Blender 5.2 LTS.

[English](#english) | [Türkçe](#türkçe)

[Contributing](CONTRIBUTING.md)

[![Blender Version](https://img.shields.io/badge/Blender-5.2%20LTS-orange.svg)](https://www.blender.org/)
[![Python](https://img.shields.io/badge/Python-3.11%20%7C%20Zero%20Dependencies-blue.svg)](https://www.python.org/)
[![Tests](https://img.shields.io/badge/Tests-835%20Unit%20%7C%2038%20Integration%20Suites-brightgreen.svg)]()
[![License: GPL-3.0](https://img.shields.io/badge/License-GPL--3.0-blue.svg)](LICENSE)

**Blender - Copilot** is a native, extensible AI agent built specifically for Blender 5.2 LTS. It connects modern Large Language Models (LLMs) directly to Blender's internal data model using deterministic grounding tools, safe scene mutations with atomic undo, strict policy-driven human approval gates, and a lightweight native GPU Viewport overlay.

## What's new (details in [CHANGELOG.md](CHANGELOG.md))

- **v1.18** task ledger: `task_report` says by meaning what an AI task changed (objects, materials, moves), `task_rollback` undoes the whole task and verifies it, and the N-panel has **What changed?** and **Undo AI task**.
- **v1.17** world pack: `create_terrain` (hills, a flat spot for buildings) and `scatter` (many linked copies over an area, along a path, onto the terrain, out of avoided objects).
- **v1.16** deeper `mesh_edit`: loop cut, knife plane, bridge two faces, delete / flip faces, dissolve, separate, apply modifiers; face selectors by material, area and nearness.
- **v1.15** textures pack: `unwrap_uv` and `bake_material` (procedural materials painted into an image, so a `.glb` carries the look).
- **v1.14** `check_model`: a model is measured, not looked at (normals, doubled vertices, scale, ground, triangle budget), with the tool that fixes each finding.
- **v1.13** `set_material` presets (wood, stone, brick, metal, gold, grass, water, sand, concrete, marble).
- **v1.12** `check_shot` (framing and brightness as numbers) and a fix for colour grades that were never applied in Blender 5.2.
- **v1.11** `create_prop`: 18 ready-made props (crate ... rig-ready person and robot) in one call; broken tool JSON from weak models is repaired.
- **v1.10** tool packs: film, character, texture and world tools load only when the request needs them (a plain modeling request sends about 5,800 tokens of tool descriptions instead of 11,000).
- **v1.3 to v1.9** film and characters: environments, 50 camera moves, colour looks, `render_shots`, `edit_video`, procedural music, rigged characters with faces, lip sync and scenes.
- **v1.2** local MCP bridge for Claude Code and other MCP clients, modeling tools, `export_gltf`, Claude Code plugin.
- **v1.0 to v1.1** grounding, safe mutations with undo, approval gate, vision, asset import, check-only updates.

Which chat model drives it best: [docs/MODELS.md](docs/MODELS.md). Verified with 835 pure-Python unit tests and 38 headless Blender suites; every feature since v1.4 was run end to end by a free chat model (demos in [demos/](demos/README.md)).

The Godot side: [Godot AI Sidebar](https://github.com/halilogia/Godot-AI-Sidebar) can use this add-on from its own settings (Settings > Blender) to get 3D models as `.glb` files.

---

## English

## Key Features

- **What a chat model can do with it (53 tools, loaded by need):**
  - **Model**: `create_prop` (18 ready-made props), `create_primitive`, `create_mesh`, `mesh_edit` (extrude, inset, bevel, loop cut, knife plane, bridge, dissolve, separate, apply modifiers ...), `add_modifier`, `add_shape_modifier`, `polish_model`, `join_objects`, `parent_object`, `apply_transform`, `set_origin`.
  - **Look**: `set_material` (colour, or a procedural preset), `unwrap_uv`, `bake_material`, `set_shading`, `set_environment`, `set_look`.
  - **Check (numbers instead of eyes)**: `check_model`, `check_shot`, `task_report`, `frame_view`, `capture_viewport`, `visual_verify`; `task_rollback` takes a whole AI task back.
  - **World**: `create_terrain`, `scatter`.
  - **Characters**: `rig_character`, `animate_character`, `animate_sequence`, `character_library`.
  - **Film**: `camera_move` (50 moves), `camera_settings`, `render_image`, `render_contact_sheet`, `render_animation`, `render_shots`, `edit_video`, `make_soundtrack`.
  - **Game engines**: `export_gltf` (with animations), and the Claude Code plugin skills that hand the file to Godot.
- **Task ledger**: before the first tool of an AI task the scene is snapshotted by meaning; `task_report` compares, `task_rollback` undoes exactly the task's undo steps and verifies the result, and the N-panel shows **What changed?** and **Undo AI task** after a task that changed something.

- **Strict Non-Destructive Grounding**:
  - `inspect_scene`: Detailed breakdown of scene hierarchy, active camera, render settings, and object counts.
  - `inspect_selection`: Active and selected object properties, types, and transforms.
  - `inspect_object`: Complete object transform, parentage, modifier stack, and material slots.
  - `inspect_material`: Principled BSDF shader parameters, color values, metallic, roughness, and slot mapping.
  - `inspect_mesh`: Topology diagnostics (vertex/edge/polygon counts), world-space bounding box dimensions, and UV availability.

- **Safe Viewport Mutations & Atomic Undo (M3.1)**:
  - `create_primitive`: Generates `CUBE`, `SPHERE`, or `PLANE` with deterministic transforms and names via Data API.
  - `transform_object`: Translates, rotates, and scales existing objects in world coordinates.
  - `delete_object`: Safely unlinks and purges targeted objects with name verification and missing-object safety.
  - **Native Undo Push**: Every mutation automatically issues `bpy.ops.ed.undo_push()`, ensuring complete, lossless `Ctrl+Z` undo integration.

- **Deterministic Approval Gate & Risk Policy (M4.1)**:
  - Hardened execution policy independent of LLM hallucination or model prompts.
  - Granular risk classification: `READ_ONLY`, `LOW` (auto-execute), `MEDIUM`, `HIGH` (require explicit human approval).
  - Destructive operations (e.g. `delete_object`) freeze execution in `PENDING_APPROVAL`.
  - In-viewport interactive approval card with `[Approve]` and `[Reject]` buttons, keyboard shortcuts (`Y`/`N`), and single-use cryptographic security tokens.
  - User rejection safely routes back to the LLM conversation loop as structured context without throwing unhandled exceptions.

- **Dual User Interface**:
  - **Native GPU Viewport Overlay (HUD)**: Sleek, floating bar rendered directly in the 3D Viewport framebuffer (`SpaceView3D.draw_handler_add` with `POST_PIXEL`). Features anti-aliased geometry, drop shadows, Unicode/Turkish input buffer, interactive buttons, and hotkey toggling (`Alt+Space`). Zero external dependencies.
  - **3D Viewport N-Panel**: Standard persistent sidebar panel with complete session history (`UIList`), operation status badges, and manual approval controls.

- **Thread-Isolated Architecture**:
  - **Background Worker**: Handles HTTP connections, SSE streaming, and payload serialization without ever freezing Blender's UI or dropping viewport frames.
  - **Main Thread Event Pump**: All Blender Python API (`bpy`) queries, mutations, and undo pushes run exclusively on Blender's main event loop via `TimerBridge` (`bpy.app.timers`).
  - **Thread-Safe Queue**: High-performance, lock-bounded event passing prevents race conditions, memory leaks, and UI starvation.

- **LLM Integration (dual dialect)**:
  - OpenAI-Compatible Chat Completions streaming (`POST /v1/chat/completions` with `stream=True`).
  - Native Anthropic Messages streaming (`POST /v1/messages`, `anthropic-version: 2023-06-01`, shared `SSEParser` + `ToolCallAccumulator`); switch via Preferences Provider dropdown or `BLENDER_AI_PROVIDER`.
  - End-to-end tool/function calling round-trips (`tool_calls` -> approval gate -> execute tool -> return `tool` message -> final synthesis).
  - Multi-round conversational loops with automated loop guards (`max_tool_rounds`).
  - Tested with **9Router**, **LM Studio**, **Ollama**, **OpenRouter**, **OpenAI**, and **Anthropic** endpoints.
- **Vision Cost Guard & Local Semantic Search**:
  - `capture_viewport(max_side=256)` thumbnail mode for cheap visual grounding.
  - Stdlib-only local embedding (hashed trigram + token TF, dim 256) for scene/asset ranking — no numpy, no network.
- **Local Asset Browser + Check-Only Updates**:
  - `import_asset(path)` (`LOW` risk, traversal-guarded, undo-integrated, verifier-checked) over a user library dir (`.blend/.glb/.obj/.fbx`).
  - `ai_sidebar.check_updates` operator: GitHub releases check only, never downloads; gated by Blender `online_access`.

- **Zero External Dependencies**:
  - Built entirely with Python's standard library (`urllib.request`, `http.client`, `json`, `threading`, `queue`, `dataclasses`).
  - No `pip install` or external wheels required inside Blender's bundled Python environment.

---

## MCP bridge and modeling tools

External agents (Claude Code, Codex) can use this add-on through a local, token-protected MCP server, and the new modeling tools build low-poly game assets without running arbitrary Python (`create_mesh`, `mesh_edit`, `add_shape_modifier`, `frame_view`, `export_gltf` ...). Start it from the N-panel section **MCP bridge (Claude Code)** or headless with `blender --background --python tools/serve_mcp_headless.py`. Claude Code plugin (skills and `/blender-connect`):

```bash
claude plugin marketplace add halilogia/Blender-Copilot && claude plugin install blender-copilot@blender-copilot
```

Details, security model and tool list: [docs/MCP.md](docs/MCP.md).

**Demo gallery:** 33 game props (crate, barrel, house, car, watchtower, cannon, soldier, castle ...) modeled from one short prompt each, by Claude Code over MCP and by the add-on's own agent through 9router (Claude Sonnet 4.6, Gemini Pro, Space Bunny) through the bridge from one short prompt each, with chats and triangle counts: [demos/](demos/README.md).

## Architecture Overview

```text
               +------------------------------------------------------+
               |                  Blender Main Thread                 |
               |                                                      |
               |  [ Viewport GPU HUD ] <======> [ N-Panel Sidebar ]   |
               |            |                        ^                |
               |            v                        |                |
               |     [ TimerBridge ] <---------------+                |
               |            |                        |                |
               |            v                        |                |
               |     [ AgentRuntime ]                |                |
               |      /     |      \                 |                |
               |     /      |       \                |                |
   [ StateMachine ]  [ Dispatcher ]  [ Conversation ]|                |
                            |                         |                |
                            v                         |                |
                  [ Approval Policy Gate ]            |                |
                   /                  \               |                |
       (Risk <= LOW)                   (Risk >= MEDIUM)|               |
             |                                  |     |                |
             v                                  v     |                |
     [ Tool Execution ]               [ PENDING APPROVAL ]             |
      - Grounding Tools                        |                       |
      - Mutation Tools                         |                       |
             |                                 | (User Approves/Rejects)
             v                                 |                       |
     [ BlenderAdapter ] <----------------------+                       |
      (bpy datablocks / undo_push)                                     |
               +-----------|-------------------------|----------------+
                           |                         |
               Thread-Safe | Event Queue             | Events
                           v                         |
               +------------------------------------------------------+
               |                Background Worker Thread              |
               |                                                      |
               |                  [ AgentWorker ]                     |
               |                         |                            |
               |                         v                            |
               |             [ OpenAICompatibleProvider ]             |
               |                         |                            |
               |            +------------+------------+               |
               |            |                         |               |
               |            v                         v               |
               |      [ HttpClient ]            [ SSEParser ]         |
               |     (urllib.request)                 |               |
               |                                      v               |
               |                         [ ToolCallAccumulator ]      |
               +--------------------------------------|---------------+
                                                      |
                                                      v
                                      Local / Remote OpenAI Endpoint
                                  (9Router / Ollama / LM Studio / OpenAI)
```

---

## Project Structure

```text
Blender Copilot/
├── adapter/                      # Main-thread Blender access
│   ├── blender_adapter.py        # One method per tool, thread-checked, wraps the mutators
│   ├── mutators/                 # bpy / bmesh code: modeling, props, materials, textures, world, cinema, looks, characters, video, QA, undo
│   ├── readers/                  # Read-only scene, object, mesh, material, viewport readers and the scene snapshot
│   └── task_ledger.py            # One AI task = report + verified rollback
├── agent/                        # The add-on's own agent: providers, runtime, dispatcher, approval policy, verifier, memory
├── bridge/                       # Local MCP server (HTTP, token, protocol, tool host, headless control)
├── core/                         # Pure Python (no bpy): types, config, tool packs, and the logic behind the tools
│   ├── camera_paths.py  lipsync.py  soundtrack.py  motion_paths.py   # film and characters
│   ├── prop_kinds.py  material_presets.py  scatter_points.py         # props, materials, terrain and scatter
│   └── shot_qa.py  model_qa.py  scene_diff.py                        # numbers instead of eyes
├── tools/                        # Tool definitions (schema, risk level) and the registry
│   ├── mutations/                # Tools that change the scene or write files
│   └── read_only/                # Inspect, capture, task_report, enable_tools
├── ui/                           # N-panel, viewport HUD, operators, preferences, MCP panel
├── plugin/                       # Claude Code plugin: skills and /blender-connect
├── scripts/                      # Benchmarks and reports: demo_bench_mcp.py, model_report.py, demo_promote.py ...
├── demos/                        # Models and films made by chat models, with chats and triangle counts
├── docs/                         # MCP.md, MODELS.md, HIGGSFIELD.md, KNOWLEDGE.md
├── tests/
│   ├── unit/                     # Pure Python suites (835 tests)
│   ├── integration/              # Headless Blender 5.2 suites (38)
│   └── run_all_blender_tests.py  # Runs every headless suite
├── blender_manifest.toml         # Blender 5.2 Extension manifest
└── __init__.py                   # Add-on lifecycle and tool registration
```

---

## Installation

### Prerequisites
- **Blender**: 5.2.0 LTS or higher (tested against Blender 5.2.2 LTS).
- **LLM Endpoint**: Any OpenAI-compatible Chat Completions endpoint (e.g. 9Router at `http://localhost:20128/v1`, Ollama, LM Studio, or OpenAI).

### Install as Extension / Addon
1. Download or clone this repository into your Blender extensions or addons directory:
   ```bash
   git clone https://github.com/halilogia/Blender-Copilot.git
   ```
2. In Blender, open **Edit > Preferences > Add-ons**.
3. Search for **Blender - Copilot** and enable the checkbox.
4. Expand the addon preferences to configure:
   - **Provider**: `OpenAI-Compatible` or `Anthropic Native`.
   - **Base URL**: e.g. `http://localhost:20128/v1` (or `https://api.anthropic.com/v1` for Anthropic).
   - **Model**: e.g. `gpt-4o`, `qwen2.5-coder`, `llama3.1`, `claude-sonnet-4-5`.
   - **API Key**: Enter if required (masked automatically; sent as `Bearer` for OpenAI, `x-api-key` for Anthropic).
   - **Timeout (seconds)**: Default is `30.0`.
5. In the 3D Viewport:
   - Press **`Alt + Space`** to open the floating **GPU Viewport HUD**, or
   - Press **`N`** to open the sidebar and switch to the **AI Copilot** tab.

---

## Usage

1. **Ask or Command**: Open the HUD (`Alt+Space`) or use the N-Panel, type a request (e.g., *"Sahneyi incele"*, *"Bir küp oluştur"*, or *"Küpü sil"*), and press Enter / Gönder.
2. **Autonomous Tool Selection**: The Copilot communicates with your LLM, selects the required grounding or mutation tools, and presents them to the execution layer.
3. **Approval Gate for Destructive Actions**: If a tool carries `MEDIUM` or `HIGH` risk (such as `delete_object`), execution stops immediately in `PENDING_APPROVAL`.
   - An amber approval card appears in the Viewport HUD and N-Panel.
   - Click **Approve (Y)** or press `Y`/`Enter` to permit execution.
   - Click **Reject (N)** or press `N`/`Esc` to decline. The rejection is fed back to the LLM to continue the conversation safely.
4. **Undo Support**: Any mutation can be reverted at any moment via Blender's standard `Ctrl + Z`.
5. **Prompt Queue**: Prompts submitted while another turn is active are kept in FIFO order and processed automatically.
6. **Plan and Task Progress**: Multi-step plans show approval cards and task progress with completed/failed step status.
7. **Multiline HUD**: Long prompts and assistant responses wrap across multiple lines. Shift+Enter inserts an explicit newline.

---

## Running Tests

### 1. Pure Python Unit Tests (Fast, No Blender Required)
Runs the complete pure-Python unit suite:
```bash
python tests/run_unit_tests.py
```

For a focused change, pass a test module or file and avoid waiting for the full suite:
```bash
python tests/run_unit_tests.py tests.unit.test_prompt_queue tests.unit.test_hardening
```

### 2. Headless Blender Integration Tests
Runs all 38 headless integration test suites inside Blender's actual Python runtime:
```bash
python tests/run_all_blender_tests.py
```

### 3. Live 9Router / OpenAI Endpoint Verification
Test your active local 9Router or OpenAI-compatible server:
```bash
python tests/manual/test_live_openai_endpoint.py
```

### 4. Diagnostics

The add-on writes a rotating diagnostic log to the operating system's temporary
directory by default. The N-Panel **Diagnostics** section shows the active path
and can copy it to the clipboard.

For local development, opt into a project-local directory without changing
the installed add-on default:

```powershell
$env:BLENDER_AI_LOG_DIR = ".\\logs"
```

The `logs/` directory and `*.log` files are excluded from Git because logs may
contain prompts and provider error details.

---

## Türkçe

Blender - Copilot, Blender içinde çalışan yerel ve genişletilebilir bir AI
ajanıdır. OpenAI uyumlu LLM sağlayıcılarıyla konuşur; sahneyi incelemek,
nesne oluşturmak, dönüştürmek, silmek, materyal düzenlemek ve çok adımlı
işlemleri güvenli biçimde yürütmek için yapılandırılmış araçlar kullanır.

### Öne çıkan özellikler

- **Bir sohbet modeli neler yapabilir (53 araç, ihtiyaca göre yüklenir):** hazır prop'lar (`create_prop`, 18 tür), modelleme ve mesh düzenleme (loop cut, bıçak, köprü, dissolve ...), malzeme presetleri, UV ve doku pişirme (`.glb` dokuyu taşır), arazi ve toplu dağıtma (`create_terrain`, `scatter`), karakter rig ve animasyonu, film (kamera hareketleri, ışık, renk, müzik, kurgu), glTF dışa aktarma.
- **Göz yerine sayı:** `check_model` (normaller, çift vertex, ölçek, zemine gömülme, üçgen bütçesi), `check_shot` (kadraj ve parlaklık), `task_report` (görevin sahnede neyi değiştirdiği).
- **Görev defteri:** yapay zekânın bir görevi tek parça olarak geri alınır (`task_rollback`, panelde "Undo AI task") ve sahnenin gerçekten eski haline döndüğü doğrulanır.
- **MCP köprüsü:** Claude Code ve diğer MCP istemcileri aynı araçları kullanır; Godot AI Sidebar da Ayarlar → Blender'dan bağlanıp 3B modelleri `.glb` olarak alabilir.
- Hangi sohbet modeli ne kadar iyi: [docs/MODELS.md](docs/MODELS.md). Sürüm notları: [CHANGELOG.md](CHANGELOG.md).

- Sahne, seçim, obje, materyal ve mesh inceleme araçları.
- Küp, küre ve düzlem oluşturma; obje dönüştürme ve silme.
- Kamera, ışık, materyal, modifier, shading, duplicate ve asset import (`import_asset`) işlemleri.
- Anthropic native desteği (Preferences > Provider), `capture_viewport(max_side=256)` maliyet kalkanı, stdlib local embedding ile sahne/asset araması.
- Check-only güncelleme kontrolü (`ai_sidebar.check_updates`; otomatik indirme yok).
- Risk tabanlı onay sistemi: düşük riskli işlemler otomatik, orta/yüksek riskli işlemler kullanıcı onaylıdır.
- Plan kartı, Approve/Reject butonları ve task ilerlemesi.
- Uzun promptlar ve AI cevapları için çok satırlı GPU HUD görünümü.
- Aktif işlem sürerken gönderilen mesajlar için FIFO queue.
- İptal, stale turn koruması, hata kaydı ve Blender `Ctrl+Z` undo desteği.
- Harici Python paketi gerektirmeyen standart kütüphane tabanlı mimari.

### Kurulum

1. Repository’yi indirin veya clone edin:

   ```bash
   git clone https://github.com/halilogia/Blender-Copilot.git
   ```

2. Blender’da **Edit > Preferences > Add-ons** menüsünü açın.
3. **Blender AI Sidebar** eklentisini etkinleştirin.
4. Eklenti ayarlarından OpenAI uyumlu endpoint, model ve gerekiyorsa API key girin.
5. GPU HUD için 3D Viewport üzerinde `Alt + Space`, N-Panel için `N` tuşuna basın.

### Kullanım

- `Sahneyi incele` gibi salt-okunur komutlar doğrudan çalışır.
- `Bir küp oluştur` gibi düşük riskli mutasyonlar güvenli şekilde yürütülür.
- Silme gibi riskli işlemlerde plan/onay kartı görünür; **Approve** veya **Reject** seçilir.
- İşlem sürerken yeni mesaj gönderilirse mesaj FIFO sırasına alınır.
- Uzun yazılar otomatik olarak alt satıra geçer; Shift+Enter manuel yeni satır ekler.
- Hata durumunda N-Panel’deki **Diagnostics** bölümünden log yolunu kopyalayabilirsiniz.

### Testler

Pure Python testlerini çalıştırmak için:

```bash
python tests/run_unit_tests.py
```

Odaklanmış test çalıştırmak için:

```bash
python tests/run_unit_tests.py tests.unit.test_prompt_queue tests.unit.test_event_router
```

v1.18.0 durumunda 835 pure-Python unit testi ve 38 Blender integration
test dosyası bulunmaktadır (+4 yeni unit suite, +2 yeni headless suite:
asset import 6/6, anthropic roundtrip). Headless 31/31 Blender 5.2.2 LTS’te
doğrulanmıştır; canlı GUI turu v1.2 kabul kapısındadır.

### Tanılama logları

Varsayılan log işletim sisteminin geçici klasörüne yazılır. Proje içinde
erişilebilir bir `logs/` klasörü kullanmak için PowerShell’de:

```powershell
$env:BLENDER_AI_LOG_DIR = ".\logs"
```

Loglar prompt ve provider hata ayrıntıları içerebileceği için Git’e eklenmez.

---

## License

This project is licensed under the **GNU General Public License v3.0** (GPL-3.0). See the [LICENSE](LICENSE) file for the full license text.
