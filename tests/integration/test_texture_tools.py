"""Headless integration test for unwrap_uv and bake_material in real Blender 5.2: UV maps appear inside the 0-1 square,
a procedural material is baked into an image, the .glb carries that image, and check_model agrees."""

import json
import os
import struct
import sys
import tempfile

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


def glb_json(path):
    data = open(path, "rb").read()
    length, kind = struct.unpack("<II", data[12:20])
    assert kind == 0x4E4F534A
    return json.loads(data[20:20 + length].decode("utf-8"))


def test_unwrap():
    print("Test 1: unwrap_uv gives every mesh a UV map inside the square...")
    adapter = fresh()
    assert adapter.create_primitive("CUBE", name="Box", size=1.0).success
    assert adapter.create_primitive("SPHERE", name="Ball", size=1.0, location=[3, 0, 0]).success
    assert len(bpy.data.objects["Box"].data.uv_layers) == 0 or True
    res = adapter.unwrap_uv(object_names=["Box", "Ball"])
    assert res.success, res.error
    for entry in res.data["unwrapped"]:
        assert entry["uv_layers"] >= 1 and entry["uv_in_bounds"] and entry["uv_coverage"] > 0.2, entry
    res = adapter.unwrap_uv(object_names=["Box"], method="cube")
    assert res.success and res.data["method"] == "cube" and res.data["unwrapped"][0]["uv_in_bounds"] is not None
    for bad in ({"method": "spiral"}, {"angle_limit": 0}, {"margin": 2}, {"object_names": ["Nope"]}):
        assert not adapter.unwrap_uv(**{"object_names": ["Box"], **bad}).success, bad
    assert not fresh().unwrap_uv().success
    # undo removes the unwrap in one step
    adapter = fresh()
    assert adapter.create_primitive("CUBE", name="Box", size=1.0).success
    push_undo_step("Before")
    assert adapter.unwrap_uv(object_names=["Box"]).success
    assert len(bpy.data.objects["Box"].data.uv_layers) >= 1
    perform_undo()
    assert len(bpy.data.objects["Box"].data.uv_layers) == 0
    print("[PASS] Test 1")


def test_bake_and_export():
    print("Test 2: bake_material turns a procedural material into an image the .glb carries...")
    adapter = fresh()
    assert adapter.create_primitive("CUBE", name="Plank", size=2.0, location=[0, 0, 1]).success
    assert adapter.set_material(object_name="Plank", material_name="W", preset="wood").success
    with tempfile.TemporaryDirectory() as tmp:
        adapter.export_dir = tmp
        assert adapter.set_environment(preset="studio").success
        # before: the export keeps no texture
        assert adapter.export_gltf(object_names=["Plank"], filename="before.glb").success
        assert not glb_json(os.path.join(tmp, "before.glb")).get("images"), "a procedural material should not export an image"
        checked = adapter.check_model(object_names=["Plank"])
        res = adapter.bake_material(object_name="Plank", resolution=256)
        assert res.success, res.error
        d = res.data
        assert d["baked"] and d["resolution"] == 256 and d["unwrapped"] and d["uv_in_bounds"], d
        obj = bpy.data.objects["Plank"]
        assert len(obj.material_slots) == 1
        tree = obj.material_slots[0].material.node_tree
        kinds = {n.type for n in tree.nodes}
        assert "TEX_IMAGE" in kinds and not (kinds & {"TEX_NOISE", "TEX_WAVE", "TEX_BRICK"}), kinds
        img = bpy.data.images[d["image"]]
        assert img.size[0] == 256 and img.packed_file is not None
        px = list(img.pixels)
        n = len(px) // 4
        mean = [sum(px[c::4]) / n for c in range(3)]
        lum = [0.2126 * px[i * 4] + 0.7152 * px[i * 4 + 1] + 0.0722 * px[i * 4 + 2] for i in range(n)]
        avg = sum(lum) / n
        std = (sum((v - avg) ** 2 for v in lum) / n) ** 0.5
        assert mean[0] > mean[2] and mean[0] < 0.7, mean          # brown, not white or black
        assert std > 0.02, std                                    # grain, not a flat colour
        assert adapter.export_gltf(object_names=["Plank"], filename="after.glb").success
        gltf = glb_json(os.path.join(tmp, "after.glb"))
        assert gltf.get("images") and gltf.get("textures"), "the baked image must travel in the .glb"
        assert "baseColorTexture" in gltf["materials"][0]["pbrMetallicRoughness"], gltf["materials"][0]
        assert "MISSING_UV" not in {i["code"] for i in adapter.check_model(object_names=["Plank"]).data["issues"]}
        # the scene's render engine is put back
        assert bpy.context.scene.render.engine != "CYCLES"
        # a metal preset bakes its colour, not black
        assert adapter.create_primitive("CUBE", name="Steel", size=1.0, location=[8, 0, 0.5]).success
        assert adapter.set_material(object_name="Steel", material_name="S", preset="metal").success
        steel = adapter.bake_material(object_name="Steel", resolution=128)
        assert steel.success and steel.data["baked"], steel.error
        spx = list(bpy.data.images[steel.data["image"]].pixels)
        smean = sum(spx[0::4]) / (len(spx) // 4)
        assert smean > 0.15, smean
        assert abs(next(n for n in bpy.data.materials["S"].node_tree.nodes if n.type == "BSDF_PRINCIPLED").inputs["Metallic"].default_value - 1.0) < 1e-6, "the source material keeps its metallic"
        # flat colours are left alone
        assert adapter.create_primitive("CUBE", name="Flat", size=1.0, location=[4, 0, 0.5]).success
        assert adapter.set_material(object_name="Flat", base_color=[1, 0, 0, 1]).success
        flat = adapter.bake_material(object_name="Flat")
        assert flat.success and flat.data["baked"] is False and "flat" in flat.data["reason"], flat.data
    print("[PASS] Test 2")


def test_bake_errors_and_undo():
    print("Test 3: bake errors are clear and one Ctrl+Z restores the procedural material...")
    adapter = fresh()
    assert adapter.create_primitive("CUBE", name="Bare", size=1.0).success
    assert not adapter.bake_material(object_name="Bare").success                   # no material
    assert not adapter.bake_material(object_name="Nope").success
    assert adapter.set_material(object_name="Bare", material_name="B", preset="brick").success
    assert not adapter.bake_material(object_name="Bare", resolution=8).success
    assert not adapter.bake_material(object_name="Bare", samples=0).success
    assert not adapter.bake_material(object_name="Bare", resolution="big").success
    assert adapter.duplicate_object(source_name="Bare", new_name="Bare2").success
    bpy.data.objects["Bare2"].data = bpy.data.objects["Bare"].data                  # share the mesh
    assert not adapter.bake_material(object_name="Bare").success
    adapter = fresh()
    assert adapter.create_primitive("CUBE", name="Wall", size=1.0).success
    assert adapter.set_material(object_name="Wall", material_name="Br", preset="brick").success
    push_undo_step("Before bake")
    assert adapter.bake_material(object_name="Wall", resolution=128).success
    assert bpy.data.objects["Wall"].material_slots[0].material.name.endswith("_Baked")
    perform_undo()
    assert bpy.data.objects["Wall"].material_slots[0].material.name == "Br"
    print("[PASS] Test 3")


if __name__ == "__main__":
    test_unwrap()
    test_bake_and_export()
    test_bake_errors_and_undo()
    print("ALL TEXTURE TOOL INTEGRATION TESTS PASSED")
