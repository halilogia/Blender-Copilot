"""BlenderAdapter facade for centralized, thread-safe Blender API access.

Ensures main-thread execution, encapsulates readers, and normalizes
Blender exceptions into standardized ToolResult objects.
"""

import threading
from pathlib import Path
from typing import Any, Dict, Optional

from core.types import ToolResult
from adapter.readers.scene_reader import SceneReader
from adapter.readers.selection_reader import SelectionReader
from adapter.readers.object_reader import ObjectReader, ObjectNotFoundError
from adapter.readers.material_reader import (
    MaterialReader,
    MaterialNotFoundError,
    MaterialSlotError,
)
from adapter.readers.mesh_reader import (
    MeshReader,
    InvalidMeshDataTypeError,
)
from adapter.readers.viewport_reader import ViewportReader
from adapter.mutators.modeling_mutator import ModelingError, ModelingMutator
from adapter.mutators.cinema_mutator import CinemaMutator
from adapter.mutators.character_mutator import CharacterMutator
from adapter.mutators.look_mutator import LookMutator
from adapter.mutators.video_mutator import VideoMutator
from adapter.mutators import (
    PrimitiveMutator,
    InvalidPrimitiveTypeError,
    CameraMutator,
    LightMutator,
    ShadingMutator,
    ModifierMutator,
    DuplicateMutator,
    TransformMutator,
    DeleteMutator,
    MaterialMutator,
)


class ThreadSafetyViolationError(RuntimeError):
    """Raised when BlenderAdapter is accessed from a background worker thread."""


def assert_main_thread() -> None:
    """Lightweight guard ensuring bpy access occurs solely on the main thread."""
    if threading.current_thread() is not threading.main_thread():
        raise ThreadSafetyViolationError(
            f"BlenderAdapter accessed from background thread '{threading.current_thread().name}'. "
            "All bpy interactions must occur on the main thread."
        )


class BlenderAdapter:
    """Centralized adapter for interacting with the Blender runtime."""

    def __init__(self, asset_library_root=None):
        self._scene_reader = SceneReader()
        self._selection_reader = SelectionReader()
        self._object_reader = ObjectReader()
        self._material_reader = MaterialReader()
        self._mesh_reader = MeshReader()
        self._viewport_reader = ViewportReader()
        self.asset_library_root = asset_library_root
        self.export_dir = str(Path.home() / "Documents" / "BlenderCopilot" / "exports")

    def inspect_scene(self) -> ToolResult:
        """Inspect the active scene summary.

        Returns:
            ToolResult conforming to inspect_scene contract.
        """
        assert_main_thread()
        tool_name = "inspect_scene"
        try:
            data = self._scene_reader.read()
            return ToolResult.ok(tool_name, data)
        except Exception as exc:
            return ToolResult.fail(
                tool=tool_name,
                error_type="CONTEXT_UNAVAILABLE",
                message=f"Failed to inspect scene: {str(exc)}",
                details={"exception": type(exc).__name__},
            )

    def inspect_selection(self) -> ToolResult:
        """Inspect the current selection state and mode.

        Returns:
            ToolResult conforming to inspect_selection contract.
        """
        assert_main_thread()
        tool_name = "inspect_selection"
        try:
            data = self._selection_reader.read()
            return ToolResult.ok(tool_name, data)
        except Exception as exc:
            return ToolResult.fail(
                tool=tool_name,
                error_type="CONTEXT_UNAVAILABLE",
                message=f"Failed to inspect selection: {str(exc)}",
                details={"exception": type(exc).__name__},
            )

    def inspect_object(self, name: str, include_evaluated: bool = False) -> ToolResult:
        """Inspect deep properties of an object by name.

        Args:
            name: Name of the object.
            include_evaluated: Whether to evaluate modifiers/depsgraph.

        Returns:
            ToolResult conforming to inspect_object contract.
        """
        assert_main_thread()
        tool_name = "inspect_object"

        if not name or not isinstance(name, str):
            return ToolResult.fail(
                tool=tool_name,
                error_type="INVALID_ARGUMENT",
                message="Argument 'name' must be a non-empty string.",
                details={"provided_name": str(name)},
            )

        try:
            data = self._object_reader.read(name, include_evaluated=include_evaluated)
            return ToolResult.ok(tool_name, data)
        except ObjectNotFoundError as not_found:
            return ToolResult.fail(
                tool=tool_name,
                error_type="OBJECT_NOT_FOUND",
                message=str(not_found),
                details={"queried_name": name},
            )
        except Exception as exc:
            return ToolResult.fail(
                tool=tool_name,
                error_type="ADAPTER_INTERNAL_ERROR",
                message=f"Unexpected error inspecting object '{name}': {str(exc)}",
                details={"exception": type(exc).__name__},
            )

    def inspect_material(
        self,
        material_name: Optional[str] = None,
        object_name: Optional[str] = None,
        slot_index: Optional[int] = 0,
    ) -> ToolResult:
        """Inspect material properties via direct name or object slot binding.

        Returns:
            ToolResult conforming to inspect_material contract.
        """
        assert_main_thread()
        tool_name = "inspect_material"

        try:
            data = self._material_reader.read(
                material_name=material_name,
                object_name=object_name,
                slot_index=slot_index,
            )
            return ToolResult.ok(tool_name, data)
        except ObjectNotFoundError as not_found:
            return ToolResult.fail(
                tool=tool_name,
                error_type="OBJECT_NOT_FOUND",
                message=str(not_found),
                details={"object_name": object_name},
            )
        except MaterialNotFoundError as not_found:
            return ToolResult.fail(
                tool=tool_name,
                error_type="MATERIAL_NOT_FOUND",
                message=str(not_found),
                details={"material_name": material_name},
            )
        except MaterialSlotError as slot_err:
            return ToolResult.fail(
                tool=tool_name,
                error_type="SLOT_INDEX_OUT_OF_RANGE",
                message=str(slot_err),
                details={"object_name": object_name, "slot_index": slot_index},
            )
        except ValueError as val_err:
            return ToolResult.fail(
                tool=tool_name,
                error_type="INVALID_ARGUMENT",
                message=str(val_err),
                details={},
            )
        except Exception as exc:
            return ToolResult.fail(
                tool=tool_name,
                error_type="ADAPTER_INTERNAL_ERROR",
                message=f"Unexpected error inspecting material: {str(exc)}",
                details={"exception": type(exc).__name__},
            )

    def inspect_mesh(self, object_name: str) -> ToolResult:
        """Inspect mesh geometry metrics, topology breakdown, and world bounding box.

        Returns:
            ToolResult conforming to inspect_mesh contract.
        """
        assert_main_thread()
        tool_name = "inspect_mesh"

        if not object_name or not isinstance(object_name, str):
            return ToolResult.fail(
                tool=tool_name,
                error_type="INVALID_ARGUMENT",
                message="Argument 'object_name' must be a non-empty string.",
                details={"provided": str(object_name)},
            )

        try:
            data = self._mesh_reader.read(object_name=object_name)
            return ToolResult.ok(tool_name, data)
        except ObjectNotFoundError as not_found:
            return ToolResult.fail(
                tool=tool_name,
                error_type="OBJECT_NOT_FOUND",
                message=str(not_found),
                details={"object_name": object_name},
            )
        except InvalidMeshDataTypeError as type_err:
            return ToolResult.fail(
                tool=tool_name,
                error_type="INVALID_DATA_TYPE",
                message=str(type_err),
                details={"object_name": object_name},
            )
        except Exception as exc:
            return ToolResult.fail(
                tool=tool_name,
                error_type="ADAPTER_INTERNAL_ERROR",
                message=f"Unexpected error inspecting mesh '{object_name}': {str(exc)}",
                details={"exception": type(exc).__name__},
            )

    def create_primitive(
        self,
        primitive_type: str,
        name: Optional[str] = None,
        location: Optional[Any] = None,
        rotation: Optional[Any] = None,
        scale: Optional[Any] = None,
        size: Optional[float] = None,
    ) -> ToolResult:
        """Create a new geometric primitive (CUBE, SPHERE, PLANE) in the scene.

        Returns:
            ToolResult conforming to create_primitive contract.
        """
        assert_main_thread()
        tool_name = "create_primitive"

        try:
            data = PrimitiveMutator.create(
                primitive_type=primitive_type,
                name=name,
                location=location,
                rotation=rotation,
                scale=scale,
                size=size,
            )
            return ToolResult.ok(tool_name, data)
        except InvalidPrimitiveTypeError as type_err:
            return ToolResult.fail(
                tool=tool_name,
                error_type="INVALID_PRIMITIVE_TYPE",
                message=str(type_err),
                details={"primitive_type": str(primitive_type)},
            )
        except ValueError as val_err:
            return ToolResult.fail(
                tool=tool_name,
                error_type="INVALID_ARGUMENT",
                message=str(val_err),
                details={"error": str(val_err)},
            )
        except Exception as exc:
            return ToolResult.fail(
                tool=tool_name,
                error_type="ADAPTER_INTERNAL_ERROR",
                message=f"Unexpected error creating primitive '{primitive_type}': {str(exc)}",
                details={"exception": type(exc).__name__},
            )

    def create_camera(
        self,
        name: Optional[str] = None,
        location: Optional[Any] = None,
        rotation: Optional[Any] = None,
        lens: Optional[float] = None,
        make_active: bool = True,
    ) -> ToolResult:
        """Create a new camera or modify an existing camera in the scene.

        Returns:
            ToolResult conforming to create_camera contract.
        """
        assert_main_thread()
        tool_name = "create_camera"

        try:
            data = CameraMutator.create_or_modify(
                name=name,
                location=location,
                rotation=rotation,
                lens=lens,
                make_active=make_active,
            )
            return ToolResult.ok(tool_name, data)
        except ValueError as val_err:
            return ToolResult.fail(
                tool=tool_name,
                error_type="INVALID_ARGUMENT",
                message=str(val_err),
                details={"error": str(val_err)},
            )
        except Exception as exc:
            return ToolResult.fail(
                tool=tool_name,
                error_type="ADAPTER_INTERNAL_ERROR",
                message=f"Unexpected error creating/modifying camera: {str(exc)}",
                details={"exception": type(exc).__name__},
            )

    def create_light(
        self,
        name: Optional[str] = None,
        light_type: Optional[str] = None,
        location: Optional[Any] = None,
        rotation: Optional[Any] = None,
        energy: Optional[float] = None,
        color: Optional[Any] = None,
    ) -> ToolResult:
        """Create a new light or modify an existing light in the scene.

        Returns:
            ToolResult conforming to create_light contract.
        """
        assert_main_thread()
        tool_name = "create_light"

        try:
            data = LightMutator.create_or_modify(
                name=name,
                light_type=light_type,
                location=location,
                rotation=rotation,
                energy=energy,
                color=color,
            )
            return ToolResult.ok(tool_name, data)
        except ValueError as val_err:
            return ToolResult.fail(
                tool=tool_name,
                error_type="INVALID_ARGUMENT",
                message=str(val_err),
                details={"error": str(val_err)},
            )
        except Exception as exc:
            return ToolResult.fail(
                tool=tool_name,
                error_type="ADAPTER_INTERNAL_ERROR",
                message=f"Unexpected error creating/modifying light: {str(exc)}",
                details={"exception": type(exc).__name__},
            )

    def set_shading(self, name: str, shading: str) -> ToolResult:
        """Set smooth or flat shading on all polygons of a target mesh object.

        Returns:
            ToolResult conforming to set_shading contract.
        """
        assert_main_thread()
        tool_name = "set_shading"

        try:
            data = ShadingMutator.set_shading(name=name, shading=shading)
            return ToolResult.ok(tool_name, data)
        except ValueError as val_err:
            return ToolResult.fail(
                tool=tool_name,
                error_type="INVALID_ARGUMENT",
                message=str(val_err),
                details={"error": str(val_err)},
            )
        except Exception as exc:
            return ToolResult.fail(
                tool=tool_name,
                error_type="ADAPTER_INTERNAL_ERROR",
                message=f"Unexpected error setting shading on '{name}': {str(exc)}",
                details={"exception": type(exc).__name__},
            )

    def add_modifier(
        self,
        name: str,
        modifier_type: str,
        modifier_name: Optional[str] = None,
        width: Optional[float] = None,
        segments: Optional[int] = None,
        levels: Optional[int] = None,
        operation: Optional[str] = None,
        target_object: Optional[str] = None,
    ) -> ToolResult:
        """Add or update a modifier on a target mesh object.

        Returns:
            ToolResult conforming to add_modifier contract.
        """
        assert_main_thread()
        tool_name = "add_modifier"

        try:
            data = ModifierMutator.add_modifier(
                name=name,
                modifier_type=modifier_type,
                modifier_name=modifier_name,
                width=width,
                segments=segments,
                levels=levels,
                operation=operation,
                target_object=target_object,
            )
            return ToolResult.ok(tool_name, data)
        except ValueError as val_err:
            return ToolResult.fail(
                tool=tool_name,
                error_type="INVALID_ARGUMENT",
                message=str(val_err),
                details={"error": str(val_err)},
            )
        except Exception as exc:
            return ToolResult.fail(
                tool=tool_name,
                error_type="ADAPTER_INTERNAL_ERROR",
                message=f"Unexpected error adding modifier to '{name}': {str(exc)}",
                details={"exception": type(exc).__name__},
            )


    def transform_object(
        self,
        name: str,
        location: Optional[Any] = None,
        rotation: Optional[Any] = None,
        scale: Optional[Any] = None,
        relative: bool = False,
    ) -> ToolResult:
        """Transform object location, rotation, or scale.

        Returns:
            ToolResult conforming to transform_object contract.
        """
        assert_main_thread()
        tool_name = "transform_object"

        try:
            data = TransformMutator.transform(
                name=name,
                location=location,
                rotation=rotation,
                scale=scale,
                relative=relative,
            )
            return ToolResult.ok(tool_name, data)
        except ObjectNotFoundError as not_found:
            return ToolResult.fail(
                tool=tool_name,
                error_type="OBJECT_NOT_FOUND",
                message=str(not_found),
                details={"object_name": name},
            )
        except ValueError as val_err:
            return ToolResult.fail(
                tool=tool_name,
                error_type="INVALID_ARGUMENT",
                message=str(val_err),
                details={"object_name": name},
            )
        except Exception as exc:
            return ToolResult.fail(
                tool=tool_name,
                error_type="ADAPTER_INTERNAL_ERROR",
                message=f"Unexpected error transforming object '{name}': {str(exc)}",
                details={"exception": type(exc).__name__},
            )

    def delete_object(self, name: str) -> ToolResult:
        """Delete object by exact name.

        Returns:
            ToolResult conforming to delete_object contract.
        """
        assert_main_thread()
        tool_name = "delete_object"

        try:
            data = DeleteMutator.delete(name=name)
            return ToolResult.ok(tool_name, data)
        except ObjectNotFoundError as not_found:
            return ToolResult.fail(
                tool=tool_name,
                error_type="OBJECT_NOT_FOUND",
                message=str(not_found),
                details={"object_name": name},
            )
        except ValueError as val_err:
            return ToolResult.fail(
                tool=tool_name,
                error_type="INVALID_ARGUMENT",
                message=str(val_err),
                details={"object_name": name},
            )
        except Exception as exc:
            return ToolResult.fail(
                tool=tool_name,
                error_type="ADAPTER_INTERNAL_ERROR",
                message=f"Unexpected error deleting object '{name}': {str(exc)}",
                details={"exception": type(exc).__name__},
            )

    def duplicate_object(
        self,
        source_name: str,
        new_name: Optional[str] = None,
        location: Optional[Any] = None,
        rotation: Optional[Any] = None,
        scale: Optional[Any] = None,
    ) -> ToolResult:
        """Safely duplicate an existing object with independent data and optional transforms.

        Returns:
            ToolResult conforming to duplicate_object contract.
        """
        assert_main_thread()
        tool_name = "duplicate_object"

        try:
            data = DuplicateMutator.duplicate(
                source_name=source_name,
                new_name=new_name,
                location=location,
                rotation=rotation,
                scale=scale,
            )
            return ToolResult.ok(tool_name, data)
        except ObjectNotFoundError as not_found:
            return ToolResult.fail(
                tool=tool_name,
                error_type="OBJECT_NOT_FOUND",
                message=str(not_found),
                details={"source_name": source_name},
            )
        except ValueError as val_err:
            return ToolResult.fail(
                tool=tool_name,
                error_type="INVALID_ARGUMENT",
                message=str(val_err),
                details={"source_name": source_name, "error": str(val_err)},
            )
        except Exception as exc:
            return ToolResult.fail(
                tool=tool_name,
                error_type="ADAPTER_INTERNAL_ERROR",
                message=f"Unexpected error duplicating object '{source_name}': {str(exc)}",
                details={"exception": type(exc).__name__},
            )

    def import_asset(self, path: str, name: Optional[str] = None) -> ToolResult:
        """Import a library asset file into the scene (v1.1 C, main thread only)."""
        assert_main_thread()
        tool_name = "import_asset"
        try:
            import os as _os
            from pathlib import Path as _Path
            from agent.asset_index import is_safe_path as _safe
            root = getattr(self, "asset_library_root", None) or _os.environ.get("BLENDER_AI_ASSET_DIR", "")
            if not root:
                return ToolResult.fail(tool=tool_name, error_type="ASSET_LIBRARY_UNCONFIGURED",
                                       message="Asset library root is not configured.",
                                       details={"path": path})
            if ".." in str(path).replace("\\", "/").split("/"):
                return ToolResult.fail(tool=tool_name, error_type="INVALID_ARGUMENT",
                                       message="Path traversal '..' is not allowed.",
                                       details={"path": path})
            if not _safe(root, path):
                return ToolResult.fail(tool=tool_name, error_type="INVALID_ARGUMENT",
                                       message="Asset path escapes library root.",
                                       details={"path": path})
            abs_p = str((_Path(root) / path).resolve())
            if not _safe(root, abs_p) or not _Path(abs_p).is_file():
                return ToolResult.fail(tool=tool_name, error_type="ASSET_NOT_FOUND",
                                       message=f"Asset not found: {path}",
                                       details={"path": path})
            try:
                import bpy as _bpy
            except ImportError:
                return ToolResult.fail(tool=tool_name, error_type="BLENDER_RUNTIME_UNAVAILABLE",
                                       message="Blender runtime (bpy) is not available.",
                                       details={"path": path})
            from adapter.mutators import push_undo_step as _push
            before = set(_bpy.data.objects.keys()) if hasattr(_bpy.data.objects, "keys") else {o.name for o in _bpy.data.objects}
            before_count = len(list(_bpy.data.objects))
            ext = _Path(abs_p).suffix.lower()
            if ext == ".blend":
                # v1.1 convention: appended Object datablock is named by file stem
                # (single-object libraries). If caller passes `name`, try it first
                # as the datablock name, then fall back to the file stem.
                _candidates = [name, _Path(abs_p).stem] if name else [_Path(abs_p).stem]
                _appended = False
                for _cand in _candidates:
                    try:
                        _bpy.ops.wm.append(filepath=_Path(abs_p).name, directory=str(abs_p) + "\\Object\\",
                                           filename=_cand)
                    except Exception:
                        continue
                    _after_try = {o.name for o in _bpy.data.objects}
                    if len(_after_try - before) > 0:
                        _appended = True
                        break
                if not _appended:
                    return ToolResult.fail(tool=tool_name, error_type="ASSET_NOT_FOUND",
                                           message=f"No appendable object datablock in '{path}' (tried { _candidates}).",
                                           details={"path": path})
            elif ext in (".glb", ".obj", ".fbx"):
                if ext == ".glb":
                    _bpy.ops.import_scene.gltf(filepath=abs_p)
                elif ext == ".obj":
                    _bpy.ops.wm.obj_import(filepath=abs_p)
                else:
                    _bpy.ops.import_scene.fbx(filepath=abs_p)
            else:
                return ToolResult.fail(tool=tool_name, error_type="INVALID_ARGUMENT",
                                       message=f"Unsupported asset extension '{ext}'.",
                                       details={"path": path})
            after = list(_bpy.data.objects)
            new_objs = [o for o in after if o.name not in before]
            obj_name = new_objs[0].name if new_objs else (name or _Path(abs_p).stem)
            if name and new_objs:
                try:
                    new_objs[0].name = name
                    obj_name = name
                except Exception:
                    pass
            _push(f"AI: Import Asset ({obj_name})")
            data: Dict[str, Any] = {"imported": True, "object_name": obj_name,
                                    "object_count": len(after),
                                    "before": {"object_count": before_count},
                                    "actual": {"imported": True, "object_name": obj_name,
                                               "object_count": len(after)}}
            return ToolResult.ok(tool_name, data)
        except Exception as exc:
            return ToolResult.fail(tool=tool_name, error_type="ADAPTER_INTERNAL_ERROR",
                                   message=f"Unexpected error importing asset '{path}': {exc}",
                                   details={"exception": type(exc).__name__})

    def set_material(
        self,
        object_name: Optional[str] = None,
        material_name: Optional[str] = None,
        slot_index: int = 0,
        base_color: Optional[Any] = None,
        metallic: Optional[float] = None,
        roughness: Optional[float] = None,
        emission_color: Optional[Any] = None,
        emission_strength: Optional[float] = None,
        alpha: Optional[float] = None,
    ) -> ToolResult:
        """Set Principled BSDF shader properties on an object slot or material.

        Returns:
            ToolResult conforming to set_material contract.
        """
        assert_main_thread()
        tool_name = "set_material"

        try:
            data = MaterialMutator.set_material(
                object_name=object_name,
                material_name=material_name,
                slot_index=slot_index,
                base_color=base_color,
                metallic=metallic,
                roughness=roughness,
                emission_color=emission_color,
                emission_strength=emission_strength,
                alpha=alpha,
            )
            return ToolResult.ok(tool_name, data)
        except ObjectNotFoundError as not_found:
            return ToolResult.fail(
                tool=tool_name,
                error_type="OBJECT_NOT_FOUND",
                message=str(not_found),
                details={"object_name": object_name},
            )
        except ValueError as val_err:
            return ToolResult.fail(
                tool=tool_name,
                error_type="INVALID_ARGUMENT",
                message=str(val_err),
                details={"object_name": object_name, "material_name": material_name},
            )
        except Exception as exc:
            return ToolResult.fail(
                tool=tool_name,
                error_type="ADAPTER_INTERNAL_ERROR",
                message=f"Unexpected error setting material: {str(exc)}",
                details={"exception": type(exc).__name__},
            )

    def assign_material(
        self,
        object_name: str,
        material_name: str,
        slot_index: int = 0,
    ) -> ToolResult:
        """Assign material to an object at the specified slot index.

        Returns:
            ToolResult conforming to assign_material contract.
        """
        assert_main_thread()
        tool_name = "assign_material"

        try:
            data = MaterialMutator.assign_material(
                object_name=object_name,
                material_name=material_name,
                slot_index=slot_index,
            )
            return ToolResult.ok(tool_name, data)
        except ObjectNotFoundError as not_found:
            return ToolResult.fail(
                tool=tool_name,
                error_type="OBJECT_NOT_FOUND",
                message=str(not_found),
                details={"object_name": object_name},
            )
        except ValueError as val_err:
            return ToolResult.fail(
                tool=tool_name,
                error_type="INVALID_ARGUMENT",
                message=str(val_err),
                details={"object_name": object_name, "material_name": material_name},
            )
        except Exception as exc:
            return ToolResult.fail(
                tool=tool_name,
                error_type="ADAPTER_INTERNAL_ERROR",
                message=f"Unexpected error assigning material: {str(exc)}",
                details={"exception": type(exc).__name__},
            )

    def capture_viewport(
        self,
        width: int = 512,
        height: int = 512,
        max_side=None,
    ) -> ToolResult:
        """Capture active 3D Viewport screenshot.

        Args:
            width: Desired image width in pixels (default 512).
            height: Desired image height in pixels (default 512).
            max_side: Optional cost-guard downscale bound (64-2048).

        Returns:
            ToolResult containing image metadata and in-memory reference.
        """
        assert_main_thread()
        tool_name = "capture_viewport"
        try:
            data = self._viewport_reader.capture(width=width, height=height, max_side=max_side)
            return ToolResult.ok(tool_name, data)
        except ValueError as val_err:
            return ToolResult.fail(
                tool=tool_name,
                error_type="INVALID_ARGUMENT",
                message=str(val_err),
                details={"width": width, "height": height, "max_side": max_side},
            )
        except Exception as exc:
            return ToolResult.fail(
                tool=tool_name,
                error_type="VIEWPORT_UNAVAILABLE",
                message=f"Failed to capture viewport: {str(exc)}",
                details={"exception": type(exc).__name__},
            )

    def get_viewport_screenshot(self, image_id: str) -> Optional[bytes]:
        """Retrieve raw PNG bytes for a captured viewport screenshot.

        Args:
            image_id: Unique identifier returned by capture_viewport.

        Returns:
            Raw PNG bytes if cached, else None.
        """
        assert_main_thread()
        return self._viewport_reader.get_image_bytes(image_id)

    # ------------------------------------------------------------------
    # Modeling (v1.2): allow-listed mesh building and editing, no arbitrary Python
    # ------------------------------------------------------------------
    def _modeling(self, tool_name: str, fn, **kwargs) -> ToolResult:
        assert_main_thread()
        try:
            return ToolResult.ok(tool_name, fn(**kwargs))
        except ModelingError as err:
            return ToolResult.fail(tool=tool_name, error_type="INVALID_ARGUMENT", message=str(err), details={"error": str(err)})
        except (TypeError, ValueError) as err:
            return ToolResult.fail(tool=tool_name, error_type="INVALID_ARGUMENT", message=str(err), details={"error": str(err)})
        except Exception as exc:
            return ToolResult.fail(tool=tool_name, error_type="MODELING_FAILED",
                                   message=f"{tool_name} failed: {exc}", details={"exception": type(exc).__name__})

    def create_mesh(self, **kwargs) -> ToolResult:
        return self._modeling("create_mesh", ModelingMutator.create_mesh, **kwargs)

    def mesh_edit(self, **kwargs) -> ToolResult:
        return self._modeling("mesh_edit", ModelingMutator.mesh_edit, **kwargs)

    def join_objects(self, **kwargs) -> ToolResult:
        return self._modeling("join_objects", ModelingMutator.join_objects, **kwargs)

    def parent_object(self, **kwargs) -> ToolResult:
        return self._modeling("parent_object", ModelingMutator.parent_object, **kwargs)

    def apply_transform(self, **kwargs) -> ToolResult:
        return self._modeling("apply_transform", ModelingMutator.apply_transform, **kwargs)

    def set_origin(self, **kwargs) -> ToolResult:
        return self._modeling("set_origin", ModelingMutator.set_origin, **kwargs)

    def export_gltf(self, **kwargs) -> ToolResult:
        kwargs.setdefault("export_dir", self.export_dir)
        return self._modeling("export_gltf", ModelingMutator.export_gltf, **kwargs)

    def add_shape_modifier(self, **kwargs) -> ToolResult:
        return self._modeling("add_shape_modifier", ModelingMutator.add_shape_modifier, **kwargs)

    def frame_view(self, **kwargs) -> ToolResult:
        return self._modeling("frame_view", ModelingMutator.frame_view, **kwargs)

    # ------------------------------------------------------------------
    # Cinematic (v1.3): environment presets, camera moves, EEVEE renders
    # ------------------------------------------------------------------
    def rig_character(self, **kwargs) -> ToolResult:
        return self._modeling("rig_character", CharacterMutator.rig_character, **kwargs)

    def animate_character(self, **kwargs) -> ToolResult:
        return self._modeling("animate_character", CharacterMutator.animate_character, **kwargs)

    def set_environment(self, **kwargs) -> ToolResult:
        return self._modeling("set_environment", CinemaMutator.set_environment, **kwargs)

    def camera_move(self, **kwargs) -> ToolResult:
        return self._modeling("camera_move", CinemaMutator.camera_move, **kwargs)

    def _attach_image(self, result: ToolResult, path_key: str) -> ToolResult:
        """Put a rendered PNG into the in-memory image store so agents (and MCP clients) can look at it."""
        import hashlib

        try:
            data = result.data
            if not result.success or not isinstance(data, dict) or not data.get(path_key):
                return result
            png = Path(data[path_key]).read_bytes()
            image_id = "rn_" + hashlib.sha1(png).hexdigest()[:12]
            cache = self._viewport_reader._cache
            if len(cache) >= self._viewport_reader.MAX_CACHE_SIZE:
                cache.popitem(last=False)
            cache[image_id] = png
            data.update({"image_id": image_id, "mime_type": "image/png", "byte_size": len(png)})
        except Exception:
            pass
        return result

    def set_look(self, **kwargs) -> ToolResult:
        return self._modeling("set_look", LookMutator.set_look, **kwargs)

    def camera_settings(self, **kwargs) -> ToolResult:
        return self._modeling("camera_settings", LookMutator.camera_settings, **kwargs)

    def render_contact_sheet(self, **kwargs) -> ToolResult:
        kwargs.setdefault("export_dir", self.export_dir)
        return self._attach_image(self._modeling("render_contact_sheet", LookMutator.render_contact_sheet, **kwargs), "path")

    def edit_video(self, **kwargs) -> ToolResult:
        kwargs.setdefault("export_dir", self.export_dir)
        return self._modeling("edit_video", VideoMutator.edit_video, **kwargs)

    def render_shots(self, **kwargs) -> ToolResult:
        kwargs.setdefault("export_dir", self.export_dir)
        return self._modeling("render_shots", VideoMutator.render_shots, **kwargs)

    def render_image(self, **kwargs) -> ToolResult:
        kwargs.setdefault("export_dir", self.export_dir)
        return self._attach_image(self._modeling("render_image", CinemaMutator.render_image, **kwargs), "path")

    def render_animation(self, **kwargs) -> ToolResult:
        kwargs.setdefault("export_dir", self.export_dir)
        if "format" in kwargs:
            kwargs["video_format"] = kwargs.pop("format")
        return self._attach_image(self._modeling("render_animation", CinemaMutator.render_animation, **kwargs), "preview_path")
