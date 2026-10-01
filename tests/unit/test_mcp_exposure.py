"""The MCP bridge is fail-closed: only tools listed in bridge/exposure_policy.py are visible to an outside agent (pure Python)."""

import importlib
import inspect
import pkgutil
import unittest

import tools
from bridge import exposure_policy as ep
from bridge.tool_host import RegistryToolHost
from core.types import RiskLevel, ToolResult
from tools.base import BaseTool
from tools.registry import ToolRegistry


def all_tool_classes():
    """Every BaseTool subclass in the tools package, instantiated: the real tool set without importing Blender."""
    found = {}
    for module in pkgutil.walk_packages(tools.__path__, "tools."):
        mod = importlib.import_module(module.name)
        for _, cls in inspect.getmembers(mod, inspect.isclass):
            if issubclass(cls, BaseTool) and cls is not BaseTool and cls.__module__ == module.name:
                tool = cls()
                found[tool.name] = tool
    return found


class Dummy(BaseTool):
    name = "brand_new_tool"
    description = "a tool somebody just registered"
    input_schema = {"type": "object", "properties": {}, "additionalProperties": False}
    risk_level = RiskLevel.LOW

    def execute(self, adapter, **kwargs):
        return ToolResult.ok(self.name, {})


class TestMcpExposure(unittest.TestCase):
    def test_every_registered_tool_is_classified_exactly_once(self):
        registered = all_tool_classes()
        self.assertGreaterEqual(len(registered), 50)
        self.assertEqual(ep.unclassified(registered), [], "classify new tools in bridge/exposure_policy.py")
        self.assertEqual(ep.overlapping(), [])

    def test_the_lists_name_only_tools_that_exist(self):
        registered = set(all_tool_classes())
        for label, names in ep.CATEGORIES.items():
            self.assertEqual(sorted(names - registered), [], f"{label} lists a tool that does not exist")

    def test_categories_agree_with_risk_levels(self):
        registered = all_tool_classes()
        for name in ep.READ_ONLY:
            self.assertEqual(registered[name].risk_level, RiskLevel.READ_ONLY, name)
        for name in ep.SAFE_MUTATION:
            self.assertEqual(registered[name].risk_level, RiskLevel.LOW, name)
        for name in ep.GATED_MUTATION:
            self.assertIn(registered[name].risk_level, (RiskLevel.MEDIUM, RiskLevel.HIGH, RiskLevel.CRITICAL), name)

    def test_internal_tools_are_never_exposed(self):
        policy = ep.ExposurePolicy.production()
        for name in ep.INTERNAL_ONLY:
            self.assertFalse(policy.is_exposed(name), name)
        self.assertTrue(policy.is_exposed("inspect_scene") and policy.is_exposed("delete_object"))

    def test_a_tool_nobody_classified_stays_invisible_and_uncallable(self):
        registry = ToolRegistry()
        registry.register(Dummy())
        host = RegistryToolHost(registry, adapter=None, submit=lambda fn, timeout=60.0: fn())
        self.assertEqual(host.list_tools(), [])
        self.assertFalse(host.has_tool("brand_new_tool"))

    def test_production_host_lists_the_classified_tools_only(self):
        registry = ToolRegistry()
        for tool in all_tool_classes().values():
            registry.register(tool)
        host = RegistryToolHost(registry, adapter=None, submit=lambda fn, timeout=60.0: fn())
        listed = {t["name"] for t in host.list_tools()}
        self.assertEqual(listed, set(ep.READ_ONLY | ep.SAFE_MUTATION | ep.GATED_MUTATION))
        self.assertNotIn("propose_plan", listed)
        self.assertNotIn("enable_tools", listed)


if __name__ == "__main__":
    unittest.main()
