"""Texture mutators: UV unwrapping and baking procedural materials into an image texture.

A game engine cannot read Blender's shader nodes: a glTF export keeps only the base colour of a procedural material. Baking
paints the look of the material into an image over the UV map, so the exported model carries a real texture.
"""

from contextlib import contextmanager
from typing import Any, Dict, List

import bmesh
import bpy

from adapter.mutators.cinema_mutator import _scene_meshes
from adapter.mutators.modeling_mutator import ModelingError, as_list
from adapter.mutators.undo_manager import push_undo_step

METHODS = ("smart", "cube")
MIN_RESOLUTION, MAX_RESOLUTION = 64, 4096
IMAGE_TYPES = {"TEX_IMAGE", "TEX_ENVIRONMENT"}


@contextmanager
def _isolated_selection(obj: "bpy.types.Object"):
    """Make ``obj`` the only selected, active object in object mode; restore afterwards."""
    view_layer = bpy.context.view_layer
    previous_active = view_layer.objects.active
    previous = [(o, o.select_get()) for o in bpy.context.scene.objects]
    if bpy.context.object is not None and bpy.context.object.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    for o, _ in previous:
        o.select_set(False)
    obj.select_set(True)
    view_layer.objects.active = obj
    try:
        yield
    finally:
        for o, was in previous:
            try:
                o.select_set(was)
            except Exception:
                pass
        view_layer.objects.active = previous_active


def _has_procedural(obj: "bpy.types.Object") -> bool:
    for slot in obj.material_slots:
        tree = getattr(slot.material, "node_tree", None) if slot.material else None
        if tree and any(n.type.startswith("TEX_") and n.type not in IMAGE_TYPES for n in tree.nodes):
            return True
    return False


def _uv_report(obj: "bpy.types.Object") -> Dict[str, Any]:
    bm = bmesh.new()
    try:
        bm.from_mesh(obj.data)
        layer = bm.loops.layers.uv.active
        if layer is None:
            return {"uv_layers": 0}
        area = 0.0
        outside = False
        for face in bm.faces:
            uvs = [loop[layer].uv for loop in face.loops]
            for uv in uvs:
                if uv.x < -1e-4 or uv.x > 1.0001 or uv.y < -1e-4 or uv.y > 1.0001:
                    outside = True
            n = len(uvs)
            area += abs(sum(uvs[i].x * uvs[(i + 1) % n].y - uvs[(i + 1) % n].x * uvs[i].y for i in range(n))) / 2.0
        return {"uv_layers": len(obj.data.uv_layers), "uv_coverage": round(min(area, 1.0), 3), "uv_in_bounds": not outside}
    finally:
        bm.free()


def _unwrap(obj: "bpy.types.Object", method: str, angle_limit: float, margin: float) -> None:
    with _isolated_selection(obj):
        bpy.ops.object.mode_set(mode="EDIT")
        try:
            bpy.ops.mesh.select_all(action="SELECT")
            if method == "cube":
                bpy.ops.uv.cube_project(cube_size=1.0)
            else:
                bpy.ops.uv.smart_project(angle_limit=angle_limit, island_margin=margin)
        finally:
            bpy.ops.object.mode_set(mode="OBJECT")


def _principled_values(obj: "bpy.types.Object") -> Dict[str, float]:
    for slot in obj.material_slots:
        tree = getattr(slot.material, "node_tree", None) if slot.material else None
        node = next((n for n in tree.nodes if n.type == "BSDF_PRINCIPLED"), None) if tree else None
        if node is not None:
            return {"roughness": float(node.inputs["Roughness"].default_value), "metallic": float(node.inputs["Metallic"].default_value)}
    return {"roughness": 0.7, "metallic": 0.0}


class TextureMutator:
    @classmethod
    def unwrap_uv(cls, object_names: Any = None, method: Any = "smart", angle_limit: Any = 66.0, margin: Any = 0.02) -> Dict[str, Any]:
        """Give meshes a UV map (replacing the active one): smart project (angle based islands) or cube project."""
        key = str(method or "smart").strip().lower()
        if key not in METHODS:
            raise ModelingError(f"method must be one of {list(METHODS)}.")
        try:
            angle = float(angle_limit)
            gap = float(margin)
        except (TypeError, ValueError):
            raise ModelingError("angle_limit (degrees) and margin must be numbers.")
        if not (1.0 <= angle <= 89.0):
            raise ModelingError("angle_limit must be between 1 and 89 degrees.")
        if not (0.0 <= gap <= 0.5):
            raise ModelingError("margin must be between 0 and 0.5.")
        objs = [o for o in _scene_meshes(as_list(object_names) if object_names else None) if o.type == "MESH"]
        if not objs:
            raise ModelingError("There is no mesh to unwrap. Name the model in object_names.")
        done: List[Dict[str, Any]] = []
        for obj in objs:
            _unwrap(obj, key, angle * 3.141592653589793 / 180.0, gap)
            done.append({"object": obj.name, **_uv_report(obj)})
        push_undo_step(f"AI: Unwrap UV ({len(done)} objects)")
        return {"method": key, "unwrapped": done}

    @classmethod
    def bake_material(cls, object_name: str, resolution: Any = 1024, samples: Any = 4) -> Dict[str, Any]:
        """Paint the object's procedural materials into one image and give the object a single image-textured material."""
        obj = bpy.data.objects.get(str(object_name or "").strip())
        if obj is None or obj.type != "MESH":
            raise ModelingError(f"'{object_name}' is not a mesh object in the scene.")
        try:
            size = int(resolution)
            count = int(samples)
        except (TypeError, ValueError):
            raise ModelingError("resolution and samples must be whole numbers.")
        if not (MIN_RESOLUTION <= size <= MAX_RESOLUTION):
            raise ModelingError(f"resolution must be between {MIN_RESOLUTION} and {MAX_RESOLUTION}.")
        if not (1 <= count <= 128):
            raise ModelingError("samples must be between 1 and 128.")
        if obj.data.users > 1:
            raise ModelingError(f"'{obj.name}' shares its mesh with another object; make it single-user before baking.")
        if not any(s.material for s in obj.material_slots):
            raise ModelingError(f"'{obj.name}' has no material to bake. Call set_material first.")
        if not _has_procedural(obj):
            return {"object": obj.name, "baked": False,
                    "reason": "the materials have no procedural texture (flat colours export as they are), nothing to bake",
                    **_uv_report(obj)}
        unwrapped = False
        if not obj.data.uv_layers:
            _unwrap(obj, "smart", 66.0 * 3.141592653589793 / 180.0, 0.02)
            unwrapped = True
        sources = [s.material.name for s in obj.material_slots if s.material]
        values = _principled_values(obj)
        image = bpy.data.images.new(f"{obj.name}_baked", size, size, alpha=False)
        scn = bpy.context.scene
        saved = (scn.render.engine, scn.cycles.samples, scn.cycles.device)
        temp_nodes = []
        metallic_saved = []
        try:
            for slot in obj.material_slots:
                tree = getattr(slot.material, "node_tree", None) if slot.material else None
                if tree is None:
                    continue
                # a fully metallic surface has no diffuse colour (it bakes black): bake the colour as if it were not metal
                for bsdf_node in (n for n in tree.nodes if n.type == "BSDF_PRINCIPLED"):
                    sock = bsdf_node.inputs["Metallic"]
                    if not sock.is_linked:
                        metallic_saved.append((sock, sock.default_value))
                        sock.default_value = 0.0
                node = tree.nodes.new("ShaderNodeTexImage")
                node.image = image
                tree.nodes.active = node
                temp_nodes.append((tree, node))
            scn.render.engine = "CYCLES"
            scn.cycles.samples = count
            scn.cycles.device = "CPU"
            with _isolated_selection(obj):
                result = bpy.ops.object.bake(type="DIFFUSE", pass_filter={"COLOR"}, margin=4, use_clear=True)
            if "FINISHED" not in result:
                raise ModelingError("Blender could not bake the material.")
        except Exception:
            bpy.data.images.remove(image)
            raise
        finally:
            for sock, value in metallic_saved:
                sock.default_value = value
            for tree, node in temp_nodes:
                try:
                    tree.nodes.remove(node)
                except Exception:
                    pass
            scn.render.engine, scn.cycles.samples, scn.cycles.device = saved
        image.pack()
        mat = bpy.data.materials.new(f"{obj.name}_Baked")
        mat.use_nodes = True
        tree = mat.node_tree
        bsdf = next((n for n in tree.nodes if n.type == "BSDF_PRINCIPLED"), None) or tree.nodes.new("ShaderNodeBsdfPrincipled")
        out = next((n for n in tree.nodes if n.type == "OUTPUT_MATERIAL"), None) or tree.nodes.new("ShaderNodeOutputMaterial")
        if not out.inputs["Surface"].is_linked:
            tree.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
        tex = tree.nodes.new("ShaderNodeTexImage")
        tex.image = image
        tree.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
        bsdf.inputs["Roughness"].default_value = values["roughness"]
        bsdf.inputs["Metallic"].default_value = values["metallic"]
        obj.data.materials.clear()
        obj.data.materials.append(mat)
        bpy.context.view_layer.update()
        push_undo_step(f"AI: Bake Material ({obj.name})")
        return {"object": obj.name, "baked": True, "material": mat.name, "image": image.name, "resolution": size,
                "source_materials": sources, "unwrapped": unwrapped, "roughness": round(values["roughness"], 3),
                "metallic": round(values["metallic"], 3), **_uv_report(obj)}
