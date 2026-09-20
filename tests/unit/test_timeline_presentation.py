"""Pure Python unit tests for V2 Agent Chat Timeline presentation helpers and rendering data."""

import unittest

from agent.timeline_models import (
    ActiveTurnView,
    TimelineTurn,
    TimelineTurnStatus,
    ToolExecutionView,
    build_timeline_projection,
)
from agent.history import HistoryItem, HistoryKind
from ui.text_formatting import (
    clean_assistant_text,
    format_tool_status_icon,
    map_agent_status_to_ui,
    wrap_multiline_text,
)


class TestTimelinePresentation(unittest.TestCase):
    """Test suite for V2 Agent Chat Timeline presentation formatting and data mapping."""

    def test_empty_timeline_ui_state(self):
        """1. Empty timeline yields empty projection and correct empty state."""
        timeline, active = build_timeline_projection([])
        self.assertEqual(timeline, ())
        self.assertIsNone(active)

    def test_completed_turn_rendering_data(self):
        """2. Completed turn provides clean prompt, final response, and status for UI."""
        turn = TimelineTurn(
            turn_id="turn_42",
            prompt="Create a golden cube at X=3",
            status=TimelineTurnStatus.COMPLETED,
            final_response="Created golden cube at (3, 0, 0).",
            tool_executions=(
                ToolExecutionView(
                    tool_name="create_primitive",
                    status="OK",
                    summary="Created CUBE",
                ),
            ),
        )
        self.assertEqual(turn.prompt, "Create a golden cube at X=3")
        self.assertEqual(turn.final_response, "Created golden cube at (3, 0, 0).")
        self.assertEqual(turn.status.value, "COMPLETED")
        self.assertEqual(len(turn.tool_executions), 1)
        self.assertEqual(format_tool_status_icon(turn.tool_executions[0].status), "✓")

    def test_active_turn_rendering_data(self):
        """3. Active turn provides live streaming text and RUNNING presentation status."""
        active = ActiveTurnView(
            turn_id="turn_live",
            prompt="Generate 3 spheres",
            streaming_response="Calculating positions...",
            status=TimelineTurnStatus.RUNNING,
            tool_executions=(
                ToolExecutionView(
                    tool_name="inspect_scene",
                    status="OK",
                    summary="Scene has 0 objects",
                ),
                ToolExecutionView(
                    tool_name="create_primitive",
                    status="RUNNING",
                    summary="Creating sphere 1...",
                ),
            ),
        )
        self.assertEqual(active.prompt, "Generate 3 spheres")
        self.assertEqual(active.streaming_response, "Calculating positions...")
        self.assertEqual(active.status.value, "RUNNING")
        self.assertEqual(len(active.tool_executions), 2)
        self.assertEqual(format_tool_status_icon(active.tool_executions[0].status), "✓")
        self.assertEqual(format_tool_status_icon(active.tool_executions[1].status), "⟳")

    def test_multiple_tool_executions_rendering(self):
        """4. Multiple tool executions map to correct sequential status symbols and summaries."""
        tools = (
            ToolExecutionView(tool_name="inspect_scene", status="OK", summary="Found 3 objects"),
            ToolExecutionView(tool_name="create_primitive", status="OK", summary="Created Plane"),
            ToolExecutionView(tool_name="transform_object", status="FAILED", summary="Failed to scale", error_message="Scale factor cannot be 0"),
        )
        icons = [format_tool_status_icon(t.status) for t in tools]
        self.assertEqual(icons, ["✓", "✓", "✕"])
        self.assertEqual(tools[2].error_message, "Scale factor cannot be 0")

    def test_error_turn_rendering(self):
        """5. Failed turn properly formats error message and failure status."""
        history = [
            HistoryItem(
                item_id="t_err_user",
                turn_id="t_err",
                kind=HistoryKind.USER,
                title="User: Invalid command",
                status="SENT",
                summary="Invalid command",
                detail="Invalid command",
            ),
            HistoryItem(
                item_id="t_err_tool",
                turn_id="t_err",
                kind=HistoryKind.TOOL,
                title="Tool: unknown_tool",
                status="ERROR",
                summary="Tool unknown_tool does not exist",
                detail="ToolNotFoundError: Tool 'unknown_tool' is not registered",
            ),
        ]
        timeline, active = build_timeline_projection(history)
        self.assertIsNone(active)
        self.assertEqual(len(timeline), 1)
        err_turn = timeline[0]
        self.assertEqual(err_turn.status, TimelineTurnStatus.FAILED)
        self.assertIn("ToolNotFoundError", err_turn.error_message)

    def test_active_turn_to_completed_timeline_transition(self):
        """6. Active turn disappears from active and appears in timeline upon completion without duplication."""
        # Step 1: Active
        history = [
            HistoryItem(
                item_id="t1_u",
                turn_id="t1",
                kind=HistoryKind.USER,
                title="User: Task 1",
                status="SENT",
                summary="Task 1",
                detail="Task 1",
            )
        ]
        timeline_1, active_1 = build_timeline_projection(
            history,
            current_turn_id="t1",
            current_prompt="Task 1",
            streaming_text="Working on task 1...",
        )
        self.assertIsNotNone(active_1)
        self.assertEqual(active_1.turn_id, "t1")
        self.assertEqual(timeline_1, ())

        # Step 2: Completed
        history.append(
            HistoryItem(
                item_id="t1_a",
                turn_id="t1",
                kind=HistoryKind.ASSISTANT,
                title="Assistant: Done",
                status="DONE",
                summary="Done",
                detail="Completed task 1.",
            )
        )
        timeline_2, active_2 = build_timeline_projection(
            history,
            current_turn_id=None,
            current_prompt="",
            streaming_text="",
        )
        self.assertIsNone(active_2)
        self.assertEqual(len(timeline_2), 1)
        self.assertEqual(timeline_2[0].turn_id, "t1")
        self.assertEqual(timeline_2[0].final_response, "Completed task 1.")

    def test_multiline_text_wrapping(self):
        """7. Multiline text wrapping splits long paragraphs cleanly without breaking empty lines."""
        long_text = "This is a very long response from the AI assistant that needs to be displayed in the N-panel."
        wrapped = wrap_multiline_text(long_text, width=30)
        self.assertTrue(len(wrapped) >= 3)
        self.assertTrue(all(len(w) <= 30 for w in wrapped))

        # Preserves explicit paragraphs
        para_text = "Paragraph 1\n\nParagraph 2 is slightly longer than paragraph 1."
        wrapped_para = wrap_multiline_text(para_text, width=25)
        self.assertIn("", wrapped_para)  # Preserves blank separator line

    def test_agent_status_mapping_to_ui(self):
        """8. Backend AgentState maps to user-friendly labels and icons."""
        idle_map = map_agent_status_to_ui("IDLE")
        self.assertEqual(idle_map["label"], "IDLE")
        self.assertEqual(idle_map["icon"], "CHECKMARK")

        proc_map = map_agent_status_to_ui("PROCESSING")
        self.assertEqual(proc_map["label"], "THINKING")
        self.assertEqual(proc_map["icon"], "TIME")

        exec_map = map_agent_status_to_ui("EXECUTING_TOOL")
        self.assertEqual(exec_map["label"], "EXECUTING")
        self.assertEqual(exec_map["icon"], "TOOL_SETTINGS")

        appr_map = map_agent_status_to_ui("PENDING_APPROVAL")
        self.assertEqual(appr_map["label"], "WAITING FOR APPROVAL")
        self.assertEqual(appr_map["icon"], "QUESTION")

        err_map = map_agent_status_to_ui("ERROR")
        self.assertEqual(err_map["label"], "ERROR")
        self.assertEqual(err_map["icon"], "ERROR")


if __name__ == "__main__":
    unittest.main()
