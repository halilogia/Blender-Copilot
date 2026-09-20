"""Focused unit tests for V2.3 Workspace Actions & Formatting.

Tests:
1. Copy Plan text formatting.
2. Copy Tool text formatting.
3. Plan step status mapping (symbols, icons, labels).
4. Edge cases: empty steps, missing summaries, unknown statuses.
"""

import unittest
from ui.text_formatting import (
    format_plan_step_status,
    format_plan_text_for_clipboard,
    format_tool_text_for_clipboard,
)


class TestWorkspaceFormatting(unittest.TestCase):
    """Test suite for V2.3 clipboard text formatting and status mapping."""

    def test_format_plan_step_status_mapping(self):
        """1. Verify PlanStepStatus correctly maps to UI symbols, icons, and labels."""
        # Completed
        s_comp = format_plan_step_status("COMPLETED")
        self.assertEqual(s_comp["symbol"], "✓")
        self.assertEqual(s_comp["icon"], "CHECKMARK")
        self.assertEqual(s_comp["label"], "completed")

        # Running
        s_run = format_plan_step_status("RUNNING")
        self.assertEqual(s_run["symbol"], "⟳")
        self.assertEqual(s_run["icon"], "TIME")
        self.assertEqual(s_run["label"], "running")

        # Pending
        s_pend = format_plan_step_status("PENDING")
        self.assertEqual(s_pend["symbol"], "○")
        self.assertEqual(s_pend["icon"], "DOT")
        self.assertEqual(s_pend["label"], "pending")

        # Failed
        s_fail = format_plan_step_status("FAILED")
        self.assertEqual(s_fail["symbol"], "!")
        self.assertEqual(s_fail["icon"], "ERROR")
        self.assertEqual(s_fail["label"], "failed")

        # Cancelled
        s_canc = format_plan_step_status("CANCELLED")
        self.assertEqual(s_canc["symbol"], "—")
        self.assertEqual(s_canc["icon"], "CANCEL")
        self.assertEqual(s_canc["label"], "cancelled")

        # Skipped
        s_skip = format_plan_step_status("SKIPPED")
        self.assertEqual(s_skip["symbol"], "⤼")
        self.assertEqual(s_skip["icon"], "FORWARD")
        self.assertEqual(s_skip["label"], "skipped")

    def test_format_plan_text_for_clipboard(self):
        """2. Verify format_plan_text_for_clipboard formats human-readable text."""
        steps = [
            {"description": "Create foundation", "status": "COMPLETED"},
            {"description": "Create main tower", "status": "RUNNING"},
            {"description": "Add materials", "status": "PENDING"},
        ]
        result = format_plan_text_for_clipboard(
            title="Create Castle",
            status="RUNNING",
            steps=steps,
        )
        expected = (
            "Plan: Create Castle\n"
            "Status: running\n\n"
            "1. Create foundation\n"
            "   Status: completed\n"
            "2. Create main tower\n"
            "   Status: running\n"
            "3. Add materials\n"
            "   Status: pending"
        )
        self.assertEqual(result, expected)

    def test_format_tool_text_for_clipboard(self):
        """3. Verify format_tool_text_for_clipboard formats clean tool text."""
        result = format_tool_text_for_clipboard(
            tool_name="inspect_scene",
            status="OK",
            summary="Scene contains 3 objects.",
        )
        expected = (
            "Tool: inspect_scene\n"
            "Status: OK\n"
            "Summary: Scene contains 3 objects."
        )
        self.assertEqual(result, expected)

    def test_edge_cases(self):
        """4. Verify formatting handles empty/None inputs safely."""
        # Empty plan
        plan_empty = format_plan_text_for_clipboard("", "", [])
        self.assertIn("Plan: Untitled Plan", plan_empty)
        self.assertIn("Status: unknown", plan_empty)

        # Tool with empty values
        tool_empty = format_tool_text_for_clipboard("", "", "")
        self.assertEqual(tool_empty, "Tool: unknown_tool\nStatus: UNKNOWN\nSummary:")

        # Unknown status
        unknown_status = format_plan_step_status("CUSTOM_STATUS")
        self.assertEqual(unknown_status["symbol"], "·")
        self.assertEqual(unknown_status["label"], "custom_status")


if __name__ == "__main__":
    unittest.main()
