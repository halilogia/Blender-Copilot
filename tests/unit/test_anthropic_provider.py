"""Unit tests for Anthropic native provider (v1.1 A2). Pure Python, local HTTP stub."""

import http.server
import json
import socket
import threading
import unittest
import urllib.parse

from core.config import Config
from agent.anthropic_provider import (
    AnthropicCompatibleProvider,
    AnthropicRequestMapper,
    AnthropicUnsupportedError,
)
from agent.context_builder import ContextBuilder, ProviderRequestContext
from agent.models import ChatMessage, Conversation, ProviderCompleted, ProviderError, Role
from tools.read_only.inspect_scene import InspectSceneTool


def _free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


class Handler(http.server.BaseHTTPRequestHandler):
    mode = "text"
    last_headers = None
    last_body = None

    def log_message(self, *a):
        pass

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(n) if n else b""
        Handler.last_headers = dict(self.headers)
        try:
            Handler.last_body = json.loads(raw.decode("utf-8")) if raw else None
        except Exception:
            Handler.last_body = None
        if self.path.endswith("/messages"):
            if Handler.mode == "text":
                chunks = [
                    'event: message_start\ndata: {"type":"message_start","message":{"id":"m1","usage":{"input_tokens":3}}}\n\n',
                    'event: content_block_delta\ndata: {"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":"hello"}}\n\n',
                    'event: message_delta\ndata: {"type":"message_delta","delta":{"stop_reason":"end_turn"},"usage":{"output_tokens":2}}\n\n',
                    'event: message_stop\ndata: {"type":"message_stop"}\n\n',
                ]
            else:
                chunks = [
                    'event: message_start\ndata: {"type":"message_start","message":{"id":"m1"}}\n\n',
                    'event: content_block_start\ndata: {"type":"content_block_start","index":0,"content_block":{"type":"tool_use","id":"toolu_1","name":"inspect_scene"}}\n\n',
                    'event: content_block_delta\ndata: {"type":"content_block_delta","index":0,"delta":{"type":"input_json_delta","partial_json":"{\\"detail\\":"}}\n\n',
                    'event: content_block_delta\ndata: {"type":"content_block_delta","index":0,"delta":{"type":"input_json_delta","partial_json":"\\"full\\"}"}}\n\n',
                    'event: message_delta\ndata: {"type":"message_delta","delta":{"stop_reason":"tool_use"}}\n\n',
                    'event: message_stop\ndata: {"type":"message_stop"}\n\n',
                ]
            body = "".join(chunks).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.end_headers()


class TestAnthropicMapper(unittest.TestCase):
    def test_system_separate_and_tool_shape(self):
        conv = Conversation([ChatMessage(role=Role.USER, content="hi")])
        ctx = ContextBuilder.build(conversation=conv, tools=[InspectSceneTool()])
        body = AnthropicRequestMapper.map_request(ctx, model="claude-x")
        self.assertEqual(body["model"], "claude-x")
        self.assertIn("system", body)
        self.assertTrue(all(m["role"] != "system" for m in body["messages"]))
        self.assertEqual(body["tools"][0]["name"], "inspect_scene")
        self.assertIn("input_schema", body["tools"][0])

    def test_multimodal_gate(self):
        conv = Conversation([ChatMessage(role=Role.USER, content="v", image_id="img_x")])
        ctx = ProviderRequestContext(messages=list(conv.messages), tools=[], system_prompt="s",
                                     images={"img_x": b"PNGDATA"})
        with self.assertRaises(AnthropicUnsupportedError):
            AnthropicRequestMapper.map_request(ctx, model="m", supports_multimodal=False)
        body = AnthropicRequestMapper.map_request(ctx, model="m", supports_multimodal=True)
        self.assertEqual(body["messages"][0]["content"][1]["type"], "image")

    def test_image_bytes_not_leaked_as_raw(self):
        conv = Conversation([ChatMessage(role=Role.USER, content="v", image_id="i1")])
        ctx = ProviderRequestContext(messages=list(conv.messages), tools=[], system_prompt="s",
                                     images={"i1": b"\x89PNG"})
        body = AnthropicRequestMapper.map_request(ctx, model="m")
        blob = json.dumps(body)
        self.assertNotIn("PNGDATA", blob)


class TestAnthropicStream(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.port = _free_port()
        cls.server = http.server.HTTPServer(("127.0.0.1", cls.port), Handler)
        cls.t = threading.Thread(target=cls.server.serve_forever, kwargs={"poll_interval": 0.01})
        cls.t.daemon = True
        cls.t.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.t.join(timeout=2)

    def _provider(self):
        cfg = Config(base_url=f"http://127.0.0.1:{self.port}/v1", model="claude-x", api_key="k")
        return AnthropicCompatibleProvider(config=cfg)

    def test_text_stream(self):
        Handler.mode = "text"
        p = self._provider()
        conv = Conversation([ChatMessage(role=Role.USER, content="hi")])
        ctx = ContextBuilder.build(conversation=conv)
        events = list(p.stream_chat(ctx, turn_id="t1"))
        self.assertTrue(any(e.__class__.__name__ == "TextDelta" for e in events))
        self.assertIsInstance(events[-1], ProviderCompleted)
        low = {k.lower(): v for k, v in (Handler.last_headers or {}).items()}
        self.assertEqual(low.get("anthropic-version"), "2023-06-01")
        self.assertEqual(low.get("x-api-key"), "k")
        self.assertNotIn("x-api-key", json.dumps(Handler.last_body))

    def test_tool_use_stream(self):
        Handler.mode = "tools"
        p = self._provider()
        conv = Conversation([ChatMessage(role=Role.USER, content="inspect")])
        ctx = ContextBuilder.build(conversation=conv, tools=[InspectSceneTool()])
        events = list(p.stream_chat(ctx, turn_id="t2"))
        self.assertTrue(p.last_tool_calls)
        self.assertEqual(p.last_tool_calls[0].tool_name, "inspect_scene")
        self.assertEqual(p.last_tool_calls[0].arguments, {"detail": "full"})
        self.assertEqual(events[-1].finish_reason, "tool_calls")

    def test_unsupported_gate(self):
        p = self._provider()
        p.supports_multimodal = False
        conv = Conversation([ChatMessage(role=Role.USER, content="v", image_id="i")])
        ctx = ProviderRequestContext(messages=list(conv.messages), tools=[], system_prompt="s",
                                     images={"i": b"xx"})
        events = list(p.stream_chat(ctx, turn_id="t3"))
        self.assertIsInstance(events[0], ProviderError)
        self.assertEqual(events[0].type, "PROVIDER_UNSUPPORTED")


if __name__ == "__main__":
    unittest.main()
