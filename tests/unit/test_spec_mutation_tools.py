"""Unit tests for procedural modeling tools (loft_profiles, place_on_socket, create_from_spec).

Zero Blender (bpy) dependencies. Pure Python.
"""

import unittest
from unittest.mock import MagicMock

from core.types import RiskLevel, ToolResult
from tools.registry import ToolRegistry
from agent.dispatcher import ToolDispatcher
from agent.models import ToolCall
from tools.mutations.loft_profiles import LoftProfilesTool
from tools.mutations.place_on_socket import PlaceOnSocketTool
from tools.mutations.create_from_spec import CreateFromSpecTool


class TestProceduralToolsContracts(unittest.TestCase):
    """Verify tool contract definitions, schemas, and risk classifications."""

    def test_loft_profiles_contract(self):
        tool = LoftProfilesTool()
        self.assertEqual(tool.name, "loft_profiles")
        self.assertEqual(tool.risk_level, RiskLevel.LOW)
        self.assertEqual(tool.input_schema["required"], ["profiles"])
        self.assertFalse(tool.input_schema["additionalProperties"])
        self.assertIn("profiles", tool.input_schema["properties"])
        self.assertIn("heights", tool.input_schema["properties"])
        self.assertIn("cap", tool.input_schema["properties"])
        self.assertIn("axis", tool.input_schema["properties"])

        schema = tool.to_schema()
        self.assertEqual(schema["name"], "loft_profiles")
        self.assertEqual(schema["risk_level"], "LOW")

    def test_place_on_socket_contract(self):
        tool = PlaceOnSocketTool()
        self.assertEqual(tool.name, "place_on_socket")
        self.assertEqual(tool.risk_level, RiskLevel.LOW)
        self.assertEqual(tool.input_schema["required"], ["object_name", "target_object"])
        self.assertFalse(tool.input_schema["additionalProperties"])
        self.assertIn("socket_name", tool.input_schema["properties"])
        self.assertIn("socket_location", tool.input_schema["properties"])
        self.assertIn("parent", tool.input_schema["properties"])

        schema = tool.to_schema()
        self.assertEqual(schema["name"], "place_on_socket")
        self.assertEqual(schema["risk_level"], "LOW")

    def test_create_from_spec_contract(self):
        tool = CreateFromSpecTool()
        self.assertEqual(tool.name, "create_from_spec")
        self.assertEqual(tool.risk_level, RiskLevel.LOW)
        self.assertEqual(tool.input_schema["required"], ["spec"])
        self.assertFalse(tool.input_schema["additionalProperties"])
        self.assertIn("spec", tool.input_schema["properties"])
        self.assertIn("name", tool.input_schema["properties"])

        schema = tool.to_schema()
        self.assertEqual(schema["name"], "create_from_spec")
        self.assertEqual(schema["risk_level"], "LOW")


class TestProceduralToolsDispatcher(unittest.TestCase):
    """Verify ToolDispatcher validation, argument checks, and mock adapter delegation."""

    def setUp(self):
        self.registry = ToolRegistry()
        self.registry.register(LoftProfilesTool())
        self.registry.register(PlaceOnSocketTool())
        self.registry.register(CreateFromSpecTool())

        self.mock_adapter = MagicMock()
        self.dispatcher = ToolDispatcher(registry=self.registry, adapter=self.mock_adapter)

    def test_loft_profiles_dispatch(self):
        self.mock_adapter.loft_profiles.return_value = ToolResult.ok(
            "loft_profiles",
            {"created": True, "object_name": "Bottle", "profile_count": 3},
        )

        tc = ToolCall(
            call_id="call_loft_1",
            tool_name="loft_profiles",
            arguments={
                "profiles": [
                    [[-1.0, -1.0, 0.0], [1.0, -1.0, 0.0], [1.0, 1.0, 0.0], [-1.0, 1.0, 0.0]],
                    [[-0.5, -0.5, 1.0], [0.5, -0.5, 1.0], [0.5, 0.5, 1.0], [-0.5, 0.5, 1.0]],
                ],
                "name": "Bottle",
            },
        )
        res = self.dispatcher.dispatch(tc)
        self.assertTrue(res.success)
        self.assertEqual(res.data["object_name"], "Bottle")
        self.mock_adapter.loft_profiles.assert_called_once()

    def test_place_on_socket_dispatch(self):
        self.mock_adapter.place_on_socket.return_value = ToolResult.ok(
            "place_on_socket",
            {"object_name": "Wheel_FL", "target_object": "Chassis", "socket_name": "socket_wheel_fl"},
        )

        tc = ToolCall(
            call_id="call_sock_1",
            tool_name="place_on_socket",
            arguments={
                "object_name": "Wheel_FL",
                "target_object": "Chassis",
                "socket_name": "socket_wheel_fl",
            },
        )
        res = self.dispatcher.dispatch(tc)
        self.assertTrue(res.success)
        self.assertEqual(res.data["target_object"], "Chassis")
        self.mock_adapter.place_on_socket.assert_called_once()

    def test_create_from_spec_dispatch(self):
        self.mock_adapter.create_from_spec.return_value = ToolResult.ok(
            "create_from_spec",
            {"asset_id": "scout_01", "part_count": 8, "root_object": "scout_01_Chassis_Main"},
        )

        spec_data = {
            "asset_id": "scout_01",
            "family": "vehicle",
            "recipe": "offroad_scout",
            "dimensions": {"length": 3.8, "width": 1.9, "height": 1.7},
        }

        tc = ToolCall(
            call_id="call_spec_1",
            tool_name="create_from_spec",
            arguments={"spec": spec_data},
        )
        res = self.dispatcher.dispatch(tc)
        self.assertTrue(res.success)
        self.assertEqual(res.data["asset_id"], "scout_01")
        self.mock_adapter.create_from_spec.assert_called_once()


if __name__ == "__main__":
    unittest.main()
