"""A model may send several tool calls in one message. If one of them needs approval the batch stops, and the calls after
it must still get a result, or strict providers reject the next request ("tool results are missing").
Pure Python, no Blender."""

import json
import unittest

from agent.dispatcher import ToolDispatcher
from agent.mock_provider import MockProvider
from agent.models import ChatMessage, Role, ToolCall
from agent.runtime import AgentRuntime
from tools.registry import ToolRegistry


def make_runtime():
    return AgentRuntime(provider=MockProvider(), dispatcher=ToolDispatcher(registry=ToolRegistry(), adapter=None))


def batch(runtime, ids, answered):
    runtime.conversation.add_message(ChatMessage(role=Role.USER, content="do three things"))
    runtime.conversation.add_message(ChatMessage(
        role=Role.ASSISTANT, content=None,
        tool_calls=[ToolCall(call_id=i, tool_name="delete_object", arguments={"name": i}) for i in ids]))
    for i in answered:
        runtime.conversation.add_message(ChatMessage(role=Role.TOOL, content="{}", tool_call_id=i, name="delete_object"))


class TestToolBatches(unittest.TestCase):
    def test_calls_after_the_gated_one_get_a_not_executed_result(self):
        rt = make_runtime()
        batch(rt, ["a", "b", "c"], answered=["a"])
        added = rt._fill_missing_tool_results("stopped for approval")
        self.assertEqual(added, 2)
        tool_msgs = [m for m in rt.conversation.messages if m.role == Role.TOOL]
        self.assertEqual({m.tool_call_id for m in tool_msgs}, {"a", "b", "c"})
        skipped = [json.loads(m.content) for m in tool_msgs if m.tool_call_id in ("b", "c")]
        self.assertTrue(all(s["type"] == "NOT_EXECUTED" and s["error"] == "stopped for approval" for s in skipped))
        rt.conversation.validate_sequence()

    def test_nothing_is_added_when_every_call_was_answered(self):
        rt = make_runtime()
        batch(rt, ["a", "b"], answered=["a", "b"])
        self.assertEqual(rt._fill_missing_tool_results("x"), 0)
        rt.conversation.validate_sequence()

    def test_only_the_last_assistant_message_is_considered(self):
        rt = make_runtime()
        batch(rt, ["old"], answered=["old"])
        rt.conversation.add_message(ChatMessage(role=Role.ASSISTANT, content="done with that"))
        rt.conversation.add_message(ChatMessage(role=Role.USER, content="next"))
        batch_ids = ["n1", "n2"]
        rt.conversation.add_message(ChatMessage(
            role=Role.ASSISTANT, content=None,
            tool_calls=[ToolCall(call_id=i, tool_name="delete_object", arguments={}) for i in batch_ids]))
        self.assertEqual(rt._fill_missing_tool_results("x"), 2)

    def test_no_tool_calls_means_nothing_to_do(self):
        rt = make_runtime()
        rt.conversation.add_message(ChatMessage(role=Role.USER, content="hi"))
        self.assertEqual(rt._fill_missing_tool_results("x"), 0)


if __name__ == "__main__":
    unittest.main()
