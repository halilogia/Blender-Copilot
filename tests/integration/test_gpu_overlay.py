"""Headless integration tests for Blender AI Viewport GPU Overlay (Blender Copilot)."""

import os
import sys
import importlib.util
import bpy
import gpu

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

from ui.gpu_overlay.state import GPUOverlayState, overlay_state
from ui.gpu_overlay.renderer import (
    build_rounded_rect_tris,
    draw_rounded_rect,
    draw_rounded_shadow,
)


def test_registration():
    """Test 1: Operator and keymap registration for viewport HUD."""
    print("Running Test 1: Operator and keymap registration...")
    blender_ai_sidebar.register()
    try:
        # Check operator
        assert hasattr(bpy.ops.ai_sidebar, "viewport_hud"), "Missing ai_sidebar.viewport_hud operator"

        # Check keymaps
        wm = bpy.context.window_manager
        kc = wm.keyconfigs.addon
        assert kc is not None
        km = kc.keymaps.get("3D View")
        assert km is not None

        found_shortcuts = []
        for kmi in km.keymap_items:
            if kmi.idname == "ai_sidebar.viewport_hud":
                found_shortcuts.append((kmi.type, kmi.alt, kmi.shift))

        assert len(found_shortcuts) >= 2, f"Expected 2 shortcuts, found: {found_shortcuts}"
        assert ("SPACE", True, False) in found_shortcuts, "Alt+Space not registered to viewport_hud"
        assert ("A", True, True) in found_shortcuts, "Shift+Alt+A not registered to viewport_hud"

        print("[PASS] Test 1: Operator and keymaps registered cleanly.")
    finally:
        blender_ai_sidebar.unregister()


def test_overlay_state_text_and_unicode():
    """Test 2: Overlay state text editing and Turkish unicode support."""
    print("Running Test 2: Overlay state text and unicode...")
    state = GPUOverlayState()

    # 1. Insertion
    state.insert_text("Merhaba")
    assert state.prompt_text == "Merhaba"
    assert state.cursor_pos == 7

    # 2. Turkish characters
    state.insert_text(" dünya! ğüşiöç ĞÜŞİÖÇ")
    assert "ğüşiöç" in state.prompt_text
    assert "ĞÜŞİÖÇ" in state.prompt_text

    # 3. Cursor navigation
    state.move_cursor_home()
    assert state.cursor_pos == 0
    state.move_cursor_right()
    assert state.cursor_pos == 1
    state.move_cursor_end()
    assert state.cursor_pos == len(state.prompt_text)

    # 4. Deletions
    state.delete_backward()
    assert not state.prompt_text.endswith("Ç")
    state.move_cursor_home()
    state.delete_forward()
    assert not state.prompt_text.startswith("M")

    # 5. Reset
    state.reset_input()
    assert state.prompt_text == ""
    assert state.cursor_pos == 0

    print("[PASS] Test 2: State text buffer and Turkish unicode handling verified.")


def test_hit_testing():
    """Test 3: Hit testing for bar, buttons, and input areas."""
    print("Running Test 3: Hit testing...")
    state = GPUOverlayState()
    state.bar_rect = (100.0, 50.0, 500.0, 70.0)
    state.input_rect = (140.0, 80.0, 320.0, 30.0)
    state.send_btn_rect = (480.0, 60.0, 100.0, 44.0)

    # Point outside
    assert state.hit_test(50.0, 50.0) is None
    assert state.hit_test(100.0, 20.0) is None

    # Point inside bar background
    assert state.hit_test(110.0, 55.0) == "bar"

    # Point inside input
    assert state.hit_test(160.0, 90.0) == "input"

    # Point inside send button
    assert state.hit_test(500.0, 75.0) == "send"

    print("[PASS] Test 3: Hit testing verified.")


def test_gpu_geometry_and_drawing():
    """Test 4: GPU rounded rectangle tessellation and drawing safety."""
    print("Running Test 4: GPU geometry and drawing...")
    gpu.init()

    # 1. Tessellation test
    tris = build_rounded_rect_tris(100, 100, 400, 70, radius=18.0)
    assert len(tris) > 20, "Tessellation should generate multiple triangles"
    for pt in tris:
        assert len(pt) == 2

    # 2. Drawing execution (must not raise exceptions)
    gpu.state.blend_set("ALPHA")
    draw_rounded_shadow(100, 100, 400, 70, radius=18.0)
    draw_rounded_rect(100, 100, 400, 70, radius=18.0, color=(0.1, 0.1, 0.12, 1.0))
    gpu.state.blend_set("NONE")

    print("[PASS] Test 4: GPU geometry tessellation and drawing verified.")


def test_hud_actions_reuse_sidebar_operators():
    """Test 5: every sidebar feature is reachable from the HUD through the existing operators."""
    print("Running Test 5: HUD action dispatch...")
    from ui.gpu_overlay.modal import AISIDEBAR_OT_viewport_hud as hud
    from ui.gpu_overlay.menu import menu_items

    blender_ai_sidebar.register()
    try:
        wm = bpy.context.window_manager
        overlay_state.panel = None
        driver = hud  # actions are static: no modal instance needed

        # Panels toggle
        driver.dispatch_action(bpy.context, "pill:menu")
        assert overlay_state.panel == "menu"
        driver.dispatch_action(bpy.context, "pill:history")
        assert overlay_state.panel == "history"
        driver.dispatch_action(bpy.context, "pill:history")
        assert overlay_state.panel is None

        # Diagnostic log path -> clipboard
        from core.logging_utils import get_log_path
        driver.dispatch_action(bpy.context, "menu:logpath")
        if wm.clipboard:  # headless Blender may have no system clipboard
            assert wm.clipboard == get_log_path()
        assert overlay_state.active_toast() == "Log path copied"

        # MCP gated switch flips through the shared controller
        from bridge import control
        ctl = control.get_controller()
        assert ctl is not None
        before = ctl.settings.allow_gated
        try:
            driver.dispatch_action(bpy.context, "menu:mcp_gated")
            assert ctl.settings.allow_gated != before
        finally:
            ctl.update_settings(allow_gated=before)

        # State sync mirrors bridge + history, and the menu lists every sidebar feature
        driver.sync_extras(bpy.context)
        assert overlay_state.mcp["available"] is True
        keys = [k for k, _ in menu_items(overlay_state.mcp, 2)]
        for needed in ("menu:mcp_toggle", "menu:mcp_gated", "task:undo", "menu:clear", "menu:logpath",
                       "menu:updates", "menu:settings"):
            assert needed in keys, needed

        # Copy plan / response / tool details go through the sidebar copy operators
        props = wm.ai_sidebar
        turn = props.timeline.add()
        turn.turn_id = "turn_x"
        turn.prompt = "make a cube"
        turn.final_response = "Done: cube created."
        tool = turn.tools.add()
        tool.tool_name = "create_cube"
        tool.status = "OK"
        tool.summary = "cube"
        driver.sync_extras(bpy.context)
        assert overlay_state.history and overlay_state.history[-1]["turn_id"] == "turn_x"
        driver.dispatch_action(bpy.context, "hist:copy:turn_x")
        from blender_ai_sidebar.ui.operators import get_last_copied_text
        assert get_last_copied_text() == "Done: cube created."
        driver.dispatch_action(bpy.context, "hist:tool:turn_x:0")
        assert "create_cube" in get_last_copied_text()

        # Clear history empties the HUD mirror too
        driver.dispatch_action(bpy.context, "menu:clear")
        assert overlay_state.history == [] and overlay_state.last_response_text == ""

        # Unknown key never raises and reports instead
        driver.dispatch_action(bpy.context, "hist:tool:nope:9")
        print("[PASS] Test 5: HUD actions dispatch to existing operators.")
    finally:
        overlay_state.panel = None
        blender_ai_sidebar.unregister()


def test_keymap_registered_without_user_setup():
    """Test 6: Alt+Space is live right after register(); unregister removes it again."""
    print("Running Test 6: default keymap...")
    blender_ai_sidebar.register()
    kc = bpy.context.window_manager.keyconfigs.addon
    ids = [(k.idname, k.type, k.alt) for k in kc.keymaps["3D View"].keymap_items]
    assert ("ai_sidebar.viewport_hud", "SPACE", True) in ids
    blender_ai_sidebar.unregister()
    ids = [(k.idname, k.type, k.alt) for k in kc.keymaps["3D View"].keymap_items]
    assert ("ai_sidebar.viewport_hud", "SPACE", True) not in ids, "keymap leaked after unregister"
    print("[PASS] Test 6: Alt+Space registered on enable and removed on disable.")


def test_hud_settings_drawer():
    """Test 7: provider/URL/model/key/timeout are editable from the HUD and land in the preferences."""
    print("Running Test 7: HUD settings drawer...")
    import time
    import types
    from ui.gpu_overlay.modal import AISIDEBAR_OT_viewport_hud as hud

    stub = types.SimpleNamespace(provider="openai_compatible", base_url="http://localhost:11434/v1",
                                 model="llama3", api_key="sk-test-123456789", timeout_seconds=30)
    original = hud.__dict__.get("_prefs")
    hud._prefs = staticmethod(lambda ctx: stub)  # no add-on preferences entry in a headless run
    ctx = bpy.context

    def key(event_type, unicode="", ctrl=False):
        return types.SimpleNamespace(type=event_type, unicode=unicode, ctrl=ctrl)

    try:
        overlay_state.panel = None
        overlay_state.settings_editor = None
        hud.dispatch_action(ctx, "menu:settings")
        assert overlay_state.panel == "settings"
        assert overlay_state.settings_values["model"] == "llama3"

        # provider cycles openai -> anthropic -> agy_cli
        hud.dispatch_action(ctx, "set:provider")
        assert stub.provider == "anthropic"
        hud.dispatch_action(ctx, "set:provider")
        assert stub.provider == "agy_cli"
        hud.dispatch_action(ctx, "set:provider")
        assert stub.provider == "openai_compatible"

        # type into the model field: keys go to the editor, Enter commits to the preferences
        hud.dispatch_action(ctx, "set:model")
        assert overlay_state.settings_editor is not None
        for ch in "-v2":
            hud.edit_setting_key(ctx, key("X", ch))
        hud.edit_setting_key(ctx, key("RET"))
        assert stub.model == "llama3-v2" and overlay_state.settings_editor is None

        # Esc cancels without touching the value; the key stays masked while typing
        hud.dispatch_action(ctx, "set:api_key")
        hud.edit_setting_key(ctx, key("X", "Z"))
        from ui.gpu_overlay.settings import display_value
        assert "sk-" not in display_value("api_key", overlay_state.settings_values, overlay_state.settings_editor)
        hud.edit_setting_key(ctx, key("ESC"))
        assert stub.api_key == "sk-test-123456789"

        # timeout steps and clamps
        hud.dispatch_action(ctx, "set:timeout:+")
        assert stub.timeout_seconds == 45
        for _ in range(30):
            hud.dispatch_action(ctx, "set:timeout:-")
        assert stub.timeout_seconds == 5

        # connection test runs on a thread and reports; agy gives a clear answer either way
        stub.provider = "agy_cli"
        hud.load_settings_snapshot(ctx)
        hud.dispatch_action(ctx, "set:test")
        deadline = time.time() + 5
        while overlay_state.settings_test["state"] == "running" and time.time() < deadline:
            time.sleep(0.05)
        assert overlay_state.settings_test["state"] in ("ok", "fail")
        assert overlay_state.settings_test["msg"]
        assert "sk-test" not in overlay_state.settings_test["msg"]
        print("[PASS] Test 7: HUD settings edit the preferences, mask the key and test the connection.")
    finally:
        if original is None:
            del hud._prefs
        else:
            hud._prefs = original
        overlay_state.panel = None
        overlay_state.settings_editor = None


def run_all():
    print("\n========================================================")
    print("   RUNNING GPU OVERLAY INTEGRATION SUITE (BLENDER 5.2)  ")
    print("========================================================\n")

    test_registration()
    test_overlay_state_text_and_unicode()
    test_hit_testing()
    test_gpu_geometry_and_drawing()
    test_hud_actions_reuse_sidebar_operators()
    test_keymap_registered_without_user_setup()
    test_hud_settings_drawer()

    print("\n========================================================")
    print("   ALL GPU OVERLAY TESTS PASSED SUCCESSFULLY!           ")
    print("========================================================\n")
    return 0


if __name__ == "__main__":
    sys.exit(run_all())
