"""Text or image to 3D through a service the USER configures (a trained generator such as Hunyuan3D, TRELLIS or Meshy).

The add-on does not bundle or choose a generator. ``BLENDER_COPILOT_3D_URL`` (and optionally
``BLENDER_COPILOT_3D_KEY``) point at an HTTP endpoint that follows a tiny contract (docs/GENERATE_3D.md):

    POST {"prompt": "...", "image_base64": "..."(optional), "seed": 1(optional), "texture": true}
      -> the .glb bytes, or {"glb_base64": "..."}, or {"glb_url": "https://..."}

The URL never comes from the model, only from the environment, so an agent cannot point the add-on at an arbitrary
address. The network rules of the add-on apply: a non-local endpoint needs Blender's online access. The result is saved
into the export folder, imported, scaled to the requested height and put on the ground at the origin.
"""

import base64
import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List

import bpy
from mathutils import Vector

from adapter.mutators.cinema_mutator import _stem
from adapter.mutators.modeling_mutator import ModelingError
from adapter.mutators.undo_manager import push_undo_step
from agent.http_client import HttpClient, HttpConnectionError, HttpError, HttpTimeoutError
from core.config import is_network_allowed

URL_ENV = "BLENDER_COPILOT_3D_URL"
KEY_ENV = "BLENDER_COPILOT_3D_KEY"
MAX_BYTES = 80 * 1024 * 1024
IMAGE_RX = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_\-]{0,60}\.(png|jpg|jpeg)$", re.I)


def _read_all(response, limit: int = MAX_BYTES) -> bytes:
    chunks, size = [], 0
    for chunk in response:
        size += len(chunk)
        if size > limit:
            raise ModelingError(f"The service sent more than {limit // (1024 * 1024)} MB; refused.")
        chunks.append(chunk)
    return b"".join(chunks)


def _slug(text: str) -> str:
    words = re.sub(r"[^A-Za-z0-9]+", "_", text).strip("_")[:40]
    return words or "generated"


class GenerateMutator:
    """Call the configured generator and bring the model into the scene."""

    @classmethod
    def generate_3d(cls, export_dir: str, prompt: Any = "", name: Any = None, image_file: Any = None, height: Any = 1.0,
                    seed: Any = None, texture: Any = True, timeout: Any = 300.0) -> Dict[str, Any]:
        url = os.environ.get(URL_ENV, "").strip()
        if not url:
            raise ModelingError(
                f"No 3D generator is configured. Set {URL_ENV} (and optionally {KEY_ENV}) to an endpoint that follows the "
                "contract in docs/GENERATE_3D.md, for example a local Hunyuan3D or TRELLIS server, then restart Blender. "
                "Until then, model with the modeling tools or import a .glb with import_asset.")
        if not url.lower().startswith(("http://", "https://")):
            raise ModelingError(f"{URL_ENV} must start with http:// or https://.")
        text = str(prompt or "").strip()
        if not text and not image_file:
            raise ModelingError("Give a prompt describing the object, or an image_file from the export folder.")
        if len(text) > 800:
            raise ModelingError("The prompt is too long (800 characters at most).")
        try:
            meters = float(height)
            wait = float(timeout)
        except (TypeError, ValueError):
            raise ModelingError("height and timeout must be numbers.")
        if not (0.02 <= meters <= 200.0):
            raise ModelingError("height must be between 0.02 and 200 meters.")
        if not (5.0 <= wait <= 1800.0):
            raise ModelingError("timeout must be between 5 and 1800 seconds.")
        folder = Path(export_dir).expanduser()
        payload: Dict[str, Any] = {"prompt": text, "texture": bool(texture)}
        if seed is not None:
            try:
                payload["seed"] = int(seed)
            except (TypeError, ValueError):
                raise ModelingError("seed must be a whole number.")
        if image_file:
            iname = str(image_file).strip()
            if not IMAGE_RX.match(iname) or not (folder / iname).exists():
                raise ModelingError("image_file must be a plain .png or .jpg name that exists in the export folder.")
            payload["image_base64"] = base64.b64encode((folder / iname).read_bytes()).decode("ascii")
        allowed, why = is_network_allowed(url, bool(getattr(bpy.app, "online_access", True)))
        if not allowed:
            raise ModelingError(why)

        headers = {"Accept": "model/gltf-binary, application/json"}
        key = os.environ.get(KEY_ENV, "").strip()
        if key:
            headers["Authorization"] = f"Bearer {key}"
        client = HttpClient(timeout=wait)
        try:
            data = _read_all(client.post(url, json.dumps(payload).encode("utf-8"), headers=headers, timeout=wait))
            glb = cls._extract_glb(data, client, headers, wait)
        except HttpError as err:
            raise ModelingError(f"The 3D service answered HTTP {err.status_code}: {(err.body_snippet or err.message)[:200]}")
        except HttpTimeoutError:
            raise ModelingError(f"The 3D service did not answer within {wait:.0f} s; raise timeout or check the server.")
        except HttpConnectionError as err:
            raise ModelingError(f"Cannot reach the 3D service at the configured address: {err}")

        stem = _stem(name or _slug(text or "generated"), "generated")
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"{stem}.glb"
        path.write_bytes(glb)
        return cls._import(path, stem, meters)

    @classmethod
    def _extract_glb(cls, data: bytes, client: HttpClient, headers: Dict[str, str], wait: float) -> bytes:
        if data[:4] == b"glTF":
            return data
        try:
            doc = json.loads(data.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            raise ModelingError("The service answered with something that is neither a .glb nor JSON.")
        if isinstance(doc, dict) and doc.get("error"):
            raise ModelingError(f"The 3D service reported an error: {str(doc['error'])[:200]}")
        if isinstance(doc, dict) and doc.get("glb_base64"):
            try:
                raw = base64.b64decode(doc["glb_base64"], validate=False)
            except ValueError:
                raise ModelingError("glb_base64 is not valid base64.")
        elif isinstance(doc, dict) and doc.get("glb_url"):
            link = str(doc["glb_url"])
            if not link.lower().startswith(("http://", "https://")):
                raise ModelingError("glb_url must be an http(s) address.")
            allowed, why = is_network_allowed(link, bool(getattr(bpy.app, "online_access", True)))
            if not allowed:
                raise ModelingError(why)
            raw = _read_all(client.get(link, headers={"Accept": "model/gltf-binary, application/octet-stream"}, timeout=wait))
        else:
            raise ModelingError("The JSON answer has none of glb_base64 or glb_url.")
        if raw[:4] != b"glTF":
            raise ModelingError("The downloaded file is not a binary glTF (.glb).")
        return raw

    @classmethod
    def _import(cls, path: Path, stem: str, meters: float) -> Dict[str, Any]:
        before = set(bpy.data.objects)
        result = bpy.ops.import_scene.gltf(filepath=str(path))
        if "FINISHED" not in result:
            raise ModelingError("Blender could not import the generated .glb.")
        new = [o for o in bpy.data.objects if o not in before]
        meshes = [o for o in new if o.type == "MESH"]
        if not meshes:
            for o in new:
                bpy.data.objects.remove(o, do_unlink=True)
            raise ModelingError("The generated file contains no mesh.")
        bpy.context.view_layer.update()
        pts = [o.matrix_world @ Vector(c) for o in meshes for c in o.bound_box]
        lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
        hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
        tall = max(hi.z - lo.z, 1e-6)
        factor = meters / tall
        root = bpy.data.objects.new(stem, None)
        root.empty_display_type = "PLAIN_AXES"
        bpy.context.scene.collection.objects.link(root)
        tops = [o for o in new if o.parent is None]
        for obj in tops:
            keep = obj.matrix_world.copy()
            obj.parent = root
            obj.matrix_parent_inverse = root.matrix_world.inverted()
            obj.matrix_world = keep
        # stand the model on the ground at the origin, scaled to the requested height
        root.scale = (factor, factor, factor)
        root.location = (-(lo.x + hi.x) / 2 * factor, -(lo.y + hi.y) / 2 * factor, -lo.z * factor)
        bpy.context.view_layer.update()
        depsgraph = bpy.context.evaluated_depsgraph_get()
        tris = 0
        for o in meshes:
            ev = o.evaluated_get(depsgraph)
            mesh = ev.to_mesh()
            mesh.calc_loop_triangles()
            tris += len(mesh.loop_triangles)
            ev.to_mesh_clear()
        push_undo_step(f"AI: Generate 3D {stem}")
        out = {"root": root.name, "meshes": [m.name for m in meshes], "triangle_count": tris, "path": str(path),
               "bytes": path.stat().st_size, "height_m": round(meters, 3),
               "width_m": round((hi.x - lo.x) * factor, 3), "depth_m": round((hi.y - lo.y) * factor, 3),
               "scale_applied": round(factor, 5)}
        if tris > 60000:
            out["warning"] = f"{tris} triangles is heavy for a game asset; consider decimating it (add_shape_modifier DECIMATE)."
        return out
