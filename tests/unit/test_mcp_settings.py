"""Unit tests for the MCP bridge settings file and environment overrides. Pure Python, zero Blender dependencies."""

import json
import os
import tempfile
import unittest
from pathlib import Path

from bridge.settings import DEFAULT_PORT, BridgeSettings, ensure_token, load_settings, mask_token, save_settings


class TestBridgeSettings(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.path = Path(self.dir.name) / "mcp_bridge.json"

    def tearDown(self):
        self.dir.cleanup()

    def test_defaults_when_file_is_missing_or_broken(self):
        s = load_settings(self.path, env={})
        self.assertFalse(s.enabled)
        self.assertFalse(s.allow_gated)
        self.assertEqual(s.port, DEFAULT_PORT)
        self.assertEqual(s.token, "")
        self.path.write_text("{not json", encoding="utf-8")
        self.assertEqual(load_settings(self.path, env={}).port, DEFAULT_PORT)

    def test_round_trip_and_token_is_generated_once(self):
        s = BridgeSettings(enabled=True, port=6611)
        token = ensure_token(s)
        self.assertGreaterEqual(len(token), 32)
        self.assertEqual(ensure_token(s), token)
        save_settings(s, self.path)
        again = load_settings(self.path, env={})
        self.assertTrue(again.enabled)
        self.assertEqual(again.port, 6611)
        self.assertEqual(again.token, token)

    def test_invalid_port_falls_back(self):
        self.path.write_text(json.dumps({"port": 80}), encoding="utf-8")
        self.assertEqual(load_settings(self.path, env={}).port, DEFAULT_PORT)
        self.path.write_text(json.dumps({"port": "abc"}), encoding="utf-8")
        self.assertEqual(load_settings(self.path, env={}).port, DEFAULT_PORT)

    def test_environment_overrides_the_file(self):
        save_settings(BridgeSettings(enabled=False, port=6600, token="filetoken", allow_gated=False, export_dir="A"), self.path)
        env = {
            "BLENDER_COPILOT_MCP": "1",
            "BLENDER_COPILOT_MCP_PORT": "6650",
            "BLENDER_COPILOT_MCP_TOKEN": "envtoken",
            "BLENDER_COPILOT_MCP_ALLOW_GATED": "true",
            "BLENDER_COPILOT_EXPORT_DIR": "B",
        }
        s = load_settings(self.path, env=env)
        self.assertTrue(s.enabled)
        self.assertEqual((s.port, s.token, s.allow_gated, s.export_dir), (6650, "envtoken", True, "B"))
        self.assertFalse(load_settings(self.path, env={"BLENDER_COPILOT_MCP": "0"}).enabled)
        self.assertEqual(load_settings(self.path, env={"BLENDER_COPILOT_MCP_PORT": "99"}).port, 6600)

    def test_environment_overrides_are_never_written_back(self):
        save_settings(BridgeSettings(enabled=False, port=6600, token="filetoken", allow_gated=False, export_dir="A"), self.path)
        env = {"BLENDER_COPILOT_MCP": "1", "BLENDER_COPILOT_MCP_PORT": "6650", "BLENDER_COPILOT_MCP_TOKEN": "envtoken",
               "BLENDER_COPILOT_MCP_ALLOW_GATED": "1", "BLENDER_COPILOT_EXPORT_DIR": "B"}
        s = load_settings(self.path, env=env)
        self.assertTrue(s.allow_gated)                                    # in force for this run
        save_settings(s, self.path)                                       # what the controller does when it starts
        on_disk = json.loads(self.path.read_text(encoding="utf-8"))
        self.assertEqual((on_disk["enabled"], on_disk["port"], on_disk["token"], on_disk["allow_gated"], on_disk["export_dir"]),
                         (False, 6600, "filetoken", False, "A"))
        again = load_settings(self.path, env={})
        self.assertFalse(again.allow_gated)
        self.assertFalse(again.enabled)

    def test_a_deliberate_change_is_kept_even_when_an_override_was_active(self):
        save_settings(BridgeSettings(allow_gated=False), self.path)
        s = load_settings(self.path, env={"BLENDER_COPILOT_MCP_ALLOW_GATED": "1"})
        s.set("allow_gated", False)                                       # the user switches it off in the panel
        s.set("export_dir", "C")
        save_settings(s, self.path)
        on_disk = json.loads(self.path.read_text(encoding="utf-8"))
        self.assertEqual((on_disk["allow_gated"], on_disk["export_dir"]), (False, "C"))

    def test_mask_token_never_returns_the_full_secret(self):
        token = "abcdef0123456789"
        masked = mask_token(token)
        self.assertNotIn(token, masked)
        self.assertTrue(masked.startswith("abcdef"))
        self.assertEqual(mask_token(""), "")


if __name__ == "__main__":
    unittest.main()
