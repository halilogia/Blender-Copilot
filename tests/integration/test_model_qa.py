"""Headless integration test for check_model in real Blender 5.2: clean props pass, every kind of defect is found, and the
suggested fix makes it go away."""

import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import bmesh  # noqa: E402
import bpy  # noqa: E402

from adapter.blender_adapter import BlenderAdapter  # noqa: E402
from adapter.mutators.undo_manager import push_undo_step  # noqa: E402


def fresh():
    bpy.ops.wm.read_homefile(use_empty=True)
    bpy.context.preferences.edit.use_global_undo = True
    adapter = BlenderAdapter()
    push_undo_step("Baseline")
    return adapter


def codes(result):
    assert result.success, result.error
    return {i["code"] for i in result.data["issues"]}


def colored_cube(adapter, name, **kwargs):
    assert adapter.create_primitive("CUBE", name=name, size=1.0, **kwargs).success
    assert adapter.set_material(object_name=name, material_name="M_" + name, base_color=[0.5, 0.4, 0.3, 1]).success


def test_clean_props():
    print("Test 1: every ready-made prop passes the model check...")
    adapter = fresh()
    for kind in ("crate", "barrel", "tree_pine", "house", "car", "chair", "humanoid"):
        adapter = fresh()
        res = adapter.create_prop(kind=kind)
        assert res.success, (kind, res.error)
        check = adapter.check_model(object_names=res.data["objects"], max_triangles=6000)
        assert check.success and check.data["ok"], (kind, check.data["issues"])
    print("[PASS] Test 1")


def test_defects_and_fixes():
    print("Test 2: defects are found and the suggested tool fixes them...")
    adapter = fresh()

    colored_cube(adapter, "Sunk", location=[0, 0, -3])
    assert "BELOW_GROUND" in codes(adapter.check_model(object_names=["Sunk"]))
    assert not adapter.check_model(object_names=["Sunk"]).data["ok"]
    assert adapter.transform_object(name="Sunk", location=[0, 0, 0.5]).success
    assert "BELOW_GROUND" not in codes(adapter.check_model(object_names=["Sunk"]))

    colored_cube(adapter, "Flipped")
    bm = bmesh.new()
    bm.from_mesh(bpy.data.objects["Flipped"].data)
    bmesh.ops.reverse_faces(bm, faces=bm.faces)
    bm.to_mesh(bpy.data.objects["Flipped"].data)
    bm.free()
    check = adapter.check_model(object_names=["Flipped"])
    assert "INVERTED_NORMALS" in codes(check) and not check.data["ok"], check.data
    assert adapter.mesh_edit(object_name="Flipped", operation="RECALC_NORMALS").success
    assert "INVERTED_NORMALS" not in codes(adapter.check_model(object_names=["Flipped"]))

    colored_cube(adapter, "Doubled")
    bm = bmesh.new()
    bm.from_mesh(bpy.data.objects["Doubled"].data)
    bmesh.ops.duplicate(bm, geom=list(bm.verts) + list(bm.edges) + list(bm.faces))   # a second copy on top
    bm.to_mesh(bpy.data.objects["Doubled"].data)
    bm.free()
    check = adapter.check_model(object_names=["Doubled"])
    assert "DUPLICATE_VERTICES" in codes(check), check.data["issues"]
    assert adapter.mesh_edit(object_name="Doubled", operation="MERGE_BY_DISTANCE", merge_distance=0.0001).success
    assert "DUPLICATE_VERTICES" not in codes(adapter.check_model(object_names=["Doubled"]))

    colored_cube(adapter, "Stretched", scale=[2.0, 1.0, 1.0], location=[5, 0, 0.5])
    assert "UNAPPLIED_SCALE" in codes(adapter.check_model(object_names=["Stretched"]))
    assert adapter.apply_transform(object_name="Stretched").success
    assert "UNAPPLIED_SCALE" not in codes(adapter.check_model(object_names=["Stretched"]))

    assert adapter.create_primitive("CUBE", name="Grey", size=1.0, location=[8, 0, 0.5]).success
    check = adapter.check_model(object_names=["Grey"])
    assert "NO_MATERIAL" in codes(check) and check.data["ok"], check.data
    assert adapter.set_material(object_name="Grey", base_color=[1, 0, 0, 1]).success
    assert "NO_MATERIAL" not in codes(adapter.check_model(object_names=["Grey"]))
    print("[PASS] Test 2")


def test_budget_duplicates_and_errors():
    print("Test 3: triangle budget, two objects in one place, read only, errors...")
    adapter = fresh()
    res = adapter.create_prop(kind="house")
    objs = res.data["objects"]
    check = adapter.check_model(object_names=objs, max_triangles=100)
    assert "TOO_MANY_TRIANGLES" in codes(check) and check.data["triangles"] > 100
    assert check.data["heaviest"] and check.data["summary"]

    adapter = fresh()
    colored_cube(adapter, "Twin", location=[0, 0, 0.5])
    assert adapter.duplicate_object(source_name="Twin", new_name="Twin2", location=[0, 0, 0.5]).success
    check = adapter.check_model()
    assert "DUPLICATE_OBJECT" in codes(check), check.data["issues"]
    dup = [i for i in check.data["issues"] if i["code"] == "DUPLICATE_OBJECT"][0]
    assert set(dup["objects"]) == {"Twin", "Twin2"}

    before = sorted(o.name for o in bpy.data.objects)
    adapter.check_model()
    assert sorted(o.name for o in bpy.data.objects) == before, "check_model must not change the scene"

    assert not fresh().check_model().success                       # nothing to check
    adapter = fresh()
    colored_cube(adapter, "Solo", location=[0, 0, 0.5])
    assert not adapter.check_model(object_names=["Nope"]).success
    assert not adapter.check_model(object_names=["Solo"], max_triangles=5).success
    assert not adapter.check_model(object_names=["Solo"], max_triangles="lots").success
    print("[PASS] Test 3")


if __name__ == "__main__":
    test_clean_props()
    test_defects_and_fixes()
    test_budget_duplicates_and_errors()
    print("ALL MODEL QA INTEGRATION TESTS PASSED")
