"""Headless integration tests for the cinematic tools in real Blender 5.2: set_environment, camera_move,
render_image and render_animation (a real PNG and a real MP4 are written and checked)."""

import os
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import bpy  # noqa: E402

from adapter.blender_adapter import BlenderAdapter  # noqa: E402
from adapter.mutators.undo_manager import perform_undo, push_undo_step  # noqa: E402
from core.camera_paths import PRESETS  # noqa: E402
from tools.registry import ToolRegistry  # noqa: E402


def scene_with_subject():
    bpy.ops.wm.read_homefile(use_empty=True)
    bpy.context.preferences.edit.use_global_undo = True
    adapter = BlenderAdapter()
    res = adapter.create_primitive("CUBE", name="Subject", size=2.0, location=[4, 3, 1])
    assert res.success, res.error
    push_undo_step("Baseline")
    return adapter


def test_environments():
    print("Test 1: set_environment presets...")
    adapter = scene_with_subject()
    for preset in ("studio", "golden_hour", "overcast", "night", "neon"):
        res = adapter.set_environment(preset=preset)
        assert res.success, (preset, res.error)
        assert "AI_Sun" in bpy.data.objects and "AI_Ground" in bpy.data.objects
        assert bpy.context.scene.world is not None and bpy.context.scene.world.name == "AI_World"
        assert bpy.context.scene.view_settings.view_transform == "Standard"
        neon = [n for n in ("AI_NeonA", "AI_NeonB") if n in bpy.data.objects]
        assert (len(neon) == 2) == (preset == "neon"), (preset, neon)
    ground = bpy.data.objects["AI_Ground"]
    assert abs(ground.location.z - 0.0) < 1e-3 and abs(ground.location.x - 4.0) < 1e-3, ground.location
    res = adapter.set_environment(preset="studio", ground=False)
    assert res.success and "AI_Ground" not in bpy.data.objects
    for bad in (dict(preset="disco"), dict(ground_color=[1, 2]), dict(ground_size=0)):
        res = adapter.set_environment(**bad)
        assert not res.success and res.error.type == "INVALID_ARGUMENT", (bad, res)
    print("[PASS] Test 1")


def test_camera_moves():
    print("Test 2: camera_move presets keyframe the shot...")
    adapter = scene_with_subject()
    for preset in PRESETS:
        res = adapter.camera_move(preset=preset, duration=1.0, fps=12)
        assert res.success, (preset, res.error)
        d = res.data
        assert d["frames"] == 12 and d["frame_range"] == [1, 12], d
        scn = bpy.context.scene
        assert scn.camera.name == "ShotCamera" and scn.frame_end == 12 and scn.render.fps == 12
        cam = bpy.data.objects["ShotCamera"]
        scn.frame_set(1)
        start = cam.matrix_world.translation.copy()
        scn.frame_set(12)
        end = cam.matrix_world.translation.copy()
        moves = {"static", "pan_left", "pan_right", "tilt_up", "tilt_down", "whip_pan", "crash_zoom_in", "crash_zoom_out", "rapid_zoom_in", "rapid_zoom_out", "yoyo_zoom", "dutch_angle", "snorricam"}
        if preset not in moves and preset != "handheld":
            assert (end - start).length > 0.2, (preset, start, end)
        assert cam.animation_data is not None and cam.data.animation_data is not None
    # the subject is what the camera looks at
    res = adapter.camera_move(preset="orbit", object_names=["Subject"], duration=2.0, fps=24, angle=90)
    assert res.success
    c = res.data["subject_center"]
    assert abs(c[0] - 4.0) < 1e-3 and abs(c[1] - 3.0) < 1e-3 and abs(c[2] - 1.0) < 1e-3, c
    bpy.context.scene.frame_set(24)
    cam = bpy.data.objects["ShotCamera"]
    to_subject = (bpy.data.objects["Subject"].location - cam.matrix_world.translation).normalized()
    forward = (cam.matrix_world.to_3x3() @ __import__("mathutils").Vector((0, 0, -1))).normalized()
    assert forward.dot(to_subject) > 0.98, forward.dot(to_subject)
    for bad in (dict(preset="teleport"), dict(preset="orbit", duration=0), dict(preset="orbit", fps=1),
                dict(preset="orbit", object_names=["Nope"])):
        res = adapter.camera_move(**bad)
        assert not res.success and res.error.type == "INVALID_ARGUMENT", (bad, res)
    print("[PASS] Test 2")


def test_renders():
    print("Test 3: render_image and render_animation write real files...")
    adapter = scene_with_subject()
    with tempfile.TemporaryDirectory() as tmp:
        adapter.export_dir = tmp
        no_cam = adapter.render_image(filename="x", width=160, height=90)
        assert not no_cam.success and "camera" in no_cam.error.message.lower(), no_cam
        assert adapter.set_environment(preset="golden_hour").success
        assert adapter.camera_move(preset="dolly_in", duration=0.5, fps=12).success
        engine_before = bpy.context.scene.render.engine
        res = adapter.render_image(filename="still", width=160, height=90, samples=4)
        assert res.success, res.error
        png = Path(res.data["path"])
        assert png.exists() and png.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n" and png.parent == Path(tmp)
        assert res.data["image_id"].startswith("rn_") and adapter.get_viewport_screenshot(res.data["image_id"])
        res = adapter.render_animation(filename="clip", width=160, height=90, samples=4)
        assert res.success, res.error
        mp4 = Path(res.data["path"])
        assert mp4.exists() and mp4.suffix == ".mp4" and mp4.stat().st_size > 1000, res.data
        assert res.data["frames"] == 6 and Path(res.data["preview_path"]).exists() and res.data["image_id"]
        assert mp4.read_bytes()[4:8] == b"ftyp", "not an MP4 container"
        res = adapter.render_animation(filename="seq", width=160, height=90, format="png", start_frame=1, end_frame=3, samples=2)
        assert res.success and len(list(Path(res.data["path"]).glob("frame_*.png"))) == 3, res
        # settings restored
        assert bpy.context.scene.render.engine == engine_before
        assert bpy.context.scene.render.resolution_x == 1920 and bpy.context.scene.frame_end == 6
        for bad in (dict(filename="../evil"), dict(filename="a/b"), dict(width=99999), dict(width=10),
                    dict(format="gif"), dict(end_frame=99999)):
            res = adapter.render_animation(**bad)
            assert not res.success and res.error.type == "INVALID_ARGUMENT", (bad, res)
        assert not adapter.render_image(filename="..\\evil").success
    print("[PASS] Test 3")


def test_undo_and_registry():
    print("Test 4: undo and tool registration...")
    adapter = scene_with_subject()
    assert adapter.set_environment(preset="night").success
    assert "AI_Sun" in bpy.data.objects
    assert perform_undo(), "undo unavailable"
    assert "AI_Sun" not in bpy.data.objects, "set_environment must be one undo step"
    from tools.mutations import CameraMoveTool, RenderAnimationTool, RenderImageTool, SetEnvironmentTool
    reg = ToolRegistry()
    for tool in (SetEnvironmentTool(), CameraMoveTool(), RenderImageTool(), RenderAnimationTool()):
        reg.register(tool)
        assert tool.risk_level.value == "LOW", tool.name
        assert tool.input_schema["type"] == "object"
    assert set(reg.names()) if hasattr(reg, "names") else True
    print("[PASS] Test 4")


def main():
    test_environments()
    test_camera_moves()
    test_renders()
    test_undo_and_registry()
    print("\nALL CINEMA TOOL INTEGRATION TESTS PASSED")


if __name__ == "__main__":
    main()
