---
name: blender-game-assets
description: Model low-poly game assets (crates, barrels, trees, rocks, sandbags, weapons, characters) in Blender 5.2 through Blender Copilot's MCP tools without writing Python, check them in the viewport and export game-ready .glb files. Use when the user wants a 3D prop, weapon, character or environment piece for a game, or asks to replace primitive boxes and spheres with real models.
---

# Blender game assets through MCP

You model with allow-listed tools, not with Python: every step is one Ctrl+Z and nothing runs arbitrary code. The tool schemas say what each tool and argument does; this file only gives the order of work and the things a schema cannot tell you.

## Order of work

1. **Spec.** Size in meters (a crate 1 m, a door 2 m, a soldier 1.8 m), a triangle budget (props 100-800, characters 500-2500, trees 300-800), 3 to 5 colours. Flat-shaded low-poly reads best.
2. **Look first.** `inspect_scene`. The startup scene has a 2 m `Cube`, a camera and a light; the cube hides small props in screenshots. Ask before deleting it (`delete_object` needs the user's approval) or build away from the origin.
3. **Start with `create_prop`** for anything it covers (one call: proportioned, coloured, standing on the ground, front toward +Y). Build from `create_primitive` / `create_mesh` / `mesh_edit` only what it does not cover. Do `apply_transform` after scaling or rotating a part.
4. **Colour per part before `join_objects`**: the joined mesh keeps one material slot per part. Reuse one `material_name` for parts that share a colour.
5. **Procedural presets (wood, brick ...) do not survive glTF**: the exporter keeps only a flat colour. For a game asset join the parts, then `bake_material` the object (it unwraps UVs itself), or use flat colours.
6. **Check by looking every few steps**: `frame_view` then `capture_viewport`; fix proportions before adding detail. `polish_model` once shapes are right.
7. **Check by measuring before export**: `check_model` on the model, fix its FAIL items (and the cheap WARNs), repeat until `ok`.
8. **Finish**: `join_objects`, `set_origin` (BOTTOM_CENTER for props, BOUNDS_CENTER for weapons), `export_gltf` with a plain file name. Check `triangle_count` in the result.
9. **At the end of a piece of work call `task_report`**: it lists what you really changed. Look for what you did not intend (a helper object, an accidental move). `task_rollback` takes the whole task back, needs the user's approval and is refused over MCP unless gated tools are allowed; use it when the work went wrong beyond a quick fix.

## Landscapes and many copies

`create_terrain` and `scatter` load with the world pack, `unwrap_uv` and `bake_material` with the textures pack: call `enable_tools` if they are missing. Never call `create_prop` in a loop for a forest: `scatter` one source object (unparented; it stays where it is, so move it away) with `ground` set to the terrain and `avoid` set to the house. Copies share one mesh, so a `.glb` keeps them as cheap instances.

## Rules that save time

- Units are meters, +Z is up, +Y is the model's forward. glTF export converts to Y-up: Blender +Y becomes Godot -Z, the forward direction.
- Real-world scale and one shared scale across assets; do not scale in the game to fix proportions.
- Symmetric things: build half and MIRROR. Repeated things: ARRAY. `export_gltf` warns above 5000 triangles.
- Name every part clearly (`CrPost0`, `RifleBarrel`); names are how you address them later. `join_objects` removes the sources; use `new_name` if you need the old names again.
- Do not model what the engine does better: use engine lights, physics shapes and materials; export meshes with colours only.
- If a tool answers `APPROVAL_REQUIRED`, stop and ask the user; do not look for a way around it.

Worked, tested recipes for a crate, barrel, tree, rock, sandbag row, rifle and soldier are in `references/recipes.md`: load it when you need exact numbers.
