"""Unit tests for asset browser index + import_asset guards (v1.1 C). Pure Python."""

import tempfile
import unittest
from pathlib import Path

from agent.asset_index import AssetLibrary, is_safe_path, scan_library
from agent.verifier import ChangeVerifier, build_change_set_from_result
from tools.mutations.import_asset import ImportAssetTool
from core.types import RiskLevel


class TestAssetIndex(unittest.TestCase):
    def test_traversal_guard(self):
        with tempfile.TemporaryDirectory() as root:
            self.assertTrue(is_safe_path(root, "props/chair.blend"))
            self.assertFalse(is_safe_path(root, "../evil.blend"))
            self.assertFalse(is_safe_path(root, "/etc/passwd"))

    def test_scan_and_search(self):
        with tempfile.TemporaryDirectory() as root:
            (Path(root) / "chair.blend").write_bytes(b"x")
            (Path(root) / "table.obj").write_bytes(b"x")
            (Path(root) / "notes.txt").write_text("ignore")
            entries = scan_library(root)
            self.assertEqual(len(entries), 2)
            lib = AssetLibrary(root=root)
            lib.refresh()
            res = lib.search("chair", k=5)
            self.assertEqual(res[0]["name"], "chair")
            self.assertEqual(lib.resolve("chair.blend") is not None, True)
            self.assertIsNone(lib.resolve("../evil.blend"))

    def test_empty_query(self):
        with tempfile.TemporaryDirectory() as root:
            (Path(root) / "a.glb").write_bytes(b"x")
            lib = AssetLibrary(root=root)
            lib.refresh()
            self.assertEqual(len(lib.search("", k=5)), 1)


class TestImportAssetTool(unittest.TestCase):
    def test_metadata(self):
        t = ImportAssetTool()
        self.assertEqual(t.name, "import_asset")
        self.assertEqual(t.risk_level, RiskLevel.LOW)
        self.assertIn("path", t.input_schema["properties"])

    def test_traversal_rejected(self):
        t = ImportAssetTool()

        class Dummy:
            def import_asset(self, **kw):
                raise AssertionError("must not reach adapter")

        res = t.execute(Dummy(), path="../evil.blend")
        self.assertFalse(res.success)
        self.assertEqual(res.error.type, "INVALID_ARGUMENT")

    def test_empty_path(self):
        t = ImportAssetTool()

        class Dummy:
            pass

        res = t.execute(Dummy(), path="  ")
        self.assertFalse(res.success)

    def test_verifier_import_pass(self):
        v = ChangeVerifier()
        cs = build_change_set_from_result("import_asset", {"path": "chair.blend"},
                                          {"imported": True, "object_name": "Chair",
                                           "object_count": 2, "before": {"object_count": 1},
                                           "actual": {"imported": True, "object_name": "Chair", "object_count": 2}})
        self.assertIsNotNone(cs)
        r = v.verify(cs)
        self.assertEqual(r.status.value, "PASS")

    def test_verifier_import_fail(self):
        v = ChangeVerifier()
        cs = build_change_set_from_result("import_asset", {"path": "x"},
                                          {"imported": False, "object_name": "",
                                           "actual": {"imported": False, "object_name": ""}})
        r = v.verify(cs)
        self.assertEqual(r.status.value, "FAIL")


if __name__ == "__main__":
    unittest.main()
