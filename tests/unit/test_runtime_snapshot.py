"""Tests for UI-neutral RuntimeSnapshot projection, including V2 timeline and active turn."""

from dataclasses import FrozenInstanceError
import unittest
from unittest.mock import MagicMock

from agent.history import HistoryKind
from agent.runtime import AgentRuntime
from agent.runtime_snapshot import RuntimeSnapshot
from agent.timeline_models import ActiveTurnView, TimelineTurn, TimelineTurnStatus, ToolExecutionView


class TestRuntimeSnapshot(unittest.TestCase):
    """Test suite for RuntimeSnapshot projection and V2 timeline behavior."""

    def _create_mock_runtime(self) -> AgentRuntime:
        return AgentRuntime(
            provider=object(),
            dispatcher=MagicMock(),
            worker=MagicMock(),
        )

    def test_empty_runtime_yields_empty_timeline_and_none_active_turn(self):
        """1. Empty runtime → empty timeline tuple + active_turn is None."""
        runtime = self._create_mock_runtime()
        snapshot = runtime.snapshot()

        self.assertIsInstance(snapshot, RuntimeSnapshot)
        self.assertEqual(snapshot.timeline, ())
        self.assertIsNone(snapshot.active_turn)

    def test_single_user_turn_projection(self):
        """2. Single completed user turn projects into TimelineTurn with correct prompt."""
        runtime = self._create_mock_runtime()
        runtime.history.add(
            item_id="turn_1_user",
            turn_id="turn_1",
            kind=HistoryKind.USER,
            title="User: Create a red cube",
            status="SENT",
            summary="Create a red cube",
        )

        snapshot = runtime.snapshot()
        self.assertEqual(len(snapshot.timeline), 1)
        turn = snapshot.timeline[0]
        self.assertIsInstance(turn, TimelineTurn)
        self.assertEqual(turn.turn_id, "turn_1")
        self.assertEqual(turn.prompt, "Create a red cube")
        self.assertEqual(turn.status, TimelineTurnStatus.COMPLETED)
        self.assertIsNone(snapshot.active_turn)

    def test_assistant_response_mapped_to_final_response(self):
        """3. Assistant response detail maps to TimelineTurn.final_response."""
        runtime = self._create_mock_runtime()
        runtime.history.add(
            item_id="turn_1_user",
            turn_id="turn_1",
            kind=HistoryKind.USER,
            title="User: Inspect camera",
            status="SENT",
            summary="Inspect camera",
        )
        runtime.history.add(
            item_id="turn_1_assistant",
            turn_id="turn_1",
            kind=HistoryKind.ASSISTANT,
            title="Assistant: Camera has 50mm lens",
            status="DONE",
            summary="Camera has 50mm lens",
            detail="The active scene camera focal length is set to 50mm with perspective projection.",
        )

        snapshot = runtime.snapshot()
        self.assertEqual(len(snapshot.timeline), 1)
        turn = snapshot.timeline[0]
        self.assertEqual(
            turn.final_response,
            "The active scene camera focal length is set to 50mm with perspective projection.",
        )

    def test_tool_history_items_projected_as_tool_execution_views(self):
        """4. Tool history items are properly projected as ToolExecutionView instances."""
        runtime = self._create_mock_runtime()
        runtime.history.add(
            item_id="turn_1_user",
            turn_id="turn_1",
            kind=HistoryKind.USER,
            title="User: Create primitive",
            status="SENT",
            summary="Create primitive",
        )
        runtime.history.add(
            item_id="turn_1_tool_1",
            turn_id="turn_1",
            kind=HistoryKind.TOOL,
            title="Tool: create_primitive",
            status="OK",
            summary="Created CUBE at (0, 0, 0)",
            detail="Created CUBE at (0, 0, 0)",
        )

        snapshot = runtime.snapshot()
        self.assertEqual(len(snapshot.timeline), 1)
        turn = snapshot.timeline[0]
        self.assertEqual(len(turn.tool_executions), 1)
        tool = turn.tool_executions[0]
        self.assertIsInstance(tool, ToolExecutionView)
        self.assertEqual(tool.tool_name, "create_primitive")
        self.assertEqual(tool.status, "OK")
        self.assertEqual(tool.summary, "Created CUBE at (0, 0, 0)")
        self.assertIsNone(tool.error_message)

    def test_multiple_tools_in_turn_preserve_order(self):
        """5. Multiple tools within a single turn preserve their chronological sequence."""
        runtime = self._create_mock_runtime()
        runtime.history.add(
            item_id="turn_1_user",
            turn_id="turn_1",
            kind=HistoryKind.USER,
            title="User: Inspect and create",
            status="SENT",
            summary="Inspect and create",
        )
        tools = ["inspect_scene", "create_primitive", "transform_object", "inspect_object"]
        for idx, t_name in enumerate(tools):
            runtime.history.add(
                item_id=f"turn_1_tool_{idx}",
                turn_id="turn_1",
                kind=HistoryKind.TOOL,
                title=f"Tool: {t_name}",
                status="OK",
                summary=f"Executed {t_name}",
            )

        snapshot = runtime.snapshot()
        self.assertEqual(len(snapshot.timeline), 1)
        turn = snapshot.timeline[0]
        self.assertEqual(len(turn.tool_executions), 4)
        projected_tool_names = [t.tool_name for t in turn.tool_executions]
        self.assertEqual(projected_tool_names, tools)

    def test_active_streaming_turn_projected_as_active_turn(self):
        """6. Active in-flight turn with streaming text is projected as active_turn."""
        runtime = self._create_mock_runtime()
        runtime._current_turn_id = "turn_active_99"
        runtime._current_prompt = "Build a lamp"
        runtime._streaming_text = "I am calculating the lamp dimensions..."

        runtime.history.add(
            item_id="turn_active_99_user",
            turn_id="turn_active_99",
            kind=HistoryKind.USER,
            title="User: Build a lamp",
            status="SENT",
            summary="Build a lamp",
        )
        runtime.history.add(
            item_id="turn_active_99_tool_0",
            turn_id="turn_active_99",
            kind=HistoryKind.TOOL,
            title="Tool: inspect_scene",
            status="OK",
            summary="Scene has 1 cube",
        )

        snapshot = runtime.snapshot()
        self.assertIsNotNone(snapshot.active_turn)
        active = snapshot.active_turn
        self.assertIsInstance(active, ActiveTurnView)
        self.assertEqual(active.turn_id, "turn_active_99")
        self.assertEqual(active.prompt, "Build a lamp")
        self.assertEqual(active.streaming_response, "I am calculating the lamp dimensions...")
        self.assertEqual(active.status, TimelineTurnStatus.RUNNING)
        self.assertEqual(len(active.tool_executions), 1)
        self.assertEqual(active.tool_executions[0].tool_name, "inspect_scene")

    def test_active_turn_not_duplicated_into_completed_timeline(self):
        """7. Active turn is strictly excluded from timeline to prevent duplicate UI rendering."""
        runtime = self._create_mock_runtime()
        # Finished Turn 1
        runtime.history.add(
            item_id="turn_1_user",
            turn_id="turn_1",
            kind=HistoryKind.USER,
            title="User: Hi",
            status="SENT",
            summary="Hi",
        )
        runtime.history.add(
            item_id="turn_1_asst",
            turn_id="turn_1",
            kind=HistoryKind.ASSISTANT,
            title="Assistant: Hello",
            status="DONE",
            summary="Hello",
            detail="Hello there!",
        )

        # Active Turn 2
        runtime._current_turn_id = "turn_2"
        runtime._current_prompt = "Make a sphere"
        runtime._streaming_text = "Generating sphere..."
        runtime.history.add(
            item_id="turn_2_user",
            turn_id="turn_2",
            kind=HistoryKind.USER,
            title="User: Make a sphere",
            status="SENT",
            summary="Make a sphere",
        )

        snapshot = runtime.snapshot()
        # Active turn present
        self.assertIsNotNone(snapshot.active_turn)
        self.assertEqual(snapshot.active_turn.turn_id, "turn_2")

        # Timeline only contains turn_1, NEVER turn_2
        self.assertEqual(len(snapshot.timeline), 1)
        self.assertEqual(snapshot.timeline[0].turn_id, "turn_1")

    def test_turn_completion_transitions_from_active_to_timeline(self):
        """8. When turn finishes, active_turn becomes None and completed turn appears in timeline."""
        runtime = self._create_mock_runtime()

        # Step 1: Turn 1 is active
        runtime._current_turn_id = "turn_10"
        runtime._current_prompt = "Scale cube by 2"
        runtime._streaming_text = "Scaling..."
        runtime.history.add(
            item_id="turn_10_user",
            turn_id="turn_10",
            kind=HistoryKind.USER,
            title="User: Scale cube by 2",
            status="SENT",
            summary="Scale cube by 2",
        )

        snapshot_active = runtime.snapshot()
        self.assertIsNotNone(snapshot_active.active_turn)
        self.assertEqual(snapshot_active.timeline, ())

        # Step 2: Turn 1 completes
        runtime._current_turn_id = None
        runtime._streaming_text = ""
        runtime.history.add(
            item_id="turn_10_asst",
            turn_id="turn_10",
            kind=HistoryKind.ASSISTANT,
            title="Assistant: Scaled",
            status="DONE",
            summary="Cube scaled by 2",
            detail="Cube scale applied successfully.",
        )

        snapshot_completed = runtime.snapshot()
        self.assertIsNone(snapshot_completed.active_turn)
        self.assertEqual(len(snapshot_completed.timeline), 1)
        self.assertEqual(snapshot_completed.timeline[0].turn_id, "turn_10")
        self.assertEqual(snapshot_completed.timeline[0].final_response, "Cube scale applied successfully.")

    def test_multiple_turns_preserve_order(self):
        """9. Multiple finalized turns appear in exact chronological order in timeline."""
        runtime = self._create_mock_runtime()
        for i in range(1, 4):
            tid = f"turn_{i}"
            runtime.history.add(
                item_id=f"{tid}_user",
                turn_id=tid,
                kind=HistoryKind.USER,
                title=f"User: Task {i}",
                status="SENT",
                summary=f"Task {i}",
            )
            runtime.history.add(
                item_id=f"{tid}_asst",
                turn_id=tid,
                kind=HistoryKind.ASSISTANT,
                title=f"Assistant: Done {i}",
                status="DONE",
                summary=f"Done {i}",
                detail=f"Completed task {i}.",
            )

        snapshot = runtime.snapshot()
        self.assertEqual(len(snapshot.timeline), 3)
        self.assertEqual([t.turn_id for t in snapshot.timeline], ["turn_1", "turn_2", "turn_3"])
        self.assertEqual([t.prompt for t in snapshot.timeline], ["Task 1", "Task 2", "Task 3"])

    def test_existing_snapshot_fields_remain_intact(self):
        """10. Existing snapshot fields (state, queued_count, history, etc.) continue to work."""
        runtime = self._create_mock_runtime()
        runtime.history.add(
            item_id="queued_1",
            turn_id="queued_1",
            kind=HistoryKind.USER,
            title="Queued: inspect scene",
            status="QUEUED",
            summary="Inspect scene",
        )
        runtime.prompt_queue.enqueue("Inspect scene")

        snapshot = runtime.snapshot()
        self.assertEqual(snapshot.state, "IDLE")
        self.assertEqual(snapshot.queued_count, 1)
        self.assertEqual(snapshot.history[0]["status"], "QUEUED")
        self.assertIsNone(snapshot.pending_approval)
        self.assertEqual(snapshot.streaming_text, "")
        self.assertEqual(snapshot.last_response_text, "")

    def test_last_plan_summary_behavior_preserved(self):
        """11. Existing last_plan_summary projection behavior is preserved."""
        runtime = self._create_mock_runtime()
        runtime._last_plan_summary = {
            "plan_id": "plan_abc",
            "title": "Build Architecture",
            "status": "COMPLETED",
            "steps_total": 3,
            "steps_completed": 3,
        }

        snapshot = runtime.snapshot()
        self.assertEqual(snapshot.last_plan_summary, runtime._last_plan_summary)
        self.assertEqual(snapshot.last_plan_summary["title"], "Build Architecture")

    def test_snapshot_is_immutable(self):
        """12. RuntimeSnapshot is frozen and cannot be mutated."""
        runtime = self._create_mock_runtime()
        snapshot = runtime.snapshot()

        with self.assertRaises(FrozenInstanceError):
            snapshot.state = "PROCESSING"

        with self.assertRaises(FrozenInstanceError):
            snapshot.timeline = ()

        with self.assertRaises(FrozenInstanceError):
            snapshot.active_turn = None


if __name__ == "__main__":
    unittest.main()
