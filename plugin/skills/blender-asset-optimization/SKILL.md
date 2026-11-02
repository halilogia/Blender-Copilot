---
name: blender-asset-optimization
description: Enforce triangle budgets, clean geometry, remove non-manifold edges, generate LOD0-LOD3 variants, and validate models with check_model and polish_model before engine export via Blender Copilot MCP.
license: GPL-3.0-or-later
metadata:
  domain: blender
  role: technical-artist
  triggers: optimize, optimization, polycount, lod, cleanup, check_model, polish_model, triangle budget, game ready, validation
---

# ⚡ Blender Asset Optimization & Validation Gate

Enforce budgets. Clean non-manifold geometry. Validate before export. Every production asset must pass this gate before `export_gltf`.

---

## 1. Triangle Budgets by Category

| Category | Hero / LOD0 | LOD1 (50%) | LOD2 (25%) | LOD3 / Proxy | Notes |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Small Props** (crates, barrels, lanterns) | 100 - 600 | 50 - 300 | Single mesh | Simple box/cylinder | Flat shading preferred |
| **Large Props** (fences, watchtowers, carts) | 600 - 2,500 | 300 - 1,200 | 150 - 600 | 50 - 150 | Instances for repeated parts |
| **Weapons** (pistols, rifles, swords) | 300 - 1,800 | 150 - 900 | 80 - 450 | - | Keep silhouette crisp on sights |
| **Vehicles** (cars, tanks, aircraft) | 1,500 - 5,000 | 800 - 2,500 | 400 - 1,200 | 100 - 300 | Wheels kept separate for physics |
| **Characters** (low-poly humanoid / robot) | 800 - 3,500 | 400 - 1,800 | 200 - 800 | Billboard / proxy | Keep joint loops intact |

---

## 2. Pre-Export Audit Checklist (MCP)

Run these checks before finalizing:

### Geometry & Transforms
- [ ] **Unapplied Transforms:** Call `apply_transform(object_name=..., location=false, rotation=true, scale=true)` on every child part.
- [ ] **Loose Vertices / Edges:** Call `polish_model(object_name=...)` to merge duplicate vertices within `0.001 m` threshold.
- [ ] **Non-Manifold Faces:** Delete interior faces created by boolean intersections.
- [ ] **Normals Consistency:** Ensure face normals point outward (`polish_model` handles recalculations).

### Materials & Draw Calls
- [ ] **Shared Material Slots:** Use identical `material_name` strings across parts before `join_objects` so glTF shares slots.
- [ ] **No Raw Procedural Shader Nodes:** glTF exporters only preserve flat PBR colors (Albedo, Roughness, Metallic) unless `bake_material` was run.
- [ ] **Draw Call Budget:** Aim for 1 to 4 materials per asset max.

---

## 3. LOD Pipeline Generation

```
LOD0: 100% (Hero detail, full bevels and greebles)
LOD1:  50% (`add_shape_modifier(obj, "DECIMATE", ratio=0.5)`)
LOD2:  25% (`add_shape_modifier(obj, "DECIMATE", ratio=0.25)`)
LOD3:  10% or simple bounding collision proxy
```

### Decimate Rules:
- **Hard-surface / Mechanical:** Use `PLANAR` decimate or collapse with edge angle limits to protect flat face readability.
- **Organic / Rocks / Foliage:** Use standard `COLLAPSE` decimate.
- **Verification:** Always `capture_viewport` after decimation to ensure silhouette integrity is preserved.

---

## 4. MCP Validation Workflow

1. `check_model(object_name=...)`:
   - Inspects triangle count vs. budget.
   - Detects negative scales or inverted normals.
   - Flags non-grounded origins.
2. `polish_model(object_name=...)`:
   - Cleans isolated islands and welds overlapping seams.
3. `task_report()`:
   - Verifies only intended assets were modified; ensures no leftover cutter boxes or test meshes remain in the scene.
4. `export_gltf(object_names=[...], filename=..., recenter=true)`.
