"""Native Anthropic Messages API streaming provider (v1.1 A2).

Stdlib only, zero bpy. Thread boundary identical to OpenAI provider:
network/SSE/JSON on worker thread; image bytes pre-resolved on main thread.

Endpoint: POST {base_url}/messages  (base_url e.g. https://api.anthropic.com/v1)
Headers: x-api-key, anthropic-version: 2023-06-01, content-type: application/json
"""

from __future__ import annotations

import base64
import json
import threading
from dataclasses import dataclass
from typing import Any, Dict, Iterator, List, Mapping, Optional

from core.config import Config, is_network_allowed
from agent.context_builder import ImageResolutionError, ProviderRequestContext
from agent.http_client import (
    HttpClient,
    HttpConnectionError,
    HttpError,
    HttpTimeoutError,
    NetworkError,
)
from agent.models import (
    ProviderCompleted,
    ProviderError,
    ProviderErrorType,
    ProviderStreamEvent,
    Role,
    TextDelta,
    ToolCall,
    ToolCallDelta,
)
from agent.sse_parser import SSEParser, SSEParseError
from agent.tool_call_accumulator import ToolCallAccumulator, ToolCallAccumulatorError

ANTHROPIC_VERSION = "2023-06-01"
DEFAULT_MAX_TOKENS = 1024


class AnthropicUnsupportedError(ValueError):
    """Raised when multimodal input is sent to a model without vision support."""


class AnthropicRequestMapper:
    """Map internal ProviderRequestContext -> Anthropic Messages body."""

    @classmethod
    def map_request(
        cls,
        context: ProviderRequestContext,
        model: str,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        supports_multimodal: bool = True,
    ) -> Dict[str, Any]:
        images = getattr(context, "images", None) or {}
        if images and not supports_multimodal:
            raise AnthropicUnsupportedError(
                f"Model '{model}' does not support multimodal vision/image input."
            )
        messages: List[Dict[str, Any]] = []
        for msg in context.messages:
            if msg.role == Role.SYSTEM:
                continue
            mapped = cls.map_message(msg, images=images)
            if mapped is not None:
                messages.append(mapped)
        # Anthropic tool_use results arrive as user messages with tool_result blocks.
        # Our internal TOOL role maps to that shape (see map_message).
        tools = cls.map_tools(getattr(context, "tools", None) or [])
        body: Dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "system": context.system_prompt,
            "messages": messages,
            "stream": True,
        }
        if tools:
            body["tools"] = tools
        return body

    @classmethod
    def map_tools(cls, tools: Any) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        for t in tools or []:
            if not isinstance(t, dict):
                continue
            fn = t.get("function", t)
            name = fn.get("name") or t.get("name")
            desc = fn.get("description", "") or ""
            schema = fn.get("parameters") or fn.get("input_schema") or {"type": "object"}
            if name:
                out.append({"name": name, "description": desc, "input_schema": schema})
        return out

    @classmethod
    def map_message(
        cls, message: Any, images: Optional[Mapping[str, bytes]] = None
    ) -> Optional[Dict[str, Any]]:
        images_dict = images or {}
        role = message.role
        if role == Role.ASSISTANT:
            blocks: List[Dict[str, Any]] = []
            if message.content:
                blocks.append({"type": "text", "text": message.content})
            for tc in message.tool_calls or []:
                blocks.append({
                    "type": "tool_use",
                    "id": tc.call_id,
                    "name": tc.tool_name,
                    "input": tc.arguments or {},
                })
            if not blocks:
                return None
            return {"role": "assistant", "content": blocks}
        if role == Role.TOOL:
            # tool result -> user role with tool_result block
            result_text = message.content or ""
            block: Dict[str, Any] = {
                "type": "tool_result",
                "tool_use_id": message.tool_call_id,
                "content": result_text,
            }
            # Attach image accompanying capture_viewport result
            img_id = getattr(message, "image_id", None)
            if not img_id and getattr(message, "name", None) == "capture_viewport" and message.content:
                try:
                    d = json.loads(message.content)
                    if isinstance(d, dict):
                        img_id = d.get("image_id")
                except Exception:
                    img_id = None
            if img_id:
                if img_id not in images_dict:
                    raise ImageResolutionError(
                        image_id=img_id,
                        message=f"Image '{img_id}' referenced in tool message not found.",
                    )
                # Anthropic allows image blocks inside user content list
                return {
                    "role": "user",
                    "content": [
                        {"type": "tool_result", "tool_use_id": message.tool_call_id,
                         "content": result_text},
                        {"type": "image",
                         "source": {"type": "base64", "media_type": "image/png",
                                    "data": base64.b64encode(images_dict[img_id]).decode("ascii")}},
                    ],
                }
            _ = block
            return {"role": "user", "content": [block]}
        if role == Role.USER:
            img_id = getattr(message, "image_id", None)
            if img_id:
                if img_id not in images_dict:
                    raise ImageResolutionError(
                        image_id=img_id,
                        message=f"Image '{img_id}' referenced in USER message not found.",
                    )
                parts: List[Dict[str, Any]] = []
                if message.content:
                    parts.append({"type": "text", "text": message.content})
                parts.append({"type": "image", "source": {
                    "type": "base64", "media_type": "image/png",
                    "data": base64.b64encode(images_dict[img_id]).decode("ascii")}})
                return {"role": "user", "content": parts}
            return {"role": "user", "content": message.content or ""}
        return None


@dataclass
class _BlockState:
    index: int
    call_id: Optional[str] = None
    name: Optional[str] = None


class AnthropicCompatibleProvider:
    """Streaming provider for Anthropic Messages API."""

    def __init__(
        self,
        config: Config,
        http_client: Optional[HttpClient] = None,
        online_access: bool = True,
        supports_multimodal: bool = True,
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ):
        self.config = config
        self.supports_multimodal = (
            bool(config.supports_multimodal)
            if hasattr(config, "supports_multimodal") and config.supports_multimodal is not None
            else supports_multimodal
        )
        effective_timeout = getattr(config, "timeout_seconds", getattr(config, "timeout", 30.0))
        self.http_client = http_client or HttpClient(
            base_url=config.base_url, timeout=effective_timeout)
        self.online_access = online_access
        self.max_tokens = max_tokens
        self.accumulator = ToolCallAccumulator()
        self.last_tool_calls: List[ToolCall] = []

    def stream_chat(
        self,
        context: ProviderRequestContext,
        turn_id: str = "turn-1",
        cancel_event: Optional[threading.Event] = None,
        online_access: Optional[bool] = None,
    ) -> Iterator[ProviderStreamEvent]:
        eff_online = online_access if online_access is not None else self.online_access
        if not self.config or not getattr(self.config, "base_url", "").strip():
            yield ProviderError(turn_id=turn_id, type=ProviderErrorType.CONFIGURATION_ERROR,
                                message="AI provider is not configured. Set Base URL in Preferences.")
            return
        if not getattr(self.config, "model", "").strip():
            yield ProviderError(turn_id=turn_id, type=ProviderErrorType.CONFIGURATION_ERROR,
                                message="AI model is not configured. Set Model in Preferences.")
            return
        allowed, reason = is_network_allowed(self.config.base_url, eff_online)
        if not allowed:
            yield ProviderError(turn_id=turn_id, type=ProviderErrorType.NETWORK_ERROR,
                                message=f"Network access forbidden: {reason}")
            return
        if cancel_event and cancel_event.is_set():
            yield ProviderError(turn_id=turn_id, type=ProviderErrorType.CANCELLED,
                                message="Request cancelled before start.")
            return
        if bool(getattr(context, "images", None)) and not self.supports_multimodal:
            yield ProviderError(turn_id=turn_id, type=ProviderErrorType.PROVIDER_UNSUPPORTED,
                                message=f"Model '{self.config.model}' does not support multimodal inputs.",
                                details={"model": self.config.model, "capability": "multimodal"})
            return
        try:
            req = AnthropicRequestMapper.map_request(
                context, self.config.model, self.max_tokens, self.supports_multimodal)
        except AnthropicUnsupportedError as exc:
            yield ProviderError(turn_id=turn_id, type=ProviderErrorType.PROVIDER_UNSUPPORTED,
                                message=str(exc), details={"model": self.config.model})
            return
        except ImageResolutionError as exc:
            yield ProviderError(turn_id=turn_id, type=ProviderErrorType.IMAGE_NOT_FOUND,
                                message=str(exc), details={"image_id": exc.image_id})
            return
        payload = json.dumps(req, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        headers = {"Content-Type": "application/json", "Accept": "text/event-stream",
                   "anthropic-version": ANTHROPIC_VERSION}
        if self.config.api_key and self.config.api_key.strip():
            headers["x-api-key"] = self.config.api_key.strip()
        try:
            resp = self.http_client.post(endpoint="/messages", payload=payload,
                                          headers=headers, cancel_event=cancel_event,
                                          timeout=getattr(self.config, "timeout_seconds", 30.0))
        except HttpError as err:
            yield ProviderError(turn_id=turn_id,
                                type=self._map_status(err.status_code),
                                message=f"HTTP {err.status_code}: {err.message}",
                                details={"status_code": err.status_code, "body_snippet": err.body_snippet})
            return
        except HttpTimeoutError as err:
            yield ProviderError(turn_id=turn_id, type=ProviderErrorType.TIMEOUT, message=err.message)
            return
        except (HttpConnectionError, NetworkError) as err:
            yield ProviderError(turn_id=turn_id, type=ProviderErrorType.NETWORK_ERROR,
                                message=f"Cannot connect to Anthropic endpoint at {self.config.base_url}.",
                                details={"error": err.message})
            return
        except Exception as err:
            yield ProviderError(turn_id=turn_id, type=ProviderErrorType.NETWORK_ERROR,
                                message=f"Unexpected transport failure: {err}")
            return

        parser = SSEParser()
        self.accumulator.reset()
        self.last_tool_calls = []
        blocks: Dict[int, _BlockState] = {}
        stop_reason: Optional[str] = None
        usage: Optional[Dict[str, int]] = None
        done = False
        with resp:
            for raw in resp:
                if cancel_event and cancel_event.is_set():
                    yield ProviderError(turn_id=turn_id, type=ProviderErrorType.CANCELLED,
                                        message="Stream cancelled by user.")
                    return
                try:
                    payloads = parser.feed(raw)
                except SSEParseError as err:
                    yield ProviderError(turn_id=turn_id, type=ProviderErrorType.INVALID_RESPONSE,
                                        message=f"SSE parsing error: {err.message}")
                    return
                for p in payloads:
                    if p == "[DONE]":
                        done = True
                        break
                    try:
                        evt = json.loads(p)
                    except json.JSONDecodeError as exc:
                        yield ProviderError(turn_id=turn_id, type=ProviderErrorType.INVALID_RESPONSE,
                                            message=f"Malformed JSON in SSE payload: {exc}")
                        return
                    etype = evt.get("type", "")
                    if etype == "message_start":
                        msg = evt.get("message", {})
                        u = msg.get("usage")
                        if isinstance(u, dict):
                            usage = {k: int(v) for k, v in u.items() if isinstance(v, int)}
                    elif etype == "content_block_start":
                        idx = int(evt.get("index", 0))
                        cb = evt.get("content_block", {}) or {}
                        if cb.get("type") == "tool_use":
                            st = _BlockState(index=idx, call_id=cb.get("id"), name=cb.get("name"))
                            blocks[idx] = st
                            self.accumulator.feed_delta(ToolCallDelta(
                                turn_id=turn_id, index=idx, call_id=st.call_id,
                                tool_name_delta=st.name, arguments_delta=None))
                    elif etype == "content_block_delta":
                        idx = int(evt.get("index", 0))
                        delta = evt.get("delta", {}) or {}
                        dtype = delta.get("type", "")
                        if dtype == "text_delta":
                            txt = delta.get("text", "")
                            if isinstance(txt, str) and txt:
                                yield TextDelta(turn_id=turn_id, text=txt)
                        elif dtype == "input_json_delta":
                            frag = delta.get("partial_json", "")
                            st = blocks.get(idx)
                            self.accumulator.feed_delta(ToolCallDelta(
                                turn_id=turn_id, index=idx,
                                call_id=st.call_id if st else None,
                                tool_name_delta=None, arguments_delta=frag))
                            yield ToolCallDelta(turn_id=turn_id, index=idx,
                                                call_id=st.call_id if st else None,
                                                tool_name_delta=None, arguments_delta=frag)
                    elif etype in ("message_delta",):
                        delta = evt.get("delta", {}) or {}
                        if delta.get("stop_reason"):
                            stop_reason = delta["stop_reason"]
                        u = evt.get("usage")
                        if isinstance(u, dict):
                            usage = {k: int(v) for k, v in u.items() if isinstance(v, int)}
                    elif etype == "message_stop":
                        done = True
                        break
                if done:
                    break
        if cancel_event and cancel_event.is_set():
            yield ProviderError(turn_id=turn_id, type=ProviderErrorType.CANCELLED,
                                message="Stream cancelled by user.")
            return
        if self.accumulator._calls:
            try:
                self.last_tool_calls = self.accumulator.finalize()
            except ToolCallAccumulatorError as exc:
                yield ProviderError(turn_id=turn_id, type=ProviderErrorType.TOOL_CALL_PARSE_ERROR,
                                    message=exc.message)
                return
        finish = "tool_calls" if self.last_tool_calls else (stop_reason or "stop")
        yield ProviderCompleted(turn_id=turn_id, finish_reason=finish, usage=usage)

    @staticmethod
    def _map_status(code: int):
        if code in (401, 403):
            return ProviderErrorType.AUTH_ERROR
        if code == 429:
            return ProviderErrorType.RATE_LIMIT
        if 500 <= code <= 599:
            return "UNAVAILABLE"
        return ProviderErrorType.NETWORK_ERROR
