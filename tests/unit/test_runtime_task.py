"""A chat message starts a task in the ledger; the panel asks the runtime about it (pure Python, no Blender)."""

import unittest

from agent.dispatcher import ToolDispatcher
from agent.mock_provider import MockProvider
from agent.runtime import AgentRuntime
from tools.registry import ToolRegistry


class FakeAdapter:
    def __init__(self):
        self.begun = []
        self.steps = 3

    def task_begin(self, label=""):
        self.begun.append(label)

    def task_open_steps(self):
        return self.steps

    def task_peek(self):
        return {"changes": ["+ Crate (MESH)"], "empty": False}

    def task_undo(self):
        return {"rolled_back": True, "undo_steps_done": 3}


def make(adapter):
    return AgentRuntime(provider=MockProvider(), dispatcher=ToolDispatcher(registry=ToolRegistry(), adapter=adapter))


class TestRuntimeTask(unittest.TestCase):
    def test_a_prompt_begins_a_task_with_its_text_as_label(self):
        adapter = FakeAdapter()
        rt = make(adapter)
        rt.submit_prompt("build a crate " + "x" * 200)
        self.assertEqual(len(adapter.begun), 1)
        self.assertTrue(adapter.begun[0].startswith("build a crate") and len(adapter.begun[0]) <= 60)

    def test_panel_questions_go_through_the_runtime(self):
        rt = make(FakeAdapter())
        self.assertEqual(rt.task_open_steps(), 3)
        self.assertEqual(rt.task_changes()["changes"], ["+ Crate (MESH)"])
        self.assertTrue(rt.task_undo()["rolled_back"])

    def test_no_ledger_is_harmless(self):
        rt = make(None)
        rt.submit_prompt("hello")
        self.assertEqual(rt.task_open_steps(), 0)
        self.assertTrue(rt.task_changes()["empty"])
        self.assertFalse(rt.task_undo()["rolled_back"])


if __name__ == "__main__":
    unittest.main()
