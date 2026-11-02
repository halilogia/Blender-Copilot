---
name: blender-to-godot
description: Hand assets made with Blender Copilot to a Godot 4 project - copy the exported .glb under res://, let the editor import it, place it in scenes with collision and the right scale, and check it in the running game. Use after export_gltf, or when replacing primitive meshes in a Godot game with models.
---

# From Blender Copilot to Godot 4

Both tool sets are MCP servers in the same Claude Code session: `blender` (Blender Copilot) makes and exports the model, `godot` (Godot AI Sidebar) imports, places and verifies it. Without the Godot tools, do the file steps with your own file tools and ask the user to focus the Godot editor so it imports.

## Steps

1. **Export** with `export_gltf` (`recenter` is on by default). The result has the absolute `path` of the `.glb` and its `triangle_count`.
2. **Copy** the file into the game project, for example `res://assets/models/<name>.glb` (create the folder). Use a lowercase file name with underscores.
3. **Import.** Call the Godot tool `sync_project` with the new `res://` path in `changed_files`. Godot imports `.glb` by itself (creating a `.glb.import` file). Wait for it before loading; a `load()` that returns null means the import has not finished.
4. **Place it.** In code: `var model := (load("res://assets/models/crate.glb") as PackedScene).instantiate() as Node3D`, then `add_child(model)`. Blender +Y (the model's forward) arrives as -Z, Godot's forward. Scale 1.0 is 1 meter.
5. **Collision.** A model has no physics. Wrap it: a `StaticBody3D` (collision layer 1) with the model as a child and a `CollisionShape3D` whose `BoxShape3D` size is the merged AABB of the model's `MeshInstance3D` children (`mi.get_aabb()` transformed), or a `CylinderShape3D` for trunks and barrels. Fall back to the old primitive shape if `load()` returns null so the game still runs.
6. **Verify in the running game.** `play_game`, `take_runtime_screenshot`, `get_runtime_errors`; look at the model from the player's height, not only in the viewer. `inspect_runtime_node` on the model reports its real local position: a node with a large offset (for example z = -20) means the model was exported without `recenter`.
7. **Iterate in Blender when it looks wrong**: proportions, missing colour, too many triangles. Re-export under the same name, `sync_project` again, replay.

## Gotchas

- A prop exported at its Blender scene position appears that far from its collision body: keep `recenter` on.
- Materials come through as StandardMaterial3D with the base colour, roughness and metallic you set. A procedural preset (wood, brick ...) is shader nodes that glTF cannot carry: `bake_material` the joined object first and the `.glb` carries a real texture.
- Before exporting run `check_model` (normals, scale, ground, triangle budget) and `task_report` (nothing left over). Landscapes: `create_terrain` and `scatter` export as a mesh plus cheap instances.
- The Godot AI Sidebar can call this add-on itself (Settings > Blender): its agent runs `blender_call`, the `.glb` is copied to `res://assets/blender/` and its path comes back as `godot_path`.
- Skinned or animated rigs are out of scope for these tools: use several static meshes and animate them in Godot (sway, bob, rotate).
- Keep viewmodel weapons small: about 0.7 m rifle, scaled down a further ~0.6 when parented to the camera; check the screenshot (the weapon should cover roughly a quarter of the screen height).
