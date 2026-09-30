"""Headless integration test for polish_model in real Blender 5.2: bevels, smooth shading with sharp edges, limits, undo."""

import math
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
    assert adapter.create_primitive("CUBE", name="Box", size=1.0, location=[0, 0, 0.5], scale=[2, 1, 1]).success
    assert adapter.create_primitive("CYLINDER", name="Post", size=1.0, location=[3, 0, 0.5]).success
    push_undo_step("Baseline")
    return adapter


def test_polish():
    print("Test 1: polish_model bevels the corners and shades smooth with sharp edges...")
    adapter = fresh()
    box = bpy.data.objects["Box"]
    before = len(box.data.polygons)
    dims_before = tuple(box.dimensions)
    res = adapter.polish_model(object_names=["Box", "Post"])
    assert res.success, res.error
    report = {r["object"]: r for r in res.data["polished"]}
    assert report["Box"]["faces"][0] == before and report["Box"]["faces"][1] > before * 3, report["Box"]
    assert report["Box"]["bevelled_edges"] == 12 and report["Box"]["bevel_m"] > 0.002, report["Box"]
    assert len(box.data.polygons) == report["Box"]["faces"][1]
    assert all(p.use_smooth for p in box.data.polygons), "faces must be smooth"
    assert report["Box"]["sharp_edges"] > 0
    # the outline does not change (the bevel only rounds the corners)
    assert all(abs(a - b) < 1e-3 for a, b in zip(box.dimensions, dims_before)), (box.dimensions, dims_before)
    # explicit width and segments
    adapter2 = fresh()
    res = adapter2.polish_model(object_names=["Box"], bevel=0.05, segments=3)
    assert res.success and abs(res.data["polished"][0]["bevel_m"] - 0.05) < 1e-6
    more = res.data["polished"][0]["faces"][1]
    adapter3 = fresh()
    default = adapter3.polish_model(object_names=["Box"], segments=1).data["polished"][0]["faces"][1]
    assert more > default, "more segments make more faces"
    # undo brings the plain mesh back
    adapter4 = fresh()
    n = len(bpy.data.objects["Box"].data.polygons)
    assert adapter4.polish_model(object_names=["Box"]).success
    assert perform_undo()
    assert len(bpy.data.objects["Box"].data.polygons) == n, "polish must be one undo step"
    print("[PASS] Test 1")


def test_errors():
    print("Test 2: bad input is refused...")
    adapter = fresh()
    for bad in (dict(object_names=[]), dict(object_names=["Nope"]), dict(object_names=["Box"], segments=9),
                dict(object_names=["Box"], bevel=0), dict(object_names=["Box"], smooth_angle=1),
                dict(object_names=["Box"], bevel="wide")):
        res = adapter.polish_model(**bad)
        assert not res.success and res.error.type == "INVALID_ARGUMENT", (bad, res)
    # models wrap lists: {"item": [...]} and a bare name work
    assert adapter.polish_model(object_names={"item": ["Box"]}).success
    assert fresh().polish_model(object_names="Post").success
    print("[PASS] Test 2")


if __name__ == "__main__":
    test_polish()
    test_errors()
    print("\nALL POLISH TOOL INTEGRATION TESTS PASSED")
