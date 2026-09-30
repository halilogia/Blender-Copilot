"""Cinematic mutators: environment presets, camera move presets and rendering (EEVEE) to PNG or MP4.

Allow-listed and bounded like the modeling tools: no arbitrary Python, output files only inside the configured export
folder, resolution and frame counts capped. Camera paths come from ``core.camera_paths`` (plain math).
"""

import math
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import bpy
from mathutils import Quaternion, Vector

from adapter.mutators.modeling_mutator import ModelingError, as_list
from adapter.mutators.undo_manager import push_undo_step
from core.camera_paths import FOLLOW_PRESETS, PRESETS, camera_rolls, camera_samples, frame_count

HELPER_PREFIX = "AI_"
CAMERA_NAME = "ShotCamera"
TARGET_NAME = "ShotTarget"
MAX_WIDTH, MAX_HEIGHT = 1920, 1080
MIN_SIDE = 64
STEM_RX = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_\-]{0,60}$")

# sky colour, sky strength, sun colour, sun energy, sun elevation, sun azimuth (0 = +Y side), sun softness (rad),
# ground colour, exposure, extra point lights
ENVIRONMENTS: Dict[str, Dict[str, Any]] = {
    "studio": {"sky": (0.72, 0.72, 0.75), "sky_strength": 1.0, "sun": (1.0, 1.0, 1.0), "energy": 2.0, "elevation": 50.0,
               "azimuth": 30.0, "softness": 0.12, "ground": (0.75, 0.75, 0.75), "exposure": 0.0,
               "about": "neutral grey backdrop, soft white key light"},
    "golden_hour": {"sky": (1.0, 0.72, 0.48), "sky_strength": 0.4, "sun": (1.0, 0.62, 0.3), "energy": 2.6, "elevation": 12.0,
                    "azimuth": 55.0, "softness": 0.03, "ground": (0.36, 0.3, 0.2), "exposure": 0.0, "nishita": (9.0, 55.0),
                    "about": "low warm sun, orange sky, long shadows"},
    "overcast": {"sky": (0.62, 0.66, 0.7), "sky_strength": 0.95, "sun": (1.0, 1.0, 1.0), "energy": 0.6, "elevation": 60.0,
                 "azimuth": 20.0, "softness": 0.5, "ground": (0.34, 0.37, 0.33), "exposure": 0.0,
                 "about": "grey sky, soft even light, weak shadows"},
    "night": {"sky": (0.02, 0.03, 0.09), "sky_strength": 0.7, "sun": (0.45, 0.55, 1.0), "energy": 2.6, "elevation": 32.0,
              "azimuth": 200.0, "softness": 0.05, "ground": (0.08, 0.1, 0.14), "exposure": 0.8,
              "about": "dark blue night with a cold moon light from behind"},
    "neon": {"sky": (0.02, 0.0, 0.05), "sky_strength": 0.4, "sun": (0.5, 0.4, 1.0), "energy": 0.05, "elevation": 40.0,
             "azimuth": 0.0, "softness": 0.1, "ground": (0.02, 0.02, 0.04), "exposure": 0.3,
             "about": "dark scene lit by a magenta and a cyan light", "point_lights": True},
    "day": {"sky": (0.5, 0.65, 0.9), "sky_strength": 0.35, "sun": (1.0, 0.96, 0.9), "energy": 1.9, "elevation": 50.0,
            "azimuth": 35.0, "softness": 0.05, "ground": (0.12, 0.22, 0.09), "exposure": -0.6, "nishita": (50.0, 35.0),
            "about": "clear blue sky with a real sky gradient, high sun"},
    "sunset": {"sky": (1.0, 0.45, 0.25), "sky_strength": 0.4, "sun": (1.0, 0.45, 0.2), "energy": 2.2, "elevation": 4.0,
               "azimuth": 70.0, "softness": 0.03, "ground": (0.25, 0.16, 0.12), "exposure": 0.0, "nishita": (3.0, 70.0),
               "about": "sun on the horizon, red and orange sky, deep long shadows"},
    "dawn": {"sky": (0.7, 0.6, 0.8), "sky_strength": 0.45, "sun": (1.0, 0.7, 0.65), "energy": 1.5, "elevation": 6.0,
             "azimuth": 300.0, "softness": 0.04, "ground": (0.22, 0.22, 0.3), "exposure": 0.0, "nishita": (5.0, 300.0),
             "about": "cool pink and blue early light"},
    "foggy": {"sky": (0.55, 0.6, 0.62), "sky_strength": 1.1, "sun": (1.0, 1.0, 1.0), "energy": 0.8, "elevation": 30.0,
              "azimuth": 20.0, "softness": 0.4, "ground": (0.55, 0.6, 0.62), "exposure": 0.0,
              "about": "grey haze: the ground melts into the sky, soft flat light"},
}


def _stem(value: Any, default: str) -> str:
    stem = str(value or default).strip()
    for ext in (".png", ".mp4"):
        if stem.lower().endswith(ext):
            stem = stem[: -len(ext)]
    if not STEM_RX.match(stem):
        raise ModelingError("filename must be a plain name (letters, digits, _ -), no folders.")
    return stem


def _size(width: Any, height: Any) -> tuple:
    try:
        w, h = int(width), int(height)
    except (TypeError, ValueError):
        raise ModelingError("width and height must be whole numbers.")
    if not (MIN_SIDE <= w <= MAX_WIDTH and MIN_SIDE <= h <= MAX_HEIGHT):
        raise ModelingError(f"width must be {MIN_SIDE}-{MAX_WIDTH} and height {MIN_SIDE}-{MAX_HEIGHT}.")
    return w, h


def _scene_meshes(names: Optional[Sequence[str]] = None) -> List["bpy.types.Object"]:
    """Named objects, or every mesh that is not one of the helper objects (ground, lights, camera rig)."""
    if names:
        objs = []
        for n in names:
            obj = bpy.data.objects.get(str(n).strip())
            if obj is None:
                raise ModelingError(f"Object '{n}' not found in the scene.")
            objs.append(obj)
            objs.extend(c for c in obj.children_recursive if c not in objs)   # a rig or parent stands for its parts
        return objs
    return [o for o in bpy.context.scene.objects if o.type == "MESH" and not o.name.startswith(HELPER_PREFIX)]


def _bounds(objs: Sequence["bpy.types.Object"]):
    pts = [o.matrix_world @ Vector(c) for o in objs if o.type == "MESH" for c in o.bound_box]
    if not pts:
        return Vector((0.0, 0.0, 0.5)), 1.0, 0.0
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    return (lo + hi) / 2.0, max((hi - lo).length / 2.0, 0.05), lo.z


def _frame_distance(objs: Sequence["bpy.types.Object"], focal_length: float) -> float:
    """Camera distance that fits the subject in the render frame: tall subjects need more room than wide ones
    because a 16:9 frame is much narrower vertically (about 32 degrees at 35 mm) than horizontally (about 54)."""
    pts = [o.matrix_world @ Vector(c) for o in objs if o.type == "MESH" for c in o.bound_box]
    if not pts:
        return 4.0
    dx = max(p.x for p in pts) - min(p.x for p in pts)
    dy = max(p.y for p in pts) - min(p.y for p in pts)
    dz = max(p.z for p in pts) - min(p.z for p in pts)
    render = bpy.context.scene.render
    aspect = render.resolution_y / max(render.resolution_x, 1)
    lens = max(float(focal_length), 10.0)
    half_w, half_h = math.tan(math.atan(18.0 / lens)), math.tan(math.atan(18.0 * aspect / lens))
    hxy = max(dx, dy) / 2.0
    return max(1.15 * max(hxy / half_w, (dz / 2.0) / half_h) + hxy, 0.5)


def _link(obj: "bpy.types.Object") -> None:
    if obj.name not in bpy.context.scene.objects:
        bpy.context.scene.collection.objects.link(obj)


def _remove_object(name: str) -> None:
    obj = bpy.data.objects.get(name)
    if obj is not None:
        bpy.data.objects.remove(obj, do_unlink=True)


def _material(name: str, color: Sequence[float], roughness: float) -> "bpy.types.Material":
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.diffuse_color = (color[0], color[1], color[2], 1.0)
    try:
        mat.use_nodes = True
        nodes = mat.node_tree.nodes
        bsdf = nodes.get("Principled BSDF")
        if bsdf is None:                      # Blender 5 gives new materials an empty node tree
            for node in list(nodes):
                nodes.remove(node)
            bsdf = nodes.new("ShaderNodeBsdfPrincipled")
            out = nodes.new("ShaderNodeOutputMaterial")
            mat.node_tree.links.new(bsdf.outputs[0], out.inputs[0])
        bsdf.inputs["Base Color"].default_value = (color[0], color[1], color[2], 1.0)
        bsdf.inputs["Roughness"].default_value = roughness
    except Exception:
        pass
    return mat


class CinemaMutator:
    """Environment, camera and render operations."""

    @classmethod
    def set_environment(cls, preset: str = "studio", ground: bool = True, ground_color: Any = None,
                        ground_size: Any = None) -> Dict[str, Any]:
        key = str(preset or "studio").strip().lower()
        if key not in ENVIRONMENTS:
            raise ModelingError(f"preset must be one of {sorted(ENVIRONMENTS)}.")
        env = ENVIRONMENTS[key]
        scn = bpy.context.scene
        center, radius, floor_z = _bounds(_scene_meshes())

        world = bpy.data.worlds.get("AI_World") or bpy.data.worlds.new("AI_World")
        try:
            world.use_nodes = True
        except Exception:
            pass
        nt = world.node_tree
        for node in list(nt.nodes):
            nt.nodes.remove(node)
        bg = nt.nodes.new("ShaderNodeBackground")
        bg.inputs[0].default_value = (*env["sky"], 1.0)
        bg.inputs[1].default_value = env["sky_strength"]
        out = nt.nodes.new("ShaderNodeOutputWorld")
        nt.links.new(bg.outputs[0], out.inputs[0])
        sky_mode = "flat"
        if env.get("nishita"):
            # a physically based sky gradient (bright near the horizon on the sun side); the real light is the sun lamp
            try:
                sky = nt.nodes.new("ShaderNodeTexSky")
                for kind in ("MULTIPLE_SCATTERING", "SINGLE_SCATTERING", "NISHITA"):
                    try:
                        sky.sky_type = kind
                        break
                    except TypeError:
                        continue
                sky.sun_disc = False
                sky.sun_elevation = math.radians(env["nishita"][0])
                sky.sun_rotation = math.radians(env["nishita"][1])
                nt.links.new(sky.outputs[0], bg.inputs[0])
                sky_mode = "sky"
            except Exception:
                sky_mode = "flat"
        # (world volumes were tried for fog and turned the EEVEE render black, so haze is done with colours)
        scn.world = world

        # Sun (reused by name): rotation Z = 180 - azimuth makes the light arrive from that side (0 = +Y, the front).
        sun_obj = bpy.data.objects.get("AI_Sun")
        if sun_obj is None or sun_obj.type != "LIGHT":
            _remove_object("AI_Sun")
            sun_obj = bpy.data.objects.new("AI_Sun", bpy.data.lights.new("AI_Sun", "SUN"))
        _link(sun_obj)
        sun_obj.data.color = env["sun"]
        sun_obj.data.energy = env["energy"]
        sun_obj.data.angle = env["softness"]
        sun_obj.rotation_euler = (math.radians(90.0 - env["elevation"]), 0.0, math.radians(180.0 - env["azimuth"]))

        lights = ["AI_Sun"]
        for name in ("AI_NeonA", "AI_NeonB"):
            _remove_object(name)
        if env.get("point_lights"):
            dist = max(radius * 2.5, 1.0)
            for name, color, sign in (("AI_NeonA", (1.0, 0.1, 0.8), 1.0), ("AI_NeonB", (0.1, 0.8, 1.0), -1.0)):
                data = bpy.data.lights.new(name, "POINT")
                data.color = color
                data.energy = 450.0 * dist * dist / 6.25
                obj = bpy.data.objects.new(name, data)
                obj.location = (center.x + sign * dist, center.y + dist * 0.8, center.z + dist * 0.6)
                _link(obj)
                lights.append(name)

        ground_name = None
        if not ground:
            _remove_object("AI_Ground")
        if ground:
            color = env["ground"]
            if ground_color is not None:
                if not isinstance(ground_color, (list, tuple)) or len(ground_color) < 3:
                    raise ModelingError("ground_color must be [r, g, b].")
                color = tuple(max(0.0, min(1.0, float(v))) for v in ground_color[:3])
            size = float(ground_size) if ground_size is not None else max(radius * 10.0, 6.0)
            if not (0.5 <= size <= 2000.0):
                raise ModelingError("ground_size must be between 0.5 and 2000 meters.")
            obj = bpy.data.objects.get("AI_Ground")
            if obj is None or obj.type != "MESH":
                _remove_object("AI_Ground")
                mesh = bpy.data.meshes.new("AI_Ground")
                obj = bpy.data.objects.new("AI_Ground", mesh)
            half = size / 2.0
            obj.data.clear_geometry()
            obj.data.from_pydata([(-half, -half, 0), (half, -half, 0), (half, half, 0), (-half, half, 0)], [], [(0, 1, 2, 3)])
            obj.data.update()
            obj.location = (center.x, center.y, floor_z)
            obj.data.materials.clear()
            obj.data.materials.append(_material("AI_Ground", color, 0.85))
            _link(obj)
            ground_name = obj.name

        scn.render.engine = "BLENDER_EEVEE"
        try:
            try:
                scn.view_settings.view_transform = "Khronos PBR Neutral"      # rolls highlights off, keeps colours
            except TypeError:
                scn.view_settings.view_transform = "Standard"
            scn.view_settings.look = "None"
        except Exception:
            pass
        scn.view_settings.exposure = env["exposure"]
        push_undo_step(f"AI: Environment {key}")
        return {"preset": key, "about": env["about"], "sky": sky_mode, "lights": lights, "ground": ground_name, "world": world.name,
                "scene_center": [round(v, 3) for v in center], "scene_radius": round(radius, 3)}

    @classmethod
    def camera_move(cls, preset: str, object_names: Any = None, duration: float = 4.0, fps: int = 24,
                    distance: Any = None, elevation: float = 15.0, azimuth: float = 35.0, angle: float = 120.0,
                    intensity: float = 1.0, focal_length: float = 35.0, follow: bool = False,
                    start_frame: Any = 1) -> Dict[str, Any]:
        key = str(preset or "").strip().lower()
        if key not in PRESETS:
            raise ModelingError(f"preset must be one of {sorted(PRESETS)}.")
        if key in FOLLOW_PRESETS:
            follow = True
        object_names = as_list(object_names)
        if object_names is not None and not isinstance(object_names, list):
            raise ModelingError("object_names must be a list of names.")
        try:
            seconds, rate = float(duration), int(fps)
        except (TypeError, ValueError):
            raise ModelingError("duration must be a number of seconds and fps a whole number.")
        if not (0.2 <= seconds <= 60.0):
            raise ModelingError("duration must be between 0.2 and 60 seconds.")
        if not (8 <= rate <= 60):
            raise ModelingError("fps must be between 8 and 60.")
        frames = frame_count(seconds, rate)
        objs = _scene_meshes(object_names)
        deltas = None
        try:
            first = int(start_frame)
        except (TypeError, ValueError):
            raise ModelingError("start_frame must be a whole number (1 or more).")
        if not 1 <= first <= 100000:
            raise ModelingError("start_frame must be between 1 and 100000.")
        bpy.context.scene.frame_set(first)      # the subject is framed as it stands at the first frame of the shot
        if follow:
            # the subject moves (a walking character): the camera keeps the same framing relative to it
            scn_f = bpy.context.scene
            centers = []
            for f in range(first, first + frames):
                scn_f.frame_set(f)
                centers.append(_bounds(objs)[0])
            deltas = [c - centers[0] for c in centers]
            scn_f.frame_set(first)
        center, radius, _ = _bounds(objs)
        distance = float(distance) if distance else _frame_distance(objs, float(focal_length))
        samples = camera_samples(key, frames, tuple(center), radius, distance,
                                 float(elevation), float(azimuth), float(angle), float(intensity), float(focal_length))
        if deltas is not None:
            samples = [((p[0] + d.x, p[1] + d.y, p[2] + d.z), (a[0] + d.x, a[1] + d.y, a[2] + d.z), fl)
                       for (p, a, fl), d in zip(samples, deltas)]

        scn = bpy.context.scene
        cam = bpy.data.objects.get(CAMERA_NAME)
        if cam is None or cam.type != "CAMERA":
            _remove_object(CAMERA_NAME)
            cam = bpy.data.objects.new(CAMERA_NAME, bpy.data.cameras.new(CAMERA_NAME))
        target = bpy.data.objects.get(TARGET_NAME)
        if target is None:
            target = bpy.data.objects.new(TARGET_NAME, None)
            target.empty_display_type = "PLAIN_AXES"
        _link(cam)
        _link(target)
        for obj in (cam, target, cam.data):
            obj.animation_data_clear()
        for con in list(cam.constraints):
            cam.constraints.remove(con)
        track = cam.constraints.new("TRACK_TO")
        track.target = target
        track.track_axis = "TRACK_NEGATIVE_Z"
        track.up_axis = "UP_Y"
        cam.data.clip_end = max(cam.data.clip_end, radius * 60.0)
        rolls = camera_rolls(key, frames, float(intensity))
        rolling = any(abs(v) > 1e-6 for v in rolls)
        track.use_target_z = rolling          # the target's Z axis then defines "up", so tilting it rolls the camera
        target.rotation_mode = "XYZ"
        target.rotation_euler = (0.0, 0.0, 0.0)
        for i, (pos, aim, focal) in enumerate(samples):
            frame = first + i
            cam.location = pos
            cam.keyframe_insert("location", frame=frame)
            target.location = aim
            target.keyframe_insert("location", frame=frame)
            if rolling:
                look = (Vector(aim) - Vector(pos)).normalized()
                up = Quaternion(look, math.radians(rolls[i])) @ Vector((0.0, 0.0, 1.0))
                target.rotation_euler = up.to_track_quat("Z", "Y").to_euler()
                target.keyframe_insert("rotation_euler", frame=frame)
            cam.data.lens = focal
            cam.data.keyframe_insert("lens", frame=frame)
        scn.camera = cam
        scn.render.fps = rate
        scn.frame_start, scn.frame_end = first, first + frames - 1
        scn.frame_set(first)
        push_undo_step(f"AI: Camera move {key}")
        return {"camera": cam.name, "target": target.name, "preset": key, "about": PRESETS[key], "frames": frames,
                "fps": rate, "seconds": round(frames / rate, 2), "frame_range": [first, first + frames - 1],
                "subject_center": [round(v, 3) for v in center], "subject_radius": round(radius, 3),
                "distance": round(float(distance) if distance else radius * 2.8, 3), "follow": bool(follow)}

    # ------------------------------------------------------------------ rendering
    @classmethod
    def _render_setup(cls, width: int, height: int, samples: int):
        scn = bpy.context.scene
        if scn.camera is None:
            raise ModelingError("The scene has no active camera. Call camera_move (or create_camera) first.")
        r = scn.render
        saved = {"engine": r.engine, "x": r.resolution_x, "y": r.resolution_y, "pct": r.resolution_percentage,
                 "path": r.filepath, "frame": scn.frame_current, "start": scn.frame_start, "end": scn.frame_end,
                 "media": getattr(r.image_settings, "media_type", None), "fmt": r.image_settings.file_format}
        r.engine = "BLENDER_EEVEE"
        r.resolution_x, r.resolution_y, r.resolution_percentage = width, height, 100
        try:
            scn.eevee.taa_render_samples = max(1, min(64, int(samples)))
        except Exception:
            pass
        return scn, saved

    @classmethod
    def _render_restore(cls, scn, saved) -> None:
        r = scn.render
        r.engine, r.resolution_x, r.resolution_y, r.resolution_percentage = saved["engine"], saved["x"], saved["y"], saved["pct"]
        if saved["media"] is not None:
            try:
                r.image_settings.media_type = saved["media"]
            except Exception:
                pass
        try:
            r.image_settings.file_format = saved["fmt"]
        except Exception:
            pass
        r.filepath = saved["path"]
        scn.frame_start, scn.frame_end = saved["start"], saved["end"]
        scn.frame_set(saved["frame"])

    @classmethod
    def _write_still(cls, scn, path: Path) -> None:
        r = scn.render
        if hasattr(r.image_settings, "media_type"):
            r.image_settings.media_type = "IMAGE"
        r.image_settings.file_format = "PNG"
        r.filepath = str(path)
        bpy.ops.render.render(write_still=True)
        if not path.exists():
            raise ModelingError("Blender did not write the image.")

    @classmethod
    def render_image(cls, export_dir: str, filename: str = "shot", width: int = 960, height: int = 540,
                     frame: Any = None, samples: int = 16) -> Dict[str, Any]:
        stem = _stem(filename, "shot")
        w, h = _size(width, height)
        folder = Path(export_dir).expanduser()
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"{stem}.png"
        scn, saved = cls._render_setup(w, h, samples)
        try:
            if frame is not None:
                scn.frame_set(int(max(scn.frame_start, min(scn.frame_end, int(frame)))))
            used_frame = scn.frame_current
            cls._write_still(scn, path)
        finally:
            cls._render_restore(scn, saved)
        return {"path": str(path), "filename": path.name, "width": w, "height": h, "frame": used_frame,
                "bytes": path.stat().st_size, "format": "PNG", "engine": "EEVEE"}

    @classmethod
    def render_animation(cls, export_dir: str, filename: str = "shot", width: int = 960, height: int = 540,
                         start_frame: Any = None, end_frame: Any = None, video_format: str = "mp4",
                         samples: int = 12) -> Dict[str, Any]:
        import time

        stem = _stem(filename, "shot")
        w, h = _size(width, height)
        fmt = str(video_format or "mp4").strip().lower()
        if fmt not in ("mp4", "png"):
            raise ModelingError("format must be 'mp4' or 'png' (a numbered image sequence).")
        folder = Path(export_dir).expanduser()
        folder.mkdir(parents=True, exist_ok=True)
        scn, saved = cls._render_setup(w, h, samples)
        try:
            first = int(start_frame) if start_frame is not None else scn.frame_start
            last = int(end_frame) if end_frame is not None else scn.frame_end
            if first < 1 or last < first:
                raise ModelingError("start_frame must be >= 1 and end_frame >= start_frame.")
            if last - first + 1 > 480:
                raise ModelingError("At most 480 frames per render; shorten the shot or lower fps.")
            scn.frame_start, scn.frame_end = first, last
            r = scn.render
            started = time.time()
            if fmt == "mp4":
                target = folder / f"{stem}.mp4"
                if hasattr(r.image_settings, "media_type"):
                    r.image_settings.media_type = "VIDEO"
                r.image_settings.file_format = "FFMPEG"
                r.ffmpeg.format = "MPEG4"
                r.ffmpeg.codec = "H264"
                try:
                    r.ffmpeg.constant_rate_factor = "MEDIUM"
                except Exception:
                    pass
                r.filepath = str(target)
                bpy.ops.render.render(animation=True)
                if not target.exists():
                    raise ModelingError("Blender did not write the video (is ffmpeg output available?).")
                out_path, size = target, target.stat().st_size
            else:
                seq = folder / f"{stem}_frames"
                seq.mkdir(parents=True, exist_ok=True)
                if hasattr(r.image_settings, "media_type"):
                    r.image_settings.media_type = "IMAGE"
                r.image_settings.file_format = "PNG"
                r.filepath = str(seq / "frame_")
                bpy.ops.render.render(animation=True)
                written = sorted(seq.glob("frame_*.png"))
                if not written:
                    raise ModelingError("Blender did not write any frames.")
                out_path, size = seq, sum(p.stat().st_size for p in written)
            seconds_taken = round(time.time() - started, 1)
            preview_path = folder / f"{stem}_preview.png"
            scn.frame_set((first + last) // 2)
            cls._write_still(scn, preview_path)
        finally:
            cls._render_restore(scn, saved)
        return {"path": str(out_path), "filename": out_path.name, "format": fmt.upper(), "frames": last - first + 1,
                "fps": scn.render.fps, "width": w, "height": h, "bytes": size, "render_seconds": seconds_taken,
                "preview_path": str(preview_path), "engine": "EEVEE"}
