"""Unit tests for the agy CLI provider. Pure Python: a fake Popen replaces the real CLI."""

import io
import json
import os
import queue
import threading
import time
import unittest
from unittest import mock

from agent import agy_cli_provider as agy
from agent.agy_cli_provider import AgyCliProvider, extract_clean_text, extract_tool_calls, normalize_model
from agent.context_builder import ProviderRequestContext
from agent.models import ChatMessage, ProviderCompleted, ProviderError, ProviderErrorType, Role, TextDelta
from core.config import Config, load_config


class _Stdout:
    """Blocking line iterator fed from a queue, like a real pipe."""

    def __init__(self):
        self.q = queue.Queue()

    def __iter__(self):
        return self

    def __next__(self):
        item = self.q.get()
        if item is None:
            raise StopIteration
        return item

    def close(self):
        self.q.put(None)


class _Stdin:
    def __init__(self, on_line):
        self.on_line = on_line
        self.lines = []

    def write(self, s):
        self.lines.append(s)
        self.on_line(s)

    def flush(self):
        pass

    def close(self):
        pass


class FakeAgy:
    """Mimics `agy`: emits init, then answers each user line with `reply`."""

    def __init__(self, reply="Merhaba", init=True, silent=False):
        self.stdout = _Stdout()
        self.reply = reply
        self.silent = silent
        self.stdin = _Stdin(self._on_user)
        self.pid = 4242
        self.killed = False
        if init:
            self.stdout.q.put(json.dumps({"event": "init"}) + "\n")

    def _on_user(self, line):
        if self.silent:
            return
        for piece in (self.reply[: len(self.reply) // 2], self.reply[len(self.reply) // 2:]):
            self.stdout.q.put(json.dumps({"event": "step_update", "step_update": {"text_delta": piece}}) + "\n")
        self.stdout.q.put(json.dumps({"event": "result", "result": {
            "response": self.reply, "status": "SUCCESS", "usage": {"output_tokens": 7}}}) + "\n")

    def poll(self):
        return 0 if self.killed else None

    def kill(self):
        self.killed = True
        self.stdout.q.put(None)


def _ctx(tools=(), images=None, text="selam"):
    return ProviderRequestContext(
        messages=[ChatMessage(role=Role.USER, content=text)],
        tools=list(tools), system_prompt="sys", images=images)


def _provider(fake, **kw):
    spawned = []

    def popen(cmd, **kwargs):
        spawned.append((cmd, kwargs))
        return fake

    p = AgyCliProvider(Config(provider="agy_cli", model="gemini-3.8-flash-low"), popen=popen, **kw)
    p.spawned = spawned
    return p


class AgyHelpers(unittest.TestCase):
    def test_normalize_model_falls_back(self):
        self.assertEqual(normalize_model("gpt-4o"), agy.DEFAULT_MODEL)
        self.assertEqual(normalize_model("gemini-3.1-pro-high"), "gemini-3.1-pro-high")

    def test_extract_tool_calls_fenced_and_raw(self):
        fenced = 'Tamam.\n```json\n{"tool_calls":[{"name":"create_primitive","arguments":{"kind":"cube"}}]}\n```'
        calls = extract_tool_calls(fenced)
        self.assertEqual([c.tool_name for c in calls], ["create_primitive"])
        self.assertEqual(calls[0].arguments, {"kind": "cube"})
        raw = extract_tool_calls('{"tool_calls":[{"name":"inspect_scene","arguments":{}}]}')
        self.assertEqual(raw[0].tool_name, "inspect_scene")
        self.assertEqual(extract_tool_calls("duz metin"), [])
        self.assertEqual(extract_tool_calls("```json\n{bozuk\n```"), [])

    def test_clean_text_strips_block(self):
        text = 'Once bakayim.\n```json\n{"tool_calls":[]}\n```\nSonra.'
        self.assertEqual(extract_clean_text(text, True), "Once bakayim.\nSonra.")
        self.assertEqual(extract_clean_text("hepsi metin", False), "hepsi metin")

    def test_resolve_command_env_and_missing(self):
        with mock.patch.dict(os.environ, {agy.ENV_AGY_PATH: ""}), mock.patch("shutil.which", return_value=None):
            self.assertIsNone(agy.resolve_agy_command())
        with mock.patch.dict(os.environ, {agy.ENV_AGY_PATH: ""}), mock.patch("shutil.which", return_value="C:/x/agy.exe"):
            self.assertEqual(agy.resolve_agy_command(), "C:/x/agy.exe")


class AgyStreaming(unittest.TestCase):
    def setUp(self):
        for patcher in (
            mock.patch.object(agy, "resolve_agy_command", return_value="agy"),
            mock.patch.object(agy.subprocess, "run"),  # never run a real taskkill against the fake pid
        ):
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_text_stream_streams_deltas_and_completes(self):
        fake = FakeAgy(reply="Merhaba dunya")
        p = _provider(fake)
        events = list(p.stream_chat(_ctx(), "t1"))
        self.assertEqual("".join(e.text for e in events if isinstance(e, TextDelta)), "Merhaba dunya")
        done = events[-1]
        self.assertIsInstance(done, ProviderCompleted)
        self.assertEqual(done.finish_reason, "stop")
        self.assertEqual(done.usage, {"output_tokens": 7})
        cmd = p.spawned[0][0]
        self.assertIn("stream-json", cmd)
        self.assertIn(agy.DEFAULT_MODEL, cmd)
        payload = json.loads(fake.stdin.lines[0])
        self.assertEqual(payload["event"], "user")
        self.assertIn("selam", payload["message"]["content"])
        p.close()

    def test_tool_calls_are_parsed_and_text_is_clean(self):
        reply = 'Kup ekliyorum.\n```json\n{"tool_calls":[{"name":"create_primitive","arguments":{"kind":"cube"}}]}\n```'
        p = _provider(FakeAgy(reply=reply))
        tools = [{"type": "function", "function": {"name": "create_primitive", "description": "d", "parameters": {"properties": {}}}}]
        events = list(p.stream_chat(_ctx(tools=tools), "t1"))
        self.assertEqual([e.text for e in events if isinstance(e, TextDelta)], ["Kup ekliyorum."])
        self.assertEqual(events[-1].finish_reason, "tool_calls")
        self.assertEqual(p.last_tool_calls[0].tool_name, "create_primitive")
        p.close()

    def test_process_is_reused_between_turns(self):
        fake = FakeAgy(reply="ok")
        p = _provider(fake)
        list(p.stream_chat(_ctx(), "t1"))
        list(p.stream_chat(_ctx(text="ikinci"), "t2"))
        self.assertEqual(len(p.spawned), 1)
        self.assertEqual(len(fake.stdin.lines), 2)
        p.close()

    def test_images_are_rejected_with_clear_error(self):
        p = _provider(FakeAgy())
        events = list(p.stream_chat(_ctx(images={"img1": b"png"}), "t1"))
        self.assertEqual(len(events), 1)
        self.assertIsInstance(events[0], ProviderError)
        self.assertEqual(events[0].type, ProviderErrorType.PROVIDER_UNSUPPORTED)
        self.assertEqual(p.spawned, [])

    def test_missing_agy_gives_configuration_error(self):
        with mock.patch.object(agy, "resolve_agy_command", return_value=None):
            p = _provider(FakeAgy())
            events = list(p.stream_chat(_ctx(), "t1"))
        self.assertEqual(events[0].type, ProviderErrorType.CONFIGURATION_ERROR)
        self.assertIn("agy CLI not found", events[0].message)
        self.assertIn(agy.ENV_AGY_PATH, events[0].message)

    def test_popen_oserror_is_reported(self):
        def boom(cmd, **kw):
            raise OSError("access denied")

        p = AgyCliProvider(Config(provider="agy_cli"), popen=boom)
        events = list(p.stream_chat(_ctx(), "t1"))
        self.assertEqual(events[0].type, ProviderErrorType.CONFIGURATION_ERROR)
        self.assertIn("access denied", events[0].message)

    def test_init_timeout(self):
        p = _provider(FakeAgy(init=False), init_timeout=0.3)
        events = list(p.stream_chat(_ctx(), "t1"))
        self.assertEqual(events[0].type, ProviderErrorType.TIMEOUT)

    def test_cancel_kills_process(self):
        fake = FakeAgy(silent=True)
        p = _provider(fake)
        cancel = threading.Event()
        threading.Timer(0.3, cancel.set).start()
        events = list(p.stream_chat(_ctx(), "t1", cancel_event=cancel))
        self.assertEqual(events[-1].type, ProviderErrorType.CANCELLED)
        self.assertTrue(fake.killed)

    def test_process_exit_before_answer(self):
        fake = FakeAgy(silent=True)
        p = _provider(fake)
        threading.Timer(0.2, fake.stdout.q.put, args=(None,)).start()
        events = list(p.stream_chat(_ctx(), "t1"))
        self.assertEqual(events[-1].type, ProviderErrorType.NETWORK_ERROR)

    def test_runs_off_the_calling_thread_contract(self):
        """stream_chat blocks on queue reads only; a waiting call must not hold the GIL-bound main thread."""
        fake = FakeAgy(silent=True)
        p = _provider(fake)
        cancel = threading.Event()
        out = []
        t = threading.Thread(target=lambda: out.extend(p.stream_chat(_ctx(), "t1", cancel_event=cancel)))
        t.start()
        started = time.monotonic()
        time.sleep(0.2)
        self.assertLess(time.monotonic() - started, 1.0)
        cancel.set()
        t.join(5)
        self.assertFalse(t.is_alive())


class AgyConfig(unittest.TestCase):
    def test_config_accepts_agy_cli(self):
        self.assertEqual(Config.from_dict({"provider": "agy_cli"}).provider, "agy_cli")
        self.assertEqual(Config.from_dict({"provider": "nope"}).provider, "openai_compatible")

    def test_env_override(self):
        with mock.patch.dict(os.environ, {"BLENDER_AI_PROVIDER": "agy_cli"}):
            cfg, _ = load_config(None)
        self.assertEqual(cfg.provider, "agy_cli")




class AgyLoginTests(unittest.TestCase):
    def setUp(self):
        import agent.agy_cli_provider as mod
        self.mod = mod
        self._orig = mod.resolve_agy_command
        mod.resolve_agy_command = lambda: "C:/bin/agy.exe"

    def tearDown(self):
        self.mod.resolve_agy_command = self._orig

    def test_launch_login_opens_own_window_without_blocking(self):
        calls = []
        ok, msg = self.mod.launch_login(popen=lambda *a, **k: calls.append((a, k)))
        self.assertTrue(ok)
        self.assertEqual(len(calls), 1)
        self.assertIn("C:/bin/agy.exe", calls[0][0][0])

    def test_launch_login_reports_missing_and_oserror(self):
        def boom(*a, **k):
            raise OSError("x")
        self.assertFalse(self.mod.launch_login(popen=boom)[0])
        self.mod.resolve_agy_command = lambda: None
        self.assertIn("not found", self.mod.launch_login(popen=boom)[1])

    def test_verify_login_states(self):
        import subprocess
        R = type("R", (), {})

        def run_ok(*a, **k):
            r = R(); r.returncode, r.stdout = 0, "ok"; return r

        def run_fail(*a, **k):
            r = R(); r.returncode, r.stdout = 1, ""; return r

        def run_timeout(*a, **k):
            raise subprocess.TimeoutExpired("agy", 1)
        self.assertEqual(self.mod.verify_login(run=run_ok)[0], "ok")
        self.assertEqual(self.mod.verify_login(run=run_fail)[0], "needs_login")
        self.assertEqual(self.mod.verify_login(run=run_timeout)[0], "needs_login")
        self.mod.resolve_agy_command = lambda: None
        self.assertEqual(self.mod.verify_login(run=run_ok)[0], "missing")

    def test_verify_uses_smallest_call(self):
        seen = []

        def run(cmd, **k):
            seen.append(cmd)
            r = type("R", (), {})(); r.returncode, r.stdout = 0, "ok"; return r
        self.mod.verify_login(run=run)
        self.assertEqual(seen[0][1:], ["--print", "ok", "--print-timeout", "30s"])

    def test_hint_mentions_google_signin(self):
        self.assertIn("Google", self.mod.LOGIN_HINT)


if __name__ == "__main__":
    unittest.main()
