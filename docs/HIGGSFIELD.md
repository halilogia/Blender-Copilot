# Higgsfield gap analysis: what an open-source, Blender-native version needs

Research date 2026-09-30. Türkçe özet en altta. The feature map below is the state before v1.3.0; the status section right after this line says what has been built since.

## Status (v1.3.0, same day)

Steps 1 to 4 of the proposed order are built: `render_image`, `render_animation` (MP4), `set_environment` (5 presets), `camera_move` (16 presets) and the skill `blender-cinematic-shot`. They were then tried the way the project intends: **chat models drive the add-on's own agent** (through 9router: `ag/claude-sonnet-4-6`, `ag/gemini-pro-agent`, `openrouter/space-bunny-alpha`), one short Turkish prompt per shot ("model a castle, set golden hour light, orbit the camera, render a 5 second MP4"). Eight shots are in [`demos/`](../demos/README.md) (`shot-*`, MP4 plus frames plus the chat). What the runs showed:

- All three models finish the whole chain (model, light, camera, MP4) unaided in 20 to 64 tool calls; free and mid models sometimes need one or two nudges ("the video is not rendered yet"), which the bench script sends like a user would.
- The weak link is the 3D model, not the camera: floating cone roofs, blocky soldiers, dark robots. Lighting presets needed tuning after the first renders (blown highlights on golden hour, white sky on overcast); more tuning and a look check by the model (`render_image`, then fix) is the next quality lever.
- Found and fixed on the way: the in-Blender agent stopped a turn on the first tool error and had a fixed limit of 5 tool rounds; the image store kept 10 pictures and a long session died with `IMAGE_NOT_FOUND`.

Still missing compared with Higgsfield: character motion (walk, aim, poses), a character library, text or image to 3D, effects such as slow motion and transitions, audio, a shot list UI. Realistic (diffusion) video is out of scope: this is 3D animation.

## What Higgsfield is (from its own pages)

An AI creative suite: text / image to **video** through hosted models (Seedance, Sora 2, Kling, Veo), image generation, and above all **direction controls**:

- **50+ camera presets**: Dolly In/Out/Left/Right, Super Dolly, Dolly Zoom, Double Dolly, Crash Zoom, Rapid Zoom, YoYo Zoom, Crane Up/Down/Over The Head, Jib, Pan, Tilt, Whip Pan, Arc Left/Right, 360 Orbit, Bullet Time, Aerial Pullback, FPV Drone, Handheld, Head Tracking, Snorricam, 3D Rotation, Hyperlapse, Timelapse, Focus Change, Dutch Angle, Fisheye, Through Object, Car Chase, Static.
- **Lighting and 50+ colour palettes**, cinematic "looks", 15+ visual effect presets.
- **Character consistency** (Soul ID: train a persona once from about 20 photos, reuse it in every shot).
- **Agent and workflow roles** (Character Creator, Cinematic Director, Content Lead, Motion Designer), an MCP server for ChatGPT, a "production skills bundle" (3D, VFX, editing).

The existing "open source" clone (OpenHiggsfield / Higgsfield-Open) is a Next.js prompt composer over 38 hosted models: "Magic Pills" add camera, framing and lighting words to the prompt, Face-Lock keeps a face, no ffmpeg (sequences export as numbered files). It does not generate anything itself and camera moves are only prompt text.

## Where Blender Copilot differs

Camera moves in a diffusion model are a hope; in Blender they are exact keyframes. Character consistency is free (the same mesh). Everything runs locally and offline. The price: the look is 3D (low-poly today), not photoreal video.

## Feature map

| Higgsfield capability | Have | Missing | Evidence / note |
|---|---|---|---|
| Low-poly props, sets | 33 demo `.glb` props by two agents | UVs, textures, organic shapes, quality control | `demos/` |
| Camera presets | `create_camera` only | `camera_move` (about 40 presets as keyframes on a rig: dolly, crane, arc, orbit, whip pan, dolly zoom, crash zoom, handheld shake, FPV path), lens and DOF settings, look-at target | pure keyframing, deterministic |
| Render still | viewport capture only | `render_image` (EEVEE) | headless EEVEE renders a 640x360 frame in about 0.15 s (probe, Blender 5.2.2) |
| Render video | none | `render_animation` to MP4 | Blender 5.2 writes MP4 directly headless: `image_settings.media_type = "VIDEO"`, `file_format = "FFMPEG"` (probe wrote a valid file); the old `file_format = "FFMPEG"` alone fails on 5.x |
| Lighting and colour looks | `create_light` | `set_environment` presets (studio, golden hour, overcast, night, neon), sky, ground, tone mapping, colour grade | probe render of the castle came out black with one sun, washed out with a flat sky: presets are needed, not optional |
| Character consistency | none, but the mesh is reusable | a named character library (`.blend` or `.glb` plus material set), `import_asset` already exists | trivial in 3D |
| Character motion | none | rig or pose presets (walk, run, idle, aim), keyframes on joined parts, or a simple armature | biggest gap: all characters are static meshes |
| Effects (slow motion, time lapse, shake, transitions) | none | time remapping, camera shake modifier, simple particle presets | mostly render settings |
| Direction from text | agent can call tools one by one | a scene-to-shot workflow skill: assets, set, light, camera move, render, check frames | skills already ship in `plugin/` |
| Generative assets (text or image to 3D) | none | optional generator tool calling an open model (Hunyuan3D, TRELLIS class) and importing the `.glb` | already listed as v1.3 candidate in ROADMAP |
| Audio, voice, lip sync | none | out of scope for now | |
| Web UI / gallery | N-panel, demo history page | project gallery, shot list, timeline | later |

## Gaps found in the current tools while doing this

1. No animation tools at all (no keyframe, no timeline, no frame range).
2. No render tools; `capture_viewport` is a UI screenshot, not a render.
3. No world or environment control (a new world has no Background node in Blender 5.x; it must be created).
4. Modeling: no UVs or textures; organic shapes (dragon, animals) stay weak; the model cannot see its own mistakes unless it calls `frame_view` and `capture_viewport` itself (the lamp run showed parts scattered and was not noticed).
5. `export_gltf` writes into one fixed folder outside the project.

## Proposed order (smallest useful step first)

1. **`render_image` and `render_animation`** (EEVEE, resolution, frame range, MP4 or PNG sequence, output inside the export folder). Everything else needs this to be visible.
2. **`set_environment`**: five lighting presets with sky, sun and tone mapping. Fixes the black or washed renders.
3. **`camera_move`**: start with 12 presets (dolly in/out, orbit, arc, crane up/down, pan, tilt, whip pan, dolly zoom, crash zoom, static), keyframed around a target, duration and speed as arguments.
4. **Shot workflow skill** `blender-cinematic-shot` (asset, set, light, move, render, verify frames).
5. **Character library and pose presets**, then simple walk cycles.
6. Optional generator tool for text or image to 3D; camera shake, time remap, transitions.

Steps 1 to 3 are three tools and one skill; the probes above show they are feasible headless. Then the same benchmark scripts (`scripts/demo_bench_mcp.py`) can produce shot demos (a 4-second orbit around the castle, a dolly-in on the soldier) with chat, frames and MP4 in `archives/`.

## Sources

- https://higgsfield.ai/ and https://higgsfield.ai/camera-controls (features, presets)
- https://github.com/princejain756/Higgsfield-Open (existing open-source clone)
- Soul ID description: https://higgsfield.ai/blog/how-to-turn-photo-into-consistent-ai-persona-creator

## Türkçe özet

Higgsfield, hazır bir video modelinin üstüne 50'den fazla kamera hareketi, ışık ve renk ayarı, karakter tutarlılığı ve bir ajan iş akışı koyan bir arayüz. Açık kaynak klon (Higgsfield-Open) yalnızca isteme kelime ekleyen bir Next.js arayüzü. Blender'da kamera hareketi kesin anahtar karedir, karakter tutarlılığı ise aynı modeli yeniden kullanmaktır; ama sonuç gerçekçi video değil 3D animasyon olur. Bizde şu an eksik olanlar: animasyon araçları, render (görüntü ve MP4), ortam ve ışık ayarları, kamera hareket ayarları, karakter hareketi. Denemelerde Blender 5.2'nin başsız modda hızlı render aldığı (kare başına yaklaşık 0,15 sn) ve doğrudan MP4 yazabildiği doğrulandı. Önerilen sıra: render araçları, ortam ayarları, kamera hareketleri, çekim skill'i, karakter kütüphanesi.
