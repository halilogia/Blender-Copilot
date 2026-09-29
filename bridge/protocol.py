"""MCP protocol handling for the Blender Copilot bridge.

Pure Python, zero Blender dependencies. Speaks the MCP 2026-07-28 specification (stateless requests,
``server/discover``, ``_meta`` protocol version, ``resultType``, cacheable ``tools/list``,
``structuredContent``, HTTP header checks) and still answers the older ``initialize`` handshake so
current and older clients both work.
"""

import json
import re
from typing import Any, Dict, Optional

SERVER_NAME = "blender-copilot"
DEFAULT_PROTOCOL_VERSION = "2025-06-18"
SUPPORTED_VERSIONS = ["2026-07-28", "2025-11-25", "2025-06-18", "2025-03-26"]
META_VERSION = "io.modelcontextprotocol/protocolVersion"
META_SERVER_INFO = "io.modelcontextprotocol/serverInfo"
TOOLS_LIST_TTL_MS = 300000

ERR_PARSE = -32700
ERR_INVALID_REQUEST = -32600
ERR_METHOD_NOT_FOUND = -32601
ERR_INVALID_PARAMS = -32602
ERR_HEADER_MISMATCH = -32020
ERR_UNSUPPORTED_VERSION = -32022

_ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def scrub_value(value: Any) -> Any:
    """Strip ANSI colour sequences and control characters from every string (keeps \\n \\r \\t)."""
    if isinstance(value, str):
        return _CONTROL.sub("", _ANSI.sub("", value))
    if isinstance(value, list):
        return [scrub_value(v) for v in value]
    if isinstance(value, dict):
        return {k: scrub_value(v) for k, v in value.items()}
    return value


def error_reply(msg_id: Any, code: int, message: str, data: Any = None) -> Dict[str, Any]:
    err: Dict[str, Any] = {"code": code, "message": message}
    if data is not None:
        err["data"] = data
    return {"jsonrpc": "2.0", "id": msg_id, "error": err}


def result_reply(msg_id: Any, result: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(result)
    out.setdefault("resultType", "complete")
    meta = dict(out.get("_meta") or {})
    meta[META_SERVER_INFO] = {"name": SERVER_NAME}
    out["_meta"] = meta
    return {"jsonrpc": "2.0", "id": msg_id, "result": out}


def unsupported_version_reply(msg_id: Any, requested: str) -> Dict[str, Any]:
    return error_reply(
        msg_id,
        ERR_UNSUPPORTED_VERSION,
        f"Unsupported protocol version: {requested}",
        {"supported": SUPPORTED_VERSIONS, "requested": requested},
    )


def normalize_id(msg_id: Any) -> Any:
    if isinstance(msg_id, float) and msg_id.is_integer():
        return int(msg_id)
    return msg_id


def validate_headers(message: Any, headers: Dict[str, str]) -> Optional[Dict[str, Any]]:
    """HTTP headers must agree with the body. Missing headers are fine (older clients omit them)."""
    if not isinstance(message, dict):
        return None
    msg_id = normalize_id(message.get("id"))
    method = str(message.get("method", ""))
    version = headers.get("mcp-protocol-version", "")
    if version and version not in SUPPORTED_VERSIONS:
        return unsupported_version_reply(msg_id, version)
    h_method = headers.get("mcp-method", "")
    if h_method and h_method != method:
        return error_reply(msg_id, ERR_HEADER_MISMATCH,
                           f"HeaderMismatch: Mcp-Method '{h_method}' does not match the request method '{method}'")
    h_name = headers.get("mcp-name", "")
    if h_name and method == "tools/call":
        params = message.get("params") if isinstance(message.get("params"), dict) else {}
        if h_name != str(params.get("name", "")):
            return error_reply(msg_id, ERR_HEADER_MISMATCH,
                               f"HeaderMismatch: Mcp-Name '{h_name}' does not match the tool name '{params.get('name', '')}'")
    return None


def to_call_result(result: Dict[str, Any]) -> Dict[str, Any]:
    """Tool result dict -> MCP tools/call result. A base64 PNG becomes an ``image`` content block."""
    shown = scrub_value(json.loads(json.dumps(result, default=str)))
    content = []
    data = shown.get("data")
    if isinstance(data, dict):
        b64 = data.get("image_base64") or data.get("base64")
        if isinstance(b64, str) and b64:
            content.append({"type": "image", "data": b64, "mimeType": "image/png"})
            data.pop("image_base64", None)
            data.pop("base64", None)
    content.insert(0, {"type": "text", "text": json.dumps(shown, ensure_ascii=False)})
    return {"content": content, "structuredContent": shown, "isError": shown.get("success") is not True}


class McpProtocol:
    """Routes one JSON-RPC message. ``host`` provides list_tools(), has_tool(name), call_tool(name, args)."""

    def __init__(self, host: Any, server_version: str = "0", instructions: str = ""):
        self.host = host
        self.server_version = server_version
        self.instructions = instructions

    def handle(self, message: Any) -> Optional[Dict[str, Any]]:
        """Return the JSON-RPC reply, or None for notifications (HTTP 202)."""
        if not isinstance(message, dict):
            return error_reply(None, ERR_INVALID_REQUEST, "Invalid Request: expected a single JSON-RPC object")
        msg_id = normalize_id(message.get("id"))
        method = str(message.get("method", ""))
        if message.get("jsonrpc") != "2.0" or not method:
            return error_reply(msg_id, ERR_INVALID_REQUEST, "Invalid Request")
        if "id" not in message:
            return None
        params = message.get("params") if isinstance(message.get("params"), dict) else {}
        meta = params.get("_meta") if isinstance(params.get("_meta"), dict) else {}
        meta_version = str(meta.get(META_VERSION, ""))
        if meta_version and meta_version not in SUPPORTED_VERSIONS:
            return unsupported_version_reply(msg_id, meta_version)
        info = {"name": SERVER_NAME, "version": self.server_version}
        caps = {"tools": {"listChanged": False}}
        if method == "initialize":
            requested = str(params.get("protocolVersion", ""))
            negotiated = requested if requested in SUPPORTED_VERSIONS else DEFAULT_PROTOCOL_VERSION
            return result_reply(msg_id, {"protocolVersion": negotiated, "capabilities": caps,
                                         "serverInfo": info, "instructions": self.instructions})
        if method == "server/discover":
            return result_reply(msg_id, {"supportedVersions": SUPPORTED_VERSIONS, "capabilities": caps,
                                         "serverInfo": info, "instructions": self.instructions})
        if method == "ping":
            return result_reply(msg_id, {})
        if method == "tools/list":
            return result_reply(msg_id, {"tools": self.host.list_tools(), "ttlMs": TOOLS_LIST_TTL_MS, "cacheScope": "private"})
        if method == "tools/call":
            name = str(params.get("name", ""))
            if not self.host.has_tool(name):
                return error_reply(msg_id, ERR_INVALID_PARAMS, f"Unknown or not exposed tool: {name}")
            arguments = params.get("arguments") if isinstance(params.get("arguments"), dict) else {}
            return result_reply(msg_id, to_call_result(self.host.call_tool(name, arguments)))
        return error_reply(msg_id, ERR_METHOD_NOT_FOUND, f"Method not found: {method}")
