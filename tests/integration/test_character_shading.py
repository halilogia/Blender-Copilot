"""Headless integration test in real Blender 5.2 for the character look: set_material layers (gradient, rim, coat,
subsurface, thin film), transparent and Cycles render_image, a transparent sprite strip from render_contact_sheet and
bake_material keeping the coat."""

import os
import sys
import tempfile

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import bpy  # noqa: E402

from adapter.blender_adapter import BlenderAdapter  # noqa: E402
from adapter.mutators.undo_manager import push_undo_step  # noqa: E402


def fresh():
    bpy.ops.wm.read_homefile(use_empty=True)
    bpy.context.preferences.edit.use_global_undo = True
    adapter = BlenderAdapter()
    push_undo_step("Baseline")
    return adapter


def pixels(path):
    img = bpy.data.images.load(str(path))
    px = list(img.pixels)
    size = tuple(img.size)
    bpy.data.images.remove(img)
    return px, size


def test_layers_build_and_replace():
    print("Test 1: character layers build nodes, re-apply without piling up, and reject bad input...")
    adapter = fresh()
    assert adapter.create_primitive("SPHERE", name="Hero", size=1.0).success
    res = adapter.set_material(object_name="Hero", material_name="M_Hero", roughness=0.3, subsurface=0.2, coat=1.0,
                               coat_roughness=0.05, thin_film=400, gradient_colors=[[0.2, 0.1, 0.9], [0.0, 0.8, 1.0]],
                               gradient_axis="diagonal", rim_colors=[[0.5, 0.9, 1.0], [0.0, 0.3, 1.0]], rim_strength=3.0)
    assert res.success, res.error
    for key in ("subsurface", "coat", "coat_roughness", "thin_film", "gradient", "rim"):
        assert key in res.data["changed"], res.data["changed"]
    mat = bpy.data.materials["M_Hero"]
    bsdf = next(n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    assert abs(bsdf.inputs["Coat Weight"].default_value - 1.0) < 1e-6
    assert abs(bsdf.inputs["Subsurface Weight"].default_value - 0.2) < 1e-6
    assert abs(bsdf.inputs["Thin Film Thickness"].default_value - 400.0) < 1e-3
    assert bsdf.inputs["Base Color"].is_linked and bsdf.inputs["Emission Color"].is_linked
    assert bsdf.inputs["Emission Strength"].is_linked
    count = len(mat.node_tree.nodes)
    again = adapter.set_material(object_name="Hero", material_name="M_Hero", gradient_colors=[[1, 0, 0], [0, 0, 1]],
                                 rim_colors=[[1, 1, 1], [0, 0, 0]])
    assert again.success, again.error
    assert len(mat.node_tree.nodes) == count, (len(mat.node_tree.nodes), count)
    bad = adapter.set_material(object_name="Hero", preset="wood", gradient_colors=[[1, 0, 0], [0, 0, 1]])
    assert not bad.success and "gradient_colors" in bad.error.message, bad
    bad = adapter.set_material(object_name="Hero", coat=3)
    assert not bad.success and "between 0 and 1" in bad.error.message, bad
    print("[PASS] Test 1")


def test_transparent_renders_and_sprite_strip():
    print("Test 2: transparent EEVEE and Cycles stills, a one-row transparent strip, and the scene settings restored...")
    adapter = fresh()
    assert adapter.create_primitive("SPHERE", name="Hero", size=1.0, location=[0, 0, 1]).success
    assert adapter.set_material(object_name="Hero", base_color=[0.1, 0.4, 1.0], coat=1.0).success
    with tempfile.TemporaryDirectory() as tmp:
        adapter.export_dir = tmp
        assert adapter.set_environment(preset="studio", ground=False).success
        assert adapter.camera_move(preset="orbit", object_names=["Hero"], duration=1.0, fps=12, distance=4.0).success
        scn = bpy.context.scene
        mode_before = scn.render.image_settings.color_mode
        for engine in ("eevee", "cycles"):
            shot = adapter.render_image(filename=f"cut_{engine}", width=96, height=96, samples=4, transparent=True, engine=engine)
            assert shot.success, (engine, shot.error)
            px, size = pixels(shot.data["path"])
            assert size == (96, 96), size
            corner, centre = px[3], px[(48 * 96 + 48) * 4 + 3]
            assert corner < 0.01 and centre > 0.99, (engine, corner, centre)
        assert scn.render.film_transparent is False and scn.render.image_settings.color_mode == mode_before
        bad = adapter.render_image(filename="x", width=64, height=64, engine="unreal")
        assert not bad.success and "engine" in bad.error.message, bad
        strip = adapter.render_contact_sheet(filename="strip", frames=4, columns=4, width=64, height=64, samples=2, transparent=True)
        assert strip.success, strip.error
        assert strip.data["tiles"] == [4, 1] and strip.data["width"] == 256 and strip.data["height"] == 64, strip.data
        px, size = pixels(strip.data["path"])
        assert size == (256, 64) and px[3] < 0.01, (size, px[3])
        assert adapter.render_contact_sheet(filename="big", frames=12, width=64, height=64, samples=1).success
        bad = adapter.render_contact_sheet(filename="s", frames=4, columns=9, width=64, height=64)
        assert not bad.success, bad
    print("[PASS] Test 2")


def test_bake_keeps_coat():
    print("Test 3: bake_material paints the gradient and keeps coat and thin film for glTF...")
    adapter = fresh()
    assert adapter.create_primitive("SPHERE", name="Hero", size=1.0).success
    assert adapter.set_material(object_name="Hero", gradient_colors=[[1, 0, 0], [0, 0, 1]], coat=0.8, thin_film=300).success
    with tempfile.TemporaryDirectory() as tmp:
        adapter.export_dir = tmp
        res = adapter.bake_material(object_name="Hero", resolution=64, samples=1)
        assert res.success and res.data.get("baked", True), res
        mat = bpy.data.objects["Hero"].material_slots[0].material
        bsdf = next(n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
        assert abs(bsdf.inputs["Coat Weight"].default_value - 0.8) < 1e-6
        assert abs(bsdf.inputs["Thin Film Thickness"].default_value - 300.0) < 1e-3
    print("[PASS] Test 3")


if __name__ == "__main__":
    test_layers_build_and_replace()
    test_transparent_renders_and_sprite_strip()
    test_bake_keeps_coat()
    print("ALL CHARACTER SHADING INTEGRATION TESTS PASSED")
