"""Which tools the MCP bridge shows to an external agent. Fail-closed: a tool that is not listed here is not exposed.

Registering a new tool in the add-on never makes it reachable over MCP by itself. Whoever adds a tool decides here, in one
place, whether an outside agent may use it: read only, a safe (undoable, low risk) change, a gated one that needs the user's
approval, or internal to the add-on's own agent. ``tests/unit/test_mcp_exposure.py`` fails when a registered tool is not
classified, when a name here does not exist, or when a category contradicts the tool's risk level.
"""

from typing import Dict, FrozenSet, Iterable, List

READ_ONLY = frozenset({
    "inspect_scene", "inspect_selection", "inspect_object", "inspect_material", "inspect_mesh",
    "capture_viewport", "visual_verify", "check_model", "check_shot", "task_report",
})

# low risk, one undo step, no arbitrary code: an outside agent may call these freely
SAFE_MUTATION = frozenset({
    "create_primitive", "create_mesh", "create_prop", "create_terrain", "scatter", "mesh_edit", "polish_model",
    "add_modifier", "add_shape_modifier", "join_objects", "parent_object", "apply_transform", "set_origin",
    "transform_object", "duplicate_object", "create_camera", "create_light", "frame_view", "import_asset",
    "set_material", "assign_material", "set_shading", "unwrap_uv", "bake_material",
    "set_environment", "set_look", "camera_move", "camera_settings", "render_image", "render_contact_sheet",
    "render_animation", "render_shots", "edit_video", "make_soundtrack",
    "rig_character", "animate_character", "animate_sequence", "character_library", "export_gltf",
})

# destructive: refused over MCP unless the user turned on "Allow gated tools" in the add-on preferences
GATED_MUTATION = frozenset({"delete_object", "task_rollback"})

# part of the add-on's own agent loop (plans, tool packs): meaningless or harmful for an outside client
INTERNAL_ONLY = frozenset({"propose_plan", "enable_tools"})

CATEGORIES: Dict[str, FrozenSet[str]] = {
    "READ_ONLY": READ_ONLY, "SAFE_MUTATION": SAFE_MUTATION, "GATED_MUTATION": GATED_MUTATION, "INTERNAL_ONLY": INTERNAL_ONLY,
}


class ExposurePolicy:
    """The set of tool names an MCP client may see and call."""

    def __init__(self, exposed: Iterable[str]):
        self._exposed = frozenset(exposed)

    @classmethod
    def production(cls) -> "ExposurePolicy":
        return cls(READ_ONLY | SAFE_MUTATION | GATED_MUTATION)

    @classmethod
    def allow_all_except(cls, names: Iterable[str], hidden: Iterable[str] = ()) -> "ExposurePolicy":
        """For tests with made-up tools: expose every given name except the hidden ones."""
        return cls(set(names) - set(hidden))

    def is_exposed(self, name: str) -> bool:
        return name in self._exposed

    @property
    def exposed(self) -> FrozenSet[str]:
        return self._exposed


def category_of(name: str) -> str:
    for label, names in CATEGORIES.items():
        if name in names:
            return label
    return ""


def unclassified(registered: Iterable[str]) -> List[str]:
    """Registered tool names that no category lists (each one is a decision somebody still has to make)."""
    return sorted(n for n in registered if not category_of(n))


def overlapping() -> List[str]:
    """Names listed in more than one category (a tool belongs in exactly one)."""
    count: Dict[str, int] = {}
    for names in CATEGORIES.values():
        for n in names:
            count[n] = count.get(n, 0) + 1
    return sorted(n for n, c in count.items() if c > 1)
