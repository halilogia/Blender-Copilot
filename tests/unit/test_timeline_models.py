"""Unit tests for V2 Agent UI timeline presentation models."""

from dataclasses import FrozenInstanceError
import unittest

from agent.timeline_models import (
    ActiveTurnView,
    TimelineTurn,
    TimelineTurnStatus,
    ToolExecutionView,
)


class TestTimelineModels(unittest.TestCase):
    """Test suite for ToolExecutionView, ActiveTurnView, and TimelineTurn."""

    def test_tool_execution_view_creation_and_defaults(self):
        """ToolExecutionView can be instantiated with required fields and optional defaults."""
        view = ToolExecutionView(
            tool_name="create_primitive",
            status="OK",
            summary="Created primitive 'Cube'",
        )
        self.assertEqual(view.tool_name, "create_primitive")
        self.assertEqual(view.status, "OK")
        self.assertEqual(view.summary, "Created primitive 'Cube'")
        self.assertIsNone(view.call_id)
        self.assertIsNone(view.error_message)

        # Serialization
        d = view.to_dict()
        self.assertEqual(d["tool_name"], "create_primitive")
        self.assertEqual(d["status"], "OK")
        self.assertEqual(d["summary"], "Created primitive 'Cube'")
        self.assertIsNone(d["call_id"])
        self.assertIsNone(d["error_message"])

    def test_tool_execution_view_with_call_id_and_error(self):
        """ToolExecutionView stores optional call_id and error_message when provided."""
        view = ToolExecutionView(
            tool_name="transform_object",
            status="FAILED",
            summary="Failed to transform 'NonExistent'",
            call_id="call_12345",
            error_message="Object 'NonExistent' does not exist in scene",
        )
        self.assertEqual(view.call_id, "call_12345")
        self.assertEqual(view.error_message, "Object 'NonExistent' does not exist in scene")
        self.assertEqual(view.to_dict()["call_id"], "call_12345")

    def test_active_turn_view_creation_and_defaults(self):
        """ActiveTurnView represents in-flight turn with default status RUNNING and empty response."""
        active = ActiveTurnView(
            turn_id="turn_001",
            prompt="Make a wooden table",
        )
        self.assertEqual(active.turn_id, "turn_001")
        self.assertEqual(active.prompt, "Make a wooden table")
        self.assertEqual(active.streaming_response, "")
        self.assertEqual(active.status, TimelineTurnStatus.RUNNING)
        self.assertEqual(active.tool_executions, ())
        self.assertIsNone(active.error_message)

    def test_active_turn_view_coerces_list_to_tuple(self):
        """ActiveTurnView converts tool_executions list into an immutable tuple."""
        tool = ToolExecutionView(tool_name="inspect_scene", status="OK", summary="Scene has 3 objects")
        active = ActiveTurnView(
            turn_id="turn_002",
            prompt="Inspect scene",
            tool_executions=[tool],
        )
        self.assertIsInstance(active.tool_executions, tuple)
        self.assertEqual(len(active.tool_executions), 1)
        self.assertEqual(active.tool_executions[0], tool)

    def test_timeline_turn_creation_and_defaults(self):
        """TimelineTurn represents finalized turn in the chat timeline."""
        turn = TimelineTurn(
            turn_id="turn_001",
            prompt="Make a wooden table",
            status=TimelineTurnStatus.COMPLETED,
            final_response="Created table with wooden material.",
        )
        self.assertEqual(turn.turn_id, "turn_001")
        self.assertEqual(turn.prompt, "Make a wooden table")
        self.assertEqual(turn.status, TimelineTurnStatus.COMPLETED)
        self.assertEqual(turn.final_response, "Created table with wooden material.")
        self.assertEqual(turn.tool_executions, ())
        self.assertIsNone(turn.error_message)

    def test_timeline_turn_coerces_string_status(self):
        """TimelineTurn coerces string status into TimelineTurnStatus enum."""
        turn = TimelineTurn(
            turn_id="turn_003",
            prompt="Delete cube",
            status="CANCELLED",
        )
        self.assertEqual(turn.status, TimelineTurnStatus.CANCELLED)

    def test_immutability_frozen_behavior(self):
        """All timeline models are frozen and reject attribute mutation."""
        tool = ToolExecutionView(tool_name="inspect_scene", status="OK", summary="OK")
        with self.assertRaises(FrozenInstanceError):
            tool.status = "FAILED"

        active = ActiveTurnView(turn_id="t1", prompt="p1")
        with self.assertRaises(FrozenInstanceError):
            active.streaming_response = "new text"

        turn = TimelineTurn(turn_id="t1", prompt="p1", status=TimelineTurnStatus.COMPLETED)
        with self.assertRaises(FrozenInstanceError):
            turn.final_response = "new response"

    def test_default_values_not_shared_or_mutable(self):
        """Default collections are independent and immutable across distinct instances."""
        t1 = ActiveTurnView(turn_id="t1", prompt="p1")
        t2 = ActiveTurnView(turn_id="t2", prompt="p2")
        self.assertIsInstance(t1.tool_executions, tuple)
        self.assertIsInstance(t2.tool_executions, tuple)
        self.assertEqual(t1.tool_executions, ())
        self.assertEqual(t2.tool_executions, ())

    def test_active_turn_and_timeline_turn_represent_two_lifecycle_stages(self):
        """ActiveTurnView and TimelineTurn represent the active and finalized stages of a turn."""
        turn_id = "turn_roundtrip_42"
        prompt = "Create a spotlight pointing down"
        tool1 = ToolExecutionView(tool_name="create_light", status="OK", summary="Created SPOT light")

        # Stage 1: Active turn while streaming
        active_stage = ActiveTurnView(
            turn_id=turn_id,
            prompt=prompt,
            streaming_response="Creating spotlight...",
            status=TimelineTurnStatus.RUNNING,
            tool_executions=(tool1,),
        )
        self.assertEqual(active_stage.status, TimelineTurnStatus.RUNNING)
        self.assertEqual(active_stage.streaming_response, "Creating spotlight...")

        # Stage 2: Finalized turn after completion
        finalized_stage = TimelineTurn(
            turn_id=turn_id,
            prompt=prompt,
            status=TimelineTurnStatus.COMPLETED,
            final_response="Created spotlight pointing directly downwards.",
            tool_executions=active_stage.tool_executions,
        )
        self.assertEqual(finalized_stage.turn_id, active_stage.turn_id)
        self.assertEqual(finalized_stage.status, TimelineTurnStatus.COMPLETED)
        self.assertEqual(finalized_stage.final_response, "Created spotlight pointing directly downwards.")
        self.assertEqual(len(finalized_stage.tool_executions), 1)

    def test_serialization_structure(self):
        """Serialization to_dict produces expected keys and values."""
        tool = ToolExecutionView(
            tool_name="create_camera",
            status="OK",
            summary="Camera created",
            call_id="call_99",
            error_message=None,
        )
        turn = TimelineTurn(
            turn_id="turn_77",
            prompt="Add camera",
            status=TimelineTurnStatus.COMPLETED,
            final_response="Done",
            tool_executions=(tool,),
            error_message=None,
        )
        data = turn.to_dict()
        self.assertEqual(data["turn_id"], "turn_77")
        self.assertEqual(data["prompt"], "Add camera")
        self.assertEqual(data["status"], "COMPLETED")
        self.assertEqual(data["final_response"], "Done")
        self.assertEqual(len(data["tool_executions"]), 1)
        self.assertEqual(data["tool_executions"][0]["tool_name"], "create_camera")


if __name__ == "__main__":
    unittest.main()
