# Higgsfield gap analysis: what an open-source, Blender-native version needs

Research date 2026-09-30. Türkçe özet en altta. The feature map below is the state before v1.3.0; the status section right after this line says what has been built since.

## Status (v1.3.0, same day)

Steps 1 to 4 of the proposed order are built: `render_image`, `render_animation` (MP4), `set_environment` (5 presets), `camera_move` (16 presets) and the skill `blender-cinematic-shot`. They were then tried the way the project intends: **chat models drive the add-on's own agent** (through 9router: `ag/claude-sonnet-4-6`, `ag/gemini-pro-agent`, `openrouter/space-bunny-alpha`), one short Turkish prompt per shot ("model a castle, set golden hour light, orbit the camera, render a 5 second MP4"). Eight shots are in [`demos/`](../demos/README.md) (`shot-*`, MP4 plus frames plus the chat). What the runs showed:

- All three models finish the whole chain (model, light, camera, MP4) unaided in 20 to 64 tool calls; free and mid models sometimes need one or two nudges ("the video is not rendered yet"), which the bench script sends like a user would.
- The weak link is the 3D model, not the camera: floating cone roofs, blocky soldiers, dark robots. Lighting presets needed tuning after the first renders (blown highlights on golden hour, white sky on overcast); more tuning and a look check by the model (`render_image`, then fix) is the next quality lever.
- Found and fixed on the way: the in-Blender agent stopped a turn on the first tool error and had a fixed limit of 5 tool rounds; the image store kept 10 pictures and a long session died with `IMAGE_NOT_FOUND`.

### v1.4.0: characters move

`rig_character` and `animate_character` (idle, walk, run, aim, wave, jump), camera `follow` and animated glb export were added. The character is built from separate parts (head, torso, arms, legs, accessories); no armature or skinning is needed because pivots sit at the joints and motion presets keyframe part rotations. Chat models (Gemini Pro agent, Space Bunny; Sonnet's Antigravity quota ran out during the runs) built soldiers, a robot, a knight and a zombie from one short prompt, rigged them, made them walk, run, wave or aim, and had the camera follow: `demos/shot-*` (soldier-walk, robot-wave, knight-run, soldier-aim, zombie-walk). Findings: models keep the parts separate when the prompt says so; hierarchy and pivots work on the first try; the visible weakness is still the look of the blocky models and small proportion mistakes (a small soldier in a big frame, washed-out light on white backdrops).

### v1.5 to v1.6: film tools, bent limbs, library, polish

- **Film language** (v1.5): 38 camera presets, 9 lights with a physical sky, `set_look` colour grades and glow, `camera_settings` (depth of field, rack focus, motion blur), `render_contact_sheet`, `edit_video` (crossfade, wipe, slow motion) and `render_shots` (a shot list to one MP4). A three-shot film was made by Space Bunny from one prompt.
- **Bent limbs** (v1.6): optional `forearm_*` and `shin_*` parts give elbows and knees; run, walk, wave, aim and jump use them. A free model (DeepSeek V4 Flash through 9router) made a runner with bending knees and elbows, polished parts and a sunset look from one prompt (`demos/shot-runner-bent-*`).
- **Character library** (v1.6): `character_library` saves a rigged character (materials included) and loads it into any later scene, so one character stays the same across shots.
- **Polish** (v1.6): `polish_model` bevels hard corners and shades smooth with sharp edges kept, the cheapest way to lift the look of blocky models.
- Weak and free models needed help: lists wrapped as `{"item": [...]}`, numbers as strings and batches of tool calls with an approval in the middle are now handled by the add-on instead of failing.

### v1.7: faces, music, 50 camera moves

- **Faces**: `eye_l`, `eye_r`, `mouth` parts blink in every animation; `talk` lip-syncs a line of text (vowels open the mouth, consonants and pauses close it, no audio needed); `happy`, `surprised`, `angry` change eyes, mouth and posture.
- **Music**: `make_soundtrack` composes six moods procedurally; `render_shots` with `music` mixes one, composed to the film's length, into the MP4 (AAC).
- **Camera**: 50 presets, the same order of magnitude as Higgsfield's list.

### An honest note on quality

Higgsfield runs models trained to generate video and 3D; here chat models (ChatGPT, Claude, Gemini, free models) direct a deterministic toolset. That means the tools can be exact (camera paths, light, edit, sound, rigs) while the look of what a model *builds* depends on that model: blocky low-poly shapes, proportions that need a second look, sometimes a wrong light preset. The project answers this with strict but forgiving tools (lists wrapped by weak models, batches with approvals, string numbers all work), recipes in the skills, and ways for the model to check its own work (`render_contact_sheet`, `render_image` returns the picture). A trained text-to-3D model can sit next to this later: generate a `.glb` with an external tool, bring it in with `import_asset`, then rig, light, film and score it with the tools above.

### v1.8: a trained generator can plug in

`generate_3d` is the seam for a trained text-to-3D or image-to-3D model: the user points `BLENDER_COPILOT_3D_URL` at a service (a local Hunyuan3D or TRELLIS server, a hosted API behind a small wrapper), and the chat model can ask it for organic or detailed props and static characters, then light, film and score them with the same tools ([GENERATE_3D.md](GENERATE_3D.md)). The contract is tested against a mock server; real generator wrappers are not bundled or tested, because the project does not pick one for the user. Shots of a film also carry on where the previous one stopped in a character's animation now (`render_shots` `continuous`).

Still missing compared with Higgsfield: a tested bundled generator wrapper (it needs a GPU and the user's choice of engine), rigging for a generated single-mesh character (generated models are static; walking and talking characters are built from parts), a shot list UI, realistic materials and hair, and above all the look of what chat models build from primitives. Realistic (diffusion) video is out of scope: this is controllable 3D animation.

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
