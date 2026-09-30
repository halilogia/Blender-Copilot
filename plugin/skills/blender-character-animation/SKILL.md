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
| accessories | anything else: `Helmet`, `Boots`, `Backpack`, `Rifle`, `Hair`. Each follows the nearest of the six parts, so put the helmet on the head and the boots at the feet |

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

3. `set_environment`, then `camera_move` with `object_names: ["Soldier_Rig"]`. For a walking or running character pass `follow: true` (the camera keeps its framing while the character moves); use `dolly_in`, `arc_left`, `static` or `crane_up` for the move. A `static` camera without follow lets the character walk out of frame.
4. `render_image` to check a frame (character in frame, light on the front), then `render_animation`.

## 3. For a game

`export_gltf` with `object_names: ["Soldier_Rig"]` and `animations: true` writes a glb with the whole hierarchy and its keyframes (recenter is off for animated exports). Godot imports it with an AnimationPlayer.

## Common problems

- "Could not find the parts": names lack the role words; rename or pass `parts`.
- A limb swings from its middle: it was joined or its origin was wrong; rebuild it as its own object (rig_character resets each pivot to the top of the part).
- The accessory floats away: it attached to the wrong part; move it closer to the part it belongs to before rigging.
- The character walks into the camera or out of frame: use `follow: true`, or set `heading` so it walks across the frame (90 or -90).
- Feet sink or hover: model the character so its lowest point is at Z = 0.
