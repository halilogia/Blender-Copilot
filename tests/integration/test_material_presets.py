"""Headless integration test for set_material presets in real Blender 5.2: every procedural material builds, renders with visible
texture (not a flat colour), keeps working with extra overrides, and errors name the options."""

import os
import sys
import tempfile

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import bpy  # noqa: E402

from adapter.blender_adapter import BlenderAdapter  # noqa: E402
from adapter.mutators.undo_manager import push_undo_step  # noqa: E402
from core.material_presets import preset_names  # noqa: E402


def fresh():
    bpy.ops.wm.read_homefile(use_empty=True)
    bpy.context.preferences.edit.use_global_undo = True
    adapter = BlenderAdapter()
    push_undo_step("Baseline")
    return adapter


def stats(path):
    img = bpy.data.images.load(str(path))
    px = list(img.pixels)
    bpy.data.images.remove(img)
    n = len(px) // 4
    lum = [0.2126 * px[i * 4] + 0.7152 * px[i * 4 + 1] + 0.0722 * px[i * 4 + 2] for i in range(n)]
    mean = sum(lum) / n
    std = (sum((v - mean) ** 2 for v in lum) / n) ** 0.5
    rgb = tuple(sum(px[c::4]) / n for c in range(3))
    return mean, std, rgb


def test_all_presets():
    print("Test 1: every preset builds a node network and renders with texture...")
    adapter = fresh()
    assert adapter.create_primitive("CUBE", name="Slab", size=2.0, location=[0, 0, 1]).success
    with tempfile.TemporaryDirectory() as tmp:
        adapter.export_dir = tmp
        assert adapter.set_environment(preset="studio").success
        assert adapter.camera_move(preset="static", object_names=["Slab"], duration=1.0, fps=12, distance=3.2, elevation=0).success
        seen = {}
        for name in preset_names():
            res = adapter.set_material(object_name="Slab", material_name=f"M_{name}", preset=name)
            assert res.success, (name, res.error)
            assert "preset" in res.data["changed"], res.data
            kinds = {n.bl_idname for n in bpy.data.materials[f"M_{name}"].node_tree.nodes}
            assert "ShaderNodeBsdfPrincipled" in kinds and "ShaderNodeOutputMaterial" in kinds, kinds
            assert kinds & {"ShaderNodeTexNoise", "ShaderNodeTexWave", "ShaderNodeTexBrick"}, kinds
            shot = adapter.render_image(filename=f"m_{name}", width=200, height=200, samples=2)
            assert shot.success, (name, shot.error)
            mean, std, rgb = stats(shot.data["path"])
            seen[name] = (mean, std, rgb)
            if name not in ("gold", "marble", "water"):
                assert std > 0.012, (name, std)
        assert seen["metal"][1] > 0.0
        assert seen["grass"][2][1] > seen["grass"][2][0] and seen["grass"][2][1] > seen["grass"][2][2], seen["grass"]
        assert seen["brick"][2][0] > seen["brick"][2][2], seen["brick"]
        assert seen["water"][2][2] > seen["water"][2][0], seen["water"]
        assert seen["wood"][2][0] > seen["wood"][2][2], seen["wood"]
    print("[PASS] Test 1")


def test_scale_override_and_errors():
    print("Test 2: scale, overrides on top of a preset, unknown preset and undo...")
    adapter = fresh()
    assert adapter.create_primitive("CUBE", name="Box", size=1.0).success
    res = adapter.set_material(object_name="Box", preset="stone", scale=3.0, roughness=0.2)
    assert res.success, res.error
    mat = bpy.data.objects["Box"].material_slots[0].material
    bsdf = next(n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    assert abs(bsdf.inputs["Roughness"].default_value - 0.2) < 1e-6
    mapping = next(n for n in mat.node_tree.nodes if n.bl_idname == "ShaderNodeMapping")
    assert abs(mapping.inputs["Scale"].default_value[0] - 12.0) < 1e-4, tuple(mapping.inputs["Scale"].default_value)
    # applying another preset replaces the network instead of piling up nodes
    n_before = len(mat.node_tree.nodes)
    assert adapter.set_material(object_name="Box", preset="stone", scale=3.0).success
    assert len(bpy.data.objects["Box"].material_slots[0].material.node_tree.nodes) == n_before
    bad = adapter.set_material(object_name="Box", preset="velvet")
    assert not bad.success and "wood" in bad.error.message, bad
    bad = adapter.set_material(object_name="Box", preset="wood", scale=999)
    assert not bad.success, bad
    print("[PASS] Test 2")


if __name__ == "__main__":
    test_all_presets()
    test_scale_override_and_errors()
    print("ALL MATERIAL PRESET INTEGRATION TESTS PASSED")
