"""Deterministic model checks as plain math (no bpy): turn mesh statistics into plain advice, in the words of the tools.

The modelling counterpart of ``shot_qa``: a model that says "I made a chair" gets told, in numbers, that the chair sinks below
the ground, has flipped normals, doubled vertices or too many triangles, and which tool call fixes each. ``check_model``
measures the statistics with bmesh; this module judges them.
"""

from typing import Any, Dict, List, Optional, Sequence

FAIL = "FAIL"
WARN = "WARN"

DEFAULT_TRIANGLE_BUDGET = 3000     # a small game prop
SCALE_TOLERANCE = 0.001
SINK_TOLERANCE = 0.02              # meters below the ground before the whole group counts as sunk
DUPLICATE_TOLERANCE = 0.02         # bounding boxes equal within 2 percent of the size are the same object twice
MIN_FACES_FOR_OPEN_WARNING = 6     # a plane or a card is open on purpose


def _issue(severity: str, code: str, message: str, fix: str, objects: Sequence[str] = ()) -> Dict[str, Any]:
    return {"severity": severity, "code": code, "message": message, "fix": fix, "objects": list(objects)}


def object_issues(stats: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Problems of one mesh object from its statistics (see ModelQaMutator for the keys)."""
    name = str(stats.get("name", ""))
    out: List[Dict[str, Any]] = []
    if stats.get("nonmanifold_edges", 0) > 0:
        out.append(_issue(FAIL, "NON_MANIFOLD", f"{name}: {stats['nonmanifold_edges']} edges are shared by 3 or more faces or belong to no face.",
                          "mesh_edit MERGE_BY_DISTANCE, or rebuild the part; a game engine and 3D printing need a clean surface", [name]))
    if stats.get("closed") and stats.get("signed_volume", 0.0) < -1e-9:
        out.append(_issue(FAIL, "INVERTED_NORMALS", f"{name}: the faces point inward (negative volume).",
                          "mesh_edit RECALC_NORMALS", [name]))
    elif stats.get("inward_parts", 0) > 0:
        # A joined object can be open overall while one of its closed pieces is inside out (a car cabin in a body).
        out.append(_issue(FAIL, "INVERTED_PART", f"{name}: {stats['inward_parts']} closed piece(s) have faces pointing inward.",
                          "mesh_edit RECALC_NORMALS", [name]))
    if stats.get("degenerate_faces", 0) > 0:
        out.append(_issue(WARN, "DEGENERATE_FACES", f"{name}: {stats['degenerate_faces']} faces have no area.",
                          "mesh_edit MERGE_BY_DISTANCE", [name]))
    if stats.get("duplicate_verts", 0) > 0:
        out.append(_issue(WARN, "DUPLICATE_VERTICES", f"{name}: {stats['duplicate_verts']} vertices sit on top of another vertex.",
                          "mesh_edit MERGE_BY_DISTANCE", [name]))
    if stats.get("loose_verts", 0) > 0:
        out.append(_issue(WARN, "LOOSE_VERTICES", f"{name}: {stats['loose_verts']} vertices belong to no edge.",
                          "mesh_edit MERGE_BY_DISTANCE, or delete the stray points", [name]))
    scale = stats.get("scale", (1.0, 1.0, 1.0))
    if any(abs(abs(float(s)) - 1.0) > SCALE_TOLERANCE for s in scale) or any(float(s) < 0 for s in scale):
        out.append(_issue(WARN, "UNAPPLIED_SCALE", f"{name}: object scale is ({scale[0]:.2f}, {scale[1]:.2f}, {scale[2]:.2f}), not 1.",
                          "apply_transform with scale true", [name]))
    if stats.get("origin_outside"):
        out.append(_issue(WARN, "ORIGIN_OUTSIDE", f"{name}: the origin (pivot) lies outside the object.",
                          "set_origin (center or bottom)", [name]))
    if not stats.get("has_material"):
        out.append(_issue(WARN, "NO_MATERIAL", f"{name}: no material, it renders and exports as plain grey.",
                          "set_material with base_color", [name]))
    if stats.get("uses_image_texture") and not stats.get("uv_layers", 0):
        out.append(_issue(WARN, "MISSING_UV", f"{name}: the material uses an image texture but the mesh has no UV map.",
                          "unwrap_uv (in the textures pack: enable_tools if it is missing) before texturing", [name]))
    if stats.get("z_max", 0.0) < -SINK_TOLERANCE:
        out.append(_issue(FAIL, "BELOW_GROUND", f"{name}: the whole object is below the ground (top at {stats['z_max']:.2f} m).",
                          "transform_object to raise it so its bottom rests on z = 0", [name]))
    return out


def group_issues(all_stats: Sequence[Dict[str, Any]], max_triangles: int = DEFAULT_TRIANGLE_BUDGET) -> List[Dict[str, Any]]:
    """Problems of the whole subject: triangle budget, sinking into the ground, the same object twice."""
    out: List[Dict[str, Any]] = []
    if not all_stats:
        return out
    tris = sum(int(s.get("tris", 0)) for s in all_stats)
    if tris > max_triangles * 3:
        out.append(_issue(FAIL, "TOO_MANY_TRIANGLES", f"{tris} triangles, far over the budget of {max_triangles}.",
                          "add_shape_modifier DECIMATE, or build simpler parts"))
    elif tris > max_triangles:
        out.append(_issue(WARN, "TOO_MANY_TRIANGLES", f"{tris} triangles, over the budget of {max_triangles}.",
                          "add_shape_modifier DECIMATE, or lower the subdivision and bevel"))
    z_min = min(float(s.get("z_min", 0.0)) for s in all_stats)
    z_max = max(float(s.get("z_max", 0.0)) for s in all_stats)
    if z_min < -SINK_TOLERANCE and z_max >= -SINK_TOLERANCE:
        low = [s["name"] for s in all_stats if float(s.get("z_min", 0.0)) < -SINK_TOLERANCE][:6]
        out.append(_issue(WARN, "SINKS_INTO_GROUND", f"Part of the model is {abs(z_min):.2f} m below the ground.",
                          "transform_object to raise the parts, unless it should be buried (a well, a foundation)", low))
    seen: List[Dict[str, Any]] = []
    for s in all_stats:
        if not s.get("bbox_min") or not s.get("bbox_max") or int(s.get("faces", 0)) < 1:
            continue
        for other in seen:
            if _same_box(s, other):
                out.append(_issue(WARN, "DUPLICATE_OBJECT", f"{s['name']} and {other['name']} occupy the same space (z-fighting, double geometry).",
                                  "delete_object one of them", [s["name"], other["name"]]))
                break
        seen.append(s)
    return out


def assembly_issues(assembly: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Problems between the parts of one asset, measured by ModelQaMutator.assembly (after Scenario's bx_audit gate, MIT):
    ``floating``: names of parts that touch nothing of the main body; ``z_fighting``: [part_a, part_b, faces] with coplanar
    faces facing the same way (they flicker in an engine)."""
    out: List[Dict[str, Any]] = []
    if not assembly:
        return out
    floating = list(assembly.get("floating") or [])
    if floating:
        out.append(_issue(WARN, "FLOATING_PART", f"{len(floating)} part(s) touch nothing of the main body: {', '.join(floating[:6])}.",
                          "transform_object to attach it (or add a joint part); if it is a separate prop, check it on its own",
                          floating))
    for a, b, count in list(assembly.get("z_fighting") or [])[:6]:
        where = f"{a}, between its own pieces" if a == b else f"{a} and {b}"
        out.append(_issue(WARN, "Z_FIGHTING", f"{where}: {count} coplanar overlapping face(s), they flicker in a game engine.",
                          "transform_object to push one part a few millimetres in or out, or mesh_edit to delete the hidden faces",
                          sorted({a, b})))
    return out


def _same_box(a: Dict[str, Any], b: Dict[str, Any]) -> bool:
    size = max(max(float(x) - float(n) for n, x in zip(a["bbox_min"], a["bbox_max"])), 1e-6)
    tol = size * DUPLICATE_TOLERANCE
    return all(abs(float(a["bbox_min"][i]) - float(b["bbox_min"][i])) <= tol and abs(float(a["bbox_max"][i]) - float(b["bbox_max"][i])) <= tol
               for i in range(3))


def verdict(all_stats: Sequence[Dict[str, Any]], max_triangles: int = DEFAULT_TRIANGLE_BUDGET,
            assembly: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Merge object, group and assembly findings: FAIL blocks ``ok``, WARN does not; the same code on several objects counts once."""
    merged: Dict[str, Dict[str, Any]] = {}
    for stats in all_stats:
        for issue in object_issues(stats):
            item = merged.setdefault(issue["code"], {**issue, "objects": [], "count": 0, "messages": []})
            item["objects"].extend(issue["objects"])
            item["count"] += 1
            if len(item["messages"]) < 3:
                item["messages"].append(issue["message"])
    for issue in group_issues(all_stats, max_triangles) + assembly_issues(assembly):
        item = merged.setdefault(issue["code"], {**issue, "objects": [], "count": 0, "messages": []})
        item["objects"].extend(issue["objects"])
        item["count"] += 1
        if len(item["messages"]) < 3:
            item["messages"].append(issue["message"])
    issues = sorted(merged.values(), key=lambda i: (i["severity"] != FAIL, -i["count"]))
    for issue in issues:
        issue["message"] = "; ".join(issue.pop("messages"))
        issue["objects"] = sorted(set(issue["objects"]))[:12]
    fails = [i for i in issues if i["severity"] == FAIL]
    warns = [i for i in issues if i["severity"] == WARN]
    summary = "the model is clean" if not issues else f"{len(fails)} failures, {len(warns)} warnings: " + "; ".join(
        i["code"].lower() for i in issues[:5])
    return {"ok": not fails, "clean": not issues, "issues": issues, "summary": summary,
            "triangles": sum(int(s.get("tris", 0)) for s in all_stats), "objects_checked": len(all_stats)}
