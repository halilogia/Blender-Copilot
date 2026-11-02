---
name: blender-character-animation
description: Build a low-poly character from separate parts in Blender 5.2 through Blender Copilot's MCP tools, rig it (no armature, no Python), animate it with walk, run, idle, aim, wave or jump presets, follow it with the camera and render an MP4 or export it to a game as an animated glb. Use when the user wants a character that moves, a walk cycle, or an animated figure in a shot.
---

# Characters that move, from chat

A rig here is a hierarchy of the parts you modelled: pivots sit at the joints, everything hangs under one empty, and motion presets keyframe part rotations plus the rig's travel. Blocky low-poly characters need nothing more. Read the tool schemas first and use their exact argument names.

## 1. Model the character from SEPARATE parts

Do not `join_objects` the parts. Use these names (the rig finds roles by name; add `_l` / `_r` or Left / Right for limbs, or pass `parts` explicitly):

| Role | Object name examples |
|---|---|
| head | `Head` |
| torso | `Torso`, `Body`, `Chest` |
| arm_l, arm_r | `ArmL`, `ArmR`, `LeftArm`, `arm_right` |
| leg_l, leg_r | `LegL`, `LegR`, `LeftLeg` |
| forearm_l, forearm_r (optional) | `ForearmL`, `LowerArmR`: the lower half of an arm, hanging from the elbow; with them elbows bend (walk, run, wave, aim) |
| shin_l, shin_r (optional) | `ShinL`, `CalfR`: the lower half of a leg, hanging from the knee; with them knees bend (walk, run, jump) |
| eye_l, eye_r, mouth (optional face) | `EyeL`, `EyeR`, `Mouth`: small boxes on the front of the head (the mouth a thin box). They blink in every animation, the mouth talks and the eyes squint or widen for expressions |
| accessories | anything else: `Helmet`, `Boots`, `Backpack`, `Rifle`, `Hair`. Each follows the nearest body part, so put the helmet on the head and the boots at the feet |

Bending limbs: split each arm into `ArmL` (shoulder to elbow) and `ForearmL` (elbow to hand), each leg into `LegL` (hip to knee) and `ShinL` (knee to foot), with the top of the lower part exactly at the bottom of the upper part. Run `polish_model` on the parts first for soft edges.

Rules: the character faces **+Y**, its right side is **+X**, it stands on Z = 0, about 1.6-2.0 m tall for a person. Arms and legs are single blocks that hang straight down (a cube scaled tall, a cylinder), the top of each at its joint. Give parts different materials (`set_material` per part: uniform, skin, boots). Keep each part simple; the whole character stays under about 1500 triangles.

## 2. Rig, animate, follow, render

1. `rig_character` with `name` and every object name (accessories included). The result lists the roles it found and where accessories attached; fix names or pass `parts` if a role is missing.
2. `animate_character` with the rig name (`Soldier_Rig`) and a preset:

| Preset | Use |
|---|---|
| `idle` | standing, breathing (2-6 s) |
| `walk` | legs and arms swing in opposition, body bobs; `distance` meters (default natural speed), `heading` degrees (0 = +Y, 90 = -X) |
| `run` | wider swing, leaning in, faster |
| `aim` | both arms forward as if holding a rifle |
| `wave` | right arm up and waving |
| `jump` | arms swing up, legs tuck, the body rises and lands |
| `talk` | lip sync: pass the spoken line in `text` (leave `duration` out, it lasts as long as the line); the mouth follows vowels, consonants and pauses, with nods and a hand gesture |
| `happy` | squinting eyes, wide smile, bouncing with raised arms |
| `surprised` | wide eyes, open mouth, a step back |
| `angry` | narrowed eyes, tight mouth, clenched fists, head down and shaking |

   For a scene with several actions call `animate_sequence` once instead: `segments` such as `[{"preset": "walk", "distance": 4}, {"preset": "wave"}, {"preset": "talk", "text": "Hello!", "heading": 90}]`. The character carries on from where the last segment ended, a segment with `heading` turns it, a blend glides between poses, and the result lists the start and end frame of each segment.
3. `set_environment`, then `camera_move` with `object_names: ["Soldier_Rig"]`. For a walking or running character pass `follow: true` (the camera keeps its framing while the character moves); use `dolly_in`, `arc_left`, `static` or `crane_up` for the move. A `static` camera without follow lets the character walk out of frame.
4. `render_image` to check a frame (character in frame, light on the front), then `render_animation`.

## 3. Keep the character for later shots

`character_library` `save` (name and rig) stores the rigged character, materials included; `load` brings it back into any scene at a location, ready for `animate_character`; `list` shows the saved ones. Use it so the same soldier appears in every shot of a film.

## 4. For a game

`export_gltf` with `object_names: ["Soldier_Rig"]` and `animations: true` writes a glb with the whole hierarchy and its keyframes (recenter is off for animated exports). Godot imports it with an AnimationPlayer.

## Common problems

- "Could not find the parts": names lack the role words; rename or pass `parts`.
- A limb swings from its middle: it was joined or its origin was wrong; rebuild it as its own object (rig_character resets each pivot to the top of the part).
- The accessory floats away: it attached to the wrong part; move it closer to the part it belongs to before rigging.
- The character walks into the camera or out of frame: use `follow: true`, or set `heading` so it walks across the frame (90 or -90).
- Feet sink or hover: model the character so its lowest point is at Z = 0.
