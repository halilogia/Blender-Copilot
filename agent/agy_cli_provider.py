"""Google Antigravity CLI (`agy`) provider: a persistent local subprocess speaking stream-json.

Ported from the Godot AI Sidebar `agy_cli_provider.gd`. No HTTP and no API key: the
user's own `agy` login does the work. Stdlib only, zero bpy.

Thread boundary: `stream_chat` runs on the AgentWorker thread, never on Blender's main
thread, so waiting for the CLI handshake (seconds) cannot freeze the UI. A small reader
thread turns the process's stdout into a queue so cancellation stays responsive.

Limits (documented in README): no image input (stream-json stdin carries text only) and
tool calls travel as a JSON block inside the model's text, parsed here.
"""

from __future__ import annotations

import json
import os
import queue
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from typing import Any, Dict, Iterator, List, Optional, Tuple

from agent.context_builder import ProviderRequestContext
from agent.models import (
    ProviderCompleted,
    ProviderError,
    ProviderErrorType,
    ProviderStreamEvent,
    Role,
    TextDelta,
    ToolCall,
)
from core.config import Config
from core.logging_utils import get_logger

_logger = get_logger("agy_cli")

OFFICIAL_MODELS: Tuple[str, ...] = (
    "gemini-3.8-flash-low",
    "gemini-3.8-flash-medium",
    "gemini-3.8-flash-high",
    "gemini-3.7-flash-low",
    "gemini-3.7-flash-medium",
    "gemini-3.7-flash-high",
    "claude-sonnet-4-6",
    "claude-opus-4-6-thinking",
    "gemini-3.6-flash-low",
    "gemini-3.6-flash-medium",
    "gemini-3.6-flash-high",
    "gemini-3.1-pro-low",
    "gemini-3.1-pro-high",
)
DEFAULT_MODEL = "gemini-3.8-flash-low"
ENV_AGY_PATH = "BLENDER_AI_AGY_PATH"
INIT_TIMEOUT_SECONDS = 90.0
_EOF = object()


def resolve_agy_command() -> Optional[str]:
    """Path of the agy executable (BLENDER_AI_AGY_PATH, then PATH) or None."""
    override = os.environ.get(ENV_AGY_PATH, "").strip()
    if override:
        return override if os.path.isfile(override) else shutil.which(override)
    return shutil.which("agy")


LOGIN_HINT = "Google sign-in may be pending: press 'Sign in with Google' in HUD Settings."
VERIFY_TIMEOUT_SECONDS = 45.0


def launch_login(popen=subprocess.Popen) -> Tuple[bool, str]:
    """Open agy in its own console window so the user can finish the Google sign-in in the browser.

    Non-blocking and credential-free: Blender never reads, logs or stores anything agy writes.
    """
    path = resolve_agy_command()
    if not path:
        return False, "agy CLI not found. Put it on PATH or set BLENDER_AI_AGY_PATH."
    try:
        if sys.platform == "win32":
            popen(["conhost.exe", path], creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0))
        else:
            popen([path], start_new_session=True)
    except OSError as exc:
        get_logger("agy_cli").warning("agy login window failed: %s", type(exc).__name__)
        return False, f"Could not open agy: {type(exc).__name__}."
    return True, "agy opened in its own window. Finish the Google sign-in in the browser."


def verify_login(run=subprocess.run) -> Tuple[str, str]:
    """Smallest possible call (`agy --print ok`). Returns (state, message); state is
    ok | needs_login | missing. Call from a worker thread. Output is never logged."""
    path = resolve_agy_command()
    if not path:
        return "missing", "agy CLI not found. Put it on PATH or set BLENDER_AI_AGY_PATH."
    try:
        res = run([path, "--print", "ok", "--print-timeout", "30s"], capture_output=True, text=True,
                  timeout=VERIFY_TIMEOUT_SECONDS, stdin=subprocess.DEVNULL)
    except subprocess.TimeoutExpired:
        return "needs_login", "Sign-in required (press 'Sign in with Google')."
    except OSError as exc:
        get_logger("agy_cli").warning("agy verify failed: %s", type(exc).__name__)
        return "missing", f"Could not run agy: {type(exc).__name__}."
    if res.returncode == 0 and (res.stdout or "").strip():
        return "ok", "Signed in."
    return "needs_login", "Sign-in required (press 'Sign in with Google')."


def normalize_model(model: str) -> str:
    """agy only accepts its own model ids; anything else falls back to the default."""
    return model if model in OFFICIAL_MODELS else DEFAULT_MODEL


def _tool_blob(text: str) -> Tuple[int, int, str]:
    """(start, end, json) of the tool-call block in a reply, or (-1, -1, "")."""
    start = text.find("```json")
    if start != -1:
        body = start + 7
        end = text.find("```", body)
        if end != -1:
            return start, end + 3, text[body:end].strip()
        return -1, -1, ""
    first = text.find('{"tool_calls"')
    if first == -1:
        first = text.find('{ "tool_calls"')
    last = text.rfind("}")
    if first != -1 and last > first:
        return first, last + 1, text[first:last + 1].strip()
    return -1, -1, ""


def extract_tool_calls(text: str) -> List[ToolCall]:
    """Find a {"tool_calls": [...]} object in a fenced ```json block or raw in the reply."""
    _, _, blob = _tool_blob(text or "")
    if not blob:
        return []
    try:
        data = json.loads(blob)
    except (ValueError, TypeError) as exc:
        _logger.debug("agy tool block is not JSON: %s", exc)
        return []
    calls: List[ToolCall] = []
    if isinstance(data, dict) and isinstance(data.get("tool_calls"), list):
        for item in data["tool_calls"]:
            if isinstance(item, dict) and item.get("name"):
                args = item.get("arguments")
                calls.append(ToolCall(
                    call_id=str(item.get("id") or f"call_{uuid.uuid4().hex[:8]}"),
                    tool_name=str(item["name"]),
                    arguments=args if isinstance(args, dict) else {},
                ))
    return calls


def extract_clean_text(text: str, has_tools: bool) -> str:
    """The user-facing text around a tool-call block (empty when the reply was only the block)."""
    if not has_tools:
        return text
    start, end, _ = _tool_blob(text)
    if start == -1:
        return ""
    return (text[:start].strip() + "\n" + text[end:].strip()).strip()


def format_prompt(context: ProviderRequestContext) -> str:
    """Flatten system prompt, tool schemas and conversation into one text message."""
    parts: List[str] = []
    if context.system_prompt:
        parts += ["=== SYSTEM DIRECTIVE ===", context.system_prompt, ""]
    if context.tools:
        parts += ["=== AVAILABLE BLENDER TOOLS ==="]
        for item in context.tools:
            fn = item.get("function", item)
            parts.append(f"- {fn.get('name', '')}: {fn.get('description', '')}")
            props = (fn.get("parameters") or {}).get("properties")
            if props:
                parts.append("  Parameters: " + json.dumps(props, ensure_ascii=False))
        parts += [
            "",
            "=== TOOL CALLING INSTRUCTIONS ===",
            "To run tools, answer ONLY with this JSON block:",
            '```json\n{"tool_calls": [{"name": "tool_name", "arguments": {"arg": "value"}}]}\n```',
            "If no tool is needed, answer with plain text for the user.",
            "",
        ]
    parts.append("=== CONVERSATION HISTORY ===")
    for msg in context.messages:
        role = msg.role.value if hasattr(msg.role, "value") else str(msg.role)
        if msg.role == Role.ASSISTANT and msg.tool_calls:
            calls = [{"name": c.tool_name, "arguments": c.arguments} for c in msg.tool_calls]
            parts.append(f"[ASSISTANT]: {msg.content or ''} {json.dumps({'tool_calls': calls}, ensure_ascii=False)}".strip())
        elif msg.role == Role.TOOL:
            parts.append(f"[TOOL RESULT {msg.name or ''}]: {msg.content or ''}")
        else:
            parts.append(f"[{role.upper()}]: {msg.content or ''}")
    return "\n".join(parts)


class AgyCliProvider:
    """Persistent `agy` subprocess; one request at a time (the worker is single threaded)."""

    supports_vision = False

    def __init__(self, config: Config, popen=subprocess.Popen, init_timeout: float = INIT_TIMEOUT_SECONDS):
        self.config = config
        self._popen = popen
        self.init_timeout = init_timeout
        self.last_tool_calls: List[ToolCall] = []
        self._proc = None
        self._model = ""
        self._events: "queue.Queue[Any]" = queue.Queue()
        self._reader: Optional[threading.Thread] = None
        self._ready = False
        self._lock = threading.Lock()

    # ------------------------------------------------------------------ process
    def _spawn(self, command: str, model: str) -> None:
        self.close()
        sandbox = os.path.join(tempfile.gettempdir(), "blender_copilot_agy")
        os.makedirs(sandbox, exist_ok=True)
        kwargs: Dict[str, Any] = {
            "stdin": subprocess.PIPE, "stdout": subprocess.PIPE, "stderr": subprocess.DEVNULL,
            "cwd": sandbox, "text": True, "encoding": "utf-8", "bufsize": 1,
        }
        if sys.platform == "win32":
            kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        self._proc = self._popen(
            [command, "--input-format", "stream-json", "--output-format", "stream-json", "--model", model],
            **kwargs,
        )
        self._model = model
        self._ready = False
        self._events = queue.Queue()
        proc, events = self._proc, self._events

        def read() -> None:
            try:
                for line in proc.stdout:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                    except ValueError:
                        continue
                    if isinstance(obj, dict):
                        events.put(obj)
            except (OSError, ValueError) as exc:
                _logger.debug("agy stdout closed: %s", exc)
            finally:
                events.put(_EOF)

        self._reader = threading.Thread(target=read, name="agy-reader", daemon=True)
        self._reader.start()

    def close(self) -> None:
        """Kill the CLI and its children (it may sit waiting for a Google sign-in)."""
        proc, self._proc = self._proc, None
        self._ready = False
        if proc is None:
            return
        try:
            if proc.poll() is None:
                if sys.platform == "win32":
                    subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                                   capture_output=True, check=False,
                                   creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                proc.kill()
        except OSError as exc:
            _logger.debug("agy kill failed (already gone?): %s", exc)
        for stream in (proc.stdin, proc.stdout):
            try:
                if stream:
                    stream.close()
            except OSError as exc:
                _logger.debug("agy pipe close failed: %s", exc)

    def _send(self, context: ProviderRequestContext, turn_id: str) -> bool:
        """Write the flattened prompt as one stream-json user event. False (and closed) on failure."""
        payload = json.dumps({"event": "user", "message": {"content": format_prompt(context)}},
                             ensure_ascii=False) + "\n"
        try:
            self._proc.stdin.write(payload)
            self._proc.stdin.flush()
        except (OSError, ValueError) as exc:
            _logger.warning("agy stdin write failed (turn %s): %s", turn_id, exc)
            self.close()
            return False
        return True

    def _alive(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    @staticmethod
    def _err(turn_id: str, kind: str, message: str, **details: Any) -> ProviderError:
        return ProviderError(turn_id=turn_id, type=kind, message=message, details=details or None)

    # ------------------------------------------------------------------ streaming
    def stream_chat(
        self,
        context: ProviderRequestContext,
        turn_id: str = "turn-1",
        cancel_event: Optional[threading.Event] = None,
        online_access: Optional[bool] = None,
    ) -> Iterator[ProviderStreamEvent]:
        self.last_tool_calls = []
        if getattr(context, "images", None):
            yield self._err(turn_id, ProviderErrorType.PROVIDER_UNSUPPORTED,
                            "The agy CLI provider cannot receive images. Use an OpenAI-compatible or "
                            "Anthropic provider for visual verification.", capability="multimodal")
            return
        command = resolve_agy_command()
        if not command:
            yield self._err(turn_id, ProviderErrorType.CONFIGURATION_ERROR,
                            f"agy CLI not found. Install the Google Antigravity CLI so `agy` is on PATH, "
                            f"or set {ENV_AGY_PATH} to its full path.")
            return
        if cancel_event and cancel_event.is_set():
            yield self._err(turn_id, ProviderErrorType.CANCELLED, "Request cancelled before start.")
            return

        with self._lock:
            model = normalize_model(self.config.model)
            if not self._alive() or self._model != model:
                try:
                    self._spawn(command, model)
                except OSError as exc:
                    yield self._err(turn_id, ProviderErrorType.CONFIGURATION_ERROR,
                                    f"Could not start agy ({command}): {exc}")
                    return
            has_tools = bool(context.tools)
            text = ""
            wrote = False
            deadline = time.monotonic() + self.init_timeout
            while True:
                if self._ready and not wrote:  # reused process: handshake already done
                    if not self._send(context, turn_id):
                        yield self._err(turn_id, ProviderErrorType.NETWORK_ERROR, "Could not write to agy.")
                        return
                    wrote = True
                if cancel_event and cancel_event.is_set():
                    self.close()
                    yield self._err(turn_id, ProviderErrorType.CANCELLED, "Stream cancelled by user.")
                    return
                try:
                    evt = self._events.get(timeout=0.1)
                except queue.Empty:
                    if not self._ready and time.monotonic() > deadline:
                        self.close()
                        yield self._err(turn_id, ProviderErrorType.TIMEOUT,
                                        "agy did not finish starting in time. " + LOGIN_HINT)
                        return
                    continue
                if evt is _EOF:
                    self.close()
                    yield self._err(turn_id, ProviderErrorType.NETWORK_ERROR,
                                    "agy exited before answering. " + LOGIN_HINT)
                    return
                kind = evt.get("event")
                if kind == "init":
                    self._ready = True
                if self._ready and not wrote:  # handshake just arrived
                    if not self._send(context, turn_id):
                        yield self._err(turn_id, ProviderErrorType.NETWORK_ERROR, "Could not write to agy.")
                        return
                    wrote = True
                if kind == "step_update" and wrote:
                    delta = (evt.get("step_update") or {}).get("text_delta")
                    if delta:
                        text += str(delta)
                        if not has_tools:
                            yield TextDelta(turn_id=turn_id, text=str(delta))
                elif kind == "result" and wrote:
                    res = evt.get("result") or {}
                    if res.get("status", "SUCCESS") != "SUCCESS":
                        yield self._err(turn_id, ProviderErrorType.INVALID_RESPONSE,
                                        f"agy ended the session with status {res.get('status')}.")
                        return
                    full = str(res.get("response") or text)
                    if not full.strip():
                        yield self._err(turn_id, ProviderErrorType.INVALID_RESPONSE,
                                        "agy returned an empty answer. " + LOGIN_HINT)
                        return
                    usage = res.get("usage") if isinstance(res.get("usage"), dict) else {}
                    calls = extract_tool_calls(full)
                    if has_tools:
                        clean = extract_clean_text(full, bool(calls))
                        if clean:
                            yield TextDelta(turn_id=turn_id, text=clean)
                    self.last_tool_calls = calls
                    yield ProviderCompleted(
                        turn_id=turn_id,
                        finish_reason="tool_calls" if calls else "stop",
                        usage={k: int(v) for k, v in usage.items() if isinstance(v, int)} or None,
                    )
                    return
