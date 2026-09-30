"""Modeling mutators: build and edit meshes without arbitrary Python (no exec/eval).

Every operation is an allow-listed, bounded, undoable step: create_mesh (own vertices and faces), mesh_edit
(extrude / inset / bevel / subdivide ... on faces picked by normal), join, parent, apply transform, set origin,
and glTF export into a configured folder. Blender Data API and BMesh only; operators are used solely where
Blender offers no data-level equivalent (object join, glTF export).
"""

import math
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import bmesh
import bpy
from mathutils import Euler, Matrix, Vector

from adapter.mutators.undo_manager import push_undo_step

MAX_VERTICES = 20000
MAX_FACES = 40000
MAX_RESULT_VERTICES = 200000
MAX_NAME_LEN = 63
DIRECTION_AXES = {
    "+X": (1, 0, 0), "-X": (-1, 0, 0),
    "+Y": (0, 1, 0), "-Y": (0, -1, 0),
    "+Z": (0, 0, 1), "-Z": (0, 0, -1),
}
FILENAME_RX = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_\-.]{0,80}$")


class ModelingError(ValueError):
    """Bad arguments or an unsupported situation; the message is shown to the agent."""


def _vec3(value: Any, what: str) -> Vector:
    # Some models wrap or stringify the vector: {"item": [0, 0, 1]}, "0, 0, 1". Accept the obvious forms.
    if isinstance(value, dict) and len(value) == 1:
        value = next(iter(value.values()))
    if isinstance(value, str):
        value = [part for part in value.replace(",", " ").split() if part]
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        raise ModelingError(f"{what} must be a list of three numbers, for example [0, 0, 1].")
    try:
        v = [float(x) for x in value]
    except (TypeError, ValueError):
        raise ModelingError(f"{what} must contain numbers only.")
    if not all(math.isfinite(x) for x in v):
        raise ModelingError(f"{what} must be finite numbers.")
    return Vector(v)


def _mesh_object(name: Any) -> "bpy.types.Object":
    if not isinstance(name, str) or not name.strip():
        raise ModelingError("Object name must be a non-empty string.")
    obj = bpy.data.objects.get(name.strip())
    if obj is None:
        raise ModelingError(f"Object '{name}' not found in the scene.")
    if obj.type != "MESH":
        raise ModelingError(f"Object '{name}' is a {obj.type}, not a MESH.")
    return obj


def _unique_mesh(obj: "bpy.types.Object") -> "bpy.types.Mesh":
    mesh = obj.data
    if mesh.users > 1:
        mesh = mesh.copy()
        obj.data = mesh
    return mesh


def _bounds(mesh: "bpy.types.Mesh"):
    if not mesh.vertices:
        return Vector((0, 0, 0)), Vector((0, 0, 0))
    xs = [v.co.x for v in mesh.vertices]
    ys = [v.co.y for v in mesh.vertices]
    zs = [v.co.z for v in mesh.vertices]
    return Vector((min(xs), min(ys), min(zs))), Vector((max(xs), max(ys), max(zs)))


def _link(obj: "bpy.types.Object") -> None:
    collection = bpy.context.collection or bpy.context.scene.collection
    collection.objects.link(obj)


def _summary(obj: "bpy.types.Object") -> Dict[str, Any]:
    mesh = obj.data
    lo, hi = _bounds(mesh)
    dims = (hi - lo) * 1.0
    mesh.calc_loop_triangles()
    return {
        "object_name": obj.name,
        "type": obj.type,
        "exists": bpy.data.objects.get(obj.name) is not None,
        "location": [round(v, 4) for v in obj.location],
        "rotation": [round(v, 4) for v in obj.rotation_euler],
        "scale": [round(v, 4) for v in obj.scale],
        "vertex_count": len(mesh.vertices),
        "face_count": len(mesh.polygons),
        "triangle_count": len(mesh.loop_triangles),
        "local_bounds_min": [round(v, 4) for v in lo],
        "local_bounds_max": [round(v, 4) for v in hi],
        "dimensions": [round(dims.x * obj.scale.x, 4), round(dims.y * obj.scale.y, 4), round(dims.z * obj.scale.z, 4)],
    }


class ModelingMutator:
    # ------------------------------------------------------------------ create_mesh
    @classmethod
    def create_mesh(cls, vertices: Any, faces: Any, name: Optional[str] = None, location: Any = None, rotation: Any = None,
                    scale: Any = None, smooth: bool = False) -> Dict[str, Any]:
        if not isinstance(vertices, list) or not vertices:
            raise ModelingError("vertices must be a non-empty list of [x, y, z] points.")
        if not isinstance(faces, list) or not faces:
            raise ModelingError("faces must be a non-empty list of vertex-index lists.")
        if len(vertices) > MAX_VERTICES or len(faces) > MAX_FACES:
            raise ModelingError(f"Too large: at most {MAX_VERTICES} vertices and {MAX_FACES} faces per call.")
        verts = [tuple(_vec3(v, f"vertices[{i}]")) for i, v in enumerate(vertices)]
        polys: List[tuple] = []
        for i, f in enumerate(faces):
            if not isinstance(f, (list, tuple)) or not 3 <= len(f) <= 8:
                raise ModelingError(f"faces[{i}] must list 3 to 8 vertex indices.")
            try:
                idx = [int(k) for k in f]
            except (TypeError, ValueError):
                raise ModelingError(f"faces[{i}] must contain integer indices.")
            if len(set(idx)) != len(idx):
                raise ModelingError(f"faces[{i}] repeats a vertex index.")
            if min(idx) < 0 or max(idx) >= len(verts):
                raise ModelingError(f"faces[{i}] uses an index outside 0..{len(verts) - 1}.")
            polys.append(tuple(idx))
        base = name.strip()[:MAX_NAME_LEN] if isinstance(name, str) and name.strip() else "Mesh"
        mesh = bpy.data.meshes.new(f"{base}_mesh")
        mesh.from_pydata(verts, [], polys)
        mesh.validate(clean_customdata=False)
        mesh.update()
        if smooth:
            for poly in mesh.polygons:
                poly.use_smooth = True
        obj = bpy.data.objects.new(base, mesh)
        _link(obj)
        if location is not None:
            obj.location = _vec3(location, "location")
        if rotation is not None:
            r = _vec3(rotation, "rotation")
            obj.rotation_euler = Euler((r.x, r.y, r.z), "XYZ")
        if scale is not None:
            obj.scale = _vec3(scale, "scale")
        bpy.context.view_layer.update()
        push_undo_step(f"AI: Create mesh ({obj.name})")
        out = _summary(obj)
        out["created"] = True
        return out

    # ------------------------------------------------------------------ mesh_edit
    OPERATIONS = ("EXTRUDE_FACES", "INSET_FACES", "BEVEL_EDGES", "SUBDIVIDE", "TRIANGULATE", "RECALC_NORMALS",
                  "MERGE_BY_DISTANCE", "SCALE_TO_HEIGHT_TAPER")

    @classmethod
    def _select_faces(cls, bm: "bmesh.types.BMesh", selector: Any) -> List["bmesh.types.BMFace"]:
        if selector in (None, {}, "ALL"):
            return list(bm.faces)
        if not isinstance(selector, dict):
            raise ModelingError("faces selector must be an object like {\"direction\": \"+Z\", \"threshold\": 0.9}.")
        direction = selector.get("direction")
        threshold = float(selector.get("threshold", 0.9))
        if direction is None:
            return list(bm.faces)
        if isinstance(direction, str):
            key = direction.strip().upper()
            if key not in DIRECTION_AXES:
                raise ModelingError(f"direction must be one of {sorted(DIRECTION_AXES)} or a [x, y, z] vector.")
            axis = Vector(DIRECTION_AXES[key])
        else:
            axis = _vec3(direction, "direction")
            if axis.length == 0:
                raise ModelingError("direction must not be a zero vector.")
            axis.normalize()
        bm.faces.ensure_lookup_table()
        picked = [f for f in bm.faces if f.normal.dot(axis) >= threshold]
        return picked

    @classmethod
    def mesh_edit(cls, object_name: str, operation: str, faces: Any = None, distance: Optional[float] = None,
                  thickness: Optional[float] = None, depth: Optional[float] = None, width: Optional[float] = None,
                  segments: Optional[int] = None, cuts: Optional[int] = None, merge_distance: Optional[float] = None,
                  sharp_angle: Optional[float] = None, top_scale: Optional[float] = None) -> Dict[str, Any]:
        op = str(operation or "").strip().upper()
        if op not in cls.OPERATIONS:
            raise ModelingError(f"operation must be one of {list(cls.OPERATIONS)}.")
        obj = _mesh_object(object_name)
        mesh = _unique_mesh(obj)
        bm = bmesh.new()
        try:
            bm.from_mesh(mesh)
            bm.faces.ensure_lookup_table()
            touched = 0
            if op in ("EXTRUDE_FACES", "INSET_FACES"):
                picked = cls._select_faces(bm, faces)
                if not picked:
                    raise ModelingError("No face matches the selector (check direction / threshold).")
                touched = len(picked)
                if op == "EXTRUDE_FACES":
                    dist = float(distance if distance is not None else 0.2)
                    normal = Vector((0, 0, 0))
                    for f in picked:
                        normal += f.normal
                    normal = normal.normalized() if normal.length > 1e-9 else Vector((0, 0, 1))
                    res = bmesh.ops.extrude_face_region(bm, geom=picked)
                    new_verts = [g for g in res["geom"] if isinstance(g, bmesh.types.BMVert)]
                    bmesh.ops.translate(bm, vec=normal * dist, verts=new_verts)
                else:
                    t = float(thickness if thickness is not None else 0.05)
                    if t <= 0:
                        raise ModelingError("thickness must be positive.")
                    bmesh.ops.inset_region(bm, faces=picked, thickness=t, depth=float(depth or 0.0), use_even_offset=True)
            elif op == "BEVEL_EDGES":
                w = float(width if width is not None else 0.03)
                if w <= 0:
                    raise ModelingError("width must be positive.")
                seg = int(segments if segments is not None else 2)
                if not 1 <= seg <= 8:
                    raise ModelingError("segments must be between 1 and 8.")
                if sharp_angle is not None:
                    limit = math.radians(float(sharp_angle))
                    edges = [e for e in bm.edges if e.is_manifold and e.calc_face_angle(0.0) >= limit]
                else:
                    edges = list(bm.edges)
                if not edges:
                    raise ModelingError("No edge matches (lower sharp_angle).")
                touched = len(edges)
                bmesh.ops.bevel(bm, geom=edges, offset=w, segments=seg, affect="EDGES")
            elif op == "SUBDIVIDE":
                n = int(cuts if cuts is not None else 1)
                if not 1 <= n <= 4:
                    raise ModelingError("cuts must be between 1 and 4.")
                touched = len(bm.edges)
                bmesh.ops.subdivide_edges(bm, edges=list(bm.edges), cuts=n, use_grid_fill=True)
            elif op == "TRIANGULATE":
                touched = len(bm.faces)
                bmesh.ops.triangulate(bm, faces=list(bm.faces))
            elif op == "RECALC_NORMALS":
                touched = len(bm.faces)
                bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
            elif op == "MERGE_BY_DISTANCE":
                d = float(merge_distance if merge_distance is not None else 0.0001)
                if d < 0:
                    raise ModelingError("merge_distance must not be negative.")
                before = len(bm.verts)
                bmesh.ops.remove_doubles(bm, verts=list(bm.verts), dist=d)
                touched = before - len(bm.verts)
            elif op == "SCALE_TO_HEIGHT_TAPER":
                # Taper: scale each vertex's X/Y toward the centre line as a linear function of its height,
                # from 1.0 at the bottom to top_scale at the top (a chimney, a wheel arch, a tree trunk).
                ts = float(top_scale if top_scale is not None else 0.5)
                if ts < 0:
                    raise ModelingError("top_scale must not be negative.")
                zs = [v.co.z for v in bm.verts]
                if not zs:
                    raise ModelingError("The mesh is empty.")
                lo, hi = min(zs), max(zs)
                span = (hi - lo) or 1.0
                for v in bm.verts:
                    k = 1.0 + ((v.co.z - lo) / span) * (ts - 1.0)
                    v.co.x *= k
                    v.co.y *= k
                touched = len(bm.verts)
            if len(bm.verts) > MAX_RESULT_VERTICES:
                raise ModelingError(f"The result would exceed {MAX_RESULT_VERTICES} vertices; use fewer cuts or segments.")
            bm.normal_update()
            bm.to_mesh(mesh)
        finally:
            bm.free()
        mesh.update()
        bpy.context.view_layer.update()
        push_undo_step(f"AI: Mesh edit {op} ({obj.name})")
        out = _summary(obj)
        out.update({"operation": op, "elements_affected": touched})
        return out

    # ------------------------------------------------------------------ join / parent / transform / origin
    @classmethod
    def join_objects(cls, object_names: Any, target_name: str, new_name: Optional[str] = None) -> Dict[str, Any]:
        if not isinstance(object_names, list) or not object_names:
            raise ModelingError("object_names must be a non-empty list of mesh object names.")
        target = _mesh_object(target_name)
        sources = []
        for n in object_names:
            obj = _mesh_object(n)
            if obj is not target:
                sources.append(obj)
        if not sources:
            raise ModelingError("Nothing to join: list at least one object besides the target.")
        if target.data.users > 1:
            target.data = target.data.copy()
        selected = sources + [target]
        with bpy.context.temp_override(active_object=target, object=target, selected_objects=selected,
                                       selected_editable_objects=selected):
            result = bpy.ops.object.join()
        if "FINISHED" not in result:
            raise ModelingError("Blender refused to join these objects.")
        if new_name and new_name.strip():
            target.name = new_name.strip()[:MAX_NAME_LEN]
        bpy.context.view_layer.update()
        push_undo_step(f"AI: Join into {target.name}")
        out = _summary(target)
        out["joined"] = [str(n) for n in object_names]
        return out

    @classmethod
    def parent_object(cls, child_name: str, parent_name: Optional[str], keep_transform: bool = True) -> Dict[str, Any]:
        child = bpy.data.objects.get(str(child_name).strip()) if child_name else None
        if child is None:
            raise ModelingError(f"Object '{child_name}' not found.")
        if not parent_name or str(parent_name).strip().upper() in ("", "NONE"):
            world = child.matrix_world.copy()
            child.parent = None
            if keep_transform:
                child.matrix_world = world
            push_undo_step(f"AI: Unparent {child.name}")
            return {"object_name": child.name, "parent": None}
        parent = bpy.data.objects.get(str(parent_name).strip())
        if parent is None:
            raise ModelingError(f"Parent '{parent_name}' not found.")
        if parent is child:
            raise ModelingError("An object cannot be its own parent.")
        p = parent
        while p is not None:
            if p is child:
                raise ModelingError("That would create a parent loop.")
            p = p.parent
        world = child.matrix_world.copy()
        child.parent = parent
        child.matrix_parent_inverse = parent.matrix_world.inverted()
        if not keep_transform:
            child.matrix_parent_inverse = Matrix.Identity(4)
        else:
            child.matrix_world = world
        bpy.context.view_layer.update()
        push_undo_step(f"AI: Parent {child.name} to {parent.name}")
        return {"object_name": child.name, "parent": parent.name,
                "location": [round(v, 4) for v in child.location]}

    @classmethod
    def apply_transform(cls, object_name: str, location: bool = False, rotation: bool = True, scale: bool = True) -> Dict[str, Any]:
        obj = _mesh_object(object_name)
        if obj.parent is not None:
            raise ModelingError("Parented objects are not supported here; unparent first (parent_object with parent_name NONE).")
        mesh = _unique_mesh(obj)
        loc = Vector(obj.location) if location else Vector((0, 0, 0))
        rot = obj.rotation_euler.copy() if rotation else Euler((0, 0, 0), "XYZ")
        sca = Vector(obj.scale) if scale else Vector((1, 1, 1))
        matrix = Matrix.LocRotScale(loc, rot, sca)
        mesh.transform(matrix)
        mesh.update()
        if location:
            obj.location = (0, 0, 0)
        if rotation:
            obj.rotation_euler = (0, 0, 0)
        if scale:
            obj.scale = (1, 1, 1)
        bpy.context.view_layer.update()
        push_undo_step(f"AI: Apply transform ({obj.name})")
        return _summary(obj)

    ORIGINS = ("BOTTOM_CENTER", "GEOMETRY_CENTER", "BOUNDS_CENTER", "WORLD_ORIGIN")

    @classmethod
    def set_origin(cls, object_name: str, mode: str = "BOTTOM_CENTER") -> Dict[str, Any]:
        m = str(mode or "").strip().upper()
        if m not in cls.ORIGINS:
            raise ModelingError(f"mode must be one of {list(cls.ORIGINS)}.")
        obj = _mesh_object(object_name)
        if obj.parent is not None:
            raise ModelingError("Parented objects are not supported here; unparent first.")
        mesh = _unique_mesh(obj)
        lo, hi = _bounds(mesh)
        if m == "BOTTOM_CENTER":
            offset = Vector(((lo.x + hi.x) / 2, (lo.y + hi.y) / 2, lo.z))
        elif m == "BOUNDS_CENTER":
            offset = (lo + hi) / 2
        elif m == "GEOMETRY_CENTER":
            n = len(mesh.vertices) or 1
            offset = sum((v.co for v in mesh.vertices), Vector((0, 0, 0))) / n
        else:  # WORLD_ORIGIN: keep geometry where it is in world space, put the origin at (0, 0, 0)
            offset = obj.matrix_world.inverted() @ Vector((0, 0, 0))
        mesh.transform(Matrix.Translation(-offset))
        mesh.update()
        obj.location = obj.matrix_world @ offset if m != "WORLD_ORIGIN" else Vector((0, 0, 0))
        bpy.context.view_layer.update()
        push_undo_step(f"AI: Set origin {m} ({obj.name})")
        out = _summary(obj)
        out["origin_mode"] = m
        return out

    # ------------------------------------------------------------------ export
    @classmethod
    def export_gltf(cls, object_names: Any, filename: str, export_dir: str, apply_modifiers: bool = True,
                    include_materials: bool = True, y_up: bool = True, recenter: bool = True) -> Dict[str, Any]:
        if not isinstance(object_names, list) or not object_names:
            raise ModelingError("object_names must be a non-empty list of object names.")
        name = str(filename or "").strip()
        if not name.lower().endswith(".glb"):
            name += ".glb"
        if not FILENAME_RX.match(name) or ".." in name:
            raise ModelingError("filename must be a plain file name (letters, digits, _ - .), no folders.")
        objs = []
        for n in object_names:
            obj = bpy.data.objects.get(str(n).strip())
            if obj is None:
                raise ModelingError(f"Object '{n}' not found.")
            objs.append(obj)
        folder = Path(export_dir).expanduser()
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / name
        # Game engines place the file's root node at its position in the Blender scene, so a prop modelled at
        # (12, 0, 0) would sit 12 m away from its collision body. recenter shifts the exported objects so the first
        # object's origin lands on (0, 0, 0) and puts everything back afterwards.
        shifted = []
        if recenter:
            delta = -Vector(objs[0].matrix_world.translation)
            for o in objs:
                if o.parent is None or o.parent not in objs:
                    shifted.append((o, Vector(o.location)))
                    o.location = Vector(o.location) + delta
            bpy.context.view_layer.update()
        # Selection drives the exporter; restore it afterwards.
        view_layer = bpy.context.view_layer
        previous = [(o, o.select_get()) for o in view_layer.objects]
        previous_active = view_layer.objects.active
        try:
            for o in view_layer.objects:
                o.select_set(False)
            for o in objs:
                o.select_set(True)
            view_layer.objects.active = objs[0]
            result = bpy.ops.export_scene.gltf(
                filepath=str(path), export_format="GLB", use_selection=True, export_apply=bool(apply_modifiers),
                export_yup=bool(y_up), export_materials="EXPORT" if include_materials else "NONE",
            )
        finally:
            for o, loc in shifted:
                o.location = loc
            if shifted:
                bpy.context.view_layer.update()
            for o, was in previous:
                try:
                    o.select_set(was)
                except Exception:
                    pass
            view_layer.objects.active = previous_active
        if "FINISHED" not in result or not path.exists():
            raise ModelingError("The glTF exporter did not write a file (is the glTF add-on enabled?).")
        tris = 0
        depsgraph = bpy.context.evaluated_depsgraph_get()
        for o in objs:
            if o.type == "MESH":
                ev = o.evaluated_get(depsgraph)
                mesh = ev.to_mesh()
                mesh.calc_loop_triangles()
                tris += len(mesh.loop_triangles)
                ev.to_mesh_clear()
        out = {
            "path": str(path), "filename": name, "bytes": path.stat().st_size, "objects": [o.name for o in objs],
            "triangle_count": tris, "format": "GLB", "y_up": bool(y_up), "recentered": bool(recenter),
        }
        if tris > 5000:
            out["warning"] = f"{tris} triangles is heavy for a game prop; consider a lower-poly version."
        return out


    # ------------------------------------------------------------------ shape modifiers
    SHAPE_MODIFIERS = ("MIRROR", "ARRAY", "SOLIDIFY", "DECIMATE", "TRIANGULATE")

    @classmethod
    def add_shape_modifier(cls, name: str, modifier_type: str, axes: Any = None, count: Optional[int] = None,
                           relative_offset: Any = None, thickness: Optional[float] = None,
                           ratio: Optional[float] = None, modifier_name: Optional[str] = None) -> Dict[str, Any]:
        kind = str(modifier_type or "").strip().upper()
        if kind not in cls.SHAPE_MODIFIERS:
            raise ModelingError(f"modifier_type must be one of {list(cls.SHAPE_MODIFIERS)}.")
        obj = _mesh_object(name)
        # Validate everything before touching the modifier stack (a bad call must change nothing).
        info: Dict[str, Any] = {}
        wanted: List[str] = []
        offset = Vector((1.0, 0.0, 0.0))
        n = 2
        t = 0.02
        r = 0.5
        if kind == "MIRROR":
            wanted = [str(a).strip().upper() for a in (axes if isinstance(axes, list) and axes else ["X"])]
            if any(a not in ("X", "Y", "Z") for a in wanted):
                raise ModelingError("axes must be a list of X, Y and/or Z.")
            info["axes"] = wanted
        elif kind == "ARRAY":
            n = int(count if count is not None else 2)
            if not 2 <= n <= 64:
                raise ModelingError("count must be between 2 and 64.")
            if relative_offset is not None:
                offset = _vec3(relative_offset, "relative_offset")
            info.update({"count": n, "relative_offset": [round(v, 4) for v in offset]})
        elif kind == "SOLIDIFY":
            t = float(thickness if thickness is not None else 0.02)
            if t == 0 or not math.isfinite(t):
                raise ModelingError("thickness must be a non-zero number (meters).")
            info["thickness"] = t
        elif kind == "DECIMATE":
            r = float(ratio if ratio is not None else 0.5)
            if not 0.02 <= r <= 1.0:
                raise ModelingError("ratio must be between 0.02 and 1.0.")
            info["ratio"] = r
        label = modifier_name.strip()[:MAX_NAME_LEN] if isinstance(modifier_name, str) and modifier_name.strip() else kind.capitalize()
        existing = obj.modifiers.get(label)
        mod = existing if existing is not None and existing.type == kind else obj.modifiers.new(name=label, type=kind)
        if kind == "MIRROR":
            for i, letter in enumerate(("X", "Y", "Z")):
                mod.use_axis[i] = letter in wanted
            mod.use_clip = True
            mod.use_mirror_merge = True
            mod.merge_threshold = 0.001
        elif kind == "ARRAY":
            mod.count = n
            mod.use_relative_offset = True
            mod.relative_offset_displace = offset
        elif kind == "SOLIDIFY":
            mod.thickness = t
        elif kind == "DECIMATE":
            mod.decimate_type = "COLLAPSE"
            mod.ratio = r
        bpy.context.view_layer.update()
        push_undo_step(f"AI: Add {kind} modifier on {obj.name}")
        out = {"object_name": obj.name, "modifier_name": mod.name, "modifier_type": kind, "exists": True}
        out.update(info)
        depsgraph = bpy.context.evaluated_depsgraph_get()
        evaluated = obj.evaluated_get(depsgraph)
        mesh = evaluated.to_mesh()
        mesh.calc_loop_triangles()
        out["evaluated_triangle_count"] = len(mesh.loop_triangles)
        evaluated.to_mesh_clear()
        return out

    # ------------------------------------------------------------------ view
    VIEW_DIRECTIONS = {
        "FRONT": (math.pi / 2, 0.0, 0.0),
        "BACK": (math.pi / 2, 0.0, math.pi),
        "RIGHT": (math.pi / 2, 0.0, math.pi / 2),
        "LEFT": (math.pi / 2, 0.0, -math.pi / 2),
        "TOP": (0.0, 0.0, 0.0),
        "ISO": (math.radians(62), 0.0, math.radians(38)),
    }

    @classmethod
    def frame_view(cls, object_names: Any = None, direction: str = "ISO", shading: Optional[str] = None,
                   overlays: Optional[bool] = None) -> Dict[str, Any]:
        from adapter.readers.viewport_reader import ViewportReader

        key = str(direction or "ISO").strip().upper()
        if key not in cls.VIEW_DIRECTIONS:
            raise ModelingError(f"direction must be one of {sorted(cls.VIEW_DIRECTIONS)}.")
        if object_names:
            if not isinstance(object_names, list):
                raise ModelingError("object_names must be a list of names.")
            objs = []
            for n in object_names:
                o = bpy.data.objects.get(str(n).strip())
                if o is None:
                    raise ModelingError(f"Object '{n}' not found.")
                objs.append(o)
        else:
            objs = [o for o in bpy.context.scene.objects if o.type == "MESH"]
        space, _region = ViewportReader()._resolve_view3d_context()
        r3d = space.region_3d
        points = [o.matrix_world @ Vector(c) for o in objs for c in o.bound_box]
        if points:
            lo = Vector((min(p.x for p in points), min(p.y for p in points), min(p.z for p in points)))
            hi = Vector((max(p.x for p in points), max(p.y for p in points), max(p.z for p in points)))
            center = (lo + hi) / 2
            radius = max((hi - lo).length / 2, 0.25)
        else:
            center, radius = Vector((0, 0, 0)), 3.0
        rx, ry, rz = cls.VIEW_DIRECTIONS[key]
        r3d.view_perspective = "PERSP"
        r3d.view_location = center
        r3d.view_rotation = Euler((rx, ry, rz), "XYZ").to_quaternion()
        r3d.view_distance = radius * 2.3
        if shading is not None:
            mode = str(shading).strip().upper()
            if mode not in ("SOLID", "MATERIAL", "WIREFRAME"):
                raise ModelingError("shading must be SOLID, MATERIAL or WIREFRAME.")
            space.shading.type = mode
        if overlays is not None:
            space.overlay.show_overlays = bool(overlays)
        return {"direction": key, "objects": [o.name for o in objs][:50], "center": [round(v, 3) for v in center],
                "radius": round(radius, 3), "shading": space.shading.type, "overlays": bool(space.overlay.show_overlays)}
