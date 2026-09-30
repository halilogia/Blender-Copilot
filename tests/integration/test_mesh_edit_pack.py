"""Headless integration test for the deeper mesh_edit operations in real Blender 5.2: flip / delete faces, loop cuts, knife
plane, dissolve, bridge, separate, apply modifiers, and the extra face selectors."""

import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import bpy  # noqa: E402

from adapter.blender_adapter import BlenderAdapter  # noqa: E402
from adapter.mutators.undo_manager import perform_undo, push_undo_step  # noqa: E402


def fresh():
    bpy.ops.wm.read_homefile(use_empty=True)
    bpy.context.preferences.edit.use_global_undo = True
    adapter = BlenderAdapter()
    push_undo_step("Baseline")
    return adapter


def cube(adapter, name="C", size=1.0, **kw):
    assert adapter.create_primitive("CUBE", name=name, size=size, **kw).success
    assert adapter.set_material(object_name=name, material_name="M_" + name, base_color=[0.5, 0.5, 0.5, 1]).success
    return bpy.data.objects[name]


def codes(adapter, name):
    res = adapter.check_model(object_names=[name], max_triangles=100000)
    assert res.success, res.error
    return {i["code"] for i in res.data["issues"]}


def edit(adapter, name, op, **kw):
    res = adapter.mesh_edit(object_name=name, operation=op, **kw)
    assert res.success, (op, kw, res.error)
    return res.data


def test_flip_delete_cut():
    print("Test 1: flip and delete faces, loop cut, knife plane, dissolve...")
    adapter = fresh()
    obj = cube(adapter, size=2.0)
    edit(adapter, "C", "FLIP_NORMALS")
    assert "INVERTED_NORMALS" in codes(adapter, "C")
    edit(adapter, "C", "RECALC_NORMALS")
    assert "INVERTED_NORMALS" not in codes(adapter, "C")

    data = edit(adapter, "C", "DELETE_FACES", faces={"direction": "-Z"})
    assert data["face_count"] == 5, data
    assert not adapter.mesh_edit(object_name="C", operation="DELETE_FACES").success     # would delete everything

    adapter = fresh()
    obj = cube(adapter, size=2.0)
    data = edit(adapter, "C", "LOOP_CUT", axis="Z", cuts=2)
    assert data["vertex_count"] == 16, data
    zs = sorted({round(v.co.z, 3) for v in obj.data.vertices})
    assert len(zs) == 4 and abs(zs[1] + 1 / 3) < 0.01 and abs(zs[2] - 1 / 3) < 0.01, zs
    data = edit(adapter, "C", "DISSOLVE_PLANAR")
    assert data["vertex_count"] == 8 and data["face_count"] == 6, data

    adapter = fresh()
    obj = cube(adapter, size=2.0)
    data = edit(adapter, "C", "KNIFE_PLANE", axis="Z", position=0.0, keep="above")
    zs = [v.co.z for v in obj.data.vertices]
    assert min(zs) > -1e-4 and abs(max(zs) - 1.0) < 1e-4, (min(zs), max(zs))
    found = codes(adapter, "C")
    assert not found & {"NON_MANIFOLD", "INVERTED_NORMALS"}, found             # capped and pointing outward
    edit(adapter, "C", "KNIFE_PLANE", axis="X", position=0.0, keep="below")
    assert max(v.co.x for v in obj.data.vertices) < 1e-4
    assert not codes(adapter, "C") & {"NON_MANIFOLD", "INVERTED_NORMALS"}
    print("[PASS] Test 1")


def test_bridge_separate_apply():
    print("Test 2: bridge two faces, separate, apply modifiers, selectors, undo...")
    adapter = fresh()
    cube(adapter, "A")
    cube(adapter, "B", location=[3, 0, 0])
    assert adapter.join_objects(object_names=["B"], target_name="A").success
    obj = bpy.data.objects["A"]
    before = len(obj.data.polygons)
    data = edit(adapter, "A", "BRIDGE_FACES", faces={"direction": "+X", "near": [0.5, 0, 0]},
                faces_b={"direction": "-X", "near": [2.5, 0, 0]})
    assert data["face_count"] == before - 2 + 4, data
    found = codes(adapter, "A")
    assert not found & {"NON_MANIFOLD", "INVERTED_NORMALS"}, found
    # nearness picks one face among parallel ones
    same = adapter.mesh_edit(object_name="A", operation="BRIDGE_FACES", faces={"direction": "+X"}, faces_b={"direction": "+X"})
    assert not same.success
    assert not adapter.mesh_edit(object_name="A", operation="BRIDGE_FACES", faces={"direction": "+X"}).success

    adapter = fresh()
    cube(adapter, "A")
    cube(adapter, "B", location=[3, 0, 0])
    assert adapter.join_objects(object_names=["B"], target_name="A").success
    data = edit(adapter, "A", "SEPARATE")
    assert data["created_objects"] and len(bpy.data.objects["A"].data.vertices) == 8, data

    adapter = fresh()
    obj = cube(adapter, "Bev")
    assert adapter.add_modifier(name="Bev", modifier_type="BEVEL", width=0.1, segments=2).success
    assert len(obj.modifiers) == 1
    data = edit(adapter, "Bev", "APPLY_MODIFIERS")
    assert len(bpy.data.objects["Bev"].modifiers) == 0 and data["vertex_count"] > 8, data
    assert not adapter.mesh_edit(object_name="Bev", operation="APPLY_MODIFIERS").success   # nothing left to apply

    adapter = fresh()
    obj = cube(adapter, "Two")
    data = edit(adapter, "Two", "INSET_FACES", faces={"direction": "+Z"}, thickness=0.1)
    big = edit(adapter, "Two", "DELETE_FACES", faces={"direction": "+Z", "min_area": 0.5})
    assert big["face_count"] == data["face_count"] - 1, (big, data)           # only the big inner face went
    ring = edit(adapter, "Two", "DELETE_FACES", faces={"direction": "+Z", "max_area": 0.3})
    assert ring["face_count"] == big["face_count"] - 4, (ring, big)           # then the four small ring faces

    adapter = fresh()
    cube(adapter, "Mix")
    bpy.data.objects["Mix"].data.materials.append(bpy.data.materials.new("Second"))
    for poly in bpy.data.objects["Mix"].data.polygons[:2]:
        poly.material_index = 1
    data = edit(adapter, "Mix", "DELETE_FACES", faces={"material": "Second"})
    assert data["face_count"] == 4, data
    assert not adapter.mesh_edit(object_name="Mix", operation="DELETE_FACES", faces={"material": "Nope"}).success

    adapter = fresh()
    obj = cube(adapter, "Undo")
    push_undo_step("Before cut")
    edit(adapter, "Undo", "LOOP_CUT", axis="X")
    assert len(obj.data.vertices) > 8
    perform_undo()
    assert len(bpy.data.objects["Undo"].data.vertices) == 8
    print("[PASS] Test 2")


def test_errors():
    print("Test 3: clear errors...")
    adapter = fresh()
    cube(adapter, "E")
    for kw in ({"operation": "LOOP_CUT"}, {"operation": "LOOP_CUT", "axis": "W"}, {"operation": "LOOP_CUT", "axis": "X", "cuts": 99},
               {"operation": "KNIFE_PLANE", "axis": "X"}, {"operation": "KNIFE_PLANE", "axis": "X", "position": 0, "keep": "left"},
               {"operation": "DISSOLVE_PLANAR", "angle": 120}, {"operation": "SEPARATE", "by": "colour"},
               {"operation": "KNIFE_PLANE", "axis": "X", "position": 50, "keep": "above"}):
        assert not adapter.mesh_edit(object_name="E", **kw).success, kw
    print("[PASS] Test 3")


if __name__ == "__main__":
    test_flip_delete_cut()
    test_bridge_separate_apply()
    test_errors()
    print("ALL MESH EDIT PACK INTEGRATION TESTS PASSED")
