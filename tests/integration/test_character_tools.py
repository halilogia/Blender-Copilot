"""Headless integration tests for rig_character, animate_character, camera_move(follow) and animated glTF export
in real Blender 5.2."""

import json
import math
import os
import struct
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

from adapter.blender_adapter import BlenderAdapter  # noqa: E402
from adapter.mutators.undo_manager import push_undo_step  # noqa: E402
from core.motion_paths import motion_samples  # noqa: E402

PARTS = {
    # name: (location, scale)   size-1 cubes, character stands on Z=0 and faces +Y, right side is +X
    "Body": ((0, 0, 1.2), (0.5, 0.3, 0.7)),
    "Head": ((0, 0, 1.75), (0.3, 0.3, 0.3)),
    "ArmL": ((-0.38, 0, 1.15), (0.14, 0.14, 0.7)),
    "ArmR": ((0.38, 0, 1.15), (0.14, 0.14, 0.7)),
    "LegL": ((-0.14, 0, 0.4), (0.2, 0.2, 0.8)),
    "LegR": ((0.14, 0, 0.4), (0.2, 0.2, 0.8)),
    "Helmet": ((0, 0, 1.95), (0.34, 0.34, 0.1)),
}


def build_character(adapter, names=None):
    bpy.ops.wm.read_homefile(use_empty=True)
    bpy.context.preferences.edit.use_global_undo = True
    for name, (loc, scale) in PARTS.items():
        if names is not None and name not in names:
            continue
        res = adapter.create_primitive("CUBE", name=name, size=1.0, location=list(loc), scale=list(scale))
        assert res.success, (name, res.error)
    push_undo_step("Baseline")
    return list(PARTS) if names is None else list(names)


def world_center(name):
    obj = bpy.data.objects[name]
    pts = [obj.matrix_world @ Vector(c) for c in obj.bound_box]
    return sum(pts, Vector()) / len(pts)


def test_rig():
    print("Test 1: rig_character finds the parts, sets pivots and builds the hierarchy...")
    adapter = BlenderAdapter()
    names = build_character(adapter)
    before = {n: world_center(n) for n in names}
    res = adapter.rig_character(name="Tester", object_names=names)
    assert res.success, res.error
    d = res.data
    assert d["rig"] == "Tester_Rig" and set(d["roles"]) == {"head", "torso", "arm_l", "arm_r", "leg_l", "leg_r"}, d
    assert d["roles"]["arm_r"] == "ArmR" and d["roles"]["leg_l"] == "LegL", d["roles"]
    assert d["attached"] == {"Helmet": "head"}, d["attached"]
    assert abs(d["height"] - 2.0) < 0.05, d["height"]
    rig = bpy.data.objects["Tester_Rig"]
    assert abs(rig.location.z - 0.0) < 1e-3, rig.location
    p = lambda n: bpy.data.objects[n].parent.name  # noqa: E731
    assert p("Body") == "Tester_Rig" and p("Head") == "Body" and p("ArmL") == "Body" and p("LegR") == "Tester_Rig"
    assert p("Helmet") == "Head"
    for n in names:                                  # nothing moved in the world
        assert (world_center(n) - before[n]).length < 1e-3, (n, world_center(n), before[n])
    # pivots: arms and legs turn about their top, the head about its bottom
    assert abs(bpy.data.objects["LegR"].matrix_world.translation.z - 0.8) < 1e-3
    assert abs(bpy.data.objects["ArmL"].matrix_world.translation.z - 1.5) < 1e-3
    assert abs(bpy.data.objects["Head"].matrix_world.translation.z - 1.6) < 1e-3
    dup = adapter.rig_character(name="Tester", object_names=names)
    assert not dup.success and "already exists" in dup.error.message
    few = adapter.rig_character(name="Other", object_names=["Body", "Head"])
    assert not few.success and few.error.type == "INVALID_ARGUMENT", few
    bad = adapter.rig_character(name="X", object_names=["Nope"])
    assert not bad.success
    print("[PASS] Test 1")
    return adapter


def test_animation():
    print("Test 2: animate_character keyframes the parts and moves the rig...")
    adapter = BlenderAdapter()
    names = build_character(adapter)
    assert adapter.rig_character(name="Tester", object_names=names).success
    res = adapter.animate_character(rig="Tester_Rig", preset="walk", duration=2.0, fps=12, distance=3.0)
    assert res.success, res.error
    assert res.data["frames"] == 24 and abs(res.data["travel_m"] - 3.0) < 1e-3, res.data
    scn = bpy.context.scene
    assert scn.frame_end == 24 and scn.render.fps == 12
    rig = bpy.data.objects["Tester_Rig"]
    samples = motion_samples("walk", 24, 12, res.data and 2.0, 1.0, 3.0)  # height from the rig below
    height = rig["character_height"]
    samples = motion_samples("walk", 24, 12, height, 1.0, 3.0)
    scn.frame_set(4)
    assert abs(bpy.data.objects["LegR"].rotation_euler.x - samples[3]["rot"]["leg_r"][0]) < 1e-4
    hip_y = bpy.data.objects["LegR"].matrix_world.translation.y
    foot_y = world_center("LegR").y
    assert samples[3]["rot"]["leg_r"][0] > 0.1 and foot_y > hip_y + 0.08, (foot_y, hip_y)   # a positive swing moves the foot forward (+Y)
    assert world_center("LegL").y < hip_y - 0.05, "the other leg swings back"
    scn.frame_set(24)
    assert abs(rig.location.y - 3.0) < 1e-3 and abs(rig.location.x) < 1e-3, rig.location
    assert (world_center("Helmet") - world_center("Head")).z > 0.15, "helmet stays on the head"
    # heading 90 walks toward -X
    res = adapter.animate_character(rig="Tester_Rig", preset="walk", duration=1.0, fps=12, distance=2.0, heading=90)
    assert res.success
    scn.frame_set(12)
    assert abs(rig.location.x + 2.0) < 1e-3 and abs(rig.location.y) < 1e-3, rig.location
    # every preset runs
    for preset in ("idle", "walk", "run", "aim", "wave", "jump"):
        assert adapter.animate_character(rig="Tester_Rig", preset=preset, duration=1.0, fps=12).success, preset
    for bad in (dict(rig="Body", preset="walk"), dict(rig="Tester_Rig", preset="moonwalk"),
                dict(rig="Tester_Rig", preset="walk", duration=0), dict(rig="Tester_Rig", preset="walk", fps=1)):
        r = adapter.animate_character(**bad)
        assert not r.success and r.error.type == "INVALID_ARGUMENT", (bad, r)
    print("[PASS] Test 2")


def test_follow_and_export():
    print("Test 3: camera_move follow keeps the framing on a walking character; animated glTF export...")
    adapter = BlenderAdapter()
    names = build_character(adapter)
    assert adapter.rig_character(name="Tester", object_names=names).success
    assert adapter.animate_character(rig="Tester_Rig", preset="walk", duration=2.0, fps=12, distance=6.0).success
    res = adapter.camera_move(preset="static", object_names=["Tester_Rig"], duration=2.0, fps=12, follow=True)
    assert res.success and res.data["follow"] is True and res.data["subject_radius"] > 0.8, res.data
    cam = bpy.data.objects["ShotCamera"]
    scn = bpy.context.scene
    dist = []
    for f in (1, 12, 24):
        scn.frame_set(f)
        dist.append((cam.matrix_world.translation - world_center("Body")).length)
    assert max(dist) - min(dist) < 0.25, dist
    scn.frame_set(24)
    assert cam.matrix_world.translation.y > 4.0, "the camera travelled with the character"
    still = adapter.camera_move(preset="static", object_names=["Tester_Rig"], duration=2.0, fps=12, follow=False)
    assert still.success
    scn.frame_set(1)
    near = (cam.matrix_world.translation - world_center("Body")).length
    cam_start = cam.matrix_world.translation.copy()
    scn.frame_set(24)
    assert (cam.matrix_world.translation - cam_start).length < 1e-4, "static without follow must not move"
    assert abs((cam.matrix_world.translation - world_center("Body")).length - near) > 0.4, "without follow the distance changes as the character walks"
    with tempfile.TemporaryDirectory() as tmp:
        adapter.export_dir = tmp
        out = adapter.export_gltf(object_names=["Tester_Rig"], filename="walker.glb", animations=True)
        assert out.success, out.error
        data = Path(out.data["path"]).read_bytes()
        length = struct.unpack_from("<I", data, 12)[0]
        doc = json.loads(data[20:20 + length])
        assert doc.get("animations"), "no animation in the glb"
        node_names = {n.get("name") for n in doc["nodes"]}
        assert {"Body", "Head", "LegR", "Helmet"} <= node_names, node_names
        chans = sum(len(a["channels"]) for a in doc["animations"])
        assert chans >= 6, chans
        plain = adapter.export_gltf(object_names=["Body"], filename="plain.glb")
        assert plain.success
    print("[PASS] Test 3")


def main():
    test_rig()
    test_animation()
    test_follow_and_export()
    print("\nALL CHARACTER TOOL INTEGRATION TESTS PASSED")


if __name__ == "__main__":
    main()
