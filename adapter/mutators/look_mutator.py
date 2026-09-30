"""Look mutators: colour grading and glow for renders, camera lens effects, and a contact sheet of a shot.

``set_look`` builds a small compositor node group (colour balance, saturation, glare) that every later
render_image / render_animation goes through. ``camera_settings`` controls depth of field, rack focus and motion blur.
``render_contact_sheet`` renders a few frames of the shot into one picture so a model can judge motion in one call.
"""

import math
from pathlib import Path
from typing import Any, Dict, Optional

import bpy
from mathutils import Vector

from adapter.mutators.cinema_mutator import CAMERA_NAME, CinemaMutator, _stem
from adapter.mutators.modeling_mutator import ModelingError
from adapter.mutators.undo_manager import push_undo_step

GROUP_NAME = "AI_Look"

# lift / gain are RGB multipliers around 1, gamma likewise; sat multiplies saturation; glare = (type, threshold, strength, size)
LOOKS: Dict[str, Dict[str, Any]] = {
    "natural": {"about": "no grading: removes any earlier look"},
    "cinematic": {"lift": (0.92, 0.97, 1.06), "gamma": (1.0, 1.0, 1.0), "gain": (1.12, 1.0, 0.88), "sat": 1.05,
                  "glare": ("Fog Glow", 1.2, 0.12, 6), "about": "teal shadows, warm highlights, a touch of glow"},
    "noir": {"lift": (1.0, 1.0, 1.0), "gamma": (0.85, 0.85, 0.85), "gain": (1.2, 1.2, 1.2), "sat": 0.05,
             "about": "black and white with hard contrast"},
    "vintage": {"lift": (1.05, 1.02, 0.95), "gamma": (1.0, 1.0, 1.0), "gain": (1.05, 0.98, 0.85), "sat": 0.7,
                "about": "warm, faded, lifted blacks"},
    "warm": {"lift": (1.0, 1.0, 1.0), "gamma": (1.0, 1.0, 1.0), "gain": (1.1, 1.0, 0.88), "sat": 1.0, "about": "warm tint"},
    "cold": {"lift": (0.95, 0.98, 1.04), "gamma": (1.0, 1.0, 1.0), "gain": (0.9, 0.98, 1.12), "sat": 0.95, "about": "cold blue tint"},
    "vivid": {"lift": (1.0, 1.0, 1.0), "gamma": (0.95, 0.95, 0.95), "gain": (1.05, 1.05, 1.05), "sat": 1.35,
              "about": "strong, saturated colour"},
    "neon_glow": {"lift": (1.0, 1.0, 1.0), "gamma": (1.0, 1.0, 1.0), "gain": (1.0, 1.0, 1.0), "sat": 1.3,
                  "glare": ("Bloom", 0.6, 1.0, 8), "about": "bright parts bloom into a glow"},
    "dreamy": {"lift": (1.02, 1.02, 1.02), "gamma": (1.0, 1.0, 1.0), "gain": (1.0, 1.0, 1.0), "sat": 0.9,
               "glare": ("Fog Glow", 0.5, 0.6, 7), "about": "soft haze around bright parts"},
}


def _socket(node, name: str, kind: Optional[str] = None):
    for sock in node.inputs:
        if sock.name == name and (kind is None or sock.type == kind):
            return sock
    return None


def _set(node, name: str, value: Any, kind: Optional[str] = None) -> bool:
    sock = _socket(node, name, kind)
    if sock is None:
        return False
    try:
        sock.default_value = value
        return True
    except Exception:
        return False


class LookMutator:
    """Grading, lens effects and contact sheets."""

    @classmethod
    def set_look(cls, preset: str = "cinematic", strength: float = 1.0) -> Dict[str, Any]:
        key = str(preset or "cinematic").strip().lower()
        if key not in LOOKS:
            raise ModelingError(f"preset must be one of {sorted(LOOKS)}.")
        try:
            amount = max(0.0, min(2.0, float(strength)))
        except (TypeError, ValueError):
            raise ModelingError("strength must be a number between 0 and 2.")
        scn = bpy.context.scene
        old = bpy.data.node_groups.get(GROUP_NAME)
        if old is not None:
            scn.compositing_node_group = None
            bpy.data.node_groups.remove(old)
        if key == "natural":
            push_undo_step("AI: Look natural")
            return {"preset": key, "about": LOOKS[key]["about"], "applied": []}
        look = LOOKS[key]
        tree = bpy.data.node_groups.new(GROUP_NAME, "CompositorNodeTree")
        tree.interface.new_socket("Image", in_out="OUTPUT", socket_type="NodeSocketColor")
        nodes, links = tree.nodes, tree.links
        source = nodes.new("CompositorNodeRLayers")
        balance = nodes.new("CompositorNodeColorBalance")
        sink = nodes.new("NodeGroupOutput")
        applied = []

        def mix(triple):  # blend a multiplier triple toward 1.0 by strength
            return tuple(1.0 + (v - 1.0) * amount for v in triple) + (1.0,)

        for name, values in (("Lift", look.get("lift")), ("Gamma", look.get("gamma")), ("Gain", look.get("gain"))):
            if values and _set(balance, name, mix(values), "RGBA"):
                applied.append(name.lower())
        links.new(source.outputs["Image"], balance.inputs["Image"])
        last = balance.outputs["Image"]
        if "sat" in look:
            try:
                hue = nodes.new("CompositorNodeHueSat")
                if _set(hue, "Saturation", 1.0 + (look["sat"] - 1.0) * amount):
                    applied.append("saturation")
                links.new(last, hue.inputs["Image"])
                last = hue.outputs["Image"]
            except Exception:
                pass
        if "glare" in look:
            try:
                glare = nodes.new("CompositorNodeGlare")
                kind, threshold, glow, size = look["glare"]
                for candidate in (kind, kind.upper().replace(" ", "_")):
                    if _set(glare, "Type", candidate):
                        break
                _set(glare, "Threshold", threshold)
                _set(glare, "Strength", glow * amount)
                _set(glare, "Size", size)
                links.new(last, glare.inputs["Image"])
                last = glare.outputs["Image"]
                applied.append("glow")
            except Exception:
                pass
        links.new(last, sink.inputs[0])
        scn.compositing_node_group = tree
        push_undo_step(f"AI: Look {key}")
        return {"preset": key, "about": look["about"], "applied": applied, "strength": amount,
                "note": "applies to render_image, render_animation and render_contact_sheet, not to the viewport"}

    @classmethod
    def camera_settings(cls, f_stop: Any = None, focus_object: Any = None, focus_distance: Any = None,
                        rack_focus_to: Any = None, motion_blur: Any = None, shutter: Any = None) -> Dict[str, Any]:
        scn = bpy.context.scene
        cam_obj = bpy.data.objects.get(CAMERA_NAME) or scn.camera
        if cam_obj is None or cam_obj.type != "CAMERA":
            raise ModelingError("There is no camera yet. Call camera_move first.")
        cam = cam_obj.data
        report: Dict[str, Any] = {"camera": cam_obj.name}
        if f_stop is not None:
            try:
                stop = float(f_stop)
            except (TypeError, ValueError):
                raise ModelingError("f_stop must be a number such as 1.8 or 5.6.")
            if not (0.5 <= stop <= 32.0):
                raise ModelingError("f_stop must be between 0.5 and 32 (small number = strong blur).")
            cam.dof.use_dof = True
            cam.dof.aperture_fstop = stop
            report["f_stop"] = stop
        if focus_object is not None:
            obj = bpy.data.objects.get(str(focus_object).strip())
            if obj is None:
                raise ModelingError(f"Object '{focus_object}' not found.")
            cam.dof.use_dof = True
            cam.dof.focus_object = obj
            report["focus_object"] = obj.name
        if focus_distance is not None:
            try:
                dist = float(focus_distance)
            except (TypeError, ValueError):
                raise ModelingError("focus_distance must be a number of meters.")
            if dist <= 0:
                raise ModelingError("focus_distance must be positive.")
            cam.dof.use_dof = True
            cam.dof.focus_object = None
            cam.dof.focus_distance = dist
            report["focus_distance"] = dist
        if rack_focus_to is not None:
            first = cam.dof.focus_object or (bpy.data.objects.get(str(focus_object).strip()) if focus_object else None)
            second = bpy.data.objects.get(str(rack_focus_to).strip())
            if second is None:
                raise ModelingError(f"Object '{rack_focus_to}' not found.")
            if first is None:
                raise ModelingError("rack_focus_to needs focus_object (where the focus starts).")
            cam.dof.use_dof = True
            cam.dof.focus_object = None
            start_f, end_f = scn.frame_start, scn.frame_end
            distances = []
            for frame, obj in ((start_f, first), (end_f, second)):
                scn.frame_set(frame)
                distances.append((cam_obj.matrix_world.translation - obj.matrix_world.translation).length)
            scn.frame_set(start_f)
            cam.animation_data_create()
            for frame, dist in ((start_f, distances[0]), (end_f, distances[1])):
                cam.dof.focus_distance = dist
                cam.dof.keyframe_insert("focus_distance", frame=frame)
            report["rack_focus"] = {"from": first.name, "to": second.name, "meters": [round(v, 2) for v in distances]}
        if motion_blur is not None:
            state = bool(motion_blur)
            scn.render.use_motion_blur = state
            if shutter is not None:
                try:
                    scn.render.motion_blur_shutter = max(0.01, min(2.0, float(shutter)))
                except (TypeError, ValueError):
                    raise ModelingError("shutter must be a number such as 0.5.")
            report["motion_blur"] = {"on": state, "shutter": round(scn.render.motion_blur_shutter, 3)}
        if len(report) == 1:
            raise ModelingError("Give at least one of f_stop, focus_object, focus_distance, rack_focus_to, motion_blur.")
        push_undo_step("AI: Camera settings")
        return report

    @classmethod
    def render_contact_sheet(cls, export_dir: str, filename: str = "sheet", frames: int = 4, width: int = 480,
                             height: int = 270, samples: int = 8) -> Dict[str, Any]:
        import numpy as np

        stem = _stem(filename, "sheet")
        try:
            count = int(frames)
        except (TypeError, ValueError):
            raise ModelingError("frames must be a whole number between 2 and 9.")
        if not (2 <= count <= 9):
            raise ModelingError("frames must be between 2 and 9.")
        if not (64 <= int(width) <= 960 and 64 <= int(height) <= 540):
            raise ModelingError("width must be 64-960 and height 64-540 (each tile).")
        w, h = int(width), int(height)
        folder = Path(export_dir).expanduser()
        folder.mkdir(parents=True, exist_ok=True)
        scn, saved = CinemaMutator._render_setup(w, h, samples)
        tiles = []
        first, last = saved["start"], saved["end"]
        picks = [round(first + (last - first) * i / (count - 1)) for i in range(count)]
        temp_files = []
        try:
            for i, frame in enumerate(picks):
                scn.frame_set(frame)
                tmp = folder / f"_{stem}_tile{i}.png"
                CinemaMutator._write_still(scn, tmp)
                temp_files.append(tmp)
                img = bpy.data.images.load(str(tmp))
                buf = np.empty(w * h * 4, dtype=np.float32)
                img.pixels.foreach_get(buf)
                tiles.append(buf.reshape(h, w, 4).copy())
                bpy.data.images.remove(img)
        finally:
            CinemaMutator._render_restore(scn, saved)
        cols = math.ceil(math.sqrt(count))
        rows = math.ceil(count / cols)
        sheet = np.zeros((rows * h, cols * w, 4), dtype=np.float32)
        sheet[..., 3] = 1.0
        for i, tile in enumerate(tiles):
            row_from_top, col = divmod(i, cols)
            y0 = (rows - 1 - row_from_top) * h        # image rows run bottom to top
            sheet[y0:y0 + h, col * w:(col + 1) * w] = tile
        path = folder / f"{stem}.png"
        out = bpy.data.images.new(f"{stem}_sheet", cols * w, rows * h, alpha=False)
        out.pixels.foreach_set(sheet.ravel())
        out.filepath_raw = str(path)
        out.file_format = "PNG"
        out.save()
        bpy.data.images.remove(out)
        for tmp in temp_files:
            tmp.unlink(missing_ok=True)
        return {"path": str(path), "filename": path.name, "frames": picks, "tiles": [cols, rows], "width": cols * w,
                "height": rows * h, "bytes": path.stat().st_size}
