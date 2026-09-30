---
name: blender-game-assets
description: Model low-poly game assets (crates, barrels, trees, rocks, sandbags, weapons, characters) in Blender 5.2 through Blender Copilot's MCP tools without writing Python, check them in the viewport and export game-ready .glb files. Use when the user wants a 3D prop, weapon, character or environment piece for a game, or asks to replace primitive boxes and spheres with real models.
---

# Blender game assets through MCP

You model with allow-listed tools, not with Python: nothing here can run arbitrary code, every step is one Ctrl+Z, and delete_object needs the user's approval. Read the tool schemas first and use their exact argument names (`delete_object` takes `name`, most others `object_name` or `name`).

## Start with `create_prop`

For common things one call builds a proportioned, coloured, bevelled and smooth-shaded result standing on the ground with its front toward +Y: `crate`, `barrel`, `tree_pine`, `tree_round`, `rock`, `house`, `tower`, `fence`, `lamp`, `tent`, `well`, `car`, `chest`, `table`, `chair`, `campfire`, and the characters `humanoid` and `robot` (separate parts named for `rig_character`, with forearms, shins, eyes and mouth). Pass `size` (height in meters), `location`, `colors` (for example `{"roof": [0.2, 0.3, 0.7]}`; the result lists the color names), `seed` for the rock. Place several with different `location`s to build a scene, then add what is missing with the modeling tools below. Only build from primitives what `create_prop` does not cover.

## Workflow (one asset)

1. **Spec first.** Size in meters (a crate 1 m, a door 2 m, a soldier 1.8 m), triangle budget (props 100-800, character 500-2500, tree 300-800), style (flat-shaded low-poly reads best without textures), 3 to 5 colours.
2. **Look at the scene.** `inspect_scene`. The default startup scene has a 2 m `Cube`, a camera and a light: the cube hides small props in screenshots. Ask before removing it (`delete_object` is gated), or build the asset away from the origin and frame it.
3. **Build from parts.** `create_primitive` (CUBE, SPHERE, PLANE, CYLINDER, CONE, ICOSPHERE, TORUS; `scale` shapes a box into a plank or a post, `rotation` in radians) then `apply_transform` so rotation is 0 and scale is 1. For shapes primitives cannot make: `create_mesh` with your own `vertices` and `faces` (counter-clockwise seen from outside).
4. **Detail with edits.** `mesh_edit`: INSET_FACES (with negative `depth` sinks a panel), EXTRUDE_FACES, BEVEL_EDGES (`sharp_angle` bevels only hard edges), SCALE_TO_HEIGHT_TAPER (trunks, chimneys), SUBDIVIDE, MERGE_BY_DISTANCE. Pick faces by direction: `faces: {"direction": "+Z", "threshold": 0.9}`. `add_shape_modifier`: MIRROR (half a prop), ARRAY (fences, rows), SOLIDIFY (thin walls), DECIMATE (budget), TRIANGULATE.
5. **Colour.** `set_material` with `object_name`, `material_name`, `base_color` [r, g, b, 1], `roughness`, `metallic`. Do it per part BEFORE `join_objects`: the joined mesh keeps one material slot per part. Reuse the same `material_name` for parts that share a colour. For a surface with texture use `preset` instead of a flat colour: wood, stone, brick, metal, gold, grass, water, sand, concrete, marble (`scale` 2 = finer pattern); no image files needed, but a preset does not survive a glTF export as nodes (the exporter bakes only the base colour), so for game assets prefer flat colours.
6. **Check by looking, every few steps.** `frame_view` (`direction` ISO / FRONT / TOP, `shading` MATERIAL, `overlays` false) then `capture_viewport`. Also `inspect_mesh` for dimensions and triangle count. Fix proportions before adding detail.
7. **Polish.** `polish_model` on the parts (or the joined prop): bevels every hard corner so light catches the edges and shades smooth with sharp edges kept. It is what makes a blocky model look finished; run it once shapes and proportions are right.
8. **Finish.** `join_objects` into one object, `set_origin` BOTTOM_CENTER (props) or BOUNDS_CENTER (weapons), then `export_gltf` (a plain file name such as `crate.glb`; `recenter` is on so the prop lands at the origin whatever its position in the Blender scene). Check `triangle_count` in the result.

## Rules that save time

- Units are meters, +Z is up, +Y is the model's forward. glTF export converts to Y-up: Blender +Y becomes Godot -Z, the forward direction.
- Real-world scale and one shared scale across assets; do not scale in the game to fix proportions.
- Symmetric things: build half and MIRROR. Repeated things: ARRAY. Keep the triangle count honest: `export_gltf` warns above 5000.
- One `create_*` per named part with a clear name (`CrPost0`, `RifleBarrel`); names are how you address them later.
- `join_objects` removes the source objects. Use a fresh name for the result via `new_name` if you need the original names again.
- Do not model what the engine does better: use engine lights, physics shapes and materials; export meshes with colours only.
- If a tool answers `APPROVAL_REQUIRED`, stop and ask the user; do not look for a way around it.

Worked, tested recipes for a crate, barrel, tree, rock, sandbag row, rifle and soldier are in `references/recipes.md`: load it when you need exact numbers.
