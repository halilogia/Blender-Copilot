"""Exposes the ToolRegistry to MCP with approval gating and tool annotations.

Zero Blender dependencies: Blender is reached only through the injected adapter, and every call is
handed to ``executor.submit`` so it runs on Blender's main thread.
"""

import base64
from typing import Any, Callable, Dict, List, Optional

from agent.models import ToolCall
from agent.policy import ApprovalDecision, ApprovalPolicy
from core.types import RiskLevel, ToolResult
from tools.registry import ToolRegistry

INSTRUCTIONS = (
    "Blender Copilot tools for Blender 5.2. Units are meters, +Z is up. "
    "Look before you change: inspect_scene, inspect_object, inspect_mesh; verify by frame_view (aim the viewport: ISO / FRONT / TOP, "
    "clean overlays off) then capture_viewport (returns an image) after every few edits. Every mutation is one Ctrl+Z step. "
    "Model game assets without Python: create_primitive (cube, sphere, plane, cylinder, cone, icosphere, torus), "
    "create_mesh (your own vertices and faces), mesh_edit (extrude / inset / bevel / subdivide / taper faces picked by normal), "
    "add_modifier (bevel, subsurf, boolean), add_shape_modifier (mirror, array, solidify, decimate, triangulate), "
    "set_material / assign_material, set_shading, parent_object, join_objects, apply_transform, set_origin. "
    "Finish with export_gltf (a .glb in the export folder, Y-up, modifiers applied) and hand the file path to the game "
    "engine (Godot: copy it under res:// and call sync_project). Keep low-poly game assets under ~3000 triangles, "
    "origin at the bottom centre, real-world scale. "
    "Tools with risk MEDIUM or higher (delete_object) need the user's approval and are refused over MCP unless the "
    "user enabled 'Allow gated tools' in the add-on preferences; tell the user instead of retrying."
)

_GATED = {RiskLevel.MEDIUM, RiskLevel.HIGH, RiskLevel.CRITICAL}


def _risk_of(tool: Any, arguments: Dict[str, Any]) -> RiskLevel:
    risk = getattr(tool, "risk_level", RiskLevel.HIGH)
    if hasattr(tool, "get_risk_level"):
        try:
            risk = tool.get_risk_level(arguments or {})
        except Exception:
            pass
    if isinstance(risk, str):
        try:
            risk = RiskLevel(risk)
        except ValueError:
            risk = RiskLevel.HIGH
    return risk


class RegistryToolHost:
    """MCP tool host over a ToolRegistry."""

    def __init__(
        self,
        registry: ToolRegistry,
        adapter: Any,
        submit: Callable[..., Any],
        allow_gated: Callable[[], bool] = lambda: False,
        exclude: Optional[set] = None,
        policy: Optional[ApprovalPolicy] = None,
        call_timeout: float = 60.0,
    ):
        self.registry = registry
        self.adapter = adapter
        self.submit = submit
        self.allow_gated = allow_gated
        self.exclude = set(exclude or {"propose_plan"})
        self.policy = policy or ApprovalPolicy()
        self.call_timeout = call_timeout
        self._counter = 0

    def has_tool(self, name: str) -> bool:
        return name not in self.exclude and self.registry.exists(name)

    @staticmethod
    def annotations_for(tool: Any) -> Dict[str, Any]:
        risk = getattr(tool, "risk_level", RiskLevel.HIGH)
        read_only = risk == RiskLevel.READ_ONLY
        return {
            "title": tool.name.replace("_", " ").title(),
            "readOnlyHint": read_only,
            "destructiveHint": risk in _GATED,
            "idempotentHint": read_only,
            "openWorldHint": False,
        }

    def list_tools(self) -> List[Dict[str, Any]]:
        out = []
        for tool in self.registry.list():
            if tool.name in self.exclude:
                continue
            out.append({
                "name": tool.name,
                "description": tool.description,
                "inputSchema": tool.input_schema,
                "annotations": self.annotations_for(tool),
            })
        return out

    def call_tool(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        tool = self.registry.get(name)
        risk = _risk_of(tool, arguments)
        if risk in _GATED and not self.allow_gated():
            return ToolResult.fail(
                tool=name,
                error_type="APPROVAL_REQUIRED",
                message=(f"'{name}' has risk {risk.value} and needs the user's approval in Blender. "
                         "Ask the user, or have them enable 'Allow gated tools' in the add-on preferences."),
                details={"risk_level": risk.value},
            ).to_dict()
        self._counter += 1
        call = ToolCall(call_id=f"mcp_{self._counter}", tool_name=name, arguments=dict(arguments))
        try:
            result = self.submit(lambda: self._dispatch(call), timeout=self.call_timeout)
        except TimeoutError:
            return ToolResult.fail(name, "TIMEOUT", f"Blender did not run '{name}' within {self.call_timeout:.0f} s "
                                   "(is the main thread busy or the add-on's timer stopped?)").to_dict()
        except Exception as exc:  # noqa: BLE001 - reported to the client, never raised into the HTTP thread
            return ToolResult.fail(name, "BRIDGE_ERROR", f"{type(exc).__name__}: {exc}").to_dict()
        return result

    def _dispatch(self, call: ToolCall) -> Dict[str, Any]:
        from agent.dispatcher import ToolDispatcher

        result = ToolDispatcher(self.registry, self.adapter).dispatch(call).to_dict()
        data = result.get("data")
        if result.get("success") and isinstance(data, dict) and data.get("image_id"):
            getter = getattr(self.adapter, "get_viewport_screenshot", None) or getattr(self.adapter, "get_image_bytes", None)
            png = getter(data["image_id"]) if callable(getter) else None
            if png:
                data["image_base64"] = base64.b64encode(png).decode("ascii")
        return result
