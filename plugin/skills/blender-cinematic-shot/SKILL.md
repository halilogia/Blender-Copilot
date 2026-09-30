---
name: blender-cinematic-shot
description: Direct a short cinematic shot in Blender 5.2 through Blender Copilot's MCP tools - build or import the subject, light it with an environment preset, move the camera (dolly, orbit, crane, whip pan, dolly zoom ...) and render a PNG or an MP4. Use when the user wants a video, a camera move, a turntable, a product or scene shot, or a Higgsfield-style result made from 3D models.
---

# A cinematic shot from chat, no Python

Every step is an allow-listed tool: no code runs, the camera moves are keyframed math, and the files land in the add-on's export folder. Read the tool schemas first and use their exact argument names.

## Workflow

1. **Subject.** Model it (skill `blender-game-assets`) or bring it in with `import_asset`. Put it near the origin, real-world scale, facing +Y. One or a few objects; the camera frames all meshes unless you pass `object_names`.
2. **Light.** `set_environment` with one of: `studio` (neutral, product shots), `day` (clear sky), `golden_hour` (low warm sun, outdoor drama), `sunset` (red horizon), `dawn` (cool pink), `overcast` (soft even light), `foggy` (air full of fog, depth), `night` (dark blue, moon light from behind), `neon` (dark, magenta and cyan). It also adds a ground plane; pass `ground: false` for floating objects or a `ground_color`.
3. **Camera.** `camera_move` with a preset. Defaults frame the subject well (distance chosen so the whole subject fits a 16:9 frame, 15 degrees up, 35 degrees to the side, 35 mm, 4 seconds, 24 fps). Change `duration`, `distance`, `elevation`, `azimuth`, `focal_length` only for a reason.
4. **Look at one frame.** `render_image` (960x540 is enough) returns the picture. Check: subject fully in frame and large enough, light on the side the camera sees, no black or washed-out areas. Fix with another `set_environment` preset, `camera_move` with a different `distance` or `azimuth`, then render again.
5. **Render the shot.** `render_animation` (mp4). Then say where the file is and how long it is.

## Choosing the move

| Want | Preset |
|---|---|
| Product turntable, show all sides | `orbit` (`angle` 360, `duration` 6-8) |
| Reveal, draw the viewer in | `dolly_in`; the opposite is `dolly_out` |
| Hero, power | `crane_up` (rises past the subject), `crane_down` |
| Sweep past the subject | `arc_left`, `arc_right` |
| Scan a scene | `pan_left`, `pan_right`, `tilt_up`, `tilt_down` |
| Fast cut, energy | `whip_pan` (short, 1-2 s), `crash_zoom_in` |
| Suspense, unease | `dolly_zoom` (subject keeps its size while the background stretches) |
| Documentary, alive | `handheld` (small shake) |
| Locked frame | `static` |

More presets (50 in all):

| Want | Preset |
|---|---|
| Truck sideways, subject slides past | `dolly_left`, `dolly_right` |
| Big push-in or pull-out | `super_dolly_in`, `super_dolly_out` |
| Reverse vertigo | `dolly_zoom_out` |
| Lens only: zoom in or out, quick or sudden, or a wobble | `rapid_zoom_in`, `rapid_zoom_out`, `crash_zoom_out`, `yoyo_zoom` |
| Lift or drop the camera straight up or down | `jib_up`, `jib_down` |
| Opening reveal, big and airy | `aerial_pullback`, `overhead` |
| Action, chase, drone | `fpv_drone`, `hyperlapse`, `robo_arm` |
| Freeze-frame look (freeze or slow the subject's animation too) | `bullet_time` |
| Tension, drunk, unease | `dutch_angle` (tilted horizon), `barrel_roll` (full roll while pushing in) |
| Camera stuck to the character's chest looking at the face | `snorricam` (follows automatically) |
| Villain or hero looming | `hero_cam` (low angle, slow push-in) |
| A full circle | `orbit_360` |
| Face close-up | `eyes_in`, `mouth_in` (push in on the head of a standing character) |
| Product turntable at close range | `lazy_susan` |
| Diagonal reveal | `incline`, `rise_reveal` |
| Orbit while closing in or opening out | `spiral_in`, `spiral_out` |
| Speed and low chase feel | `road_rush` |
| Flattering low arc | `glam` |
| Lens looks | `fisheye` (10 mm), `telephoto` (long lens, compressed depth) |
| Over the head and down the other side | `crane_over` |

Move length: 2-3 s for whip_pan, crash_zoom_in, dolly_zoom; 4-6 s for dolly, arc, crane; 6-10 s for a full orbit. Slow moves read as expensive.

## Look, lens and checking

- `set_look` grades everything you render afterwards: `cinematic` (teal and orange), `noir`, `vintage`, `warm`, `cold`, `vivid`, `neon_glow`, `dreamy`; `natural` removes it. Pair a look with the light: `noir` with `overcast` or `night`, `cinematic` with `golden_hour` or `sunset`, `neon_glow` with `neon`.
- `camera_settings`: `f_stop` 1.8 with `focus_object` blurs the background (portrait feel); `focus_object` plus `rack_focus_to` glides the focus from one object to another; `motion_blur` true softens fast moves. Call it after `camera_move`.
- `render_contact_sheet` renders 4 frames of the whole move into one picture: use it instead of several `render_image` calls to check framing and motion.

## Several shots, one film

Either call `render_shots` with a shot list (each shot: `preset`, `duration`, optional `environment`, `look`, `object_names`, `azimuth`, `follow` ...; crossfades between them), or render clips one by one with `render_animation` and join them with `edit_video` (`clips` such as `["a.mp4", {"file": "b.mp4", "speed": 0.5}]`, `transition` cut, crossfade or wipe; speed 0.5 is slow motion, 2 is fast forward). A trailer rhythm: an establishing wide shot (aerial_pullback or dolly_in, 4 s), a mid shot with movement (arc or dolly_left, 3 s), a close hero shot (hero_cam or crash_zoom_in, 2 s), crossfade 0.5 s.

## Music

`render_shots` takes `music`: a mood (`calm`, `tense`, `epic`, `playful`, `night`, `synthwave`) is composed to the film's length and mixed in as AAC. For clips you edit yourself: `make_soundtrack` (mood, seconds) then `edit_video` with `soundtrack` (and `music_volume`). Match the mood to the picture: `epic` with a hero shot, `tense` with night and dutch angles, `calm` with golden hour, `playful` with bright cartoon props, `synthwave` with neon.

## Rules that save time

- Camera azimuth 0 is in front of the subject (models face +Y); a positive azimuth moves the camera toward +X.
- Call `set_environment` before the first `render_image`; a scene without light renders black.
- `camera_move` replaces the previous shot (same `ShotCamera`); to make a second shot with another move, render the first one, then call `camera_move` again.
- Small subjects (a 0.3 m prop) still work: the distance scales with the subject's size.
- Renders block Blender for a few seconds (about 0.1 s per frame at 960x540). Keep shots under 10 seconds while iterating and use 1280x720 or 1920x1080 only for the final render.
- Call tools one at a time and read each result; do not use `propose_plan` for shots.
- To use the video in a game engine or an editor, copy the MP4 from the export folder; it is a normal H.264 file.
