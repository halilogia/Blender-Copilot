"""The runtime sends only the tools a conversation needs; enable_tools and keywords load the packs (pure Python)."""

import unittest

from agent.dispatcher import ToolDispatcher
from agent.mock_provider import MockProvider
from agent.models import ToolCall
from agent.runtime import AgentRuntime
from core.types import RiskLevel, ToolResult
from tools.base import BaseTool
from tools.read_only.enable_tools import EnableToolsTool
from tools.registry import ToolRegistry


def fake(name):
    cls = type("Fake_" + name, (BaseTool,), {
        "name": name, "description": name,
        "input_schema": {"type": "object", "properties": {}, "additionalProperties": False},
        "risk_level": RiskLevel.READ_ONLY,
        "execute": lambda self, adapter, **kwargs: ToolResult.ok(self.name, {}),
    })
    return cls()


def make_runtime():
    reg = ToolRegistry()
    for n in ("create_primitive", "camera_move", "render_animation", "rig_character", "export_gltf"):
        reg.register(fake(n))
    reg.register(EnableToolsTool())
    return AgentRuntime(provider=MockProvider(), dispatcher=ToolDispatcher(registry=reg, adapter=None))


def names(rt):
    return [t.name for t in rt._request_tools()]


class TestRuntimePacks(unittest.TestCase):
    def test_a_plain_modeling_request_gets_only_the_core(self):
        rt = make_runtime()
        self.assertEqual(names(rt), ["create_primitive", "enable_tools", "export_gltf"])

    def test_words_in_the_request_load_the_packs(self):
        rt = make_runtime()
        rt.submit_prompt("gün batımında 5 saniyelik bir MP4 çek")
        self.assertIn("camera_move", names(rt))
        self.assertNotIn("rig_character", names(rt))
        rt2 = make_runtime()
        rt2.submit_prompt("make a soldier walk")
        self.assertTrue({"camera_move", "rig_character"} <= set(names(rt2)))

    def test_enable_tools_loads_a_pack_for_the_rest_of_the_conversation(self):
        rt = make_runtime()
        res = rt._execute_and_verify(ToolCall(call_id="c1", tool_name="enable_tools", arguments={"packs": ["characters"]}))
        self.assertTrue(res.success, res.error)
        self.assertIn("rig_character", names(rt))
        self.assertNotIn("camera_move", names(rt))
        self.assertIn("animate_character", res.data["tools"])

    def test_enable_tools_refuses_unknown_packs(self):
        rt = make_runtime()
        for args in ({"packs": ["magic"]}, {"packs": []}):
            res = rt._execute_and_verify(ToolCall(call_id="c2", tool_name="enable_tools", arguments=args))
            self.assertFalse(res.success)
        self.assertEqual(rt.active_packs, set())

    def test_the_toolset_over_the_wire_is_much_smaller_without_packs(self):
        import json
        import tools.mutations as m
        import tools.read_only as ro
        from core.tool_packs import filter_tools
        import inspect

        everything = []
        for mod in (m, ro):
            for n in dir(mod):
                c = getattr(mod, n)
                if inspect.isclass(c) and issubclass(c, BaseTool) and c is not BaseTool:
                    everything.append(c())
        everything.append(EnableToolsTool())
        size = lambda ts: sum(len(json.dumps(t.to_schema())) for t in ts)  # noqa: E731
        core, full = size(filter_tools(everything, [])), size(everything)
        self.assertLess(core, full * 0.6, (core, full))


if __name__ == "__main__":
    unittest.main()
