"""Unit tests for the HUD settings drawer logic and the design tokens (pure Python, no bpy)."""

import importlib.util
import os
import unittest

from agent.http_client import HttpConnectionError, HttpError

_HUD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "ui", "gpu_overlay")


def _load(name):
    spec = importlib.util.spec_from_file_location(f"hud_{name}", os.path.join(_HUD_DIR, f"{name}.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


settings = _load("settings")
theme = _load("theme")
state_mod = _load("state")

SECRET = "placeholder-not-a-real-key-1234"


class _Resp:
    def __init__(self, status=200):
        self.status_code = status

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class _Client:
    """Stands in for HttpClient: records the request, returns or raises the scripted result."""

    def __init__(self, result):
        self.result = result
        self.calls = []

    def get(self, endpoint, headers=None, timeout=None):
        self.calls.append((endpoint, dict(headers or {}), timeout))
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


class FieldTests(unittest.TestCase):
    def test_agy_hides_network_fields(self):
        self.assertEqual(settings.visible_fields("agy_cli"), ["provider", "model"])
        self.assertIn("api_key", settings.visible_fields("openai_compatible"))

    def test_provider_cycles_through_all_three(self):
        seen, p = [], "openai_compatible"
        for _ in range(3):
            p = settings.next_provider(p)
            seen.append(p)
        self.assertEqual(seen, ["anthropic", "agy_cli", "openai_compatible"])

    def test_timeout_is_clamped(self):
        self.assertEqual(settings.step_timeout(5, -15), 5)
        self.assertEqual(settings.step_timeout(295, 15), 300)

    def test_api_key_is_never_shown_in_clear(self):
        values = {"api_key": SECRET}
        shown = settings.display_value("api_key", values, None)
        self.assertNotIn(SECRET, shown)
        editor = settings.FieldEditor("api_key", SECRET)
        typing = settings.display_value("api_key", values, editor)
        self.assertNotIn("placeholder", typing)
        self.assertEqual(len(typing), len(SECRET))
        self.assertEqual(settings.display_value("api_key", {"api_key": ""}, None), "not set")

    def test_editor_insert_strips_newlines_and_backspaces(self):
        ed = settings.FieldEditor("model", "gpt")
        ed.insert("-4\no\r")
        self.assertEqual(ed.text, "gpt-4o")
        ed.backspace()
        self.assertEqual(ed.text, "gpt-4")
        ed.text = "one two"
        ed.backspace(word=True)
        self.assertEqual(ed.text, "one ")


class ProviderNoteTests(unittest.TestCase):
    def test_agy_note_mentions_text_only_and_model_fallback(self):
        self.assertIn("Text only", settings.provider_note("agy_cli", "gemini-3.8-flash-low"))
        fallback = settings.provider_note("agy_cli", "gpt-4o")
        self.assertIn("gemini-3.8-flash-low", fallback)
        self.assertEqual(settings.provider_note("anthropic", "claude"), "")


class OnlineStatusTests(unittest.TestCase):
    def test_remote_without_online_access_warns(self):
        level, text = settings.online_status("openai_compatible", "https://api.openai.com/v1", False)
        self.assertEqual(level, "warn")
        self.assertIn("Online access", text)

    def test_local_and_enabled_are_ok(self):
        self.assertEqual(settings.online_status("openai_compatible", "http://localhost:11434/v1", False)[0], "ok")
        self.assertEqual(settings.online_status("anthropic", "https://api.anthropic.com/v1", True)[0], "ok")

    def test_agy_is_informational(self):
        self.assertEqual(settings.online_status("agy_cli", "", False)[0], "info")


class ConnectionTestTests(unittest.TestCase):
    def run_test(self, provider, url, result, online=True, key=SECRET):
        client = _Client(result)
        ok, msg = settings.run_connection_test(provider, url, key, 10, online, client=client)
        return ok, msg, client

    def test_success_openai_uses_bearer_and_models_path(self):
        ok, msg, c = self.run_test("openai_compatible", "https://x.test/v1/", _Resp(200))
        self.assertTrue(ok)
        self.assertEqual(c.calls[0][0], "/models")
        self.assertEqual(c.calls[0][1]["Authorization"], "Bearer " + SECRET)

    def test_anthropic_uses_x_api_key_header(self):
        ok, _, c = self.run_test("anthropic", "https://api.anthropic.com/v1", _Resp(200))
        self.assertTrue(ok)
        self.assertEqual(c.calls[0][1]["x-api-key"], SECRET)
        self.assertEqual(c.calls[0][1]["anthropic-version"], settings.ANTHROPIC_VERSION)

    def test_rejected_key_is_reported_without_leaking_it(self):
        ok, msg, _ = self.run_test("openai_compatible", "https://x.test/v1", HttpError(401, "Unauthorized"))
        self.assertFalse(ok)
        self.assertIn("401", msg)
        self.assertNotIn(SECRET, msg)

    def test_missing_models_route_still_counts_as_reached(self):
        ok, _, _ = self.run_test("openai_compatible", "https://x.test/v1", HttpError(404, "Not Found"))
        self.assertTrue(ok)

    def test_unreachable_host(self):
        ok, msg, _ = self.run_test("openai_compatible", "http://localhost:9/v1",
                                   HttpConnectionError("refused", details="refused"))
        self.assertFalse(ok)
        self.assertIn("Cannot reach", msg)

    def test_remote_blocked_when_online_access_off(self):
        ok, msg, c = self.run_test("openai_compatible", "https://x.test/v1", _Resp(200), online=False)
        self.assertFalse(ok)
        self.assertIn("online access", msg.lower())
        self.assertEqual(c.calls, [], "no request may leave the machine when access is off")

    def test_local_endpoint_allowed_when_offline(self):
        ok, _, c = self.run_test("openai_compatible", "http://127.0.0.1:11434/v1", _Resp(200), online=False)
        self.assertTrue(ok)
        self.assertEqual(len(c.calls), 1)

    def test_agy_checks_path_only(self):
        ok, msg = settings.run_connection_test("agy_cli", "", "", 10, False, agy_resolver=lambda: "C:/agy.exe")
        self.assertTrue(ok)
        ok, msg = settings.run_connection_test("agy_cli", "", "", 10, False, agy_resolver=lambda: None)
        self.assertFalse(ok)
        self.assertIn("not found", msg)


class ThemeTests(unittest.TestCase):
    def test_tokens_are_valid_rgba(self):
        for name in ("ACCENT", "ACCENT_HOVER", "ACCENT_INK", "SURFACE", "SURFACE_2", "BORDER", "CTRL",
                     "CTRL_HOVER", "TEXT", "TEXT_DIM", "TEXT_FAINT", "OK", "WARN", "DANGER"):
            value = getattr(theme, name)
            self.assertEqual(len(value), 4, name)
            self.assertTrue(all(0.0 <= c <= 1.0 for c in value), name)

    def test_spacing_and_type_scale_are_consistent(self):
        self.assertEqual((theme.SPACE_1, theme.SPACE_2, theme.SPACE_3, theme.SPACE_4), (4.0, 8.0, 16.0, 24.0))
        self.assertGreater(theme.T_INPUT, theme.T_TITLE)
        self.assertGreater(theme.T_TITLE, theme.T_BODY)
        self.assertGreater(theme.T_BODY, theme.T_SMALL)

    def test_renderer_has_no_inline_colour_literals(self):
        """All colours must come from theme.py (transparent zero rects excepted)."""
        import re
        src = open(os.path.join(_HUD_DIR, "renderer.py"), encoding="utf-8").read()
        literals = set(re.findall(r"\(\d(?:\.\d+)?, \d(?:\.\d+)?, \d(?:\.\d+)?, \d(?:\.\d+)?\)", src))
        self.assertLessEqual(literals, {"(0.0, 0.0, 0.0, 0.0)", "(0, 0, 0, 0)"})


class SettingsStateTests(unittest.TestCase):
    def test_closing_the_drawer_drops_the_editor(self):
        st = state_mod.GPUOverlayState()
        st.panel = "settings"
        st.settings_editor = settings.FieldEditor("model", "x")
        st.toggle_panel("settings")
        self.assertIsNone(st.panel)
        self.assertIsNone(st.settings_editor)


if __name__ == "__main__":
    unittest.main()
