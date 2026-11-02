---
name: blender-lego-artist
description: Dedicated workflow for generating, assembling, and rendering authentic LEGO models in Blender Copilot via LDraw CAD parts format and ImportLDraw.
license: GPL-3.0-or-later
metadata:
  domain: blender
  role: lego-artist
  triggers: lego, ldraw, brick, stud, minifig, mpd, ldr, tobylobster, plastic, toy, voxel-brick
---

# 🧱 Blender LEGO & LDraw Artist (MCP Workflow)

Authentic virtual LEGO CAD assembly. Official LDraw parts library. Mathematical stud-tube grid alignment. Physically grounded ABS plastic shaders with genuine LEGO logo studs and micro-gaps.

---

## 1. LEGO & LDraw Grid Units (LDU)

Never guess coordinates when placing LEGO bricks. Virtual LEGO uses **LDU (LDraw Units)**:

| Metric | LDU Value | Real-World Size | Notes |
| :--- | :--- | :--- | :--- |
| **1 Stud Pitch** | `20 LDU` | `8.0 mm` | Center-to-center distance between studs (X / Z) |
| **1 Brick Height** | `24 LDU` | `9.6 mm` | Standard brick body height |
| **1 Plate Height** | `8 LDU` | `3.2 mm` | Exactly 1/3 of a brick body height |
| **1 Stud Height** | `4 LDU` | `1.6 mm` | Vertical height of the stud cylinder |
| **1 Stud Diameter** | `12 LDU` | `4.8 mm` | Radius = `6 LDU` |

> [!IMPORTANT]
> **Coordinate Orientation in LDraw:**
> - In standard LDraw CAD files, **`-Y` points UP** (towards the ceiling), and **`+Y` points DOWN** (towards the ground/table).
> - When importing into Blender with `realScale=True`, the importer converts coordinates into standard Blender metric (`+Z` UP, 1 LDU = 0.0004 m).

---

## 2. Essential Official LDraw Part IDs

The official parts library contains over 18,000 components. Core elements frequently used in agentic builds:

### A. Standard Bricks & Plates
- **Bricks (Height 24 LDU):**
  - `3001.dat`: Brick 2 x 4
  - `3002.dat`: Brick 2 x 3
  - `3003.dat`: Brick 2 x 2
  - `3004.dat`: Brick 1 x 2
  - `3005.dat`: Brick 1 x 1
  - `3010.dat`: Brick 1 x 4
  - `3009.dat`: Brick 1 x 6
  - `3008.dat`: Brick 1 x 8
- **Plates (Height 8 LDU):**
  - `3020.dat`: Plate 2 x 4
  - `3021.dat`: Plate 2 x 3
  - `3022.dat`: Plate 2 x 2
  - `3023.dat`: Plate 1 x 2
  - `3024.dat`: Plate 1 x 1
  - `3710.dat`: Plate 1 x 4
  - `3666.dat`: Plate 1 x 6
  - `3460.dat`: Plate 1 x 8
- **Tiles (Smooth Flat Plates, Height 8 LDU, No Studs):**
  - `3069b.dat`: Tile 1 x 2 with Groove
  - `3068b.dat`: Tile 2 x 2 with Groove
  - `2431.dat`: Tile 1 x 4 with Groove
  - `6636.dat`: Tile 1 x 6 with Groove

### B. Slopes, Wedges & Arches
- `3040.dat`: Slope Brick 45 2 x 1
- `3039.dat`: Slope Brick 45 2 x 2
- `3037.dat`: Slope Brick 45 2 x 4
- `3298.dat`: Slope Brick 33 3 x 2
- `6091.dat`: Brick 1 x 2 x 1 1/3 with Curved Top

---

## 3. Official LDraw Color Codes

| Code | Color Name | Hex Approximate | Material Behavior |
| :---: | :--- | :--- | :--- |
| `0` | Black | `#1B2A34` | Opaque ABS Plastic |
| `1` | Blue | `#0055BF` | Opaque ABS Plastic |
| `2` | Green | `#237841` | Opaque ABS Plastic |
| `4` | Red | `#C91A09` | Opaque ABS Plastic |
| `14` | Yellow | `#F2CD37` | Opaque ABS Plastic |
| `15` | White | `#FFFFFF` | Opaque ABS Plastic |
| `19` | Tan / Light Brown | `#E4CD9E` | Opaque ABS Plastic |
| `71` | Light Bluish Gray | `#A0A5A9` | Opaque ABS Plastic |
| `72` | Dark Bluish Gray | `#6C6E68` | Opaque ABS Plastic |
| `36` | Trans-Red | `#C91A09` (Glass) | Transparent Transmission |
| `40` | Trans-Black / Smoked | `#635F52` (Glass) | Transparent Windshield |
| `47` | Trans-Clear | `#FCFCFC` (Glass) | Transparent Headlights |
| `383` | Chrome Silver | `#E0E0E0` | Metallic Mirror |

---

## 4. LDraw Syntax & Writing Models

An LDraw file (`.ldr`) or Multi-Part Document (`.mpd`) is UTF-8 text with space-delimited records:

```ldraw
0 FILE my_model.ldr
0 My Custom LEGO Model
0 Name: my_model.ldr
0 Author: Blender Copilot
0 !LDRAW_ORG Model

1 4   0 -24   0   1 0 0  0 1 0  0 0 1   3001.dat
1 1   0 -48   0   1 0 0  0 1 0  0 0 1   3003.dat
1 14  0 -56   0   1 0 0  0 1 0  0 0 1   3020.dat
0 NOFILE
```

- **Format:** `1 <color_code> <x> <y> <z>  a b c  d e f  g h i  <part_id.dat>`
- `a..i` is the 3x3 rotation matrix (identity matrix `1 0 0  0 1 0  0 0 1` for 0° rotation).

---

## 5. Blender Import & Rendering Workflow

To render an LDraw model in Blender with production quality:

```python
import bpy
import addon_utils

# 1. Enable TobyLobster's ImportLDraw add-on
addon_utils.enable("io_scene_importldraw", default_set=True)

# 2. Import with authentic physical properties
bpy.ops.import_scene.importldraw(
    filepath="path/to/model.mpd",
    ldrawPath="path/to/ldraw/library",
    realScale=True,            # Converts LDU into real-world meters
    useLogoStuds=True,         # Adds the raised genuine LEGO logo to every stud
    addGaps=True,              # Realistic micro-gaps between bricks
    gapWidthMM=0.1,            # 0.1mm micro gap
    bevelEdges=True,           # Molded plastic bevels on all brick edges
    bevelWidth=0.0004,         # 0.4mm edge softening
    positionOnGround=True,     # Snaps lowest brick to ground (Z=0)
    addEnvironment=True,       # Studio ground plane and lighting
)
```

---

## 6. Golden Rules for LEGO Models

1. **Stud Interlocking:** Bricks must overlap across layers (running bond / staggered joints) to maintain realistic structural rigidity.
2. **Never Float Bricks:** Every secondary brick must either rest on a stud connection or lock into a Technic pin/axle.
3. **Plates for Finer Steps:** Use 3 stacked plates (`8 LDU` each) when vertical transitions require finer height increments than a full brick (`24 LDU`).
4. **Finish with Tiles:** Exterior vehicle hoods, table tops, and building roofs should be covered with smooth tiles (`3069b`, `3068b`) to hide raw studs where intentional.
