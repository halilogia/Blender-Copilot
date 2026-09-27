"""Headless integration tests for v1.1 Track C: import_asset in live Blender.

Covers fixture .blend creation, library-relative import, object count growth,
ChangeVerifier import rule, atomic undo/redo restoration, fail-closed guards
(traversal, missing file, unconfigured library), and thread safety.
"""

import os
import sys
import tempfile
import threading

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import bpy

from adapter.blender_adapter import BlenderAdapter, ThreadSafetyViolationError
from adapter.mutators.undo_manager import perform_undo, perform_redo, push_undo_step
from agent.verifier import ChangeVerifier, build_change_set_from_result
from core.change_set import VerificationStatus
from tools.mutations.import_asset import ImportAssetTool
from tools.registry import ToolRegistry


def clean_scene():
    """Reset scene to a completely empty state and initialize baseline undo point."""
    bpy.ops.wm.read_homefile(use_empty=True)
    bpy.context.preferences.edit.use_global_undo = True
    push_undo_step("Initial Scene Baseline")


def make_fixture_library():
    """Create temp library dir with FixtureChair.blend containing object FixtureChair."""
    libdir = tempfile.mkdtemp(prefix="b3d_asset_lib_")
    clean_scene()
    adapter = BlenderAdapter()
    res = adapter.create_primitive(primitive_type="CUBE", name="FixtureChair",
                                   location=[1.0, 2.0, 3.0])
    assert res.success, f"Fixture setup failed: {res.error.message if res.error else '?'}"
    fixture = os.path.join(libdir, "FixtureChair.blend")
    bpy.ops.wm.save_as_mainfile(filepath=fixture)
    assert os.path.isfile(fixture), "Fixture .blend was not written"
    return libdir


def test_tool_registration():
    print("Test 1: Tool registration and risk metadata...")
    registry = ToolRegistry()
    tool = ImportAssetTool()
    registry.register(tool)
    assert registry.exists("import_asset")
    assert tool.risk_level.value == "LOW"
    assert "path" in tool.input_schema["properties"]
    print("[PASS] Test 1: Tool registration verified.")


def test_thread_safety_guard():
    print("Test 2: Thread safety guard...")
    adapter = BlenderAdapter()
    caught = []

    def background_worker():
        try:
            adapter.import_asset(path="x.blend")
        except ThreadSafetyViolationError:
            caught.append("import_asset")

    t = threading.Thread(target=background_worker)
    t.start()
    t.join()
    assert caught == ["import_asset"], f"Expected ThreadSafetyViolationError, got {caught}"
    print("[PASS] Test 2: ThreadSafetyViolationError strictly enforced on background thread.")


def test_guards_without_library():
    print("Test 3: Fail-closed guards (unconfigured, traversal, missing)...")
    clean_scene()
    adapter = BlenderAdapter(asset_library_root=None)
    if "BLENDER_AI_ASSET_DIR" in os.environ:
        del os.environ["BLENDER_AI_ASSET_DIR"]

    r1 = adapter.import_asset(path="chair.blend")
    assert not r1.success and r1.error.type == "ASSET_LIBRARY_UNCONFIGURED"

    with tempfile.TemporaryDirectory() as libdir:
        adapter2 = BlenderAdapter(asset_library_root=libdir)
        r2 = adapter2.import_asset(path="../evil.blend")
        assert not r2.success and r2.error.type == "INVALID_ARGUMENT"
        r3 = adapter2.import_asset(path="ghost.blend")
        assert not r3.success and r3.error.type == "ASSET_NOT_FOUND"
    print("[PASS] Test 3: Fail-closed guards verified.")


def test_import_blend_and_verify():
    print("Test 4: .blend import + ChangeVerifier integration...")
    libdir = make_fixture_library()
    clean_scene()
    adapter = BlenderAdapter(asset_library_root=libdir)
    verifier = ChangeVerifier()

    before_count = len(bpy.data.objects)
    args = {"path": "FixtureChair.blend"}
    res = adapter.import_asset(**args)
    assert res.success, f"Import failed: {res.error.message if res.error else '?'}"
    data = res.data
    assert data["imported"] is True
    assert data["object_name"] == "FixtureChair"
    assert data["object_count"] == before_count + 1
    assert bpy.data.objects.get("FixtureChair") is not None

    obj = bpy.data.objects["FixtureChair"]
    assert [round(v, 2) for v in obj.location] == [1.0, 2.0, 3.0]

    cs = build_change_set_from_result("import_asset", args, data)
    assert cs is not None and cs.operation == "import"
    v_res = verifier.verify(cs)
    assert v_res.status == VerificationStatus.PASS, f"Mismatches: {v_res.mismatches}"
    print("[PASS] Test 4: .blend import + verification verified.")
    return libdir


def test_import_with_rename_and_undo(libdir):
    print("Test 5: Import with rename + atomic undo/redo...")
    clean_scene()
    adapter = BlenderAdapter(asset_library_root=libdir)

    res = adapter.import_asset(path="FixtureChair.blend", name="ImportedChair")
    assert res.success, f"Import failed: {res.error.message if res.error else '?'}"
    assert res.data["object_name"] == "ImportedChair"
    assert bpy.data.objects.get("ImportedChair") is not None

    perform_undo()
    assert bpy.data.objects.get("ImportedChair") is None, "ImportedChair must vanish after undo"

    perform_redo()
    assert bpy.data.objects.get("ImportedChair") is not None, "ImportedChair must return after redo"
    print("[PASS] Test 5: Rename + undo/redo verified.")


def test_tool_dispatch_end_to_end(libdir):
    print("Test 6: ToolDispatcher end-to-end via registry tool...")
    from agent.dispatcher import ToolDispatcher
    from agent.models import ToolCall

    clean_scene()
    adapter = BlenderAdapter(asset_library_root=libdir)
    registry = ToolRegistry()
    registry.register(ImportAssetTool())
    dispatcher = ToolDispatcher(registry=registry, adapter=adapter)

    tc = ToolCall(call_id="call_asset_01", tool_name="import_asset",
                  arguments={"path": "FixtureChair.blend"})
    result = dispatcher.dispatch(tc)
    assert result.success, f"Dispatch failed: {result.error.message if result.error else '?'}"
    assert result.data["imported"] is True
    assert bpy.data.objects.get(result.data["object_name"]) is not None
    print("[PASS] Test 6: Dispatcher end-to-end verified.")


def run_all():
    print("\n========================================================")
    print("   RUNNING v1.1 ASSET IMPORT HEADLESS INTEGRATION TESTS  ")
    print("========================================================\n")

    test_tool_registration()
    test_thread_safety_guard()
    test_guards_without_library()
    libdir = test_import_blend_and_verify()
    test_import_with_rename_and_undo(libdir)
    test_tool_dispatch_end_to_end(libdir)

    print("\n========================================================")
    print("   ALL ASSET IMPORT TESTS PASSED (6/6)                  ")
    print("========================================================\n")


if __name__ == "__main__":
    try:
        run_all()
    except Exception as e:
        print(f"\n[FAIL] Test suite failed with exception: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
