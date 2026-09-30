"""World mutators: terrain and scattering copies of an object over an area, along a path, or onto a terrain.

Copies are linked duplicates (they share the mesh), so 300 trees cost one tree of memory and a glTF export keeps them as
instances of one mesh. The points come from core.scatter_points (seeded), so the same request gives the same world.
"""

import math
import random
from typing import Any, Dict, List, Optional

import bmesh
import bpy
from mathutils import Matrix, Vector

from adapter.mutators.modeling_mutator import ModelingError, _link, _summary, as_list
from adapter.mutators.undo_manager import push_undo_step
from core.scatter_points import (MAX_COUNT, height_grid, min_distance_for, rect_of_box, sample_area, sample_path)

MAX_RESOLUTION = 160
GROUND_PROBE_HEIGHT = 1000.0


def _object(name: Any) -> "bpy.types.Object":
    obj = bpy.data.objects.get(str(name or "").strip())
    if obj is None:
        raise ModelingError(f"Object '{name}' not found in the scene.")
    return obj


def _world_box(objs: List["bpy.types.Object"]):
    pts = [o.matrix_world @ Vector(c) for o in objs if o.type == "MESH" for c in o.bound_box]
    if not pts:
        raise ModelingError("The source has no mesh.")
    return (Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts))),
            Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts))))


def _triangles(objs: List["bpy.types.Object"]) -> int:
    total = 0
    for o in objs:
        if o.type == "MESH":
            o.data.calc_loop_triangles()
            total += len(o.data.loop_triangles)
    return total


class WorldMutator:
    @classmethod
    def create_terrain(cls, name: Any = None, size: Any = 40.0, resolution: Any = 48, height: Any = 4.0, roughness: Any = 0.5,
                       seed: Any = 1, flat_radius: Any = 0.0, location: Any = None) -> Dict[str, Any]:
        try:
            size_v, height_v, rough_v = float(size), float(height), float(roughness)
            res, seed_v, flat_v = int(resolution), int(seed), float(flat_radius)
        except (TypeError, ValueError):
            raise ModelingError("size, height, roughness and flat_radius are numbers; resolution and seed whole numbers.")
        if not (2.0 <= size_v <= 2000.0):
            raise ModelingError("size must be between 2 and 2000 meters.")
        if not (4 <= res <= MAX_RESOLUTION):
            raise ModelingError(f"resolution must be between 4 and {MAX_RESOLUTION} (quads per side).")
        if not (0.0 <= height_v <= size_v):
            raise ModelingError("height must be between 0 and size.")
        if not (0.05 <= rough_v <= 0.95):
            raise ModelingError("roughness must be between 0.05 (smooth hills) and 0.95 (jagged).")
        if not (0.0 <= flat_v <= size_v / 2):
            raise ModelingError("flat_radius must be between 0 and half the size.")
        grid = height_grid(size_v, res, height_v, rough_v, seed_v, flat_v)
        step, half = size_v / res, size_v / 2
        verts = [(-half + i * step, -half + j * step, grid[j][i]) for j in range(res + 1) for i in range(res + 1)]
        faces = [(j * (res + 1) + i, j * (res + 1) + i + 1, (j + 1) * (res + 1) + i + 1, (j + 1) * (res + 1) + i)
                 for j in range(res) for i in range(res)]
        base = str(name).strip()[:40] if isinstance(name, str) and name.strip() else "Terrain"
        mesh = bpy.data.meshes.new(f"{base}_mesh")
        mesh.from_pydata(verts, [], faces)
        mesh.validate(clean_customdata=False)
        for poly in mesh.polygons:
            poly.use_smooth = True
        mesh.update()
        obj = bpy.data.objects.new(base, mesh)
        _link(obj)
        if location is not None:
            loc = as_list(location)
            try:
                obj.location = (float(loc[0]), float(loc[1]), float(loc[2]))
            except (TypeError, ValueError, IndexError):
                raise ModelingError("location must be [x, y, z].")
        bpy.context.view_layer.update()
        push_undo_step(f"AI: Create terrain ({obj.name})")
        out = _summary(obj)
        out.update({"created": True, "highest_m": round(max(v[2] for v in verts), 3), "flat_radius": flat_v, "seed": seed_v})
        return out

    @classmethod
    def scatter(cls, source: Any, count: Any = 20, area: Any = None, path: Any = None, spread: Any = 2.0, min_distance: Any = None,
                scale_range: Any = None, random_rotation: Any = True, seed: Any = 1, ground: Any = None, ground_z: Any = 0.0,
                avoid: Any = None, name: Any = None) -> Dict[str, Any]:
        """Place linked copies of ``source`` (one object or a group) inside an area or along a path."""
        names = as_list(source)
        names = names if isinstance(names, list) else [names]
        sources = [_object(n) for n in names if str(n).strip()]
        if not sources:
            raise ModelingError("source must name the object (or list of objects) to copy.")
        try:
            n = int(count)
            seed_v = int(seed)
            spread_v = float(spread)
            base_z = float(ground_z)
        except (TypeError, ValueError):
            raise ModelingError("count and seed are whole numbers; spread and ground_z numbers.")
        if not (1 <= n <= MAX_COUNT):
            raise ModelingError(f"count must be between 1 and {MAX_COUNT}.")
        if (area is None) == (path is None):
            raise ModelingError("Give exactly one of area ({\"center\": [x, y], \"size\": [w, d]} or {\"center\": [x, y], \"radius\": r}) or path ([[x, y], ...]).")
        lo_s, hi_s = 0.8, 1.2
        if scale_range is not None:
            rng = as_list(scale_range)
            try:
                lo_s, hi_s = float(rng[0]), float(rng[1])
            except (TypeError, ValueError, IndexError):
                raise ModelingError("scale_range must be [min, max], for example [0.8, 1.2].")
            if not (0.05 <= lo_s <= hi_s <= 20.0):
                raise ModelingError("scale_range must satisfy 0.05 <= min <= max <= 20.")
        ground_obj = _object(ground) if ground else None
        if ground_obj is not None and ground_obj.type != "MESH":
            raise ModelingError("ground must be a mesh object (a terrain or a plane).")
        avoid_objs = [_object(a) for a in (as_list(avoid) or [])] if avoid else []
        avoid_rects = []
        for obj in avoid_objs:
            lo, hi = _world_box([obj] + list(obj.children_recursive))
            avoid_rects.append(rect_of_box(lo, hi, 0.5))
        lo, hi = _world_box(sources)
        footprint_x, footprint_y = hi.x - lo.x, hi.y - lo.y
        gap = min_distance_for(footprint_x, footprint_y, hi_s, None if min_distance is None else float(min_distance))
        try:
            if area is not None:
                points = sample_area(area, n, gap, seed_v, avoid_rects)
            else:
                points = sample_path(as_list(path), n, spread_v, gap, seed_v, avoid_rects)
        except ValueError as err:
            raise ModelingError(str(err))
        if not points:
            raise ModelingError("No room for a single copy: lower min_distance or widen the area.")
        anchor = Vector(((lo.x + hi.x) / 2.0, (lo.y + hi.y) / 2.0, lo.z))      # bottom centre of the source
        rnd = random.Random(seed_v + 7)
        label = str(name).strip()[:40] if isinstance(name, str) and name.strip() else f"Scatter_{sources[0].name}"
        collection = bpy.data.collections.new(label)
        bpy.context.scene.collection.children.link(collection)
        made: List["bpy.types.Object"] = []
        skipped = 0
        for x, y in points:
            z = base_z
            if ground_obj is not None:
                # cast against the ground object alone (a house or a tree above it must not count as ground)
                inv = ground_obj.matrix_world.inverted()
                start = inv @ Vector((x, y, GROUND_PROBE_HEIGHT))
                aim = (inv.to_3x3() @ Vector((0, 0, -1))).normalized()
                hit, where, _normal, _idx = ground_obj.ray_cast(start, aim)
                if not hit:
                    skipped += 1
                    continue
                z = (ground_obj.matrix_world @ where).z
            scale = rnd.uniform(lo_s, hi_s)
            angle = rnd.uniform(0.0, math.tau) if random_rotation else 0.0
            spot = Vector((x, y, z))
            if len(sources) == 1:
                src = sources[0]
                copy = src.copy()                              # linked: shares the mesh
                collection.objects.link(copy)
                copy.parent = None
                offset = src.matrix_world.translation - anchor
                copy.location = spot + Matrix.Rotation(angle, 3, "Z") @ (offset * scale)
                copy.rotation_euler = (src.rotation_euler.x, src.rotation_euler.y, src.rotation_euler.z + angle)
                copy.scale = src.scale * scale
                made.append(copy)
            else:
                root = bpy.data.objects.new(f"{label}_group", None)
                collection.objects.link(root)
                root.location = spot
                root.rotation_euler = (0.0, 0.0, angle)
                root.scale = (scale, scale, scale)
                for src in sources:
                    part = src.copy()
                    collection.objects.link(part)
                    part.parent = root
                    part.location = src.matrix_world.translation - anchor
                    part.rotation_euler = src.rotation_euler
                    part.scale = src.scale
                made.append(root)
        if not made:
            bpy.data.collections.remove(collection)
            raise ModelingError("Every point missed the ground object: make sure ground covers the area (seen from above).")
        bpy.context.view_layer.update()
        push_undo_step(f"AI: Scatter {len(made)} x {sources[0].name}")
        return {"collection": collection.name, "count": len(made), "requested": n, "skipped_off_ground": skipped,
                "spacing_m": round(gap, 3), "scale_range": [lo_s, hi_s], "seed": seed_v,
                "triangles_total": _triangles(sources) * len(made), "instances": [o.name for o in made[:12]],
                "note": "copies share the source mesh (linked); the originals stay where they were"}
