"""HUD click-chain audit as tests: hit-test geometry plus "every drawn control has a handler"."""

import importlib.util
import os
import re
import unittest

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_HUD_DIR = os.path.join(_ROOT, "ui", "gpu_overlay")


def _load(name):
    spec = importlib.util.spec_from_file_location(f"hud_{name}", os.path.join(_HUD_DIR, f"{name}.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


state_mod = _load("state")
menu = _load("menu")


def _src(name):
    with open(os.path.join(_HUD_DIR, name), encoding="utf-8") as fh:
        return fh.read()


def _state():
    st = state_mod.GPUOverlayState()
    st.bar_rect = (100.0, 40.0, 600.0, 74.0)
    st.input_rect = (140.0, 60.0, 420.0, 40.0)
    st.send_btn_rect = (580.0, 55.0, 110.0, 44.0)
    return st


class HitGeometry(unittest.TestCase):
    def test_regions_of_the_bar(self):
        st = _state()
        self.assertEqual(st.hit_test(600, 70), "send")
        self.assertEqual(st.hit_test(200, 80), "input")
        self.assertEqual(st.hit_test(110, 45), "bar")
        self.assertIsNone(st.hit_test(50, 300))

    def test_unused_zero_rects_never_hit(self):
        st = _state()
        st.cancel_btn_rect = (0, 0, 0, 0)
        self.assertIsNone(st.hit_test(0, 0))

    def test_cards_sink_clicks_so_they_do_not_reach_the_viewport(self):
        st = _state()
        st.buttons["card:response"] = (100.0, 130.0, 600.0, 120.0)
        self.assertEqual(st.hit_test(300, 200), "card:response")
        self.assertIsNone(st.hit_test(300, 400))

    def test_buttons_on_a_card_win_over_the_card(self):
        st = _state()
        st.buttons["card:response"] = (100.0, 130.0, 600.0, 120.0)
        st.buttons["copy_response"] = (630.0, 220.0, 60.0, 22.0)
        self.assertEqual(st.hit_test(640, 230), "copy_response")

    def test_approval_buttons_have_priority(self):
        st = _state()
        st.pending_approval = {"approval_id": "a"}
        st.approval_card_rect = (100.0, 130.0, 600.0, 100.0)
        st.approve_btn_rect = (560.0, 140.0, 120.0, 32.0)
        st.reject_btn_rect = (120.0, 140.0, 115.0, 32.0)
        st.buttons["card:response"] = (100.0, 130.0, 600.0, 100.0)
        self.assertEqual(st.hit_test(600, 150), "approve")
        self.assertEqual(st.hit_test(150, 150), "reject")
        self.assertEqual(st.hit_test(400, 200), "approval_card")

    def test_response_scroll_is_clamped(self):
        st = _state()
        st.response_max_scroll = 5
        self.assertTrue(st.scroll_response(3))
        self.assertEqual(st.response_scroll, 3)
        self.assertTrue(st.scroll_response(9))
        self.assertEqual(st.response_scroll, 5)
        self.assertFalse(st.scroll_response(3))
        st.scroll_response(-99)
        self.assertEqual(st.response_scroll, 0)
        self.assertFalse(st.scroll_response(-3))


class EveryControlHasAHandler(unittest.TestCase):
    """No dead buttons: each key the renderer registers is routed somewhere in modal.py."""

    @classmethod
    def setUpClass(cls):
        cls.renderer = _src("renderer.py")
        cls.modal = _src("modal.py")

    def drawn_keys(self):
        static = set(re.findall(r'draw_button\(\s*"([^"]+)"', self.renderer))
        static |= set(re.findall(r'buttons\["([^"]+)"\]\s*=', self.renderer))
        static |= {k for k, _ in menu.menu_items({"available": True, "running": True, "endpoint": "x",
                                                   "token": "t", "allow_gated": False}, 2)}
        return static

    def test_static_keys_are_handled(self):
        sinks = ("card:", "panel_bg")
        for key in sorted(self.drawn_keys()):
            if key.startswith(sinks):
                continue  # intentional click sinks
            if key.startswith("set:"):
                field = key[len("set:"):]
                self.assertTrue(
                    f'"{field}"' in self.modal or f'"{key}"' in self.modal or field.startswith("timeout"),
                    f"settings key {key} has no handler")
                continue
            self.assertIn(f'"{key}"', self.modal, f"{key} is drawn but modal.py never handles it")

    def test_dynamic_history_keys_are_handled(self):
        self.assertIn('startswith("hist:copy:")', self.modal)
        self.assertIn('startswith("hist:tool:")', self.modal)

    def test_set_keys_cover_every_settings_button(self):
        for key in ("set:test", "set:save", "set:reload", "set:prefs"):
            self.assertIn(key, self.renderer)
        for field in ("test", "save", "reload", "prefs", "provider", "timeout:-", "timeout:+"):
            self.assertIn(f'"{field}"', self.modal)

    def test_pointer_events_do_not_leak_to_the_viewport(self):
        for token in ("WHEELUPMOUSE", "RIGHTMOUSE", "MIDDLEMOUSE"):
            self.assertIn(token, self.modal)


if __name__ == "__main__":
    unittest.main()
