"""Model QA mutator (read only): measure meshes with bmesh and let core.model_qa judge the numbers."""

from typing import Any, Dict, List, Optional

import bmesh
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

from adapter.mutators.cinema_mutator import _scene_meshes
from adapter.mutators.modeling_mutator import ModelingError, as_list
from core.model_qa import DEFAULT_TRIANGLE_BUDGET, verdict

DOUBLE_DISTANCE = 1e-5
DEGENERATE_AREA = 1e-10
# Part checks, after Scenario's bx_audit.deliverable gate (MIT, github.com/scenario-labs/skills), as fractions of the
# model's bounding diagonal: coplanar distance for z-fighting, touching distance, and the gap past which a part floats.
COPLANAR_FRACTION = 1e-4
TOUCH_FRACTION = 2e-3
GAP_FRACTION = 1e-2
MAX_PARTS = 400            # floating check skipped above this many loose pieces (scattered forests)
MAX_ZFIGHT_FACES = 60000   # z-fighting check skipped above this many faces


def _uses_image_texture(obj: "bpy.types.Object") -> bool:
    for slot in obj.material_slots:
        tree = getattr(slot.material, "node_tree", None) if slot.material else None
        if tree and any(n.type == "TEX_IMAGE" for n in tree.nodes):
            return True
    return False


def _origin_outside(obj: "bpy.types.Object") -> bool:
    corners = [Vector(c) for c in obj.bound_box]
    for axis in range(3):
        lo, hi = min(c[axis] for c in corners), max(c[axis] for c in corners)
        slack = max(hi - lo, 1e-3) * 0.1
        if not (lo - slack <= 0.0 <= hi + slack):
            return True
    return False


def measure(obj: "bpy.types.Object") -> Dict[str, Any]:
    """Statistics of the mesh as it would export (modifiers applied)."""
    depsgraph = bpy.context.evaluated_depsgraph_get()
    evaluated = obj.evaluated_get(depsgraph)
    mesh = evaluated.to_mesh()
    bm = bmesh.new()
    try:
        bm.from_mesh(mesh)
        bm.edges.ensure_lookup_table()
        nonmanifold = sum(1 for e in bm.edges if len(e.link_faces) > 2 or len(e.link_faces) == 0)
        boundary = sum(1 for e in bm.edges if len(e.link_faces) == 1)
        closed = bool(bm.faces) and nonmanifold == 0 and boundary == 0
        volume = float(bm.calc_volume(signed=True)) if closed else 0.0
        tris = sum(max(len(f.verts) - 2, 0) for f in bm.faces)
        degenerate = sum(1 for f in bm.faces if f.calc_area() < DEGENERATE_AREA)
        doubles = len(bmesh.ops.find_doubles(bm, verts=bm.verts, dist=DOUBLE_DISTANCE)["targetmap"]) if bm.verts else 0
        loose = sum(1 for v in bm.verts if not v.link_edges)
        faces = len(bm.faces)
    finally:
        bm.free()
        evaluated.to_mesh_clear()
    world = [obj.matrix_world @ Vector(c) for c in obj.bound_box]
    return {
        "name": obj.name, "tris": tris, "faces": faces, "nonmanifold_edges": nonmanifold, "boundary_edges": boundary,
        "closed": closed, "signed_volume": volume, "degenerate_faces": degenerate, "duplicate_verts": doubles,
        "loose_verts": loose, "scale": tuple(float(s) for s in obj.scale), "origin_outside": _origin_outside(obj),
        "has_material": any(s.material for s in obj.material_slots), "uses_image_texture": _uses_image_texture(obj),
        "uv_layers": len(obj.data.uv_layers), "z_min": min(p.z for p in world), "z_max": max(p.z for p in world),
        "bbox_min": tuple(min(p[i] for p in world) for i in range(3)), "bbox_max": tuple(max(p[i] for p in world) for i in range(3)),
    }


def _world_bmesh(obj: "bpy.types.Object", weld: float) -> "bmesh.types.BMesh":
    """Evaluated mesh in world space, welded so UV-seam splits (every glTF import) do not read as separate pieces."""
    depsgraph = bpy.context.evaluated_depsgraph_get()
    evaluated = obj.evaluated_get(depsgraph)
    mesh = evaluated.to_mesh()
    bm = bmesh.new()
    try:
        bm.from_mesh(mesh)
    finally:
        evaluated.to_mesh_clear()
    bm.transform(obj.matrix_world)
    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=weld)
    if obj.matrix_world.determinant() < 0:
        bmesh.ops.reverse_faces(bm, faces=bm.faces[:])
    bm.verts.ensure_lookup_table()
    bm.faces.ensure_lookup_table()
    bm.normal_update()
    return bm


def _pieces(bm: "bmesh.types.BMesh") -> List[Dict[str, Any]]:
    """Connected pieces of a mesh: closed flag, signed volume, surface area, bounds and a BVH for distance tests."""
    out, done = [], set()
    for f0 in bm.faces:
        if f0.index in done:
            continue
        done.add(f0.index)
        stack, faces = [f0], []
        while stack:
            f = stack.pop()
            faces.append(f)
            for v in f.verts:
                for g in v.link_faces:
                    if g.index not in done:
                        done.add(g.index)
                        stack.append(g)
        local: Dict[int, int] = {}
        coords: List[Vector] = []
        polys: List[List[int]] = []
        closed, volume, area = True, 0.0, 0.0
        for f in faces:
            ids = []
            for v in f.verts:
                if v.index not in local:
                    local[v.index] = len(coords)
                    coords.append(v.co.copy())
                ids.append(local[v.index])
            polys.append(ids)
            closed = closed and all(len(e.link_faces) == 2 for e in f.edges)
            co = [v.co for v in f.verts]
            volume += sum(co[0].dot(co[i].cross(co[i + 1])) for i in range(1, len(co) - 1)) / 6.0
            area += f.calc_area()
        out.append({"coords": coords, "polys": polys, "closed": closed, "volume": volume, "area": area,
                    "centers": [f.calc_center_median() for f in faces], "normals": [f.normal.copy() for f in faces],
                    "lo": [min(c[k] for c in coords) for k in range(3)], "hi": [max(c[k] for c in coords) for k in range(3)],
                    "tree": BVHTree.FromPolygons(coords, polys)})
    return out


def _touching(a: Dict[str, Any], b: Dict[str, Any], tol: float) -> bool:
    if any(b["lo"][k] > a["hi"][k] + tol or a["lo"][k] > b["hi"][k] + tol for k in range(3)):
        return False
    if a["tree"].overlap(b["tree"]):
        return True
    for x, y in ((a, b), (b, a)):
        step = max(1, len(x["coords"]) // 256)
        if any(y["tree"].find_nearest(c, tol)[0] is not None for c in x["coords"][::step]):
            return True
    return False


def _inside(a: Dict[str, Any], b: Dict[str, Any]) -> bool:
    """Sampled vertices of piece a all lie inside closed piece b (an eye in a head counts as attached)."""
    if not b["closed"] or b["volume"] <= 0:
        return False
    for c in a["coords"][::max(1, len(a["coords"]) // 64)]:
        loc, normal, _, _ = b["tree"].find_nearest(c)
        if loc is None or (c - loc).dot(normal) >= 0:
            return False
    return True


def assembly(objs: List["bpy.types.Object"]) -> Dict[str, Any]:
    """Per-object inward pieces, plus floating parts and z-fighting between parts (see core.model_qa.assembly_issues)."""
    corners = [o.matrix_world @ Vector(c) for o in objs for c in o.bound_box]
    diag = (Vector([max(c[k] for c in corners) for k in range(3)]) - Vector([min(c[k] for c in corners) for k in range(3)])).length or 1.0
    eps, tol, gap = diag * COPLANAR_FRACTION, diag * TOUCH_FRACTION, diag * GAP_FRACTION
    pieces: List[Dict[str, Any]] = []
    owner: List[str] = []
    inward: Dict[str, int] = {}
    for o in objs:
        bm = _world_bmesh(o, diag * 1e-6)
        try:
            found = _pieces(bm)
        finally:
            bm.free()
        inward[o.name] = sum(1 for p in found if p["closed"] and p["volume"] < -(diag ** 3) * 1e-9)
        pieces += found
        owner += [o.name] * len(found)
    result: Dict[str, Any] = {"inward_parts": inward, "floating": [], "z_fighting": [], "skipped": []}

    if sum(len(p["polys"]) for p in pieces) <= MAX_ZFIGHT_FACES and len(pieces) > 1:
        coords: List[Vector] = []
        polys: List[List[int]] = []
        face_piece: List[int] = []
        for i, p in enumerate(pieces):
            polys += [[k + len(coords) for k in poly] for poly in p["polys"]]
            coords += p["coords"]
            face_piece += [i] * len(p["polys"])
        tree = BVHTree.FromPolygons(coords, polys)
        hits: Dict[tuple, int] = {}
        for i, p in enumerate(pieces):
            for c, nrm in zip(p["centers"], p["normals"]):
                for loc, hn, idx, _ in tree.find_nearest_range(c, eps):
                    j = face_piece[idx]
                    off = c - loc
                    # same facing, and the centre projects inside the other face rather than grazing its edge
                    if j != i and nrm.dot(hn) > 0.999 and (off - off.dot(hn) * hn).length < eps * 0.01:
                        key = (min(owner[i], owner[j]), max(owner[i], owner[j]))
                        hits[key] = hits.get(key, 0) + 1
        result["z_fighting"] = [[a, b, count // 2 or 1] for (a, b), count in sorted(hits.items(), key=lambda kv: -kv[1])]
    elif len(pieces) > 1:
        result["skipped"].append("z_fighting")

    if 1 < len(pieces) <= MAX_PARTS:
        root = list(range(len(pieces)))

        def find(i: int) -> int:
            while root[i] != i:
                root[i] = root[root[i]]
                i = root[i]
            return i

        order = sorted(range(len(pieces)), key=lambda i: pieces[i]["lo"][0])
        for n, i in enumerate(order):
            for j in order[n + 1:]:
                if pieces[j]["lo"][0] > pieces[i]["hi"][0] + gap:
                    break
                if find(i) == find(j):
                    continue
                if _touching(pieces[i], pieces[j], tol) or _inside(pieces[i], pieces[j]) or _inside(pieces[j], pieces[i]):
                    root[find(i)] = find(j)
        groups: Dict[int, List[int]] = {}
        for i in range(len(pieces)):
            groups.setdefault(find(i), []).append(i)
        main = max(groups.values(), key=lambda g: sum(pieces[i]["area"] for i in g))
        floating = set()
        for g in groups.values():
            if g is main:
                continue
            # between touching and the gap a part is close enough to read as placed on purpose
            near = any(_touching(pieces[i], pieces[m], gap) for i in g for m in main[:64])
            if not near:
                floating.update(owner[i] for i in g)
        result["floating"] = sorted(floating)
    elif len(pieces) > MAX_PARTS:
        result["skipped"].append("floating")
    return result


class ModelQaMutator:
    @classmethod
    def check_model(cls, object_names: Any = None, max_triangles: Any = DEFAULT_TRIANGLE_BUDGET) -> Dict[str, Any]:
        """Measure the named objects (a parent stands for its parts) or every mesh in the scene except helpers."""
        try:
            budget = int(max_triangles)
        except (TypeError, ValueError):
            raise ModelingError("max_triangles must be a whole number between 100 and 1000000.")
        if not (100 <= budget <= 1_000_000):
            raise ModelingError("max_triangles must be between 100 and 1000000.")
        objs = [o for o in _scene_meshes(as_list(object_names) if object_names else None) if o.type == "MESH"]
        if not objs:
            raise ModelingError("There is no mesh to check. Model something first, or name the subject in object_names.")
        stats: List[Dict[str, Any]] = [measure(o) for o in objs]
        parts = assembly(objs)
        for s in stats:
            s["inward_parts"] = parts["inward_parts"].get(s["name"], 0)
        result = verdict(stats, budget, parts)
        if parts["skipped"]:
            result["skipped_checks"] = parts["skipped"]
        biggest = sorted(stats, key=lambda s: -s["tris"])[:5]
        result.update({"triangle_budget": budget, "heaviest": [{"name": s["name"], "triangles": s["tris"]} for s in biggest],
                       "checked": [s["name"] for s in stats][:24]})
        return result
