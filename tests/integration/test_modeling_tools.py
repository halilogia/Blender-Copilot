"""Headless integration tests for the v1.2 modeling tools in real Blender 5.2.

Covers the new primitives, create_mesh, mesh_edit, join_objects, parent_object, apply_transform, set_origin,
export_gltf (a real .glb is written and read back), argument validation, undo and thread safety.
"""

import math
import os
import sys
import tempfile
import threading

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import bpy  # noqa: E402

from adapter.blender_adapter import BlenderAdapter, ThreadSafetyViolationError  # noqa: E402
from adapter.mutators.undo_manager import perform_undo, push_undo_step  # noqa: E402
from tools.mutations.create_mesh import CreateMeshTool  # noqa: E402
from tools.mutations.mesh_edit import MeshEditTool  # noqa: E402
from tools.registry import ToolRegistry  # noqa: E402


def clean_scene():
    bpy.ops.wm.read_homefile(use_empty=True)
    bpy.context.preferences.edit.use_global_undo = True
    push_undo_step("Initial Scene Baseline")


def near(a, b, tol=1e-3):
    return abs(a - b) <= tol


def dims(name):
    return list(bpy.data.objects[name].dimensions)


def test_new_primitives():
    print("Test 1: CYLINDER, CONE, ICOSPHERE, TORUS...")
    clean_scene()
    adapter = BlenderAdapter()
    for kind, name in (("CYLINDER", "Cyl"), ("CONE", "Cone"), ("ICOSPHERE", "Ico"), ("TORUS", "Ring")):
        res = adapter.create_primitive(kind, name=name, size=2.0)
        assert res.success, f"{kind}: {res.error}"
        assert res.data["vertex_count"] > 8 and res.data["face_count"] > 8, (kind, res.data)
    cyl = dims("Cyl")
    assert near(cyl[0], 2.0, 0.05) and near(cyl[1], 2.0, 0.05) and near(cyl[2], 2.0, 0.05), cyl
    cone = bpy.data.objects["Cone"].data
    top = max(v.co.z for v in cone.vertices)
    assert sum(1 for v in cone.vertices if near(v.co.z, top, 1e-4)) == 1, "cone apex must be a single vertex"
    ring = dims("Ring")
    assert near(ring[0], 1.4 + 0.6, 0.06) and near(ring[2], 0.6, 0.05), ring
    bad = adapter.create_primitive("DONUT")
    assert not bad.success and bad.error.type == "INVALID_PRIMITIVE_TYPE"
    print("[PASS] Test 1")


def test_create_mesh():
    print("Test 2: create_mesh...")
    clean_scene()
    adapter = BlenderAdapter()
    verts = [[0, 0, 0], [2, 0, 0], [2, 2, 0], [0, 2, 0], [1, 1, 3]]
    faces = [[0, 3, 2, 1], [0, 1, 4], [1, 2, 4], [2, 3, 4], [3, 0, 4]]
    res = adapter.create_mesh(name="Pyramid", vertices=verts, faces=faces, location=[5, 0, 0])
    assert res.success, res.error
    d = res.data
    assert d["vertex_count"] == 5 and d["face_count"] == 5 and d["triangle_count"] == 6, d
    assert near(d["dimensions"][2], 3.0) and d["location"] == [5.0, 0.0, 0.0], d
    obj = bpy.data.objects["Pyramid"]
    assert all(p.normal.z <= 1.0 for p in obj.data.polygons)
    # outward normals: the base faces down, the sides face away from the centre
    base = obj.data.polygons[0]
    assert base.normal.z < -0.9, base.normal
    for verts_bad, faces_bad, why in (
        ([[0, 0, 0]] * 3, [[0, 1, 5]], "index"),
        ([[0, 0, 0]] * 3, [[0, 0, 1]], "repeat"),
        ([[0, 0]] * 3, [[0, 1, 2]], "vec"),
        ([[0, 0, float("nan")]] * 3, [[0, 1, 2]], "nan"),
        ([[0, 0, 0]] * 3, [[0, 1]], "short"),
        ([], [[0, 1, 2]], "empty"),
    ):
        r = adapter.create_mesh(vertices=verts_bad, faces=faces_bad)
        assert not r.success and r.error.type == "INVALID_ARGUMENT", (why, r)
    big = adapter.create_mesh(vertices=[[0, 0, 0]] * 20001, faces=[[0, 1, 2]])
    assert not big.success and "Too large" in big.error.message
    before = len(bpy.data.objects)
    push_undo_step("before undo test")
    ok = adapter.create_mesh(name="UndoMe", vertices=verts, faces=faces)
    assert ok.success and len(bpy.data.objects) == before + 1
    perform_undo()
    assert "UndoMe" not in bpy.data.objects, "create_mesh must be one Ctrl+Z step"
    print("[PASS] Test 2")


def test_mesh_edit():
    print("Test 3: mesh_edit...")
    clean_scene()
    adapter = BlenderAdapter()
    adapter.create_primitive("CUBE", name="Box", size=2.0)
    v0 = len(bpy.data.objects["Box"].data.vertices)
    top = {"direction": "+Z", "threshold": 0.9}
    r = adapter.mesh_edit(object_name="Box", operation="EXTRUDE_FACES", faces=top, distance=1.0)
    assert r.success, r.error
    assert near(dims("Box")[2], 3.0), dims("Box")
    assert r.data["elements_affected"] == 1
    r = adapter.mesh_edit(object_name="Box", operation="INSET_FACES", faces=top, thickness=0.2, depth=-0.1)
    assert r.success and r.data["vertex_count"] > v0 + 4, r
    r = adapter.mesh_edit(object_name="Box", operation="BEVEL_EDGES", width=0.05, segments=2, sharp_angle=60)
    assert r.success and r.data["vertex_count"] > 20, r
    r = adapter.mesh_edit(object_name="Box", operation="SUBDIVIDE", cuts=1)
    assert r.success
    r = adapter.mesh_edit(object_name="Box", operation="TRIANGULATE")
    assert r.success and r.data["triangle_count"] == r.data["face_count"], r
    r = adapter.mesh_edit(object_name="Box", operation="RECALC_NORMALS")
    assert r.success
    r = adapter.mesh_edit(object_name="Box", operation="MERGE_BY_DISTANCE", merge_distance=0.001)
    assert r.success
    # taper a cylinder: top ring narrower than bottom
    adapter.create_primitive("CYLINDER", name="Stack", size=2.0)
    r = adapter.mesh_edit(object_name="Stack", operation="SCALE_TO_HEIGHT_TAPER", top_scale=0.5)
    assert r.success, r.error
    mesh = bpy.data.objects["Stack"].data
    hi = max(v.co.z for v in mesh.vertices)
    lo = min(v.co.z for v in mesh.vertices)
    top_r = max(math.hypot(v.co.x, v.co.y) for v in mesh.vertices if near(v.co.z, hi, 1e-3))
    bot_r = max(math.hypot(v.co.x, v.co.y) for v in mesh.vertices if near(v.co.z, lo, 1e-3))
    assert near(top_r / bot_r, 0.5, 0.02), (top_r, bot_r)
    # errors
    assert adapter.mesh_edit(object_name="Nope", operation="SUBDIVIDE").error.type == "INVALID_ARGUMENT"
    assert not adapter.mesh_edit(object_name="Box", operation="EXPLODE").success
    assert not adapter.mesh_edit(object_name="Box", operation="EXTRUDE_FACES", faces={"direction": "+Q"}).success
    fresh = BlenderAdapter()
    fresh.create_primitive("PLANE", name="Flat", size=2.0)
    none = fresh.mesh_edit(object_name="Flat", operation="EXTRUDE_FACES", faces={"direction": "-Z", "threshold": 0.99})
    assert not none.success and "No face matches" in none.error.message, none
    assert not fresh.mesh_edit(object_name="Flat", operation="SUBDIVIDE", cuts=9).success
    print("[PASS] Test 3")


def test_join_parent_transform_origin():
    print("Test 4: join, parent, apply transform, set origin...")
    clean_scene()
    adapter = BlenderAdapter()
    adapter.create_primitive("CUBE", name="A", size=1.0, location=[0, 0, 0])
    adapter.create_primitive("CUBE", name="B", size=1.0, location=[3, 0, 0])
    adapter.create_primitive("SPHERE", name="C", size=1.0, location=[6, 0, 0])
    total = sum(len(bpy.data.objects[n].data.vertices) for n in "ABC")
    res = adapter.join_objects(object_names=["A", "B", "C"], target_name="A", new_name="Combined")
    assert res.success, res.error
    assert "Combined" in bpy.data.objects and "B" not in bpy.data.objects and "C" not in bpy.data.objects
    assert res.data["vertex_count"] == total, (res.data["vertex_count"], total)
    assert near(res.data["dimensions"][0], 7.0, 0.05), res.data["dimensions"]
    assert not adapter.join_objects(object_names=["Combined"], target_name="Combined").success

    adapter.create_primitive("CUBE", name="Body", size=1.0)
    adapter.create_primitive("CUBE", name="Turret", size=0.5, location=[0, 0, 2])
    p = adapter.parent_object(child_name="Turret", parent_name="Body")
    assert p.success and bpy.data.objects["Turret"].parent.name == "Body"
    assert near(bpy.data.objects["Turret"].matrix_world.translation.z, 2.0), "world position must be kept"
    assert not adapter.parent_object(child_name="Body", parent_name="Turret").success, "parent loop must be refused"
    assert not adapter.parent_object(child_name="Body", parent_name="Body").success
    un = adapter.parent_object(child_name="Turret", parent_name="NONE")
    assert un.success and bpy.data.objects["Turret"].parent is None
    assert near(bpy.data.objects["Turret"].matrix_world.translation.z, 2.0)

    adapter.create_primitive("CUBE", name="Scaled", size=1.0, scale=[1, 1, 3], location=[0, 5, 0])
    before = dims("Scaled")
    ap = adapter.apply_transform(object_name="Scaled")
    assert ap.success, ap.error
    obj = bpy.data.objects["Scaled"]
    assert list(obj.scale) == [1.0, 1.0, 1.0]
    assert all(near(a, b) for a, b in zip(dims("Scaled"), before)), (dims("Scaled"), before)
    assert near(obj.location.y, 5.0), "location is kept unless requested"

    adapter.create_primitive("CUBE", name="Prop", size=2.0, location=[4, 4, 1])
    world_min_before = min((bpy.data.objects["Prop"].matrix_world @ v.co).z for v in bpy.data.objects["Prop"].data.vertices)
    so = adapter.set_origin(object_name="Prop", mode="BOTTOM_CENTER")
    assert so.success, so.error
    prop = bpy.data.objects["Prop"]
    world_min_after = min((prop.matrix_world @ v.co).z for v in prop.data.vertices)
    assert near(world_min_before, world_min_after), "geometry must not move in the world"
    assert near(prop.location.z, world_min_after), (prop.location.z, world_min_after)
    assert near(min(v.co.z for v in prop.data.vertices), 0.0)
    assert not adapter.set_origin(object_name="Prop", mode="MIDDLE").success
    print("[PASS] Test 4")


def test_export_gltf():
    print("Test 5: export_gltf writes a real .glb...")
    clean_scene()
    adapter = BlenderAdapter()
    out_dir = tempfile.mkdtemp(prefix="bc_glb_")
    adapter.export_dir = out_dir
    adapter.create_primitive("CUBE", name="Crate", size=1.0)
    adapter.mesh_edit(object_name="Crate", operation="BEVEL_EDGES", width=0.05, segments=2)
    adapter.create_primitive("CYLINDER", name="Barrel", size=1.0, location=[2, 0, 0])
    mat = adapter.set_material(object_name="Crate", material_name="CrateWood", base_color=[0.6, 0.4, 0.2, 1.0], roughness=0.8)
    assert mat.success, mat.error
    res = adapter.export_gltf(object_names=["Crate", "Barrel"], filename="props")
    assert res.success, res.error
    path = res.data["path"]
    assert path.startswith(out_dir) and path.endswith("props.glb") and os.path.exists(path)
    with open(path, "rb") as fh:
        assert fh.read(4) == b"glTF", "not a binary glTF"
    assert res.data["bytes"] > 500 and res.data["triangle_count"] > 12, res.data
    assert set(res.data["objects"]) == {"Crate", "Barrel"}
    # selection is restored (nothing selected before, nothing after)
    assert not any(o.select_get() for o in bpy.context.view_layer.objects)
    for bad in ("../evil", "a/b", "sub\\dir", ".hidden", "", "x" * 200):
        r = adapter.export_gltf(object_names=["Crate"], filename=bad)
        assert not r.success and r.error.type == "INVALID_ARGUMENT", (bad, r)
    assert not adapter.export_gltf(object_names=["Missing"], filename="x").success
    assert not adapter.export_gltf(object_names=[], filename="x").success
    assert sorted(os.listdir(out_dir)) == ["props.glb"], "only the requested file may be written"
    print("[PASS] Test 5")


def test_crate_acceptance():
    print("Test 6: build a game crate the way an agent would...")
    clean_scene()
    adapter = BlenderAdapter()
    adapter.export_dir = tempfile.mkdtemp(prefix="bc_crate_")
    adapter.create_primitive("CUBE", name="Crate", size=1.0)
    for step in (
        dict(operation="INSET_FACES", thickness=0.12, depth=0.0),
        dict(operation="EXTRUDE_FACES", distance=-0.04),
        dict(operation="BEVEL_EDGES", width=0.02, segments=1, sharp_angle=30),
        dict(operation="TRIANGULATE"),
    ):
        r = adapter.mesh_edit(object_name="Crate", **step)
        assert r.success, (step, r.error)
    assert adapter.set_origin(object_name="Crate", mode="BOTTOM_CENTER").success
    res = adapter.export_gltf(object_names=["Crate"], filename="crate")
    assert res.success and res.data["triangle_count"] < 3000 and "warning" not in res.data, res.data
    print(f"[PASS] Test 6: crate exported with {res.data['triangle_count']} triangles")


def test_registry_and_thread_safety():
    print("Test 7: registration, risk levels and thread safety...")
    registry = ToolRegistry()
    registry.register(CreateMeshTool())
    registry.register(MeshEditTool())
    assert registry.get("create_mesh").risk_level.value == "LOW"
    adapter = BlenderAdapter()
    caught = []

    def worker():
        try:
            adapter.create_mesh(vertices=[[0, 0, 0], [1, 0, 0], [0, 1, 0]], faces=[[0, 1, 2]])
        except ThreadSafetyViolationError:
            caught.append(True)

    t = threading.Thread(target=worker)
    t.start()
    t.join()
    assert caught == [True], "modeling tools must refuse background threads"
    print("[PASS] Test 7")


def test_shape_modifiers():
    print("Test 8: add_shape_modifier...")
    clean_scene()
    adapter = BlenderAdapter()
    adapter.create_primitive("CUBE", name="Half", size=1.0, location=[0.5, 0, 0])
    adapter.apply_transform(object_name="Half", location=True)
    r = adapter.add_shape_modifier(name="Half", modifier_type="MIRROR", axes=["X"])
    assert r.success, r.error
    assert r.data["axes"] == ["X"] and r.data["evaluated_triangle_count"] >= 12, r.data
    adapter.create_primitive("CUBE", name="Post", size=1.0, location=[0, 5, 0])
    r = adapter.add_shape_modifier(name="Post", modifier_type="ARRAY", count=4, relative_offset=[1.5, 0, 0])
    assert r.success and r.data["count"] == 4 and r.data["evaluated_triangle_count"] == 4 * 12, r.data
    adapter.create_primitive("PLANE", name="Slab", size=2.0, location=[0, 10, 0])
    r = adapter.add_shape_modifier(name="Slab", modifier_type="SOLIDIFY", thickness=0.1)
    assert r.success and r.data["thickness"] == 0.1
    adapter.create_primitive("ICOSPHERE", name="Rock", size=1.0, location=[0, 15, 0])
    before = bpy.data.objects["Rock"].data
    before.calc_loop_triangles()
    tris_before = len(before.loop_triangles)
    r = adapter.add_shape_modifier(name="Rock", modifier_type="DECIMATE", ratio=0.3)
    assert r.success and r.data["evaluated_triangle_count"] < tris_before * 0.6, (r.data, tris_before)
    assert adapter.add_shape_modifier(name="Rock", modifier_type="TRIANGULATE").success
    for bad in (dict(name="Half", modifier_type="WIGGLE"), dict(name="Half", modifier_type="MIRROR", axes=["W"]),
                dict(name="Post", modifier_type="ARRAY", count=1), dict(name="Slab", modifier_type="SOLIDIFY", thickness=0),
                dict(name="Rock", modifier_type="DECIMATE", ratio=0.0), dict(name="Nope", modifier_type="MIRROR")):
        res = adapter.add_shape_modifier(**bad)
        assert not res.success and res.error.type == "INVALID_ARGUMENT", (bad, res)
    assert [m.type for m in bpy.data.objects["Post"].modifiers] == ["ARRAY"], "failed calls must not leave modifiers behind"
    print("[PASS] Test 8")


def main():
    test_new_primitives()
    test_create_mesh()
    test_mesh_edit()
    test_join_parent_transform_origin()
    test_export_gltf()
    test_crate_acceptance()
    test_registry_and_thread_safety()
    test_shape_modifiers()
    print("\nALL MODELING TOOL INTEGRATION TESTS PASSED")


if __name__ == "__main__":
    main()
