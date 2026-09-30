"""Semantic diff of two scene snapshots (plain dicts, no bpy): what an AI task added, removed and changed.

A ``.blend`` file is binary, so a task is compared by meaning: objects with their transform, parent, materials, modifiers and
mesh size, plus the list of materials and collections and a few scene settings. ``scene_snapshot`` builds the dicts in Blender;
this module only compares them and writes the result in words a person (or a model) can read.
"""

from typing import Any, Dict, List

MAX_LINES = 40
FIELDS = ("type", "location", "rotation", "scale", "parent", "hidden", "materials", "modifiers", "collections", "data")


def _fmt(value: Any) -> str:
    if isinstance(value, (list, tuple)):
        return "[" + ", ".join(_fmt(v) for v in value) + "]"
    if isinstance(value, dict):
        return "{" + ", ".join(f"{k}: {_fmt(v)}" for k, v in value.items()) + "}"
    if isinstance(value, float):
        return f"{value:g}"
    return str(value)


def _same(a: Any, b: Any) -> bool:
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        return len(a) == len(b) and all(_same(x, y) for x, y in zip(a, b))
    if isinstance(a, float) or isinstance(b, float):
        try:
            return abs(float(a) - float(b)) < 1e-4
        except (TypeError, ValueError):
            return False
    return a == b


def diff(before: Dict[str, Any], after: Dict[str, Any]) -> Dict[str, Any]:
    """Compare two snapshots. ``empty`` is true when nothing differs."""
    b_objs, a_objs = before.get("objects", {}), after.get("objects", {})
    added = [{"name": n, "type": a_objs[n].get("type", "")} for n in a_objs if n not in b_objs]
    removed = [{"name": n, "type": b_objs[n].get("type", "")} for n in b_objs if n not in a_objs]
    changed: List[Dict[str, Any]] = []
    for name in a_objs:
        if name not in b_objs:
            continue
        old, new = b_objs[name], a_objs[name]
        fields = [f for f in FIELDS if not _same(old.get(f), new.get(f))]
        if fields:
            changed.append({"name": name, "fields": {f: {"before": old.get(f), "after": new.get(f)} for f in fields}})
    b_mats, a_mats = set(before.get("materials", [])), set(after.get("materials", []))
    b_cols, a_cols = set(before.get("collections", [])), set(after.get("collections", []))
    scene_changes = {k: {"before": before.get("scene", {}).get(k), "after": v} for k, v in after.get("scene", {}).items()
                     if not _same(before.get("scene", {}).get(k), v)}
    result = {
        "added": added, "removed": removed, "changed": changed,
        "materials_added": sorted(a_mats - b_mats), "materials_removed": sorted(b_mats - a_mats),
        "collections_added": sorted(a_cols - b_cols), "collections_removed": sorted(b_cols - a_cols),
        "scene": scene_changes,
    }
    result["empty"] = not any(result[k] for k in ("added", "removed", "changed", "materials_added", "materials_removed",
                                                  "collections_added", "collections_removed", "scene"))
    result["counts"] = {"objects_added": len(added), "objects_removed": len(removed), "objects_changed": len(changed),
                        "materials_added": len(result["materials_added"])}
    result["summary"] = summarize(result)
    return result


def summarize(result: Dict[str, Any]) -> List[str]:
    """Lines such as ``+ Chair (MESH)``, ``- Cube``, ``~ Table: location [0, 0, 0] -> [1, 0, 0]``."""
    lines: List[str] = []
    for item in result["added"]:
        lines.append(f"+ {item['name']} ({item['type']})")
    for item in result["removed"]:
        lines.append(f"- {item['name']} ({item['type']})")
    for item in result["changed"]:
        for field, change in item["fields"].items():
            lines.append(f"~ {item['name']}: {field} {_fmt(change['before'])} -> {_fmt(change['after'])}")
    for name in result["materials_added"]:
        lines.append(f"+ material {name}")
    for name in result["materials_removed"]:
        lines.append(f"- material {name}")
    for name in result["collections_added"]:
        lines.append(f"+ collection {name}")
    for name in result["collections_removed"]:
        lines.append(f"- collection {name}")
    for key, change in result["scene"].items():
        lines.append(f"~ scene {key} {_fmt(change['before'])} -> {_fmt(change['after'])}")
    if len(lines) > MAX_LINES:
        extra = len(lines) - MAX_LINES
        lines = lines[:MAX_LINES] + [f"... and {extra} more"]
    return lines


def headline(result: Dict[str, Any]) -> str:
    """One line for a status bar: ``3 added, 1 removed, 2 changed`` or ``no changes``."""
    if result.get("empty"):
        return "no changes"
    c = result["counts"]
    parts = [f"{c['objects_added']} added" if c["objects_added"] else "", f"{c['objects_removed']} removed" if c["objects_removed"] else "",
             f"{c['objects_changed']} changed" if c["objects_changed"] else "",
             f"{c['materials_added']} new materials" if c["materials_added"] else ""]
    text = ", ".join(p for p in parts if p)
    return text or "scene settings changed"
