"""Phase 8: UI Hardening & Edge Cases Tests.

The N-panel is a thin launcher for the Alt+Space HUD, so this checks that it draws
safely in every agent state and always offers the HUD and pending approvals.
"""

import os
import sys
import importlib.util
import bpy

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

init_path = os.path.join(PROJECT_ROOT, "__init__.py")
spec = importlib.util.spec_from_file_location(
    "blender_ai_sidebar",
    init_path,
    submodule_search_locations=[PROJECT_ROOT],
)
blender_ai_sidebar = importlib.util.module_from_spec(spec)
sys.modules["blender_ai_sidebar"] = blender_ai_sidebar
spec.loader.exec_module(blender_ai_sidebar)

from blender_ai_sidebar.ui.panel import AISIDEBAR_PT_main_panel


class DummyLayout:
    """Mock layout to verify draw calls without crashing."""
    def __init__(self):
        self.labels = []
        self.operators = []
        self.scale_y = 1.0

    def box(self):
        return self

    def column(self, align=False):
        return self

    def row(self, align=False):
        return self

    def label(self, text="", icon="NONE"):
        self.labels.append((text, icon))

    def separator(self):
        pass

    def prop(self, data, prop_name, text=""):
        pass

    def operator(self, op_name, text="", icon="NONE"):
        self.operators.append((op_name, text))
        return self

    def template_list(self, *args, **kwargs):
        pass


import types

def test_ui_drawing_edge_cases():
    print("Testing launcher panel drawing under extreme states...")
    blender_ai_sidebar.register()
    try:
        props = bpy.context.window_manager.ai_sidebar

        def draw():
            panel = types.SimpleNamespace(layout=DummyLayout())
            AISIDEBAR_PT_main_panel.draw(panel, bpy.context)
            return panel.layout

        # 1. Idle: the HUD launcher and the shortcut are always offered
        layout = draw()
        assert ("ai_sidebar.viewport_hud", "Open AI HUD") in layout.operators
        assert any("Alt+Space" in l[0] for l in layout.labels)

        # 2. Every agent state draws without raising
        for status in ("IDLE", "PROCESSING", "EXECUTING_TOOL", "ERROR", "CANCELLED", "SOMETHING_NEW"):
            props.agent_status = status
            draw()

        # 3. Queued prompts are shown
        props.agent_status = "PROCESSING"
        props.queued_count = 2
        assert any("2 queued" in l[0] for l in draw().labels)
        props.queued_count = 0

        # 4. Approval stays answerable from the panel when the HUD is closed
        props.agent_status = "PENDING_APPROVAL"
        ops = [o[0] for o in draw().operators]
        assert "ai_sidebar.approve_action" in ops and "ai_sidebar.reject_action" in ops
        props.agent_status = "IDLE"
        ops = [o[0] for o in draw().operators]
        assert "ai_sidebar.approve_action" not in ops

        print("[PASS] Launcher panel draw edge cases verified successfully.")
    finally:
        blender_ai_sidebar.unregister()


if __name__ == "__main__":
    test_ui_drawing_edge_cases()
    sys.exit(0)
