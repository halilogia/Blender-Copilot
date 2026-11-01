"""Same car prompt as demos/car, built with Scenario's hard-surface method (School A:
real-size blockout, applied scale, design + micro bevel, EXACT booleans, weighted normals,
game copy). blender -b --factory-startup -P build_car.py -- <scenario skills>/skills/dcc/blender <out.glb>
Needs a clone of github.com/scenario-labs/skills (MIT) for bx_hardsurface."""
import math
import os
import sys

import bmesh
import bpy

argv = sys.argv[sys.argv.index("--") + 1:]
skills, out = argv[0], argv[1]
sys.path.append(os.path.join(skills, "scenario-blender-hard-surface", "scripts"))
import bx_hardsurface as HS  # noqa: E402  (path added at run time)

bpy.ops.wm.read_factory_settings(use_empty=True)
col = bpy.context.scene.collection


def mat(name, color, metal=0.0, rough=0.5, emit=None):
    m = bpy.data.materials.new(name)
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*color, 1)
    b.inputs["Metallic"].default_value = metal
    b.inputs["Roughness"].default_value = rough
    if emit:
        b.inputs["Emission Color"].default_value = (*emit, 1)
        b.inputs["Emission Strength"].default_value = 3.0
    return m


PAINT = mat("CarPaint", (0.55, 0.04, 0.03), 0.4, 0.3)
GLASS = mat("Glass", (0.03, 0.06, 0.09), 0.0, 0.08)
TIRE = mat("Rubber", (0.025, 0.025, 0.025), 0.0, 0.85)
RIM = mat("Chrome", (0.8, 0.8, 0.82), 1.0, 0.2)
TRIM = mat("Trim", (0.06, 0.06, 0.07), 0.0, 0.6)
HEAD = mat("Headlight", (0.9, 0.9, 0.85), 0.0, 0.1, emit=(1.0, 0.95, 0.8))
TAIL = mat("Taillight", (0.6, 0.02, 0.02), 0.0, 0.2, emit=(1.0, 0.05, 0.02))


def obj_from_bm(name, bm, material):
    me = bpy.data.meshes.new(name)
    bm.normal_update()
    bm.to_mesh(me)
    bm.free()
    o = bpy.data.objects.new(name, me)
    col.objects.link(o)
    me.materials.append(material)
    return o


def prism_xz(name, pts, half_w, material):
    """Side profile (x, z) extruded across y = -half_w..half_w."""
    bm = bmesh.new()
    a = [bm.verts.new((x, -half_w, z)) for x, z in pts]
    b = [bm.verts.new((x, half_w, z)) for x, z in pts]
    bm.faces.new(a[::-1])
    bm.faces.new(b)
    n = len(pts)
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((a[i], a[j], b[j], b[i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return obj_from_bm(name, bm, material)


def frustum(name, lo, hi, material):
    """Box from a bottom rect lo=(x0,x1,y,z) to a top rect hi=(x0,x1,y,z)."""
    bm = bmesh.new()
    v = []
    for x0, x1, y, z in (lo, hi):
        v += [bm.verts.new(p) for p in ((x0, -y, z), (x1, -y, z), (x1, y, z), (x0, y, z))]
    bm.faces.new(v[3::-1])
    bm.faces.new(v[4:])
    for i in range(4):
        j = (i + 1) % 4
        bm.faces.new((v[i], v[j], v[4 + j], v[4 + i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return obj_from_bm(name, bm, material)


def cyl_y(name, radius, depth, center, material, segs=32):
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=segs, radius1=radius, radius2=radius, depth=depth,
                          matrix=__import__("mathutils").Matrix.Rotation(math.pi / 2, 4, "X"))
    bmesh.ops.translate(bm, verts=bm.verts, vec=center)
    return obj_from_bm(name, bm, material)


def box(name, size, center, material):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=size, verts=bm.verts)
    bmesh.ops.translate(bm, verts=bm.verts, vec=center)
    return obj_from_bm(name, bm, material)


# 1. Blockout at real size (4.0 x 1.8 x 1.45 m), no object scale anywhere.
body = prism_xz("Body", [(-2.0, 0.28), (2.0, 0.28), (2.0, 0.60), (1.9, 0.72), (0.7, 0.80),
                         (-1.2, 0.84), (-1.96, 0.82), (-2.0, 0.66)], 0.86, PAINT)
cabin = frustum("Cabin", (-1.18, 0.72, 0.80, 0.78), (-0.85, 0.12, 0.68, 1.42), GLASS)
roof = frustum("Roof", (-0.86, 0.13, 0.69, 1.40), (-0.82, 0.09, 0.65, 1.45), PAINT)

# 2. Design bevel on the silhouette edges of the body, then the School A stack.
HS.set_edge_attr(body, HS.find_edges(body, min_angle=25), 1.0)
HS.hard_surface_stack(body, micro_width=0.006, micro_segments=2, design_width=0.05, design_segments=6)
for o, w in ((cabin, 0.012), (roof, 0.01)):
    HS.hard_surface_stack(o, micro_width=w, micro_segments=2)

# 3. Cuts: wheel arches (round, half-segment phase), grille pocket, door seams.
for i, x in enumerate((1.3, -1.3)):
    for s in (-1, 1):
        HS.make_cutter(body, "CYLINDER", (0.82, 0.82, 0.48), (x, s * 0.86, 0.33), (90, 0, 0),
                       name=f"ArchCut{i}{s:+d}", vertices=48)
HS.make_cutter(body, "BOX", (0.12, 1.0, 0.16), (2.0, 0, 0.46), name="GrilleCut")
for i, x in enumerate((0.62, -0.42)):
    for s in (-1, 1):
        HS.make_cutter(body, "BOX", (0.016, 0.03, 0.34), (x, s * 0.86, 0.53), name=f"Seam{i}{s}")
HS.order_stack(body)

# 4. Parts: wheels in the arches, rims, bumpers, lights, grille.
parts = [body, cabin, roof]
for x in (1.3, -1.3):
    for s in (-1, 1):
        t = cyl_y(f"Tire{x:+.0f}{s:+d}", 0.33, 0.24, (x, s * 0.76, 0.33), TIRE, 32)
        HS.hard_surface_stack(t, micro_width=0.035, micro_segments=3)
        r = cyl_y(f"Rim{x:+.0f}{s:+d}", 0.2, 0.03, (x, s * 0.88, 0.33), RIM, 24)
        HS.hard_surface_stack(r, micro_width=0.006, micro_segments=2)
        a = cyl_y(f"Axle{x:+.0f}{s:+d}", 0.06, 0.14, (x, s * 0.59, 0.33), TRIM, 12)
        parts += [t, r, a]
for name, x in (("BumperF", 2.03), ("BumperR", -2.03)):
    b = box(name, (0.14, 1.78, 0.16), (x, 0, 0.36), TRIM)
    HS.hard_surface_stack(b, micro_width=0.02, micro_segments=2)
    parts.append(b)
grille = box("Grille", (0.04, 0.98, 0.14), (1.965, 0, 0.46), TRIM)
parts.append(grille)
for s in (-1, 1):
    h = box(f"Headlight{s:+d}", (0.06, 0.3, 0.1), (1.96, s * 0.6, 0.62), HEAD)
    t = box(f"Taillight{s:+d}", (0.06, 0.3, 0.1), (-1.99, s * 0.6, 0.72), TAIL)
    for o in (h, t):
        HS.hard_surface_stack(o, micro_width=0.01, micro_segments=2)
    parts += [h, t]

# 5. Shading QA on the hero part.
report = HS.verdict(HS.shading_audit(body))
print("VERDICT body:", report)

# 6. Game copies (1 micro segment, triangulated, custom normals kept), then export them only.
games = []
for o in parts:
    if any(m.type == "BEVEL" for m in o.modifiers):
        g, tris = HS.game_version(o, micro_segments=1)
    else:
        g = o
    games.append(g)
bpy.ops.object.select_all(action="DESELECT")
for g in games:
    g.hide_set(False)
    g.select_set(True)
os.makedirs(os.path.dirname(out), exist_ok=True)
bpy.ops.export_scene.gltf(filepath=out, use_selection=True, export_apply=True)
print("EXPORTED", out)
