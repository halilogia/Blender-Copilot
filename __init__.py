"""Blender - Copilot — Autonomous AI Agent & Grounding Copilot for Blender."""

bl_info = {
    "name": "Blender - Copilot",
    "author": "Halil Emre",
    "version": (1, 7, 0),
    "blender": (4, 2, 0),
    "location": "View3D > Sidebar > Blender - Copilot / View3D > Alt+Space",
    "description": "Autonomous AI Agent & Grounding Copilot for Blender",
    "category": "Development",
}

import os
import sys
from typing import Optional

# Ensure the addon directory is in sys.path so that internal packages
# (core, tools, adapter, agent, ui) resolve reliably when loaded by Blender.
_addon_dir = os.path.dirname(os.path.abspath(__file__))
if _addon_dir not in sys.path:
    sys.path.insert(0, _addon_dir)

from .ui.preferences import register_preferences, unregister_preferences
from .ui.properties import register_properties, unregister_properties
from .ui.operators import register_operators, unregister_operators
from .ui.panel import register_panels, unregister_panels
from .ui.keymap import register_keymaps, unregister_keymaps
from .ui.header import register_header, unregister_header
from .ui.gpu_overlay import register as register_gpu_overlay, unregister as unregister_gpu_overlay
from .ui.timer_bridge import TimerBridge
from .ui.mcp_panel import register_mcp_ui, unregister_mcp_ui
from .adapter.blender_adapter import BlenderAdapter
# The rest of the agent imports the top-level ``tools`` package after adding
# the addon directory to sys.path above.  Importing the registry relatively
# here creates a second class identity (``blender_ai_sidebar.tools.registry``)
# and makes isinstance checks in plan validation fail inside Blender.
from tools.registry import ToolRegistry
from bridge import control as mcp_control
from .tools.read_only.inspect_scene import InspectSceneTool
from .tools.read_only.inspect_selection import InspectSelectionTool
from .tools.read_only.inspect_object import InspectObjectTool
from .tools.read_only.inspect_material import InspectMaterialTool
from .tools.read_only.inspect_mesh import InspectMeshTool
from .tools.mutations.create_primitive import CreatePrimitiveTool
from .tools.mutations.create_camera import CreateCameraTool
from .tools.mutations.create_light import CreateLightTool
from .tools.mutations.set_shading import SetShadingTool
from .tools.mutations.add_modifier import AddModifierTool
from .tools.mutations.duplicate_object import DuplicateObjectTool
from .tools.mutations.transform_object import TransformObjectTool
from .tools.mutations.delete_object import DeleteObjectTool
from .tools.mutations.set_material import SetMaterialTool
from .tools.mutations.assign_material import AssignMaterialTool
from .tools.mutations.import_asset import ImportAssetTool
from .tools.mutations.create_mesh import CreateMeshTool
from .tools.mutations.mesh_edit import MeshEditTool
from .tools.mutations.join_objects import JoinObjectsTool
from .tools.mutations.parent_object import ParentObjectTool
from .tools.mutations.apply_transform import ApplyTransformTool
from .tools.mutations.set_origin import SetOriginTool
from .tools.mutations.export_gltf import ExportGltfTool
from .tools.mutations.add_shape_modifier import AddShapeModifierTool
from .tools.mutations.frame_view import FrameViewTool
from .tools.mutations.set_environment import SetEnvironmentTool
from .tools.mutations.make_soundtrack import MakeSoundtrackTool
from .tools.mutations.polish_model import PolishModelTool
from .tools.mutations.character_library import CharacterLibraryTool
from .tools.mutations.set_look import SetLookTool
from .tools.mutations.camera_settings import CameraSettingsTool
from .tools.mutations.render_contact_sheet import RenderContactSheetTool
from .tools.mutations.edit_video import EditVideoTool
from .tools.mutations.render_shots import RenderShotsTool
from .tools.mutations.rig_character import RigCharacterTool
from .tools.mutations.animate_character import AnimateCharacterTool
from .tools.mutations.camera_move import CameraMoveTool
from .tools.mutations.render_image import RenderImageTool
from .tools.mutations.render_animation import RenderAnimationTool
from .tools.read_only.capture_viewport import CaptureViewportTool
from .tools.read_only.visual_verify import VisualVerifyTool
from .tools.propose_plan import ProposePlanTool
from .core.config import Config
from .agent.provider import BaseProvider
from .agent.mock_provider import MockProvider
from .agent.openai_provider import OpenAICompatibleProvider
from .agent.dispatcher import ToolDispatcher
from .agent.runtime import AgentRuntime
from .ui.preferences import get_effective_config
from .adapter.session_persistence import (
    register_session_handlers,
    unregister_session_handlers,
    set_runtime_getter,
    load_session_memory_from_scene,
)

_runtime: Optional[AgentRuntime] = None
_timer_bridge: Optional[TimerBridge] = None


def create_production_provider() -> BaseProvider:
    """Construct real provider from effective configuration (v1.1: openai|anthropic)."""
    import bpy
    cfg = get_effective_config()
    online_access = getattr(bpy.app, "online_access", True)
    if getattr(cfg, "provider", "openai_compatible") == "anthropic":
        from .agent.anthropic_provider import AnthropicCompatibleProvider
        return AnthropicCompatibleProvider(config=cfg, online_access=online_access)
    return OpenAICompatibleProvider(config=cfg, online_access=online_access)


def update_runtime_config(config: Config) -> None:
    """Dynamically sync configuration changes to the running provider."""
    global _runtime
    if _runtime and hasattr(_runtime, "provider"):
        provider = _runtime.provider
        if hasattr(provider, "config"):
            provider.config = config
            effective_timeout = getattr(config, "timeout_seconds", 30.0)
            if hasattr(provider, "http_client"):
                provider.http_client.base_url = config.base_url
                provider.http_client.timeout = effective_timeout


def _max_tool_rounds() -> int:
    """Tool rounds per prompt: modeling a prop takes dozens of calls (BLENDER_AI_MAX_TOOL_ROUNDS, default 100)."""
    try:
        return max(1, min(200, int(os.environ.get("BLENDER_AI_MAX_TOOL_ROUNDS", "100"))))
    except ValueError:
        return 100


def get_runtime() -> Optional[AgentRuntime]:
    """Retrieve the active extension agent runtime."""
    return _runtime


def get_timer_bridge() -> Optional[TimerBridge]:
    """Retrieve the active extension timer bridge."""
    return _timer_bridge


def register(provider: Optional[BaseProvider] = None):
    """Register all extension components, tools, runtime, and timer bridge."""
    global _runtime, _timer_bridge

    # Idempotency guard: if already registered, unregister cleanly first
    if _runtime is not None or _timer_bridge is not None:
        unregister()

    # 1. UI Preferences, Properties, Operators, Panels, Header, Keymaps & GPU Overlay
    register_preferences()
    register_properties()
    register_operators()
    register_panels()
    register_header()
    register_keymaps()
    register_gpu_overlay()

    # 2. Tool Registry (Inspection & Safe Mutation Tools)
    registry = ToolRegistry()
    registry.register(InspectSceneTool())
    registry.register(InspectSelectionTool())
    registry.register(InspectObjectTool())
    registry.register(InspectMaterialTool())
    registry.register(InspectMeshTool())
    registry.register(CreatePrimitiveTool())
    registry.register(CreateCameraTool())
    registry.register(CreateLightTool())
    registry.register(SetShadingTool())
    registry.register(AddModifierTool())
    registry.register(DuplicateObjectTool())
    registry.register(TransformObjectTool())
    registry.register(DeleteObjectTool())
    registry.register(SetMaterialTool())
    registry.register(AssignMaterialTool())
    registry.register(ImportAssetTool())
    registry.register(CreateMeshTool())
    registry.register(MeshEditTool())
    registry.register(JoinObjectsTool())
    registry.register(ParentObjectTool())
    registry.register(ApplyTransformTool())
    registry.register(SetOriginTool())
    registry.register(ExportGltfTool())
    registry.register(AddShapeModifierTool())
    registry.register(FrameViewTool())
    registry.register(SetEnvironmentTool())
    registry.register(MakeSoundtrackTool())
    registry.register(PolishModelTool())
    registry.register(CharacterLibraryTool())
    registry.register(SetLookTool())
    registry.register(CameraSettingsTool())
    registry.register(RenderContactSheetTool())
    registry.register(EditVideoTool())
    registry.register(RenderShotsTool())
    registry.register(RigCharacterTool())
    registry.register(AnimateCharacterTool())
    registry.register(CameraMoveTool())
    registry.register(RenderImageTool())
    registry.register(RenderAnimationTool())
    registry.register(CaptureViewportTool())
    registry.register(VisualVerifyTool())
    registry.register(ProposePlanTool())

    # 3. Adapter & Dispatcher
    adapter = BlenderAdapter()
    dispatcher = ToolDispatcher(registry=registry, adapter=adapter)

    # 4. Production Real Provider & Agent Runtime
    if provider is not None:
        effective_provider = provider
    elif os.environ.get("BLENDER_AI_USE_MOCK_PROVIDER") == "1":
        effective_provider = MockProvider()
    else:
        effective_provider = create_production_provider()

    _runtime = AgentRuntime(
        provider=effective_provider,
        dispatcher=dispatcher,
        auto_approve_low_risk_plans=True,
        max_tool_rounds=_max_tool_rounds(),
        continue_on_tool_failure=os.environ.get("BLENDER_AI_CONTINUE_ON_TOOL_ERROR") == "1",
    )

    # 5. Timer Bridge for Async Event Loop
    _timer_bridge = TimerBridge(runtime=_runtime, event_queue=_runtime.event_queue)
    _timer_bridge.register()

    # 5b. MCP bridge (Claude Code / other MCP clients). Starts only if enabled in its settings or by env.
    register_mcp_ui()
    try:
        from .ui.preferences import get_config_path
        mcp_control.attach(registry, adapter, get_config_path().parent / "mcp_bridge.json", version=".".join(str(v) for v in bl_info["version"]))
    except Exception as exc:  # the bridge must never stop the add-on from loading
        print(f"[Blender Copilot] MCP bridge unavailable: {exc}")

    # 6. Session Persistence (.blend save_pre and load_post handlers)
    set_runtime_getter(get_runtime)
    register_session_handlers()
    try:
        load_session_memory_from_scene(runtime=_runtime)
    except Exception:
        pass


def unregister():
    """Unregister all extension components and guarantee clean shutdown."""
    global _runtime, _timer_bridge

    # 0. Unregister session persistence handlers
    unregister_session_handlers()
    set_runtime_getter(None)

    # 0b. Stop the MCP bridge
    mcp_control.detach()
    unregister_mcp_ui()

    # 1. Stop timer bridge
    if _timer_bridge is not None:
        _timer_bridge.unregister()
        _timer_bridge = None

    # 2. Shutdown runtime and background workers
    if _runtime is not None:
        _runtime.shutdown()
        _runtime = None

    # 3. Unregister UI & Keymaps
    unregister_gpu_overlay()
    unregister_keymaps()
    unregister_header()
    unregister_panels()
    unregister_operators()
    unregister_properties()
    unregister_preferences()


if __name__ == "__main__":
    register()
