"""Persistent MCP bridge settings (a small JSON next to config.json) with environment overrides.

Pure Python, zero Blender dependencies. The file holds the bridge token, so it is written with
owner-only permissions where the platform supports it and the token is never logged.

Environment overrides (win over the file, useful for headless runs and CI). They are for that one run only: they are never
written back to the file (a headless run with ALLOW_GATED must not switch "Allow gated tools" on in the user's profile):
  BLENDER_COPILOT_MCP=1              start the bridge when the add-on registers
  BLENDER_COPILOT_MCP_PORT=6590      listening port (default 6590)
  BLENDER_COPILOT_MCP_TOKEN=...      bearer token (otherwise generated once and stored)
  BLENDER_COPILOT_MCP_ALLOW_GATED=1  let MCP clients run MEDIUM+ risk tools without in-Blender approval
  BLENDER_COPILOT_EXPORT_DIR=...     folder export_gltf writes into
"""

import json
import os
import secrets
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional

DEFAULT_PORT = 6590


def default_export_dir() -> str:
    return str(Path.home() / "Documents" / "BlenderCopilot" / "exports")


@dataclass
class BridgeSettings:
    enabled: bool = False
    port: int = DEFAULT_PORT
    token: str = ""
    allow_gated: bool = False
    export_dir: str = field(default_factory=default_export_dir)
    # values an environment variable replaced for this run: key -> what the file / default held (never persisted over)
    _env_replaced: Dict[str, Any] = field(default_factory=dict, repr=False, compare=False)

    def to_dict(self) -> Dict[str, Any]:
        """What to write to the file: the settings with every environment override taken out again."""
        data = asdict(self)
        data.pop("_env_replaced", None)
        data.update(self._env_replaced)
        return data

    def set(self, key: str, value: Any) -> None:
        """A change made on purpose (the panel): it replaces any environment override of that key and is kept."""
        setattr(self, key, value)
        self._env_replaced.pop(key, None)


def _as_bool(value: Any) -> bool:
    return str(value).strip().lower() in ("1", "true", "yes", "on")


def load_settings(path: Path, env: Optional[Dict[str, str]] = None) -> BridgeSettings:
    env = os.environ if env is None else env
    data: Dict[str, Any] = {}
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            data = {}
    except (OSError, ValueError):
        data = {}
    settings = BridgeSettings()
    settings.enabled = bool(data.get("enabled", settings.enabled))
    settings.allow_gated = bool(data.get("allow_gated", settings.allow_gated))
    settings.token = str(data.get("token", "")) if isinstance(data.get("token", ""), str) else ""
    settings.export_dir = str(data.get("export_dir") or settings.export_dir)
    try:
        port = int(data.get("port", settings.port))
        settings.port = port if 1024 <= port <= 65535 else DEFAULT_PORT
    except (TypeError, ValueError):
        settings.port = DEFAULT_PORT
    def override(key: str, value: Any) -> None:
        settings._env_replaced.setdefault(key, getattr(settings, key))
        setattr(settings, key, value)

    if "BLENDER_COPILOT_MCP" in env:
        override("enabled", _as_bool(env["BLENDER_COPILOT_MCP"]))
    if env.get("BLENDER_COPILOT_MCP_PORT", "").isdigit():
        port = int(env["BLENDER_COPILOT_MCP_PORT"])
        if 1024 <= port <= 65535:
            override("port", port)
    if env.get("BLENDER_COPILOT_MCP_TOKEN"):
        override("token", env["BLENDER_COPILOT_MCP_TOKEN"])
    if "BLENDER_COPILOT_MCP_ALLOW_GATED" in env:
        override("allow_gated", _as_bool(env["BLENDER_COPILOT_MCP_ALLOW_GATED"]))
    if env.get("BLENDER_COPILOT_EXPORT_DIR"):
        override("export_dir", env["BLENDER_COPILOT_EXPORT_DIR"])
    return settings


def ensure_token(settings: BridgeSettings) -> str:
    if not settings.token:
        settings.token = secrets.token_hex(24)
    return settings.token


def save_settings(settings: BridgeSettings, path: Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = settings.to_dict()
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def mask_token(token: str) -> str:
    return "" if not token else token[:6] + "…" + "*" * 6
