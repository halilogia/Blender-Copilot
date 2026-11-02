---
name: blender-procedural-pipeline
description: 5-stage procedural modeling pipeline for vehicles, hard-surface props, and modular game assets (Blockout -> Bevel & Form -> Boolean & Greeble -> Color ID & Shading -> LOD & glTF Export) using Blender Copilot's MCP tools.
license: GPL-3.0-or-later
metadata:
  domain: blender
  role: procedural-modeler
  triggers: procedural, 5-stage, recipe, vehicle, truck, hard-surface, blockout, boolean, greeble, lod, gltf
---

# 🚚 5-Stage Procedural 3D Modeling Pipeline (Greybox to Game-Ready)

This skill defines the standard recipe-driven modeling workflow in Blender Copilot without manual sculpting, translating parametric grayboxes into clean, game-ready assets for Godot, Unity, or Unreal.

---

## 1. The 5-Stage Pipeline

```mermaid
flowchart LR
    A["Stage 1<br/>Blockout / Greybox"] --> B["Stage 2<br/>Bevel & Form"]
    B --> C["Stage 3<br/>Boolean & Greeble"]
    C --> D["Stage 4<br/>Color ID & Shading"]
    D --> E["Stage 5<br/>LOD & Godot glTF"]
```

### Stage 1: Mass & Volume Blockout (Greybox Volumes)
- **Goal:** Lock silhouette, dimensions, and real-world proportions before any detail.
- **MCP Workflow:**
  1. `create_primitive` (CUBE, CYLINDER, ICOSPHERE) for primary chassis, cabin, and major mass.
  2. Align to origin: ground on Z=0, model forward facing +Y (becomes Godot -Z).
  3. `apply_transform(location=false, rotation=true, scale=true)` after scaling any primitive.
  4. Inspect silhouette: `frame_view` followed by `capture_viewport`.
- **Constraint:** Do not bevel or cut details early. Verify scale against character metrics (1.8 m door, 0.9 m barrel, 4.5 m vehicle).

### Stage 2: Structural Bevels & Primary Curvature (Bevel & Form)
- **Goal:** Break sharp boxiness, produce aerodynamic / armored industrial silhouettes.
- **MCP Workflow:**
  1. Use non-destructive modifiers where possible: `add_shape_modifier(object_name=..., modifier_type="BEVEL", width=0.04, segments=2)`.
  2. Targeted edge bevels via `mesh_edit(object_name=..., action="BEVEL_EDGES", width=..., segments=1, sharp_angle=40)`.
  3. Maintain clean surface normals using `add_shape_modifier(..., modifier_type="WEIGHTED_NORMAL")`.

### Stage 3: Boolean Cutters & Surface Detailing (Boolean & Greeble)
- **Goal:** Add functional mechanical features (windows, wheel arches, vents, panel gaps, hinges, bolts).
- **MCP Workflow:**
  1. Create cutter primitives (`prim(CUBE, ...)` or `prim(CYLINDER, ...)`).
  2. Use parametric insets: `mesh_edit(..., action="INSET_FACES", thickness=0.03, depth=-0.02)`.
  3. Repeat mechanical elements using `add_shape_modifier(..., modifier_type="ARRAY", count=..., relative_offset=[...])`.
  4. Symmetrical features: model one side and apply `add_shape_modifier(..., modifier_type="MIRROR")`.

### Stage 4: Color ID Slots & Palette Shading (Color ID & Materials)
- **Goal:** High-readability game art without tedious manual UV unwrapping.
- **MCP Workflow:**
  1. Assign material per functional system *before* joining:
     - **Main Body / Armor:** `set_material(obj, "BodyPaint", [r, g, b], roughness=0.55)`
     - **Tires / Rubber:** `set_material(obj, "TireRubber", [0.12, 0.12, 0.12], roughness=0.9)`
     - **Chassis / Mechanism:** `set_material(obj, "SteelChassis", [0.25, 0.25, 0.28], roughness=0.4, metallic=0.8)`
     - **Glass / Windshield:** `set_material(obj, "TintedGlass", [0.15, 0.2, 0.25], roughness=0.1, metallic=0.2)`
     - **Lights / Emissive:** `set_material(obj, "Headlight", [0.9, 0.9, 0.8], emission=True)`
  2. Reusable material names ensure joined objects share palette slots cleanly.

### Stage 5: LODs, Collision & Game Sync (Game-Ready Export)
- **Goal:** One-click engine synchronization with physics and performance validation.
- **MCP Workflow:**
  1. `check_model(object_name=...)` to verify normals, transforms, and triangle count.
  2. `polish_model(object_name=...)` to clean loose geometry and clamp shading.
  3. Generate LODs: `add_shape_modifier(..., modifier_type="DECIMATE", ratio=0.5)` for LOD1.
  4. Set pivot: `set_origin(object_name=..., origin_type="BOTTOM_CENTER")`.
  5. Export: `export_gltf(object_names=[...], filename="asset_name.glb", recenter=true)`.
  6. Godot Sync: Godot AI Sidebar auto-imports into `res://assets/` and builds collision hulls (`-col` or `-convcol`).

---

## 2. Tested Recipe: Armored Transport Truck (approx. 1800 triangles)

```
1. Chassis:     prim(CUBE, "Chassis", loc=[0,0,0.4], scale=[1.6, 4.4, 0.35])
2. Cabin:       prim(CUBE, "Cabin", loc=[0,1.2,1.3], scale=[1.5, 1.8, 1.4])
3. Cargo Bay:   prim(CUBE, "Cargo", loc=[0,-1.0,1.35], scale=[1.55, 2.4, 1.5])
4. Windshield:  mesh_edit("Cabin", INSET_FACES, faces={direction:"+Y"}, thickness=0.08, depth=-0.05)
5. Wheel Arches: 4x prim(CYLINDER, "Arch_{i}", scale=[0.9, 0.4, 0.9], rot=[0, 90, 0]) -> cut from Chassis
6. Wheels:      4x prim(CYLINDER, "Wheel_{i}", scale=[0.8, 0.35, 0.8], rot=[0, 90, 0]) -> TireRubber
7. Bumpers:     prim(CUBE, "BumperF", loc=[0, 2.25, 0.35], scale=[1.65, 0.15, 0.25])
8. Materials:   Assign BodyPaint, TireRubber, SteelChassis, TintedGlass
9. Finalize:    join_objects(["Chassis", "Cabin", "Cargo", "BumperF"] -> "Truck_Body")
                set_origin("Truck_Body", "BOTTOM_CENTER")
                check_model("Truck_Body") -> export_gltf(["Truck_Body", "Wheel_*"], "truck_armored.glb")
```
