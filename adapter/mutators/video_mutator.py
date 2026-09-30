"""Video mutators: join rendered clips with transitions and speed changes (Blender's own video editor), and render a
whole shot list in one call.

Everything stays inside the export folder and uses plain file names; the edit runs in a throw-away scene so the user's
scene is never touched. No ffmpeg command line: Blender writes the final MP4 itself.
"""

import math
import re
from pathlib import Path
from typing import Any, Dict, List

import bpy

from adapter.mutators.cinema_mutator import CinemaMutator, ENVIRONMENTS, _stem
from adapter.mutators.look_mutator import LOOKS, LookMutator
from adapter.mutators.modeling_mutator import ModelingError, as_list
from core.camera_paths import PRESETS
from core.soundtrack import MOODS, write_wav

CLIP_RX = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_\-]{0,60}\.mp4$")
SOUND_RX = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_\-]{0,60}\.(wav|mp3|ogg|flac)$", re.I)
TRANSITIONS = {"cut": None, "crossfade": "CROSS", "wipe": "WIPE"}
MAX_CLIPS = 12
MAX_SHOTS = 8
MAX_TOTAL_FRAMES = 1800
SHOT_KEYS = {"preset", "duration", "object_names", "environment", "look", "azimuth", "elevation", "distance",
             "focal_length", "follow", "intensity", "angle", "fps", "start_frame"}


def _strips(editor):
    return editor.strips if hasattr(editor, "strips") else editor.sequences


class VideoMutator:
    """Editing and multi-shot rendering."""

    @classmethod
    def make_soundtrack(cls, export_dir: str, mood: str = "calm", seconds: float = 20.0, filename: Any = None,
                        seed: int = 1) -> Dict[str, Any]:
        key = str(mood or "calm").strip().lower()
        if key not in MOODS:
            raise ModelingError(f"mood must be one of {sorted(MOODS)}.")
        try:
            length = float(seconds)
        except (TypeError, ValueError):
            raise ModelingError("seconds must be a number.")
        if not (1.0 <= length <= 90.0):
            raise ModelingError("seconds must be between 1 and 90.")
        stem = _stem(filename or f"music_{key}", "music")
        folder = Path(export_dir).expanduser()
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"{stem}.wav"
        info = write_wav(str(path), key, length, int(seed))
        return {"path": str(path), "filename": path.name, "mood": key, "about": MOODS[key], "seconds": info["seconds"],
                "bytes": path.stat().st_size, "use": "pass the file name as soundtrack to edit_video, or use render_shots with music"}

    @classmethod
    def edit_video(cls, export_dir: str, filename: str, clips: Any, transition: str = "cut",
                   transition_seconds: float = 0.5, soundtrack: Any = None, music_volume: float = 0.6) -> Dict[str, Any]:
        import time

        stem = _stem(filename, "film")
        kind = str(transition or "cut").strip().lower()
        if kind not in TRANSITIONS:
            raise ModelingError(f"transition must be one of {sorted(TRANSITIONS)}.")
        clips = as_list(clips)
        if not isinstance(clips, list) or not (1 <= len(clips) <= MAX_CLIPS):
            raise ModelingError(f"clips must be a list of 1 to {MAX_CLIPS} clip names, or {{'file': name, 'speed': 0.5}}.")
        folder = Path(export_dir).expanduser()
        items = []
        for entry in clips:
            spec = entry if isinstance(entry, dict) else {"file": entry}
            name = str(spec.get("file", "")).strip()
            if not name.lower().endswith(".mp4"):
                name += ".mp4"
            if not CLIP_RX.match(name):
                raise ModelingError(f"'{name}' is not a plain clip name (letters, digits, _ -; .mp4).")
            if not (folder / name).exists():
                raise ModelingError(f"Clip '{name}' is not in the export folder. Render it first with render_animation.")
            try:
                speed = float(spec.get("speed", 1.0))
            except (TypeError, ValueError):
                raise ModelingError("speed must be a number: 0.5 is slow motion, 2 is fast forward.")
            if not (0.1 <= speed <= 4.0):
                raise ModelingError("speed must be between 0.1 and 4.")
            items.append((name, speed))
        try:
            fade = float(transition_seconds)
        except (TypeError, ValueError):
            raise ModelingError("transition_seconds must be a number.")
        if not (0.1 <= fade <= 3.0):
            raise ModelingError("transition_seconds must be between 0.1 and 3.")

        sound_path = None
        if soundtrack:
            sname = str(soundtrack).strip()
            if not SOUND_RX.match(sname):
                raise ModelingError("soundtrack must be a plain audio file name (.wav, .mp3, .ogg, .flac) in the export folder.")
            if not (folder / sname).exists():
                raise ModelingError(f"Sound '{sname}' is not in the export folder. Make one with make_soundtrack.")
            sound_path = folder / sname
            try:
                volume = float(music_volume)
            except (TypeError, ValueError):
                raise ModelingError("music_volume must be a number between 0.05 and 1.")
            if not (0.05 <= volume <= 1.0):
                raise ModelingError("music_volume must be between 0.05 and 1.")
        edit = bpy.data.scenes.new("AI_Edit")
        try:
            edit.sequence_editor_create()
            coll = _strips(edit.sequence_editor)
            cursor, visible, total_frames = 1, [], 0
            width = height = fps = None
            for i, (name, speed) in enumerate(items):
                channel = 1 + (i % 2) if kind != "cut" else 1
                movie = coll.new_movie(f"clip{i}", str(folder / name), channel, cursor)
                if width is None:
                    width, height, fps = movie.elements[0].orig_width, movie.elements[0].orig_height, movie.fps or 24.0
                length = movie.frame_final_duration
                top = movie
                if abs(speed - 1.0) > 1e-6:
                    # the speed effect takes its length from the strip under it: stretch or shrink that strip first
                    length = max(2, int(round(length / speed)))
                    movie.frame_final_duration = length
                    top = coll.new_effect(f"speed{i}", "SPEED", channel + 4, cursor, input1=movie)
                    top.speed_control = "MULTIPLY"
                    top.speed_factor = speed
                end = cursor + length
                if i > 0 and kind != "cut":
                    overlap = min(int(round(fade * fps)), length - 1, visible[-1][1] - visible[-1][0] - 1)
                    # start this clip early so the two overlap, then blend them
                    shift = end - length - overlap
                    movie.frame_start = shift
                    if top is not movie:
                        top.frame_start = shift
                    end = shift + length
                    coll.new_effect(f"x{i}", TRANSITIONS[kind], 3, shift, input1=visible[-1][2], input2=top)
                    visible.append((shift, end, top))
                else:
                    visible.append((cursor, end, top))
                cursor = end
                total_frames = max(total_frames, end - 1)
            if sound_path is not None:
                music = coll.new_sound("music", str(sound_path), 6, 1)
                music.volume = volume
                if music.frame_final_duration > total_frames:
                    music.frame_final_duration = total_frames
            edit.frame_start, edit.frame_end = 1, total_frames
            if total_frames > MAX_TOTAL_FRAMES:
                raise ModelingError(f"The edit would be {total_frames} frames; the limit is {MAX_TOTAL_FRAMES}.")
            r = edit.render
            r.resolution_x, r.resolution_y, r.resolution_percentage = width, height, 100
            r.fps = int(round(fps))
            r.use_sequencer = True
            if hasattr(r.image_settings, "media_type"):
                r.image_settings.media_type = "VIDEO"
            r.image_settings.file_format = "FFMPEG"
            r.ffmpeg.format = "MPEG4"
            r.ffmpeg.codec = "H264"
            if sound_path is not None:
                r.ffmpeg.audio_codec = "AAC"
                r.ffmpeg.audio_bitrate = 160
            target = folder / f"{stem}.mp4"
            r.filepath = str(target)
            started = time.time()
            bpy.ops.render.render(animation=True, scene=edit.name)
            if not target.exists():
                raise ModelingError("Blender did not write the edited video.")
        finally:
            bpy.data.scenes.remove(edit)
        return {"path": str(target), "filename": target.name, "clips": [n for n, _ in items], "frames": total_frames,
                "fps": int(round(fps)), "seconds": round(total_frames / fps, 2), "width": width, "height": height,
                "transition": kind, "soundtrack": sound_path.name if sound_path else None, "bytes": target.stat().st_size, "render_seconds": round(time.time() - started, 1)}

    @classmethod
    def render_shots(cls, export_dir: str, filename: str, shots: Any, transition: str = "crossfade",
                     transition_seconds: float = 0.5, width: int = 960, height: int = 540, samples: int = 12,
                     music: Any = None, music_volume: float = 0.6, continuous: bool = True) -> Dict[str, Any]:
        stem = _stem(filename, "film")
        mood = str(music).strip().lower() if music else None
        if mood and mood not in MOODS and not SOUND_RX.match(str(music).strip()):
            raise ModelingError(f"music must be a mood ({sorted(MOODS)}) or an audio file name in the export folder.")
        shots = as_list(shots)
        if not isinstance(shots, list) or not (1 <= len(shots) <= MAX_SHOTS):
            raise ModelingError(f"shots must be a list of 1 to {MAX_SHOTS} shot objects.")
        plan = []
        total = 0.0
        for n, shot in enumerate(shots, 1):
            if not isinstance(shot, dict):
                raise ModelingError(f"shot {n} must be an object such as {{\"preset\": \"orbit\", \"duration\": 3}}.")
            extra = set(shot) - SHOT_KEYS
            if extra:
                raise ModelingError(f"shot {n}: unknown keys {sorted(extra)}. Allowed: {sorted(SHOT_KEYS)}.")
            if shot.get("preset") not in PRESETS:
                raise ModelingError(f"shot {n}: preset must be one of {sorted(PRESETS)}.")
            if shot.get("environment") is not None and shot["environment"] not in ENVIRONMENTS:
                raise ModelingError(f"shot {n}: environment must be one of {sorted(ENVIRONMENTS)}.")
            if shot.get("look") is not None and shot["look"] not in LOOKS:
                raise ModelingError(f"shot {n}: look must be one of {sorted(LOOKS)}.")
            total += float(shot.get("duration", 3.0))
            plan.append(shot)
        if total > 75:
            raise ModelingError("The shots add up to more than 75 seconds; use fewer or shorter shots.")
        clips, details = [], []
        offset = 1
        try:
            for n, shot in enumerate(plan, 1):
                if shot.get("environment"):
                    CinemaMutator.set_environment(preset=shot["environment"])
                if shot.get("look"):
                    LookMutator.set_look(preset=shot["look"])
                cam_args = {k: v for k, v in shot.items() if k not in ("environment", "look")}
                if continuous and "start_frame" not in cam_args:
                    cam_args["start_frame"] = offset          # each shot carries on where the last one stopped
                cam = CinemaMutator.camera_move(**cam_args)
                offset += cam["frames"]
                clip = CinemaMutator.render_animation(export_dir=export_dir, filename=f"{stem}_shot{n}", width=width,
                                                      height=height, samples=samples)
                clips.append(f"{stem}_shot{n}.mp4")
                details.append({"shot": n, "preset": shot["preset"], "seconds": cam["seconds"], "frames": cam["frames"],
                                "render_seconds": clip["render_seconds"]})
            soundtrack = None
            if mood in MOODS:
                # the film lasts the sum of the shots minus the overlaps; the edit trims any excess
                fade_frames = int(round(float(transition_seconds) * 24))
                total_seconds = sum(d["seconds"] for d in details) - (len(details) - 1) * fade_frames / 24.0
                soundtrack = f"{stem}_music.wav"
                cls.make_soundtrack(export_dir, mood, min(90.0, max(1.0, total_seconds + 1.0)), stem + "_music")
            elif mood:
                soundtrack = str(music).strip()
            final = cls.edit_video(export_dir, stem, clips, transition=transition, transition_seconds=transition_seconds,
                                   soundtrack=soundtrack, music_volume=music_volume)
        finally:
            folder = Path(export_dir).expanduser()
            for n in range(1, len(plan) + 1):           # the per-shot files were only material for the edit
                (folder / f"{stem}_shot{n}.mp4").unlink(missing_ok=True)
                (folder / f"{stem}_shot{n}_preview.png").unlink(missing_ok=True)
            (folder / f"{stem}_music.wav").unlink(missing_ok=True)      # the mood bed was only material for the edit
        final["shots"] = details
        return final
