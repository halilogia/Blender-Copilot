"""Unit tests for the pure parts of the Alt+Space HUD: menu model, history digest, click registry."""

import importlib.util
import os
import types
import unittest

_HUD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "ui", "gpu_overlay")


def _load(name):
    # Loaded by path: the package __init__ imports bpy, which the pure runner does not have.
    spec = importlib.util.spec_from_file_location(f"hud_{name}", os.path.join(_HUD_DIR, f"{name}.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


menu = _load("menu")
state_mod = _load("state")

MCP_STOPPED = {"available": True, "running": False, "endpoint": "", "token": "", "allow_gated": False}
MCP_RUNNING = {"available": True, "running": True, "endpoint": "127.0.0.1:8765", "token": "abc123…******", "allow_gated": True}


class MenuItemsTests(unittest.TestCase):
    def keys(self, mcp, steps=0):
        return [k for k, _ in menu.menu_items(mcp, steps)]

    def test_every_sidebar_feature_has_a_menu_entry(self):
        keys = self.keys(MCP_RUNNING, steps=3)
        for needed in (
            "menu:mcp_toggle", "menu:mcp_copy", "menu:mcp_gated", "task:changes", "task:undo",
            "menu:clear", "menu:logpath", "menu:updates", "menu:settings",
        ):
            self.assertIn(needed, keys)

    def test_stopped_bridge_offers_start_and_no_copy(self):
        items = dict(menu.menu_items(MCP_STOPPED, 0))
        self.assertEqual(items["menu:mcp_toggle"], "Start MCP bridge")
        self.assertNotIn("menu:mcp_copy", items)
        self.assertEqual(items["menu:mcp_gated"], "Gated tools: ask me")

    def test_running_bridge_offers_stop_and_gated_state(self):
        items = dict(menu.menu_items(MCP_RUNNING, 0))
        self.assertEqual(items["menu:mcp_toggle"], "Stop MCP bridge")
        self.assertEqual(items["menu:mcp_gated"], "Gated tools: allowed")

    def test_task_actions_only_when_a_task_changed_something(self):
        self.assertNotIn("task:undo", self.keys(MCP_STOPPED, 0))
        items = dict(menu.menu_items(MCP_STOPPED, 4))
        self.assertEqual(items["task:undo"], "Undo AI task (4)")

    def test_no_bridge_hides_mcp_entries(self):
        keys = self.keys({"available": False}, 0)
        self.assertFalse([k for k in keys if k.startswith("menu:mcp")])

    def test_mcp_summary(self):
        self.assertIn("stopped", menu.mcp_summary(MCP_STOPPED))
        self.assertIn("127.0.0.1:8765", menu.mcp_summary(MCP_RUNNING))
        self.assertIn("unavailable", menu.mcp_summary({"available": False}))


class DigestTests(unittest.TestCase):
    def test_digest_copies_turns_and_tools(self):
        tool = types.SimpleNamespace(tool_name="create_cube", status="OK", summary="made")
        turn = types.SimpleNamespace(turn_id="t1", prompt="p", final_response="r", status="COMPLETED",
                                     error_message="", tools=[tool])
        out = menu.digest_turns([turn])
        self.assertEqual(out[0]["turn_id"], "t1")
        self.assertEqual(out[0]["tools"][0]["tool_name"], "create_cube")

    def test_digest_keeps_only_latest(self):
        turns = [types.SimpleNamespace(turn_id=str(i), tools=[]) for i in range(30)]
        out = menu.digest_turns(turns, limit=15)
        self.assertEqual(len(out), 15)
        self.assertEqual(out[-1]["turn_id"], "29")


class ClickRegistryTests(unittest.TestCase):
    def test_topmost_registered_button_wins_and_sinks_clicks(self):
        st = state_mod.GPUOverlayState()
        st.buttons["panel_bg"] = (0, 100, 400, 200)
        st.buttons["hist:copy:t1"] = (300, 120, 50, 20)
        self.assertEqual(st.hit_test(310, 130), "hist:copy:t1")
        self.assertEqual(st.hit_test(10, 150), "panel_bg")
        self.assertIsNone(st.hit_test(900, 900))

    def test_toggle_panel(self):
        st = state_mod.GPUOverlayState()
        st.toggle_panel("menu")
        self.assertEqual(st.panel, "menu")
        st.toggle_panel("history")
        self.assertEqual(st.panel, "history")
        st.toggle_panel("history")
        self.assertIsNone(st.panel)

    def test_toast_expires(self):
        st = state_mod.GPUOverlayState()
        st.set_toast("Copied", seconds=-1.0)
        self.assertEqual(st.active_toast(), "")
        st.set_toast("Copied", seconds=5.0)
        self.assertEqual(st.active_toast(), "Copied")


if __name__ == "__main__":
    unittest.main()
