"""Headless integration test for create_prop in real Blender 5.2: every kind builds a well-proportioned object standing on
the ground, colours can be overridden, humanoids are rig-ready and animate, limits and undo."""

import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

from adapter.blender_adapter import BlenderAdapter  # noqa: E402
from adapter.mutators.prop_mutator import BUILDERS, KINDS  # noqa: E402
from adapter.mutators.undo_manager import perform_undo, push_undo_step  # noqa: E402
from core.prop_kinds import KIND_INFO  # noqa: E402


def fresh():
    bpy.ops.wm.read_homefile(use_empty=True)
    bpy.context.preferences.edit.use_global_undo = True
    adapter = BlenderAdapter()
    push_undo_step("Baseline")
    return adapter


def box(names):
    pts = []
    for n in names:
        o = bpy.data.objects[n]
        pts += [o.matrix_world @ Vector(c) for c in o.bound_box]
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    return lo, hi


def test_every_kind():
    print("Test 1: every kind builds a proportioned object on the ground...")
    assert set(BUILDERS) == set(KIND_INFO) == set(KINDS)
    for kind, (default_h, about, rigged) in KIND_INFO.items():
        adapter = fresh()
        res = adapter.create_prop(kind=kind)
        assert res.success, (kind, res.error)
        d = res.data
        lo, hi = box(d["objects"])
        # every recipe stands on the ground and is roughly as tall as asked (fences and cars are wider than tall)
        assert abs(lo.z) < 0.02 * max(default_h, 1) + 1e-3, (kind, lo.z)
        assert 0.6 * default_h < (hi.z - lo.z) < 1.45 * default_h + 0.15, (kind, hi.z - lo.z, default_h)
        assert d["triangle_count"] < 6000, (kind, d["triangle_count"])
        assert d["rigged_ready"] is rigged and d["parts"] >= 3
        assert len(d["objects"]) == (d["parts"] if rigged else 1), (kind, d["objects"])
        if not rigged:
            obj = bpy.data.objects[d["objects"][0]]
            assert obj.name == kind and len(obj.material_slots) >= 1 and all(p.use_smooth for p in obj.data.polygons)
    print("[PASS] Test 1")


def test_options():
    print("Test 2: size, location, colours, seed and undo...")
    adapter = fresh()
    res = adapter.create_prop(kind="house", name="Cottage", size=6.0, location=[10, 5, 0],
                              colors={"roof": [0.1, 0.2, 0.8]})
    assert res.success, res.error
    d = res.data
    assert d["objects"] == ["Cottage"] and abs(d["height_m"] - 6.0) < 1.6, d
    lo, hi = box(["Cottage"])
    assert abs((lo.x + hi.x) / 2 - 10) < 0.5 and abs(lo.z) < 0.05, (lo, hi)
    roof = [m for m in bpy.data.objects["Cottage"].data.materials if m.name.endswith("_roof")][0]
    c = next(n for n in roof.node_tree.nodes if n.bl_idname == "ShaderNodeBsdfPrincipled").inputs["Base Color"].default_value
    assert abs(c[2] - 0.8) < 1e-3 and abs(c[0] - 0.1) < 1e-3, tuple(c)
    assert "roof" in d["colors"] and "wall" in d["colors"]
    a = adapter.create_prop(kind="rock", seed=1).data
    fresh_adapter = fresh()
    b = fresh_adapter.create_prop(kind="rock", seed=99).data
    c2 = fresh().create_prop(kind="rock", seed=1).data
    assert a["width_m"] == c2["width_m"], "same seed, same rock"
    assert a["width_m"] != b["width_m"], "another seed, another rock"
    adapter = fresh()
    assert adapter.create_prop(kind="crate").success
    n = len(bpy.data.objects)
    assert adapter.create_prop(kind="barrel").success and len(bpy.data.objects) == n + 1
    assert perform_undo() and len(bpy.data.objects) == n, "one undo step removes a prop"
    r = fresh().create_prop(kind="crate", polish=False).data
    assert r["triangle_count"] == 12 * 6 or r["triangle_count"] >= 12, r
    print("[PASS] Test 2")


def test_humanoid_is_rig_ready():
    print("Test 3: a humanoid rigs and acts...")
    adapter = fresh()
    res = adapter.create_prop(kind="humanoid", size=1.8, location=[2, 0, 0])
    assert res.success, res.error
    names = res.data["objects"]
    assert {"Head", "Torso", "ArmL", "ForearmL", "LegR", "ShinR", "EyeL", "Mouth"} <= {n.split(".")[0] for n in names}, names
    rig = adapter.rig_character(name="Hero", object_names=names)
    assert rig.success, rig.error
    roles = rig.data["roles"]
    assert {"head", "torso", "arm_l", "arm_r", "forearm_l", "forearm_r", "leg_l", "leg_r", "shin_l", "shin_r", "eye_l", "eye_r", "mouth"} <= set(roles), roles
    assert abs(rig.data["height"] - 1.8) < 0.25, rig.data["height"]
    assert set(rig.data["attached"].values()) <= set(roles), rig.data["attached"]
    seq = adapter.animate_sequence(rig="Hero_Rig", fps=12, segments=[{"preset": "walk", "duration": 1.0, "distance": 1.5},
                                                                     {"preset": "talk", "text": "Merhaba!"}])
    assert seq.success, seq.error
    # a second person and a robot in the same scene do not collide in name or role detection
    assert adapter.create_prop(kind="robot", location=[-2, 0, 0]).success
    robot_parts = [o.name for o in bpy.data.objects if o.type == "MESH" and o.location.x < -1 and o.name not in names]
    r2 = adapter.rig_character(name="Bot", object_names=robot_parts)
    assert r2.success and "mouth" in r2.data["roles"], r2
    print("[PASS] Test 3")


def test_errors():
    print("Test 4: bad input is refused...")
    adapter = fresh()
    for bad in (dict(kind="spaceship"), dict(kind="crate", size=0), dict(kind="crate", size="tall"), dict(kind="crate", size=9999),
                dict(kind="crate", location=[1, 2]), dict(kind="crate", colors={"nope": [1, 0, 0]}),
                dict(kind="crate", colors={"wood": [1, 0]}), dict(kind="crate", colors="red"), dict(kind="crate", seed="x")):
        res = adapter.create_prop(**bad)
        assert not res.success and res.error.type == "INVALID_ARGUMENT", (bad, res)
    # weak models wrap things
    assert adapter.create_prop(kind="crate", location={"item": [1, 1, 0]}, colors={"item": {"wood": {"item": [0.5, 0.4, 0.2]}}}).success
    print("[PASS] Test 4")


if __name__ == "__main__":
    test_every_kind()
    test_options()
    test_humanoid_is_rig_ready()
    test_errors()
    print("\nALL PROP TOOL INTEGRATION TESTS PASSED")
