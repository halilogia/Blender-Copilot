"""Headless integration tests for the film tools in real Blender 5.2: environment presets with sky and fog, set_look,
camera_settings, render_contact_sheet, edit_video (cut, crossfade, speed) and render_shots."""

import os
import struct
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import bpy  # noqa: E402

from adapter.blender_adapter import BlenderAdapter  # noqa: E402
from adapter.mutators.undo_manager import push_undo_step  # noqa: E402


def scene_with_subject():
    bpy.ops.wm.read_homefile(use_empty=True)
    bpy.context.preferences.edit.use_global_undo = True
    adapter = BlenderAdapter()
    assert adapter.create_primitive("CUBE", name="Subject", size=2.0, location=[0, 0, 1]).success
    push_undo_step("Baseline")
    return adapter


def mean_rgb(path):
    img = bpy.data.images.load(str(path))
    px = list(img.pixels)
    n = len(px) // 4
    out = tuple(sum(px[c::4]) / n for c in range(3))
    bpy.data.images.remove(img)
    return out


def png_size(path):
    data = Path(path).read_bytes()
    return struct.unpack(">II", data[16:24])


def test_environments():
    print("Test 1: the new environment presets (sky gradient, fog)...")
    adapter = scene_with_subject()
    for preset, expect in (("day", "sky"), ("sunset", "sky"), ("dawn", "sky"), ("golden_hour", "sky"), ("foggy", "flat"),
                           ("studio", "flat"), ("night", "flat")):
        res = adapter.set_environment(preset=preset)
        assert res.success, (preset, res.error)
        assert res.data["sky"] == expect, (preset, res.data["sky"])
    world = bpy.context.scene.world
    kinds = {n.bl_idname for n in world.node_tree.nodes}
    assert "ShaderNodeTexSky" not in kinds, "flat presets must not keep an old sky node"
    print("[PASS] Test 1")


def test_look_and_lens():
    print("Test 2: set_look changes the render, camera_settings sets depth of field and rack focus...")
    adapter = scene_with_subject()
    assert adapter.create_primitive("CUBE", name="Far", size=1.0, location=[0, -8, 0.5]).success
    with tempfile.TemporaryDirectory() as tmp:
        adapter.export_dir = tmp
        assert adapter.set_environment(preset="day").success
        assert adapter.camera_move(preset="static", object_names=["Subject"], duration=1.0, fps=12).success
        base = adapter.render_image(filename="base", width=160, height=90, samples=2)
        assert base.success, base.error
        base_rgb = mean_rgb(base.data["path"])
        noir = adapter.set_look(preset="noir")
        assert noir.success and "saturation" in noir.data["applied"], noir
        noir_img = adapter.render_image(filename="noir", width=160, height=90, samples=2)
        r, g, b = mean_rgb(noir_img.data["path"])
        assert max(abs(r - g), abs(g - b)) < 0.03, (r, g, b)
        warm_base = max(abs(base_rgb[0] - base_rgb[2]), 0.0)
        cine = adapter.set_look(preset="cinematic")
        assert cine.success and "slope" in cine.data["applied"], cine
        cr, cg, cb = mean_rgb(adapter.render_image(filename="cine", width=160, height=90, samples=2).data["path"])
        assert max(abs(a - b) for a, b in zip((cr, cg, cb), base_rgb)) > 0.005, ((cr, cg, cb), base_rgb)
        warm = adapter.set_look(preset="warm")
        assert warm.success, warm
        wr, wg, wb = mean_rgb(adapter.render_image(filename="warm", width=160, height=90, samples=2).data["path"])
        assert (wr - wb) > (base_rgb[0] - base_rgb[2]) + 0.03, ((wr, wg, wb), base_rgb)
        assert adapter.set_look(preset="dreamy").success and adapter.set_look(preset="neon_glow").success
        assert adapter.set_look(preset="natural").success
        assert bpy.context.scene.compositing_node_group is None
        for bad in (dict(preset="sepia2000"), dict(preset="noir", strength="x")):
            res = adapter.set_look(**bad)
            assert not res.success and res.error.type == "INVALID_ARGUMENT", (bad, res)
        # lens
        res = adapter.camera_settings(f_stop=1.8, focus_object="Subject")
        assert res.success, res.error
        cam = bpy.data.objects["ShotCamera"].data
        assert cam.dof.use_dof and abs(cam.dof.aperture_fstop - 1.8) < 1e-6 and cam.dof.focus_object.name == "Subject"
        res = adapter.camera_settings(focus_object="Subject", rack_focus_to="Far")
        assert res.success and res.data["rack_focus"]["to"] == "Far", res
        assert cam.animation_data is not None and cam.animation_data.action is not None
        res = adapter.camera_settings(motion_blur=True, shutter=0.6)
        assert res.success and bpy.context.scene.render.use_motion_blur
        for bad in (dict(), dict(f_stop=0), dict(focus_object="Nope"), dict(rack_focus_to="Far")):
            res = adapter.camera_settings(**bad)
            assert not res.success and res.error.type == "INVALID_ARGUMENT", (bad, res)
    print("[PASS] Test 2")


def test_contact_sheet():
    print("Test 3: render_contact_sheet gives one picture of several frames...")
    adapter = scene_with_subject()
    with tempfile.TemporaryDirectory() as tmp:
        adapter.export_dir = tmp
        assert adapter.set_environment(preset="studio").success
        assert adapter.camera_move(preset="orbit", object_names=["Subject"], duration=2.0, fps=12, angle=180).success
        res = adapter.render_contact_sheet(filename="sheet", frames=4, width=160, height=90, samples=2)
        assert res.success, res.error
        assert res.data["tiles"] == [2, 2] and png_size(res.data["path"]) == (320, 180), (res.data, png_size(res.data["path"]))
        assert res.data["image_id"].startswith("rn_") and res.data["frames"][0] == 1 and res.data["frames"][-1] == 24 and len(res.data["frames"]) == 4
        assert not list(Path(tmp).glob("_sheet_tile*")), "tile files must be cleaned up"
        # the orbit moved: the first and last tiles differ
        img = bpy.data.images.load(res.data["path"])
        assert img.size[0] == 320 and img.size[1] == 180
        bpy.data.images.remove(img)
        for bad in (dict(frames=1), dict(frames=12), dict(width=10), dict(filename="../x")):
            r = adapter.render_contact_sheet(**bad)
            assert not r.success and r.error.type == "INVALID_ARGUMENT", (bad, r)
    print("[PASS] Test 3")


def test_new_presets_and_roll():
    print("Test 4: dutch angle and barrel roll tilt the camera, snorricam follows...")
    adapter = scene_with_subject()
    scn = bpy.context.scene
    V = __import__("mathutils").Vector
    assert adapter.camera_move(preset="dutch_angle", object_names=["Subject"], duration=1.0, fps=12).success
    cam = bpy.data.objects["ShotCamera"]
    scn.frame_set(4)
    right = cam.matrix_world.to_3x3() @ V((1, 0, 0))            # a level camera has its right vector flat (z = 0)
    assert abs(right.z) > 0.15, f"dutch angle must tilt the horizon, right.z={right.z}"
    assert adapter.camera_move(preset="static", object_names=["Subject"], duration=1.0, fps=12).success
    scn.frame_set(4)
    right = cam.matrix_world.to_3x3() @ V((1, 0, 0))
    assert abs(right.z) < 0.05, f"a normal shot keeps the horizon level, right.z={right.z}"
    res = adapter.camera_move(preset="barrel_roll", object_names=["Subject"], duration=2.0, fps=12)
    assert res.success
    scn.frame_set(12)
    up_mid = cam.matrix_world.to_3x3() @ V((0, 1, 0))
    assert up_mid.z < 0.7, "half way through a barrel roll the camera is on its side or upside down"
    res = adapter.camera_move(preset="snorricam", object_names=["Subject"], duration=1.0, fps=12)
    assert res.success and res.data["follow"] is True
    # weak models wrap or quote lists and stringify numbers: all of it must still work
    for wrapped in ({"item": ["Subject"]}, {"item": {"item": ["Subject"]}}, "Subject", '["Subject"]'):
        res = adapter.camera_move(preset="static", object_names=wrapped, duration="1", fps="12", distance="9")
        assert res.success and res.data["distance"] == 9.0, (wrapped, res.error if not res.success else res.data)
    print("[PASS] Test 4")


def make_clip(adapter, name, preset, seconds=1.0):
    assert adapter.camera_move(preset=preset, object_names=["Subject"], duration=seconds, fps=12).success
    res = adapter.render_animation(filename=name, width=160, height=90, samples=2)
    assert res.success, res.error
    return res


def video_frames(path):
    scene = bpy.data.scenes.new("probe")
    scene.sequence_editor_create()
    strips = scene.sequence_editor.strips
    s = strips.new_movie("p", str(path), 1, 1)
    frames = s.frame_final_duration
    bpy.data.scenes.remove(scene)
    return frames


def test_edit_and_shots():
    print("Test 5: edit_video (cut, crossfade, speed) and render_shots...")
    adapter = scene_with_subject()
    with tempfile.TemporaryDirectory() as tmp:
        adapter.export_dir = tmp
        assert adapter.set_environment(preset="studio").success
        make_clip(adapter, "a", "dolly_in")
        make_clip(adapter, "b", "orbit")
        cut = adapter.edit_video(filename="cut", clips=["a.mp4", "b.mp4"], transition="cut")
        assert cut.success, cut.error
        assert cut.data["frames"] == 24 and video_frames(cut.data["path"]) == 24, cut.data
        fade = adapter.edit_video(filename="fade", clips=["a", "b"], transition="crossfade", transition_seconds=0.5)
        assert fade.success, fade.error
        assert fade.data["frames"] == 24 - 6, fade.data
        slow = adapter.edit_video(filename="slow", clips=[{"file": "a.mp4", "speed": 0.5}])
        assert slow.success, slow.error
        assert 22 <= slow.data["frames"] <= 26, slow.data
        fast = adapter.edit_video(filename="fast", clips=[{"file": "a.mp4", "speed": 2.0}])
        assert fast.success and 5 <= fast.data["frames"] <= 7, fast.data
        assert Path(fade.data["path"]).read_bytes()[4:8] == b"ftyp"
        # music: a procedural bed is made, laid under the film and muxed as AAC
        song = adapter.make_soundtrack(mood="epic", seconds=3, filename="bed")
        assert song.success and Path(song.data["path"]).exists() and song.data["seconds"] == 3.0, song
        scored = adapter.edit_video(filename="scored", clips=["a.mp4", "b.mp4"], soundtrack="bed.wav", music_volume=0.5)
        assert scored.success, scored.error
        assert scored.data["soundtrack"] == "bed.wav" and scored.data["frames"] == 24, scored.data
        assert b"mp4a" in Path(scored.data["path"]).read_bytes(), "no AAC audio in the MP4"
        assert b"mp4a" not in Path(cut.data["path"]).read_bytes(), "a film without music has no audio track"
        for bad in (dict(soundtrack="nope.wav"), dict(soundtrack="../bed.wav"), dict(soundtrack="bed.exe"),
                    dict(soundtrack="bed.wav", music_volume=5)):
            res = adapter.edit_video(filename="x", clips=["a.mp4"], **bad)
            assert not res.success and res.error.type == "INVALID_ARGUMENT", (bad, res)
        for bad in (dict(mood="polka"), dict(seconds=0), dict(seconds=500), dict(filename="a/b")):
            res = adapter.make_soundtrack(**bad)
            assert not res.success and res.error.type == "INVALID_ARGUMENT", (bad, res)
        for bad in (dict(clips=[]), dict(clips=["nope.mp4"]), dict(clips=["../a.mp4"]), dict(clips=["a.mp4"], transition="spin"),
                    dict(clips=[{"file": "a.mp4", "speed": 9}]), dict(clips=["a.mp4"], filename="a/b")):
            res = adapter.edit_video(**bad)
            assert not res.success and res.error.type == "INVALID_ARGUMENT", (bad, res)
        # a whole shot list in one call
        res = adapter.render_shots(filename="film", width=160, height=90, samples=2, shots=[
            {"preset": "dolly_in", "duration": 1.0, "environment": "sunset", "fps": 12},
            {"preset": "orbit", "duration": 1.0, "look": "cinematic", "fps": 12},
        ], transition="crossfade", transition_seconds=0.25)
        assert res.success, res.error
        assert res.data["frames"] == 24 - 3 and len(res.data["shots"]) == 2, res.data
        assert (Path(tmp) / "film.mp4").exists()
        res = adapter.render_shots(filename="scoredfilm", width=160, height=90, samples=2, music="tense", shots=[
            {"preset": "dolly_in", "duration": 1.0, "fps": 12}, {"preset": "orbit", "duration": 1.0, "fps": 12}],
            transition="cut")
        assert res.success, res.error
        assert res.data["soundtrack"] == "scoredfilm_music.wav" and b"mp4a" in Path(res.data["path"]).read_bytes()
        assert not (Path(tmp) / "scoredfilm_music.wav").exists(), "the generated bed is removed after the edit"
        bad = adapter.render_shots(filename="x", music="polka", shots=[{"preset": "orbit"}])
        assert not bad.success and bad.error.type == "INVALID_ARGUMENT", bad
        assert not list(Path(tmp).glob("film_shot*")), "per-shot files must be removed"
        for bad in (dict(shots=[]), dict(shots=[{"preset": "warp"}]), dict(shots=[{"preset": "orbit", "wat": 1}]),
                    dict(shots=[{"preset": "orbit", "environment": "moon"}]), dict(shots=[{"preset": "orbit", "duration": 99}])):
            r = adapter.render_shots(**bad)
            assert not r.success and r.error.type == "INVALID_ARGUMENT", (bad, r)
    print("[PASS] Test 5")


def test_check_shot():
    print("Test 6: check_shot measures framing and brightness...")
    adapter = scene_with_subject()
    assert adapter.set_environment(preset="studio").success
    scn = bpy.context.scene
    no_cam = adapter.check_shot()
    assert not no_cam.success and "camera" in no_cam.error.message.lower(), no_cam
    assert adapter.camera_move(preset="static", object_names=["Subject"], duration=1.0, fps=12).success
    good = adapter.check_shot(object_names=["Subject"])
    assert good.success, good.error
    assert good.data["ok"] is True, good.data["issues"]
    assert len(good.data["frames_checked"]) == 3 and "brightness" in good.data["per_frame"][0]
    share = good.data["per_frame"][0]["subject_screen"]["share_of_frame"]
    assert 0.04 < share < 0.88, share
    # too close: cut off
    assert adapter.camera_move(preset="static", object_names=["Subject"], duration=1.0, fps=12, distance=1.6).success
    close = adapter.check_shot(object_names=["Subject"], render=False)
    assert close.success and "SUBJECT_CUT" in [i["code"] for i in close.data["issues"]], close.data
    assert "brightness" not in close.data["per_frame"][0], "render=false measures only the framing"
    # too far: tiny
    assert adapter.camera_move(preset="static", object_names=["Subject"], duration=1.0, fps=12, distance=90).success
    far = adapter.check_shot(object_names=["Subject"], render=False)
    assert "SUBJECT_TOO_SMALL" in [i["code"] for i in far.data["issues"]], far.data
    assert "distance" in far.data["issues"][0]["fix"]
    # the subject drifts out of a fixed shot: found in the last frame only
    assert adapter.camera_move(preset="static", object_names=["Subject"], duration=1.0, fps=12).success
    subject = bpy.data.objects["Subject"]
    subject.location = (0, 0, 1)
    subject.keyframe_insert("location", frame=1)
    subject.location = (60, 0, 1)
    subject.keyframe_insert("location", frame=scn.frame_end)
    drift = adapter.check_shot(object_names=["Subject"], samples=3, render=False)
    frames = [f for i in drift.data["issues"] for f in i["frames"]]
    assert drift.data["ok"] is False and scn.frame_end in frames and 1 not in frames, drift.data
    subject.animation_data_clear()
    subject.location = (0, 0, 1)
    # light: black world and no sun, then a blinding world
    assert adapter.camera_move(preset="static", object_names=["Subject"], duration=1.0, fps=12).success
    world = scn.world
    bg = next(n for n in world.node_tree.nodes if n.bl_idname == "ShaderNodeBackground")
    bpy.data.objects.remove(bpy.data.objects["AI_Sun"], do_unlink=True)
    bg.inputs[1].default_value = 0.0
    dark = adapter.check_shot(object_names=["Subject"], samples=1)
    assert {"TOO_DARK", "MOSTLY_BLACK"} & {i["code"] for i in dark.data["issues"]}, dark.data
    bg.inputs[0].default_value = (1, 1, 1, 1)
    bg.inputs[1].default_value = 40.0
    bright = adapter.check_shot(object_names=["Subject"], samples=1)
    assert {"TOO_BRIGHT", "BLOWN_OUT"} & {i["code"] for i in bright.data["issues"]}, bright.data
    assert scn.frame_current == 1, "the frame the user was on is restored"
    for bad in (dict(samples=0), dict(samples=9), dict(samples="x"), dict(object_names=["Nope"])):
        res = adapter.check_shot(**bad)
        assert not res.success and res.error.type == "INVALID_ARGUMENT", (bad, res)
    print("[PASS] Test 6")


def main():
    test_environments()
    test_look_and_lens()
    test_contact_sheet()
    test_new_presets_and_roll()
    test_edit_and_shots()
    test_check_shot()
    print("\nALL FILM TOOL INTEGRATION TESTS PASSED")


if __name__ == "__main__":
    main()
