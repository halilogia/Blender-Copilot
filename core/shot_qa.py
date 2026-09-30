"""Deterministic shot checks as plain math (no bpy): turn framing and brightness numbers into plain advice.

A model that cannot look at a picture (or misreads it) still needs to know that the subject is cut off, tiny, off centre,
behind the camera, or that the frame is black or blown out. ``check_shot`` measures those things exactly and this module
says what they mean and what to change, in the words of the tools.
"""

from typing import Any, Dict, List, Sequence

# thresholds, tuned on the demo shots
MIN_AREA = 0.04          # subject smaller than 4 percent of the frame is lost
MAX_AREA = 0.88          # bigger than that leaves no air around it
EDGE_TOLERANCE = 0.02    # how far past the frame edge before it counts as cut
MAX_OFFSET = 0.30        # distance of the subject centre from the frame centre (0 to 0.7)
DARK_MEAN = 0.10
BRIGHT_MEAN = 0.86
WHITE_LIMIT = 0.25       # share of blown pixels
BLACK_LIMIT = 0.55       # share of crushed pixels


def rect_of(points: Sequence[Sequence[float]]) -> Dict[str, Any]:
    """Screen rectangle of projected points (x, y in 0..1 across the frame, z = distance in front of the camera)."""
    front = [p for p in points if p[2] > 1e-6]
    if not front:
        return {"visible": False, "behind": True}
    xs, ys = [p[0] for p in front], [p[1] for p in front]
    return {"visible": True, "behind": len(front) < len(points), "xmin": min(xs), "xmax": max(xs), "ymin": min(ys), "ymax": max(ys)}


def frame_issues(rect: Dict[str, Any]) -> List[Dict[str, str]]:
    """Problems with where the subject sits in the frame."""
    if not rect.get("visible"):
        return [{"code": "SUBJECT_BEHIND_CAMERA", "message": "The subject is behind the camera or not in view at all.",
                 "fix": "call camera_move again with the subject's object_names (and follow=true if it moves)"}]
    issues: List[Dict[str, str]] = []
    xmin, xmax, ymin, ymax = rect["xmin"], rect["xmax"], rect["ymin"], rect["ymax"]
    width, height = max(xmax - xmin, 1e-6), max(ymax - ymin, 1e-6)
    area = min(xmax, 1.0) - max(xmin, 0.0)
    area = max(area, 0.0) * max(min(ymax, 1.0) - max(ymin, 0.0), 0.0)
    cut = [name for name, over in (("left", -xmin), ("right", xmax - 1.0), ("bottom", -ymin), ("top", ymax - 1.0)) if over > EDGE_TOLERANCE]
    if cut:
        issues.append({"code": "SUBJECT_CUT", "message": f"The subject is cut off at the {' and '.join(cut)} of the frame.",
                       "fix": "raise camera_move distance (about 20 to 30 percent), lower elevation, or use a smaller focal_length"})
    full_area = width * height
    if not cut and full_area < MIN_AREA:
        issues.append({"code": "SUBJECT_TOO_SMALL", "message": f"The subject fills only {full_area * 100:.1f} percent of the frame.",
                       "fix": "lower camera_move distance, or raise focal_length"})
    if full_area > MAX_AREA and not cut:
        issues.append({"code": "SUBJECT_TOO_BIG", "message": f"The subject fills {full_area * 100:.0f} percent of the frame, no air around it.",
                       "fix": "raise camera_move distance"})
    cx, cy = (xmin + xmax) / 2 - 0.5, (ymin + ymax) / 2 - 0.5
    if (cx * cx + cy * cy) ** 0.5 > MAX_OFFSET and not cut:
        side = ("right" if cx > 0 else "left") if abs(cx) >= abs(cy) else ("top" if cy > 0 else "bottom")
        issues.append({"code": "SUBJECT_OFF_CENTER", "message": f"The subject sits far toward the {side} of the frame.",
                       "fix": "give camera_move the subject's object_names so the camera aims at it (follow=true if it moves)"})
    if rect.get("behind"):
        issues.append({"code": "CAMERA_INSIDE_SUBJECT", "message": "Part of the subject is behind the camera: the camera is inside or right next to it.",
                       "fix": "raise camera_move distance"})
    return issues


def light_issues(stats: Dict[str, float]) -> List[Dict[str, str]]:
    """Problems with brightness: mean luminance 0..1, share of blown (white) and crushed (black) pixels."""
    issues: List[Dict[str, str]] = []
    mean, white, black = stats["mean"], stats["white"], stats["black"]
    if mean < DARK_MEAN:
        issues.append({"code": "TOO_DARK", "message": f"The picture is very dark (average brightness {mean:.2f}).",
                       "fix": "call set_environment (studio, day or overcast are bright) and check that the subject is lit from the camera side"})
    elif black > BLACK_LIMIT:
        issues.append({"code": "MOSTLY_BLACK", "message": f"{black * 100:.0f} percent of the picture is black.",
                       "fix": "call set_environment with a brighter preset, or camera_move azimuth so the light falls on the visible side"})
    if mean > BRIGHT_MEAN:
        issues.append({"code": "TOO_BRIGHT", "message": f"The picture is very bright (average brightness {mean:.2f}).",
                       "fix": "call set_environment with overcast or night, or set_look with cold"})
    elif white > WHITE_LIMIT:
        issues.append({"code": "BLOWN_OUT", "message": f"{white * 100:.0f} percent of the picture is blown out to white.",
                       "fix": "call set_environment with overcast, or give light-coloured objects darker colours"})
    return issues


def verdict(frames: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Merge the per-frame results: an issue counts once, with the frames it appears in."""
    merged: Dict[str, Dict[str, Any]] = {}
    for entry in frames:
        for issue in entry.get("issues", []):
            item = merged.setdefault(issue["code"], {**issue, "frames": []})
            item["frames"].append(entry["frame"])
    issues = sorted(merged.values(), key=lambda i: -len(i["frames"]))
    return {"ok": not issues, "issues": issues,
            "summary": "the shot looks fine" if not issues else "; ".join(i["message"] for i in issues[:3])}
