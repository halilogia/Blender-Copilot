"""Headless integration test for the task ledger in real Blender 5.2: a task's changes are reported by meaning, one rollback
undoes the whole task and is verified, the snapshot is taken by the dispatcher before the first tool."""

import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import bpy  # noqa: E402

from adapter.blender_adapter import BlenderAdapter  # noqa: E402
from adapter.mutators import undo_manager  # noqa: E402
from adapter.readers import scene_snapshot  # noqa: E402
from adapter.task_ledger import LEDGER  # noqa: E402
from agent.dispatcher import ToolDispatcher  # noqa: E402
from core.scene_diff import diff  # noqa: E402
from agent.models import ToolCall  # noqa: E402
from core.types import RiskLevel  # noqa: E402
from tools.mutations.create_primitive import CreatePrimitiveTool  # noqa: E402
from tools.mutations.create_prop import CreatePropTool  # noqa: E402
from tools.mutations.delete_object import DeleteObjectTool  # noqa: E402
from tools.mutations.set_material import SetMaterialTool  # noqa: E402
from tools.mutations.task_rollback import TaskRollbackTool  # noqa: E402
from tools.mutations.transform_object import TransformObjectTool  # noqa: E402
from tools.read_only.task_report import TaskReportTool  # noqa: E402
from tools.registry import ToolRegistry  # noqa: E402

_ids = iter(range(10000))


def start():
    bpy.ops.wm.read_homefile(use_empty=True)
    bpy.context.preferences.edit.use_global_undo = True
    LEDGER._baseline = None
    registry = ToolRegistry()
    for tool in (CreatePrimitiveTool(), CreatePropTool(), DeleteObjectTool(), SetMaterialTool(), TransformObjectTool(),
                 TaskReportTool(), TaskRollbackTool()):
        registry.register(tool)
    adapter = BlenderAdapter()
    undo_manager.push_undo_step("Baseline")
    return ToolDispatcher(registry=registry, adapter=adapter), adapter


def call(dispatcher, tool, **arguments):
    res = dispatcher.dispatch(ToolCall(call_id=f"c{next(_ids)}", tool_name=tool, arguments=arguments))
    assert res.success, (tool, arguments, res.error)
    return res.data


def test_report():
    print("Test 1: the dispatcher opens a task; task_report says what changed...")
    d, adapter = start()
    call(d, "create_primitive", primitive_type="CUBE", name="Crate", size=1.0, location=[0, 0, 0.5])
    call(d, "create_prop", kind="house", location=[5, 0, 0])
    call(d, "set_material", object_name="Crate", material_name="Wood", base_color=[0.4, 0.2, 0.1, 1])
    call(d, "transform_object", name="Crate", location=[2, 0, 0.5])
    report = call(d, "task_report", close=False)
    text = "\n".join(report["changes"])
    assert "+ Crate (MESH)" in text and "+ house" in text and "+ material Wood" in text, text
    assert report["undo_steps"] == 4 and not report["empty"], report           # create_prop counts as one step
    assert report["counts"]["objects_added"] >= 2 and "added" in report["headline"]
    # the task stays open with close=false; closing starts a new one
    again = call(d, "task_report")
    assert again["undo_steps"] == 4
    call(d, "create_primitive", primitive_type="SPHERE", name="Ball", size=1.0, location=[0, 5, 0.5])
    fresh = call(d, "task_report")
    assert fresh["changes"] and all("Crate" not in line and "house" not in line for line in fresh["changes"]), fresh
    assert fresh["undo_steps"] == 1
    empty = call(d, "task_report")
    assert empty["empty"] and empty["undo_steps"] == 0 and empty["changes"] == []
    print("[PASS] Test 1")


def test_rollback():
    print("Test 2: one rollback takes back the whole task, verified...")
    d, adapter = start()
    call(d, "create_primitive", primitive_type="CUBE", name="Keep", size=1.0, location=[0, 0, 0.5])
    call(d, "task_report")                                                        # closes the first task
    before = scene_snapshot.take()
    call(d, "create_prop", kind="barrel", location=[3, 0, 0])
    call(d, "set_material", object_name="Keep", material_name="Red", base_color=[1, 0, 0, 1])
    call(d, "transform_object", name="Keep", location=[9, 9, 9])
    bpy.data.objects["Keep"].name  # still there
    res = call(d, "task_rollback")
    assert res["rolled_back"] and res["verified"] and res["remaining_differences"] == [], res
    assert res["undo_steps_done"] == res["undo_steps_expected"] == 3
    assert diff(before, scene_snapshot.take())["empty"], "the scene must equal the snapshot taken before the task"
    assert "Red" not in bpy.data.materials and tuple(round(v, 3) for v in bpy.data.objects["Keep"].location) == (0, 0, 0.5)
    # rolling back twice: nothing is open any more
    twice = call(d, "task_rollback")
    assert twice["rolled_back"] is False
    # a task that deleted something comes back too
    call(d, "delete_object", name="Keep")
    assert "Keep" not in bpy.data.objects
    res = call(d, "task_rollback")
    assert res["rolled_back"] and "Keep" in bpy.data.objects, res
    # a task that changed nothing
    call(d, "task_report")
    call(d, "task_report", close=False)
    nothing = call(d, "task_rollback")
    assert nothing["rolled_back"] is False and "nothing" in nothing["reason"]
    print("[PASS] Test 2")


def test_begin_and_gating():
    print("Test 3: a new chat message starts a new task; rollback needs approval; counter stays honest...")
    d, adapter = start()
    call(d, "create_primitive", primitive_type="CUBE", name="Old", size=1.0)
    adapter.task_begin("second message")                                           # what the agent runtime does per message
    call(d, "create_primitive", primitive_type="CUBE", name="New", size=1.0, location=[4, 0, 0])
    report = call(d, "task_report")
    assert report["task"] == "second message"
    assert "+ New (MESH)" in report["changes"] and all("Old" not in line for line in report["changes"])
    assert TaskRollbackTool.risk_level == RiskLevel.MEDIUM and TaskReportTool.risk_level == RiskLevel.READ_ONLY
    n = undo_manager.undo_counter()
    call(d, "create_primitive", primitive_type="CUBE", name="Third", size=1.0, location=[8, 0, 0])
    assert undo_manager.undo_counter() == n + 1
    call(d, "task_rollback")
    assert undo_manager.undo_counter() == n
    # a failing tool does not break the ledger
    bad = d.dispatch(ToolCall(call_id="x", tool_name="create_prop", arguments={"kind": "spaceship"}))
    assert not bad.success
    assert call(d, "task_report")["empty"]
    print("[PASS] Test 3")


if __name__ == "__main__":
    test_report()
    test_rollback()
    test_begin_and_gating()
    print("ALL TASK LEDGER INTEGRATION TESTS PASSED")
