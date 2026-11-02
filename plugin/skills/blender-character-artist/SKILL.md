---
name: blender-character-artist
description: Create stylized and low-poly humanoid characters, soldiers, NPCs, and robots in Blender Copilot via MCP tools with anatomical proportions, T-pose alignment, modular limb hierarchy, and Godot-ready origins.
license: GPL-3.0-or-later
metadata:
  domain: blender
  role: character-artist
  triggers: character, humanoid, person, soldier, mannequin, npc, robot, knight, t-pose, limb, head ratio
---

# 🧍 Blender Character & Humanoid Artist (MCP Workflow)

Low-poly humanoids. Clean head-to-body proportions. Modular articulation-ready hierarchy. T-Pose standards for game engines.

---

## 1. Proportion Standards

Always establish proportions before adding facial or armor details. Character scale is `1.0 = 1 meter`.

| Character Type | Total Height | Head Units | Head Size | Aesthetic / Use Case |
| :--- | :--- | :--- | :--- | :--- |
| **Realistic Adult / Hero** | `1.75 m - 1.85 m` | 7.5 - 8.0 heads | ~0.23 m | Tactical soldiers, realistic NPCs |
| **Stylized / Action Game** | `1.60 m - 1.75 m` | 5.5 - 6.0 heads | ~0.28 m | Retro shooters, stylized RPGs |
| **Chibi / Mini-Fig / Mech** | `1.00 m - 1.30 m` | 3.0 - 4.0 heads | ~0.35 m | Arcade, strategy, toy aesthetic |

### Standard Vertical Landmarks (1.80 m Humanoid):
- **Crown / Top of Head:** `Z = 1.80 m`
- **Chin / Neck Base:** `Z = 1.57 m`
- **Shoulder Line:** `Z = 1.48 m`
- **Chest / Torso Center:** `Z = 1.25 m`
- **Pelvis / Hip Joint:** `Z = 0.90 m` (exact 50% midpoint of body)
- **Knee Joint:** `Z = 0.45 m` (midpoint between hip and ankle)
- **Ankle / Ground:** `Z = 0.08 m` to `Z = 0.00 m` (grounded)

---

## 2. Rest Pose & Alignment Rules

- **Forward Facing:** Model faces **+Y** in Blender (imports as **-Z** in Godot).
- **T-Pose Stance:** Arms extended along the **X-axis** (Right Arm points to `+X`, Left Arm points to `-X`). Palms face down toward `-Z`.
- **Feet:** Grounded exactly on `Z = 0.0`.
- **Symmetry:** Model the left side and use `add_shape_modifier(obj, modifier_type="MIRROR")` where applicable.

---

## 3. Modular Object Hierarchy (Segmented Game Characters)

For low-poly games, keeping limbs as discrete objects or joined meshes with defined vertex groups avoids complex skin weighting:

| Object Name | Description | Origin Point / Pivot |
| :--- | :--- | :--- |
| `SM_Char_Head` | Head, facial features, hair/helmet | Base of neck (`Z = 1.57`) |
| `SM_Char_Torso` | Chest, spine, pelvis | Mid-pelvis (`Z = 0.90`) |
| `SM_Char_Arm_Upper_L/R` | Shoulder to elbow | Shoulder ball center (`X = ±0.22, Z = 1.45`) |
| `SM_Char_Arm_Lower_L/R` | Forearm and hand | Elbow pivot (`X = ±0.48, Z = 1.45`) |
| `SM_Char_Leg_Upper_L/R` | Hip to knee | Hip socket (`X = ±0.12, Z = 0.88`) |
| `SM_Char_Leg_Lower_L/R` | Shin, calf and boot | Knee joint (`X = ±0.12, Z = 0.45`) |
| `SM_Char_Weapon_R` | Attached weapon/shield | Grip point |

*Note:* If exporting as a single static prop, call `join_objects(all -> "Character")` and `set_origin("Character", "BOTTOM_CENTER")`.

---

## 4. Tested Recipes

### Recipe A: Standard Low-Poly Soldier (1.8 m, T-Pose)
```
1. Torso:        prim(CUBE, "Torso", loc=[0,0,1.22], scale=[0.42, 0.22, 0.58]) -> uniform [0.34, 0.36, 0.28]
2. Pelvis:       prim(CUBE, "Pelvis", loc=[0,0,0.92], scale=[0.36, 0.20, 0.16]) -> dark [0.22, 0.24, 0.20]
3. Head:         prim(CUBE, "Head", loc=[0,0,1.66], scale=[0.20, 0.22, 0.24]) -> skin [0.78, 0.60, 0.48]
4. Helmet:       prim(ICOSPHERE, "Helmet", loc=[0,0,1.75], scale=[1.0, 1.05, 0.7], size=0.32) -> [0.27, 0.30, 0.24]
5. Arms (T-Pose):
   Upper L/R:    prim(CYLINDER, "ArmUp_{L/R}", loc=[±0.34, 0, 1.45], scale=[0.10, 0.10, 0.26], rot=[0, 90, 0])
   Forearm L/R:  prim(CYLINDER, "Forearm_{L/R}", loc=[±0.60, 0, 1.45], scale=[0.08, 0.08, 0.24], rot=[0, 90, 0])
6. Legs:
   Thigh L/R:    prim(CYLINDER, "Thigh_{L/R}", loc=[±0.12, 0, 0.68], scale=[0.11, 0.11, 0.42])
   Shin L/R:     prim(CYLINDER, "Shin_{L/R}", loc=[±0.12, 0, 0.26], scale=[0.09, 0.09, 0.38])
7. Boots:        prim(CUBE, "Boot_{L/R}", loc=[±0.12, 0.04, 0.06], scale=[0.12, 0.24, 0.12]) -> leather [0.12, 0.09, 0.07]
8. Finalize:     check_model -> polish_model -> export_gltf
```

### Recipe B: Sci-Fi Combat Android (1.9 m, Angular Mecha Silhouette)
```
1. Core Chassis: prim(CUBE, "Chassis", loc=[0,0,1.25], scale=[0.46, 0.26, 0.55])
                 mesh_edit(Chassis, BEVEL_EDGES, width=0.03, segments=1) -> chassis metal [0.2,0.22,0.25]
2. Visor Head:   prim(CUBE, "Head", loc=[0,0,1.70], scale=[0.18, 0.20, 0.20])
                 mesh_edit(Head, INSET_FACES, faces={direction:"+Y"}, depth=-0.04)
                 set_material on inset: EmissiveCyan [0.0, 0.8, 1.0]
3. Pauldrons:    2x prim(CUBE, "Pauldron_{L/R}", loc=[±0.32, 0, 1.50], scale=[0.18, 0.16, 0.12])
4. Joints:       prim(CYLINDER, "Joint_{Elbow/Knee}", scale=[0.07, 0.07, 0.14], rot=[90,0,0]) -> dark steel
5. Finalize:     join_objects or export modular hierarchy.
```
