"""Polish mutator: bevel the hard edges and smooth-shade by angle, so blocky low-poly models catch light like designed ones.

Bevels and sharp edges are what separate a grey-box prop from a finished one, and models rarely add them on their own.
Data API and BMesh only, bounded like the other modeling tools.
"""

import math
from typing import Any, Dict

import bmesh
import bpy
from mathutils import Vector

from adapter.mutators.modeling_mutator import MAX_FACES, MAX_VERTICES, ModelingError, _mesh_object, _unique_mesh, as_list
from adapter.mutators.undo_manager import push_undo_step


class PolishMutator:
    """Bevel hard edges and set smooth shading with sharp edges."""

    @classmethod
    def polish_model(cls, object_names: Any, bevel: Any = None, segments: int = 3, smooth_angle: float = 45.0,
                     bevel_angle: float = 30.0) -> Dict[str, Any]:
        object_names = as_list(object_names)
        if not isinstance(object_names, list) or not object_names:
            raise ModelingError("object_names must be a non-empty list of mesh object names.")
        try:
            seg = int(segments)
            smooth = float(smooth_angle)
            hard = float(bevel_angle)
            width = float(bevel) if bevel is not None else None
        except (TypeError, ValueError):
            raise ModelingError("bevel, segments, smooth_angle and bevel_angle must be numbers.")
        if not 1 <= seg <= 4:
            raise ModelingError("segments must be between 1 and 4.")
        if not (5.0 <= smooth <= 90.0) or not (5.0 <= hard <= 90.0):
            raise ModelingError("smooth_angle and bevel_angle must be between 5 and 90 degrees.")
        if width is not None and not (0.0005 <= width <= 1.0):
            raise ModelingError("bevel must be between 0.0005 and 1 meter.")
        report = []
        for name in object_names:
            obj = _mesh_object(name)
            mesh = _unique_mesh(obj)
            dims = obj.dimensions
            smallest = min((d for d in dims if d > 1e-6), default=0.1)
            # default bevel: 4 percent of the smallest side, between 2 mm and 5 cm, in meters
            meters = width if width is not None else min(max(smallest * 0.04, 0.002), 0.05)
            scale = max(sum(abs(s) for s in obj.scale) / 3.0, 1e-6)
            local = meters / scale
            bm = bmesh.new()
            try:
                bm.from_mesh(mesh)
                edges = [e for e in bm.edges if e.is_manifold and e.calc_face_angle(0.0) >= math.radians(hard)]
                before = len(bm.faces)
                if edges:
                    bmesh.ops.bevel(bm, geom=edges, offset=local, segments=seg, affect="EDGES")
                if len(bm.verts) > MAX_VERTICES or len(bm.faces) > MAX_FACES:
                    raise ModelingError(f"'{name}' would exceed the size limit after bevelling; lower segments or bevel fewer edges.")
                limit = math.radians(smooth)
                sharp = 0
                for face in bm.faces:
                    face.smooth = True
                for edge in bm.edges:
                    if edge.is_manifold and edge.calc_face_angle(0.0) > limit:
                        edge.smooth = False
                        sharp += 1
                    else:
                        edge.smooth = True
                bm.normal_update()
                bm.to_mesh(mesh)
                after = len(bm.faces)
            finally:
                bm.free()
            mesh.update()
            report.append({"object": obj.name, "bevelled_edges": len(edges), "faces": [before, after],
                           "sharp_edges": sharp, "bevel_m": round(meters, 4)})
        push_undo_step(f"AI: Polish {len(report)} object(s)")
        return {"polished": report, "note": "smooth shading with sharp edges; shade flat again with set_shading if a faceted look is wanted"}
