"""Tool arguments from weak models: truncated, padded or comma-happy JSON is repaired; garbage still fails (pure Python)."""

import json
import unittest

from agent.models import ToolCallDelta
from agent.tool_call_accumulator import ToolCallAccumulator, ToolCallAccumulatorError, lenient_json_loads


class TestLenientJson(unittest.TestCase):
    def test_valid_json_is_untouched(self):
        self.assertEqual(lenient_json_loads('{"a": [1, {"b": 2}]}'), {"a": [1, {"b": 2}]})

    def test_repairable_cases(self):
        cases = {
            '{"a": 1} and then some words': {"a": 1},
            '{"a": [1, 2': {"a": [1, 2]},
            '{"a": {"b": "x"': {"a": {"b": "x"}},
            '{"a": 1,}': {"a": 1},
            '{"shots": [{"preset": "orbit", "duration": 3},]}': {"shots": [{"preset": "orbit", "duration": 3}]},
            '{"text": "half a sentence': {"text": "half a sentence"},
            '{"q": "say \\"hi\\"", "n": [1': {"q": 'say "hi"', "n": [1]},
            '{"follow": True, "x": None}': {"follow": True, "x": None},
            "{'preset': 'orbit', 'follow': False}": {"preset": "orbit", "follow": False},
            '{"shots": [{"follow": True, "preset": "orbit"': {"shots": [{"follow": True, "preset": "orbit"}]},
        }
        for raw, expected in cases.items():
            self.assertEqual(lenient_json_loads(raw), expected, raw)

    def test_garbage_still_fails(self):
        for raw in ('not json at all', '{"a": ', '', '{"a" 1}'):
            with self.assertRaises(json.JSONDecodeError):
                lenient_json_loads(raw)

    def test_accumulator_repairs_a_truncated_call(self):
        acc = ToolCallAccumulator()
        acc.feed_delta(ToolCallDelta(turn_id="t1", index=0, call_id="c1", tool_name_delta="render_shots", arguments_delta='{"filename": "film", "shots": [{"preset": "orbit"'))
        calls = acc.finalize()
        self.assertEqual(calls[0].arguments, {"filename": "film", "shots": [{"preset": "orbit"}]})

    def test_accumulator_still_reports_hopeless_json(self):
        acc = ToolCallAccumulator()
        acc.feed_delta(ToolCallDelta(turn_id="t1", index=0, call_id="c1", tool_name_delta="x", arguments_delta='{"a": '))
        with self.assertRaises(ToolCallAccumulatorError) as ctx:
            acc.finalize()
        self.assertEqual(ctx.exception.code, "MALFORMED_JSON")


if __name__ == "__main__":
    unittest.main()
