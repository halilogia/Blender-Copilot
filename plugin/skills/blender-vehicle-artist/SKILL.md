---
name: blender-vehicle-artist
description: Dedicated workflow for modeling cars, trucks, tanks, aircraft, mechs, and sci-fi rovers in Blender Copilot via MCP with chassis blockout, body panels, wheel articulation, and collision proxies.
license: GPL-3.0-or-later
metadata:
  domain: blender
  role: vehicle-artist
  triggers: vehicle, car, truck, tank, mech, rover, aircraft, chassis, bodywork, wheels, suspension, gltf
---

# 🏎️ Blender Vehicle & Mechanical Artist (MCP Workflow)

Proportion-driven vehicles. Modular mechanical systems. Articulation-ready wheel hierarchy. Engine-ready collision proxies.

---

## 1. Modular Hierarchy & Object Split

Never merge animated or rotating vehicle systems into a single mesh. Keep these separate objects:

| Object Name | Function | Material Slots | Origin Point |
| :--- | :--- | :--- | :--- |
| `SM_Vehicle_Body` | Main chassis, cabin, fenders, cargo | BodyPaint, SteelChassis, EmissiveLights | `BOTTOM_CENTER` (ground level) |
| `SM_Wheel_FL` | Front Left steer/spin wheel | TireRubber, RimAlloy | Center of wheel cylinder |
| `SM_Wheel_FR` | Front Right steer/spin wheel | TireRubber, RimAlloy | Center of wheel cylinder |
| `SM_Wheel_RL` | Rear Left drive wheel | TireRubber, RimAlloy | Center of wheel cylinder |
| `SM_Wheel_RR` | Rear Right drive wheel | TireRubber, RimAlloy | Center of wheel cylinder |
| `SM_Vehicle_Glass` | Windshield / windows (separate for alpha sort) | TintedGlass (Roughness 0.1) | Matches Body |
| `SM_Turret` *(if armed)* | Rotating turret or weapon pod | ArmorPlate, GunMetal | Turret pivot base |

---

## 2. Proportion & Stance Blockout

1. **Wheelbase & Stance:**
   - Wheel diameter: `0.6 m - 0.9 m` (cars), `0.9 m - 1.4 m` (trucks/tanks).
   - Ground clearance: `0.2 m` (sports car), `0.4 m` (pickup/SUV), `0.6 m` (armored rover).
   - Place wheel cylinders first to establish the stance before sculpting the body.
2. **Cabin Silhouette:**
   - Hood line: 30-40% of overall vehicle length.
   - Windshield angle: 30° to 45° incline from vertical.
   - Keep overall length between `3.8 m - 5.5 m` for standard ground vehicles.

---

## 3. Detailing with MCP Tools

- **Wheel Arches:**
  - Create cylindrical cutters slightly larger than wheel diameter (+0.15 m margin).
  - Apply boolean difference to the lower chassis block.
- **Grilles & Intakes:**
  - `mesh_edit(Chassis, action="INSET_FACES", thickness=0.04, depth=-0.08)`.
  - Add arrayed slats: `add_shape_modifier(Slat, modifier_type="ARRAY", count=5, relative_offset=[0,0,-1.2])`.
- **Panel Seams & Armor Cuts:**
  - Subtle insets along door lines break flat boxiness and catch viewport shadows.
- **Lights & Indicators:**
  - Recessed sockets with high-roughness glass cover and emissive bulb mesh behind.

---

## 4. Collision Proxies & Godot Integration

- **Chassis Body:**
  - Create a simplified low-poly convex hull enclosing the main body (`SM_Vehicle_Body-col` or `-convcol`).
- **Wheel Colliders:**
  - Raycast or cylinder colliders setup in Godot's `VehicleBody3D` or custom arcade vehicle controller.
- **Forward Axis Rule:**
  - In Blender: vehicle points toward **+Y** (forward), **+Z** (up).
  - On `export_gltf`: Godot imports this automatically as **-Z** (forward), matching standard engine conventions.
