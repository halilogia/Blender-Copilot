"""Loopback HTTP endpoint for the MCP bridge (POST /mcp), stdlib only.

Security: binds 127.0.0.1 only, requires ``Authorization: Bearer <token>`` (constant-time compare),
rejects any request that carries an ``Origin`` header (browsers), accepts only POST, caps the body size.
Zero Blender dependencies.
"""

import hmac
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Optional

from bridge import protocol

MAX_BODY_BYTES = 4 * 1024 * 1024


class BridgeServer:
    def __init__(self, mcp: protocol.McpProtocol, token: str, port: int, host: str = "127.0.0.1"):
        if not token:
            raise ValueError("a non-empty token is required")
        self.mcp = mcp
        self.token = token
        self.port = port
        self.host = host
        self._httpd: Optional[ThreadingHTTPServer] = None
        self._thread: Optional[threading.Thread] = None

    def endpoint(self) -> str:
        return f"http://{self.host}:{self.port}/mcp"

    def claude_add_command(self) -> str:
        return (f'claude mcp add --transport http blender {self.endpoint()} '
                f'--header "Authorization: Bearer {self.token}"')

    def is_running(self) -> bool:
        return self._httpd is not None

    def start(self) -> int:
        """Start listening (port 0 picks a free port). Returns the bound port."""
        outer = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, fmt: str, *args: Any) -> None:  # keep Blender's console quiet
                return

            def _send(self, status: int, body: Any = None, extra: Optional[dict] = None) -> None:
                raw = b"" if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8")
                self.send_response(status)
                if raw:
                    self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(raw)))
                for k, v in (extra or {}).items():
                    self.send_header(k, v)
                self.send_header("Connection", "close")
                self.end_headers()
                if raw:
                    self.wfile.write(raw)
                self.close_connection = True

            def do_GET(self) -> None:
                self._send(405, {"error": "Use POST /mcp"}, {"Allow": "POST"})

            do_PUT = do_DELETE = do_PATCH = do_GET

            def do_POST(self) -> None:
                if self.path.split("?")[0] != "/mcp":
                    return self._send(404, {"error": "Not found; the MCP endpoint is /mcp"})
                headers = {k.lower(): v for k, v in self.headers.items()}
                if headers.get("origin"):
                    return self._send(403, {"error": "Browser-origin requests are not allowed"})
                supplied = headers.get("authorization", "")
                if not hmac.compare_digest(supplied.encode("utf-8"), f"Bearer {outer.token}".encode("utf-8")):
                    return self._send(401, {"error": "Missing or invalid bearer token"})
                if "chunked" in headers.get("transfer-encoding", "").lower():
                    return self._send(411, {"error": "Chunked bodies are not supported; send Content-Length"})
                try:
                    length = int(headers.get("content-length", "0"))
                except ValueError:
                    length = -1
                if length < 0 or length > MAX_BODY_BYTES:
                    return self._send(413, {"error": "Body too large or invalid Content-Length"})
                raw = self.rfile.read(length) if length else b""
                try:
                    message = json.loads(raw.decode("utf-8"))
                except (ValueError, UnicodeDecodeError):
                    return self._send(400, protocol.error_reply(None, protocol.ERR_PARSE, "Parse error"))
                header_error = protocol.validate_headers(message, headers)
                if header_error is not None:
                    return self._send(400, header_error)
                try:
                    reply = outer.mcp.handle(message)
                except Exception as exc:  # noqa: BLE001 - never crash the handler thread
                    reply = protocol.error_reply(protocol.normalize_id(message.get("id") if isinstance(message, dict) else None),
                                                 -32603, f"Internal error: {type(exc).__name__}: {exc}")
                if reply is None:
                    return self._send(202)
                self._send(200, reply)

        self._httpd = ThreadingHTTPServer((self.host, self.port), Handler)
        self._httpd.daemon_threads = True
        self.port = self._httpd.server_address[1]
        self._thread = threading.Thread(target=self._httpd.serve_forever, name="blender-copilot-mcp", daemon=True)
        self._thread.start()
        return self.port

    def stop(self) -> None:
        if self._httpd is not None:
            self._httpd.shutdown()
            self._httpd.server_close()
            self._httpd = None
        self._thread = None
