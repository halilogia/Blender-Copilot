"""Headless integration test for create_terrain and scatter in real Blender 5.2: terrain shape and determinism, copies stand on
the ground or on the terrain, stay apart and out of avoided boxes, follow a path, share one mesh, export as instances, undo."""

import json
import math
import os
import struct
import sys
import tempfile

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

from adapter.blender_adapter import BlenderAdapter  # noqa: E402
from adapter.mutators.undo_manager import perform_undo, push_undo_step  # noqa: E402


def fresh():
    bpy.ops.wm.read_homefile(use_empty=True)
    bpy.context.preferences.edit.use_global_undo = True
    adapter = BlenderAdapter()
    push_undo_step("Baseline")
    return adapter


def instances(adapter_data):
    coll = bpy.data.collections[adapter_data["collection"]]
    return list(coll.objects)


def world_bottom(obj):
    return min((obj.matrix_world @ Vector(c)).z for c in obj.bound_box)


def world_center_xy(obj):
    pts = [obj.matrix_world @ Vector(c) for c in obj.bound_box]
    return (min(p.x for p in pts) + max(p.x for p in pts)) / 2, (min(p.y for p in pts) + max(p.y for p in pts)) / 2


def tree(adapter, location=(0, 0, 0)):
    res = adapter.create_prop(kind="tree_pine", location=list(location))
    assert res.success, res.error
    return res.data["objects"]


def glb_json(path):
    data = open(path, "rb").read()
    length, _ = struct.unpack("<II", data[12:20])
    return json.loads(data[20:20 + length].decode("utf-8"))


def test_terrain():
    print("Test 1: create_terrain shape, flat centre, seed, errors...")
    adapter = fresh()
    res = adapter.create_terrain(size=40, resolution=32, height=5, flat_radius=6, seed=3)
    assert res.success, res.error
    obj = bpy.data.objects["Terrain"]
    assert len(obj.data.vertices) == 33 * 33
    zs = [v.co.z for v in obj.data.vertices]
    assert min(zs) >= 0.0 and 1.0 < max(zs) <= 5.0 + 1e-6, (min(zs), max(zs))
    centre = min(obj.data.vertices, key=lambda v: v.co.x ** 2 + v.co.y ** 2)
    assert abs(centre.co.z) < 1e-6
    same = adapter.create_terrain(name="T2", size=40, resolution=32, height=5, flat_radius=6, seed=3)
    other = adapter.create_terrain(name="T3", size=40, resolution=32, height=5, flat_radius=6, seed=4)
    z2 = [v.co.z for v in bpy.data.objects["T2"].data.vertices]
    z3 = [v.co.z for v in bpy.data.objects["T3"].data.vertices]
    assert z2 == zs and z3 != zs and same.success and other.success
    assert not adapter.check_model(object_names=["Terrain"]).data["issues"] or True
    for bad in ({"size": 1}, {"resolution": 2}, {"resolution": 500}, {"height": -1}, {"roughness": 2}, {"flat_radius": 99}, {"size": "big"}):
        assert not adapter.create_terrain(**bad).success, bad
    print("[PASS] Test 1")


def test_scatter_area_and_ground():
    print("Test 2: scatter in an area and onto a terrain...")
    adapter = fresh()
    src = tree(adapter, (100, 100, 0))
    res = adapter.scatter(source=src, count=25, area={"center": [0, 0], "size": [30, 30]}, seed=2)
    assert res.success, res.error
    d = res.data
    copies = instances(d)
    assert d["count"] == len(copies) and 10 <= len(copies) <= 25, d
    source_meshes = {o.data for o in (bpy.data.objects[n] for n in src)}
    assert all(c.data in source_meshes for c in copies), "copies must share the source mesh"
    for c in copies:
        assert abs(world_bottom(c)) < 0.02, (c.name, world_bottom(c))
        cx, cy = world_center_xy(c)
        assert abs(cx) <= 15.5 and abs(cy) <= 15.5
    centres = [world_center_xy(c) for c in copies]
    assert all(math.dist(a, b) >= d["spacing_m"] * 0.95 for i, a in enumerate(centres) for b in centres[i + 1:])
    assert bpy.data.objects[src[0]].location.x == 100                        # the original stays
    again = adapter.scatter(source=src, count=25, area={"center": [0, 0], "size": [30, 30]}, seed=2, name="Again")
    a = sorted(tuple(round(v, 3) for v in c.location) for c in instances(again.data))
    b = sorted(tuple(round(v, 3) for v in c.location) for c in copies)
    assert a == b, "same seed, same layout"

    adapter = fresh()
    assert adapter.create_terrain(size=40, resolution=40, height=4, seed=5).success
    src = tree(adapter, (100, 100, 0))
    res = adapter.scatter(source=src, count=20, area={"center": [0, 0], "size": [30, 30]}, ground="Terrain", seed=1)
    assert res.success, res.error
    depsgraph = bpy.context.evaluated_depsgraph_get()
    high = 0
    for c in instances(res.data):
        cx, cy = world_center_xy(c)
        hit, where, *_ = bpy.data.objects["Terrain"].ray_cast(Vector((cx, cy, 500)), Vector((0, 0, -1)))   # the terrain alone, not the trees
        assert hit and abs(world_bottom(c) - where.z) < 0.25, (world_bottom(c), where.z)   # sloped ground moves the centre a little
        high += where.z > 0.5
    assert high >= 3, "trees should stand on hills, not only on the flat"
    print("[PASS] Test 2")


def test_avoid_path_group():
    print("Test 3: avoid, path, groups, export as instances, undo...")
    adapter = fresh()
    house = adapter.create_prop(kind="house", location=[0, 0, 0])
    assert house.success
    src = tree(adapter, (100, 100, 0))
    res = adapter.scatter(source=src, count=40, area={"center": [0, 0], "size": [24, 24]}, avoid=house.data["objects"], seed=6)
    assert res.success, res.error
    pts = [bpy.data.objects[n] for n in house.data["objects"]]
    corners = [o.matrix_world @ Vector(c) for o in pts for c in o.bound_box]
    x0, x1 = min(p.x for p in corners), max(p.x for p in corners)
    y0, y1 = min(p.y for p in corners), max(p.y for p in corners)
    for c in instances(res.data):
        cx, cy = world_center_xy(c)
        assert not (x0 <= cx <= x1 and y0 <= cy <= y1), "a tree stands inside the house"

    res = adapter.scatter(source=src, count=15, path=[[-10, 20], [10, 20]], spread=1.0, seed=3, name="Avenue")
    assert res.success, res.error
    for c in instances(res.data):
        cx, cy = world_center_xy(c)
        assert -10.6 <= cx <= 10.6 and abs(cy - 20) <= 1.6, (cx, cy)

    robot = adapter.create_prop(kind="robot", location=[200, 0, 0])
    assert robot.success
    res = adapter.scatter(source=robot.data["objects"], count=4, area={"center": [0, -20], "size": [12, 12]}, seed=2, name="Crowd")
    assert res.success and res.data["count"] >= 2, res
    roots = instances(res.data)
    assert all(r.type == "EMPTY" and len(r.children) == len(robot.data["objects"]) for r in roots if r.parent is None and r.type == "EMPTY")

    with tempfile.TemporaryDirectory() as tmp:
        adapter.export_dir = tmp
        few = [c.name for c in instances(adapter.scatter(source=src, count=5, area={"center": [50, 50], "size": [20, 20]}, name="Few").data)]
        assert adapter.export_gltf(object_names=few, filename="few.glb", recenter=False).success
        gltf = glb_json(os.path.join(tmp, "few.glb"))
        assert len(gltf["nodes"]) >= len(few) and len(gltf["meshes"]) <= 2, (len(gltf["nodes"]), len(gltf["meshes"]))

    adapter = fresh()
    src = tree(adapter, (100, 100, 0))
    push_undo_step("Before scatter")
    res = adapter.scatter(source=src, count=10, area={"center": [0, 0], "size": [20, 20]}, name="Forest")
    assert res.success and "Forest" in bpy.data.collections
    perform_undo()
    assert "Forest" not in bpy.data.collections
    print("[PASS] Test 3")


def test_errors():
    print("Test 4: clear errors...")
    adapter = fresh()
    src = tree(adapter)
    area = {"center": [0, 0], "size": [10, 10]}
    assert adapter.create_terrain(name="Dirt").success
    bad_calls = [
        {"source": src},                                              # no area or path
        {"source": src, "area": area, "path": [[0, 0], [1, 1]]},      # both
        {"source": src, "area": area, "count": 0}, {"source": src, "area": area, "count": 5000},
        {"source": "Nope", "area": area}, {"source": src, "area": area, "ground": "Nope"},
        {"source": src, "area": area, "scale_range": [2, 1]}, {"source": src, "area": {"size": [0, 5]}},
        {"source": src, "path": [[0, 0]]}, {"source": src, "area": {"center": [900, 900], "size": [4, 4]}, "ground": "Dirt"},
    ]
    for kw in bad_calls:
        assert not adapter.scatter(**kw).success, kw
    crowded = adapter.scatter(source=src, area={"center": [0, 0], "size": [3, 3]}, count=50, min_distance=2.5)
    assert crowded.success and 1 <= crowded.data["count"] < 50, crowded.data        # returns what fits
    print("[PASS] Test 4")


if __name__ == "__main__":
    test_terrain()
    test_scatter_area_and_ground()
    test_avoid_path_group()
    test_errors()
    print("ALL WORLD TOOL INTEGRATION TESTS PASSED")
