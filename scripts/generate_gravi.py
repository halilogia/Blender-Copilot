"""GRAVI, the Antigravity mascot, built in 3D with Blender Copilot's own tools (headless).

    blender --background --python scripts/generate_gravi.py -- --out-dir D [--samples 128] [--skip-beauty]

Writes into --out-dir: gravi_3d.blend, gravi_3d_render.png (1024x1024, transparent, Cycles), gravi_3d_sheet.png (8-frame
turntable strip), gravi_3d_idle_sheet.png (8-frame front idle loop: bob, happy eyes, blink) and gravi.glb (baked PBR,
armature, Idle animation, Blink and Happy morph targets).

The shapes (lathe body, ray-cast face visor, morphing pill eyes) are made here with bmesh; everything a tool covers goes
through the BlenderAdapter: set_material (character layers: gradient, Fresnel rim, coat, subsurface, thin film),
create_light, camera_move, render_image (transparent, Cycles), render_contact_sheet (sprite strip), bake_material,
check_model and export_gltf.
"""

import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import bmesh  # noqa: E402
import bpy  # noqa: E402
from mathutils import Euler, Matrix, Vector  # noqa: E402
from mathutils.bvhtree import BVHTree  # noqa: E402

from adapter.blender_adapter import BlenderAdapter  # noqa: E402
from adapter.mutators.undo_manager import push_undo_step  # noqa: E402

LOOP = 48                     # idle loop length in frames (2 s at 24 fps)
VISOR_Z, VISOR_A, VISOR_B = 0.415, 0.38, 0.245
EYE_X, EYE_Z = 0.165, VISOR_Z + 0.035


def srgb(hex_code):
    """#RRGGBB to linear RGB."""
    out = []
    for i in (1, 3, 5):
        c = int(hex_code[i:i + 2], 16) / 255.0
        out.append(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4)
    return out


CYAN, ROYAL, VIOLET = srgb("#00E5FF"), srgb("#2563EB"), srgb("#8B5CF6")
SKY = srgb("#7DD3FC")


def parse(argv):
    args = {"out_dir": str(ROOT / "exports" / "gravi"), "samples": 128, "skip_beauty": False}
    it = iter(argv)
    for a in it:
        if a == "--out-dir":
            args["out_dir"] = next(it)
        elif a == "--samples":
            args["samples"] = int(next(it))
        elif a == "--skip-beauty":
            args["skip_beauty"] = True
    return args


def ok(res, what):
    if not res.success:
        raise RuntimeError(f"{what} failed: {res.error}")
    return res.data


# ---------------------------------------------------------------- shapes
def catmull_rom(points, steps):
    pts = [points[0]] + list(points) + [points[-1]]
    out = []
    for i in range(1, len(pts) - 2):
        p0, p1, p2, p3 = (Vector(p) for p in pts[i - 1:i + 3])
        for s in range(steps):
            t = s / steps
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t
                              + (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3))
    out.append(Vector(points[-1]))
    return out


def resample(curve, count):
    """``count`` points evenly spaced along a polyline (arc length)."""
    lengths = [0.0]
    for a, b in zip(curve, curve[1:]):
        lengths.append(lengths[-1] + (b - a).length)
    total, out, j = lengths[-1], [], 0
    for k in range(count):
        d = total * k / (count - 1)
        while j < len(lengths) - 2 and lengths[j + 1] < d:
            j += 1
        span = lengths[j + 1] - lengths[j] or 1.0
        out.append(curve[j].lerp(curve[j + 1], (d - lengths[j]) / span))
    return out


# (radius, height): soft gumdrop "A" with a full belly, round bottom corners and a rounded apex
PROFILE = [(0.0, 0.0), (0.26, 0.0), (0.47, 0.02), (0.585, 0.10), (0.605, 0.22), (0.565, 0.38), (0.47, 0.57),
           (0.355, 0.76), (0.235, 0.92), (0.12, 1.035), (0.045, 1.08), (0.0, 1.09)]
BODY_Z0, DEPTH = 0.19, 0.86


def body_point(r, z, theta):
    x, y = r * math.cos(theta), r * math.sin(theta) * DEPTH
    # belly: the front swells a little where the face sits
    front = max(0.0, math.sin(theta)) ** 2
    y += 0.055 * front * math.exp(-((z - 0.36) / 0.24) ** 2) * min(1.0, r / 0.2)
    return Vector((x, y, BODY_Z0 + z))


def build_body(segments=56, rings=46):
    prof = resample(catmull_rom([Vector((r, z)) for r, z in PROFILE], 12), rings)
    bm = bmesh.new()
    bottom = bm.verts.new(body_point(0.0, prof[0].y, 0.0))
    top = bm.verts.new(body_point(0.0, prof[-1].y, 0.0))
    grid = []
    for p in prof[1:-1]:
        grid.append([bm.verts.new(body_point(p.x, p.y, 2 * math.pi * j / segments)) for j in range(segments)])
    for j in range(segments):
        k = (j + 1) % segments
        bm.faces.new((bottom, grid[0][k], grid[0][j]))
        bm.faces.new((top, grid[-1][j], grid[-1][k]))
        for i in range(len(grid) - 1):
            bm.faces.new((grid[i][j], grid[i][k], grid[i + 1][k], grid[i + 1][j]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return bm


def visor_param(rho, phi, n=2.5):
    c, s = math.cos(phi), math.sin(phi)
    u = rho * math.copysign(abs(c) ** (2 / n), c)
    v = rho * math.copysign(abs(s) ** (2 / n), s)
    width = 1.0 - 0.16 * v           # a gumdrop: narrower at the top
    return u * VISOR_A * width, VISOR_Z + v * VISOR_B


def build_visor(body_tree, segments=64, rings=20, dome=0.048):
    """A pillow-shaped face plate that follows the body: ray-cast from the front, lifted along the surface normal."""
    bm = bmesh.new()

    def lifted(x, z, rho):
        hit, normal, _i, _d = body_tree.ray_cast(Vector((x, 3.0, BODY_Z0 + z)), Vector((0, -1, 0)))
        if hit is None:
            raise RuntimeError("visor ray missed the body")
        lift = -0.012 + (dome + 0.012) * max(0.0, 1.0 - rho ** 8) ** 0.32
        return hit + normal * lift

    centre = bm.verts.new(lifted(0.0, VISOR_Z, 0.0))
    ring_rhos = [1.0 - (1.0 - k / rings) ** 1.7 for k in range(1, rings + 1)]
    grid = []
    for rho in ring_rhos:
        row = []
        for j in range(segments):
            x, z = visor_param(rho, 2 * math.pi * j / segments)
            row.append(bm.verts.new(lifted(x, z, rho)))
        grid.append(row)
    for j in range(segments):
        k = (j + 1) % segments
        bm.faces.new((centre, grid[0][j], grid[0][k]))
        for i in range(rings - 1):
            bm.faces.new((grid[i][j], grid[i + 1][j], grid[i + 1][k], grid[i][k]))
    bm.normal_update()
    if sum(f.normal.y for f in bm.faces) < 0:
        bmesh.ops.reverse_faces(bm, faces=bm.faces)
    return bm


def surface_frame(tree, x, z, step=0.02):
    """Where a front ray at (x, z) lands, with axes that follow the surface: X sideways, Y out of it, Z up along it."""
    def land(px, pz):
        hit = tree.ray_cast(Vector((px, 3.0, pz)), Vector((0, -1, 0)))[0]
        if hit is None:
            raise RuntimeError(f"ray at ({px:.3f}, {pz:.3f}) missed the surface")
        return hit
    centre = land(x, z)
    side = (land(x + step, z) - land(x - step, z)).normalized()
    up = (land(x, z + step) - land(x, z - step)).normalized()
    out = up.cross(side).normalized()
    if out.y < 0:
        out = -out
    up = side.cross(out).normalized()
    m = Matrix((side, out, up)).transposed().to_4x4()
    m.translation = centre
    return m


def mesh_object(name, bm, smooth=True):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for poly in me.polygons:
        poly.use_smooth = smooth
    obj = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(obj)
    return obj


def eye_mesh(name):
    """A glossy pill (capsule-ish ellipsoid, local +Y out of the face) with two sparkles; shape keys Blink and Happy."""
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=32, v_segments=18, radius=1.0)
    for v in bm.verts:
        x, y, z = v.co
        v.co = Vector((x * 0.056, y * 0.016, z * 0.054 + math.copysign(0.034, z) * min(1.0, abs(z) * 4)))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    # sparkles sit on the front of the eye: a big one top right (screen), a small one lower left
    for (sx, sz, rad) in ((-0.019, 0.04, 0.016), (0.018, -0.036, 0.008)):
        ret = bmesh.ops.create_uvsphere(bm, u_segments=12, v_segments=8, radius=rad)
        bmesh.ops.recalc_face_normals(bm, faces=list({f for v in ret["verts"] for f in v.link_faces}))
        for v in ret["verts"]:
            v.co = Vector((v.co.x + sx, v.co.y * 0.3 + 0.0155, v.co.z + sz))
        for f in {f for v in ret["verts"] for f in v.link_faces}:
            f.material_index = 1
    obj = mesh_object(name, bm)
    me = obj.data
    # bmesh reuses freed slots, so vertex order says nothing: the sparkles are the vertices of material 1
    sparkle = {v for p in me.polygons if p.material_index == 1 for v in p.vertices}
    basis = obj.shape_key_add(name="Basis", from_mix=False)
    blink = obj.shape_key_add(name="Blink", from_mix=False)
    happy = obj.shape_key_add(name="Happy", from_mix=False)
    for i in range(len(me.vertices)):
        x, y, z = basis.data[i].co
        if i in sparkle:   # sparkles hide behind the closed eye
            blink.data[i].co = happy.data[i].co = Vector((0.0, -0.01, -0.012))
            continue
        blink.data[i].co = Vector((x * 1.1, y, z * 0.12 - 0.018))
        # happy ^ ^: the pill bends into an upward arc
        u, t = max(-1.0, min(1.0, x / 0.056)), max(-1.0, min(1.0, z / 0.088))
        theta, radius = u * 1.2, 0.062 + t * 0.018
        happy.data[i].co = Vector((radius * math.sin(theta), y + 0.004 * math.cos(theta), radius * math.cos(theta) - 0.062 + 0.01))
    return obj


def capsule(name, length, radius, depth, segments=32, rings=14):
    """A pill lying along X: a sphere stretched in its middle."""
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=segments, v_segments=rings, radius=1.0)
    half = length / 2 - radius
    for v in bm.verts:
        x, y, z = v.co
        v.co = Vector((x * radius + math.copysign(half, x) * min(1.0, abs(x) * 5), y * depth, z * radius))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return mesh_object(name, bm)


def torus(name, major, minor, segments=48, sides=8):
    bm = bmesh.new()
    verts = [[bm.verts.new(Vector(((major + minor * math.cos(b)) * math.cos(a), (major + minor * math.cos(b)) * math.sin(a),
                                    minor * math.sin(b))))
              for b in (2 * math.pi * k / sides for k in range(sides))] for a in (2 * math.pi * j / segments for j in range(segments))]
    for j in range(segments):
        for k in range(sides):
            jj, kk = (j + 1) % segments, (k + 1) % sides
            bm.faces.new((verts[j][k], verts[jj][k], verts[jj][kk], verts[j][kk]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return mesh_object(name, bm)


# ---------------------------------------------------------------- shading
def blush_visor(mat):
    """Cream pearl face with two soft rosy cheeks (object-space spots, no UVs)."""
    tree = mat.node_tree
    bsdf = next(n for n in tree.nodes if n.type == "BSDF_PRINCIPLED")
    coord = tree.nodes.new("ShaderNodeTexCoord")
    masks = []
    for side in (-1, 1):
        sub = tree.nodes.new("ShaderNodeVectorMath")
        sub.operation = "SUBTRACT"
        sub.inputs[1].default_value = (side * 0.25, 0.0, BODY_Z0 + VISOR_Z - 0.075)
        squash = tree.nodes.new("ShaderNodeVectorMath")
        squash.operation = "MULTIPLY"
        squash.inputs[1].default_value = (1.0, 0.0, 1.45)
        length = tree.nodes.new("ShaderNodeVectorMath")
        length.operation = "LENGTH"
        fall = tree.nodes.new("ShaderNodeMapRange")
        fall.interpolation_type = "SMOOTHERSTEP"
        fall.inputs["From Min"].default_value, fall.inputs["From Max"].default_value = 0.015, 0.088
        fall.inputs["To Min"].default_value, fall.inputs["To Max"].default_value = 0.9, 0.0
        tree.links.new(coord.outputs["Object"], sub.inputs[0])
        tree.links.new(sub.outputs["Vector"], squash.inputs[0])
        tree.links.new(squash.outputs["Vector"], length.inputs[0])
        tree.links.new(length.outputs["Value"], fall.inputs["Value"])
        masks.append(fall)
    both = tree.nodes.new("ShaderNodeMath")
    both.operation = "MAXIMUM"
    tree.links.new(masks[0].outputs["Result"], both.inputs[0])
    tree.links.new(masks[1].outputs["Result"], both.inputs[1])
    mix = tree.nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    mix.inputs["A"].default_value = (*srgb("#FBF7F0"), 1.0)
    mix.inputs["B"].default_value = (*srgb("#FF8FAB"), 1.0)
    tree.links.new(both.outputs["Value"], mix.inputs["Factor"])
    tree.links.new(mix.outputs["Result"], bsdf.inputs["Base Color"])
    bsdf.inputs["Base Color"].default_value = (*srgb("#FBF7F0"), 1.0)


def shade(adapter, objs):
    ok(adapter.set_material(object_name=objs["body"].name, material_name="GRAVI_Body", roughness=0.32,
                            gradient_colors=[VIOLET, ROYAL, CYAN], gradient_axis="diagonal",
                            rim_colors=[SKY, CYAN, ROYAL], rim_strength=1.6,
                            coat=1.0, coat_roughness=0.035, subsurface=0.12, thin_film=260), "body material")
    ok(adapter.set_material(object_name=objs["visor"].name, material_name="GRAVI_Visor", roughness=0.28,
                            coat=0.85, coat_roughness=0.05, subsurface=0.25, thin_film=420,
                            rim_colors=[[0.75, 0.9, 1.0], [0.92, 0.88, 1.0]], rim_strength=0.35), "visor material")
    blush_visor(bpy.data.materials["GRAVI_Visor"])
    for eye in (objs["eye_l"], objs["eye_r"]):
        ok(adapter.set_material(object_name=eye.name, material_name="GRAVI_Eye", base_color=srgb("#141A3D"),
                                roughness=0.16), "eye material")
        # the sparkles carry the shine: a half-strength specular keeps the key light from drawing a white bar
        eye_bsdf = next(n for n in bpy.data.materials["GRAVI_Eye"].node_tree.nodes if n.type == "BSDF_PRINCIPLED")
        eye_bsdf.inputs["Specular IOR Level"].default_value = 0.22
        ok(adapter.set_material(object_name=eye.name, material_name="GRAVI_Sparkle", slot_index=1,
                                base_color=[1, 1, 1], emission_color=[1, 1, 1], emission_strength=6.0, roughness=0.2),
           "sparkle material")
    ok(adapter.set_material(object_name=objs["pad_r"].name, material_name="GRAVI_PadR", roughness=0.3,
                            gradient_colors=[ROYAL, CYAN], gradient_axis="x", coat=1.0,
                            rim_colors=[SKY, CYAN], rim_strength=1.8), "pad material")
    ok(adapter.set_material(object_name=objs["pad_l"].name, material_name="GRAVI_PadL", roughness=0.3,
                            gradient_colors=[VIOLET, ROYAL], gradient_axis="x", coat=1.0,
                            rim_colors=[[0.75, 0.6, 1.0], VIOLET], rim_strength=1.8), "pad material")
    ok(adapter.set_material(object_name=objs["orb"].name, material_name="GRAVI_Orb", roughness=0.15,
                            gradient_colors=[ROYAL, CYAN, [0.85, 0.98, 1.0]], coat=1.0, thin_film=380,
                            rim_colors=[[0.8, 0.97, 1.0], CYAN], rim_strength=5.0), "orb material")
    for name, colour in (("field_r", CYAN), ("field_l", VIOLET), ("ring", CYAN)):
        ok(adapter.set_material(object_name=objs[name].name, material_name=f"GRAVI_Glow_{name}", base_color=colour,
                                emission_color=colour, emission_strength=5.0 if name == "ring" else 3.5, roughness=0.4),
           "glow material")


# ---------------------------------------------------------------- rig and motion
BONES = {"root": ((0, 0, 0), (0, 0, 0.15), None), "body": ((0, 0, 0.19), (0, 0, 1.28), "root"),
         "orb": ((0, 0, 1.43), (0, 0, 1.56), "body"), "pad_l": ((-0.216, 0, 0.0), (-0.216, 0, 0.1), "root"),
         "pad_r": ((0.216, 0, 0.0), (0.216, 0, 0.1), "root")}


def build_rig(objs):
    arm_data = bpy.data.armatures.new("GRAVI_Armature")
    rig = bpy.data.objects.new("GRAVI_Rig", arm_data)
    bpy.context.scene.collection.objects.link(rig)
    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode="EDIT")
    for name, (head, tail, parent) in BONES.items():
        bone = arm_data.edit_bones.new(name)
        bone.head, bone.tail = head, tail
        if parent:
            bone.parent = arm_data.edit_bones[parent]
    bpy.ops.object.mode_set(mode="OBJECT")
    owners = {"body": ("body", "visor", "eye_l", "eye_r"), "orb": ("orb", "ring", "orb_light"),
              "pad_l": ("pad_l", "field_l"), "pad_r": ("pad_r", "field_r")}
    bpy.context.view_layer.update()
    for bone, names in owners.items():
        for n in names:
            obj = objs[n]
            world = obj.matrix_world.copy()
            obj.parent, obj.parent_type, obj.parent_bone = rig, "BONE", bone
            bpy.context.view_layer.update()
            obj.matrix_world = world
    for pb in rig.pose.bones:
        pb.rotation_mode = "XYZ"
    return rig


def bump(f, centre, half):
    d = abs(f - centre) / half
    return 0.0 if d >= 1 else 0.5 * (1 + math.cos(math.pi * d))


def key_pose(rig, eyes, f, phase, spin=0.0, happy=0.0, blink=0.0):
    """One pose: bones move along their own Y (up); ``phase`` is the loop position 0-1."""
    tau = 2 * math.pi * phase
    pb = rig.pose.bones
    pb["root"].rotation_euler = (0.0, spin, 0.0)
    pb["body"].location = (0.0, 0.028 * math.sin(tau), 0.0)
    squash = 0.012 * math.cos(2 * tau)
    pb["body"].scale = (1.0 + squash, 1.0 - squash, 1.0 + squash)
    pb["orb"].location = (0.0, 0.03 * math.sin(tau - 1.1), 0.0)
    pb["orb"].rotation_euler = (0.0, tau, 0.0)
    pb["pad_l"].location = (0.0, 0.018 * math.sin(tau - 0.7), 0.0)
    pb["pad_r"].location = (0.0, 0.018 * math.sin(tau - 1.3), 0.0)
    for bone in pb:
        bone.keyframe_insert("location", frame=f)
        bone.keyframe_insert("rotation_euler", frame=f)
        bone.keyframe_insert("scale", frame=f)
    for eye in eyes:
        keys = eye.data.shape_keys.key_blocks
        keys["Happy"].value, keys["Blink"].value = happy, blink
        keys["Happy"].keyframe_insert("value", frame=f)
        keys["Blink"].keyframe_insert("value", frame=f)


def new_actions(rig, eyes, name):
    rig.animation_data_create()
    rig.animation_data.action = bpy.data.actions.new(name)
    for eye in eyes:
        eye.data.shape_keys.animation_data_create()
        eye.data.shape_keys.animation_data.action = bpy.data.actions.new(f"{name}_{eye.name}")


def animate_idle(rig, eyes):
    """A 2-second loop: float, squash, orb orbit, happy eyes around frame 13 and a blink around frame 31."""
    new_actions(rig, eyes, "Idle")
    for f in range(1, LOOP + 1):
        key_pose(rig, eyes, f, (f - 1) / LOOP, happy=bump(f, 13, 5), blink=bump(f, 31, 2.6))


def animate_turntable(rig, eyes, count=8):
    new_actions(rig, eyes, "Turntable")
    for i in range(count):
        key_pose(rig, eyes, i + 1, i / count, spin=2 * math.pi * i / count)
    bpy.context.scene.frame_start, bpy.context.scene.frame_end = 1, count


# ---------------------------------------------------------------- scene
def studio(adapter, objs):
    world = bpy.data.worlds.new("GRAVI_Studio")
    bpy.context.scene.world = world
    world.use_nodes = True
    tree = world.node_tree
    bg = next(n for n in tree.nodes if n.type == "BACKGROUND")
    coord = tree.nodes.new("ShaderNodeTexCoord")
    split = tree.nodes.new("ShaderNodeSeparateXYZ")
    ramp = tree.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position, ramp.color_ramp.elements[0].color = 0.42, (0.025, 0.02, 0.06, 1)
    ramp.color_ramp.elements[1].position, ramp.color_ramp.elements[1].color = 0.75, (0.55, 0.6, 0.75, 1)
    to_unit = tree.nodes.new("ShaderNodeMapRange")
    to_unit.inputs["From Min"].default_value, to_unit.inputs["From Max"].default_value = -1.0, 1.0
    tree.links.new(coord.outputs["Generated"], split.inputs["Vector"])
    tree.links.new(split.outputs["Z"], to_unit.inputs["Value"])
    tree.links.new(to_unit.outputs["Result"], ramp.inputs["Fac"])
    tree.links.new(ramp.outputs["Color"], bg.inputs["Color"])
    bg.inputs["Strength"].default_value = 0.45

    # three-point light plus two coloured kickers that draw the silhouette
    lights = [("GRAVI_Key", (1.7, 2.3, 2.3), 170.0, (1.0, 0.95, 0.9), 1.4),
              ("GRAVI_Fill", (-2.2, 1.9, 1.0), 55.0, (0.82, 0.86, 1.0), 2.4),
              ("GRAVI_RimCyan", (1.5, -1.9, 1.9), 380.0, tuple(CYAN), 1.0),
              ("GRAVI_RimViolet", (-1.6, -1.7, 1.3), 380.0, tuple(VIOLET), 1.0),
              ("GRAVI_Top", (0.0, 0.4, 3.0), 30.0, (1.0, 1.0, 1.0), 2.0)]
    target = Vector((0, 0, 0.75))
    for name, loc, energy, colour, size in lights:
        rot = (target - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
        ok(adapter.create_light(name=name, light_type="AREA", location=list(loc), rotation=list(rot), energy=energy,
                                color=list(colour)), name)
        bpy.data.objects[name].data.size = size
    point = bpy.data.lights.new("GRAVI_OrbGlow", "POINT")
    point.energy, point.color, point.shadow_soft_size = 12.0, tuple(CYAN), 0.05
    point.use_shadow = False
    glow = bpy.data.objects.new("GRAVI_OrbGlow", point)
    glow.location = objs["orb"].location
    bpy.context.scene.collection.objects.link(glow)
    objs["orb_light"] = glow

    scn = bpy.context.scene
    # Standard keeps the brand colours saturated (AgX pulls bright cyan towards white)
    scn.view_settings.view_transform = "Standard"
    for prop in ("use_raytracing", "use_shadows"):
        if hasattr(scn.eevee, prop):
            setattr(scn.eevee, prop, True)


def frame(adapter, names, elevation=6.0, distance=3.05):
    ok(adapter.camera_move(preset="static", object_names=names, duration=1.0, fps=24, distance=distance,
                           elevation=elevation, azimuth=0.0, focal_length=50.0), "camera")


def main():
    args = parse(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
    out = Path(args["out_dir"]).expanduser().resolve()
    out.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.read_homefile(use_empty=True)
    bpy.context.preferences.edit.use_global_undo = True
    adapter = BlenderAdapter()
    adapter.export_dir = str(out)
    push_undo_step("Baseline")
    scn = bpy.context.scene
    scn.render.fps = 24

    print("[gravi] modelling", flush=True)
    body_bm = build_body()
    body_tree = BVHTree.FromBMesh(body_bm)
    visor_bm = build_visor(body_tree)
    visor_tree = BVHTree.FromBMesh(visor_bm)
    objs = {"body": mesh_object("GRAVI_Body", body_bm), "visor": mesh_object("GRAVI_Visor", visor_bm)}
    for side, x in (("eye_l", -EYE_X), ("eye_r", EYE_X)):
        frame_m = surface_frame(visor_tree, x, BODY_Z0 + EYE_Z)
        eye = eye_mesh(f"GRAVI_{side.title().replace('_', '')}")
        eye.matrix_world = Matrix.Translation(frame_m.translation - frame_m.col[1].xyz * 0.002) @ frame_m.to_3x3().to_4x4()
        objs[side] = eye
    for side, x in (("pad_l", -0.2), ("pad_r", 0.2)):
        pad = capsule(f"GRAVI_{side.title().replace('_', '')}", 0.33, 0.068, 0.11)
        pad.location = (x * 1.08, 0.03, 0.07)
        objs[side] = pad
        field = torus(f"GRAVI_Field{side[-1].upper()}", 0.13, 0.007)
        field.data.transform(Matrix.Diagonal((1.3, 0.75, 1.0, 1.0)))
        field.location = (x * 1.08, 0.03, 0.012)
        objs["field" + side[-2:]] = field
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=32, v_segments=16, radius=0.085)
    objs["orb"] = mesh_object("GRAVI_Orb", bm)
    objs["orb"].location = (0.0, 0.0, 1.47)
    ring = torus("GRAVI_OrbRing", 0.15, 0.006)
    ring.location, ring.rotation_euler = (0.0, 0.0, 1.47), Euler((math.radians(16), math.radians(-22), 0.0))
    objs["ring"] = ring

    print("[gravi] shading and lighting", flush=True)
    shade(adapter, objs)
    studio(adapter, objs)
    rig = build_rig(objs)
    eyes = [objs["eye_l"], objs["eye_r"]]
    meshes = [o.name for o in objs.values() if o.type == "MESH"]

    # front idle pose for the hero shot, camera framed on the whole character
    animate_idle(rig, eyes)
    frame(adapter, meshes)
    scn.frame_start, scn.frame_end = 1, LOOP
    scn.frame_set(1)
    bpy.context.view_layer.update()
    qa = ok(adapter.check_model(object_names=meshes), "check_model")
    print("[gravi] check_model:", qa["summary"], "| triangles", qa["triangles"], flush=True)
    if not args["skip_beauty"]:
        print("[gravi] beauty render (Cycles)", flush=True)
        beauty = ok(adapter.render_image(filename="gravi_3d_render", width=1024, height=1024, frame=1,
                                         samples=args["samples"], transparent=True, engine="cycles"), "beauty render")
        print("[gravi] beauty:", beauty["path"], flush=True)

    print("[gravi] idle sprite strip", flush=True)
    scn.frame_start, scn.frame_end = 1, LOOP - LOOP // 8 + 1      # 8 picks, 6 frames apart, the loop closes
    idle = ok(adapter.render_contact_sheet(filename="gravi_3d_idle_sheet", frames=8, columns=8, width=256, height=256,
                                           samples=32, transparent=True), "idle sheet")
    print("[gravi] idle sheet:", idle["path"], idle["frames"], flush=True)

    print("[gravi] turntable sprite strip", flush=True)
    idle_actions = (rig.animation_data.action, [e.data.shape_keys.animation_data.action for e in eyes])
    animate_turntable(rig, eyes)
    sheet = ok(adapter.render_contact_sheet(filename="gravi_3d_sheet", frames=8, columns=8, width=256, height=256,
                                            samples=32, transparent=True), "turntable sheet")
    print("[gravi] sheet:", sheet["path"], sheet["frames"], flush=True)

    # back to the idle loop, then keep the production file (the turntable stays in it as a spare action)
    turntable = [rig.animation_data.action] + [e.data.shape_keys.animation_data.action for e in eyes]
    rig.animation_data.action = idle_actions[0]
    for eye, act in zip(eyes, idle_actions[1]):
        eye.data.shape_keys.animation_data.action = act
    for act in turntable:
        act.use_fake_user = True
    scn.frame_start, scn.frame_end = 1, LOOP
    scn.frame_set(1)
    blend = out / "gravi_3d.blend"
    bpy.context.preferences.filepaths.save_version = 0      # regenerating must not leave .blend1 backups
    bpy.ops.wm.save_as_mainfile(filepath=str(blend), compress=True)
    print("[gravi] saved", blend, flush=True)

    print("[gravi] glTF: baking procedural looks", flush=True)
    for act in turntable:          # only the idle loop goes into the game file
        bpy.data.actions.remove(act)
    for key, size in (("body", 1024), ("visor", 1024), ("pad_l", 256), ("pad_r", 256), ("orb", 256)):
        ok(adapter.bake_material(object_name=objs[key].name, resolution=size, samples=4), f"bake {key}")
    orb_mat = objs["orb"].material_slots[0].material
    bsdf = next(n for n in orb_mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    bsdf.inputs["Emission Color"].default_value, bsdf.inputs["Emission Strength"].default_value = (*CYAN, 1), 1.5
    names = [rig.name] + meshes
    glb = ok(adapter.export_gltf(object_names=names, filename="gravi.glb", apply_modifiers=False, animations=True),
             "export")
    print("[gravi] glb:", glb.get("path"), "triangles", glb.get("triangle_count"), flush=True)
    print("[gravi] done", flush=True)


if __name__ == "__main__":
    main()
