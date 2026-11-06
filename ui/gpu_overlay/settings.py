"""Pure logic behind the HUD settings drawer: field set, inline editor, online status, connection test.

No bpy here so it stays unit-testable. The API key is only ever shown masked and is never
logged or included in a returned message.
"""

from typing import Callable, List, Optional, Tuple

from agent.http_client import HttpClient, HttpError, NetworkError
from core.config import is_local_endpoint, is_network_allowed, mask_api_key

ANTHROPIC_VERSION = "2023-06-01"

PROVIDERS: Tuple[Tuple[str, str], ...] = (
    ("openai_compatible", "OpenAI-compatible"),
    ("anthropic", "Anthropic"),
    ("agy_cli", "Antigravity CLI"),
)
TIMEOUT_MIN, TIMEOUT_MAX, TIMEOUT_STEP = 5, 300, 15

LABELS = {"provider": "Provider", "base_url": "Base URL", "model": "Model",
          "api_key": "API key", "timeout": "Timeout"}


def provider_label(provider: str) -> str:
    return dict(PROVIDERS).get(provider, provider)


def next_provider(provider: str) -> str:
    ids = [p[0] for p in PROVIDERS]
    return ids[(ids.index(provider) + 1) % len(ids)] if provider in ids else ids[0]


def visible_fields(provider: str) -> List[str]:
    """The agy CLI needs no URL, key or timeout, so those rows disappear."""
    if provider == "agy_cli":
        return ["provider", "model"]
    return ["provider", "base_url", "model", "api_key", "timeout"]


def provider_note(provider: str, model: str) -> str:
    """One short line under the fields: the limits the user must know about."""
    if provider != "agy_cli":
        return ""
    from agent.agy_cli_provider import DEFAULT_MODEL, OFFICIAL_MODELS
    if model not in OFFICIAL_MODELS:
        return f"Text only. Not an agy model id: {DEFAULT_MODEL} is used."
    return "Text only: the agy CLI cannot receive images."


def step_timeout(value: int, delta: int) -> int:
    return max(TIMEOUT_MIN, min(TIMEOUT_MAX, int(value) + delta))


def display_value(field: str, values: dict, editing: Optional["FieldEditor"]) -> str:
    """Text shown for a field. The key is masked, also while it is being typed."""
    if editing is not None and editing.field == field:
        return ("•" * len(editing.text)) if field == "api_key" else editing.text
    raw = values.get(field, "")
    if field == "provider":
        return provider_label(str(raw))
    if field == "api_key":
        return mask_api_key(str(raw)) or "not set"
    if field == "timeout":
        return f"{int(raw)} s"
    return str(raw)


class FieldEditor:
    """Single-line text buffer for the field being edited (the HUD routes keys here)."""

    def __init__(self, field: str, text: str):
        self.field = field
        self.text = text

    def insert(self, chars: str) -> None:
        self.text += chars.replace("\n", "").replace("\r", "")

    def backspace(self, word: bool = False) -> None:
        if word:
            self.text = self.text.rstrip()
            cut = self.text.rfind(" ")
            self.text = self.text[: cut + 1] if cut != -1 else ""
        else:
            self.text = self.text[:-1]


def online_status(provider: str, base_url: str, online_access: bool) -> Tuple[str, str]:
    """(level, text); level is ok | warn | info. Remote endpoints need Blender's online access."""
    if provider == "agy_cli":
        return "info", "Local CLI. No network setting needed."
    if is_local_endpoint(base_url):
        return "ok", "Local endpoint. Online access not required."
    if online_access:
        return "ok", "Online access is on."
    return "warn", "Online access is OFF. Enable it in Blender Preferences > System > Network."


def run_connection_test(
    provider: str,
    base_url: str,
    api_key: str,
    timeout: float,
    online_access: bool,
    client: Optional[object] = None,
    agy_resolver: Optional[Callable[[], Optional[str]]] = None,
) -> Tuple[bool, str]:
    """Blocking reachability probe; call it from a worker thread. Messages never include the key."""
    if provider == "agy_cli":
        if agy_resolver is None:
            from agent.agy_cli_provider import resolve_agy_command as agy_resolver
        path = agy_resolver()
        if path:
            return True, "agy found. It signs in on first use."
        return False, "agy CLI not found. Put it on PATH or set BLENDER_AI_AGY_PATH."
    allowed, reason = is_network_allowed(base_url, online_access)
    if not allowed:
        return False, reason
    headers = {"Accept": "application/json"}
    key = (api_key or "").strip()
    if provider == "anthropic":
        headers["anthropic-version"] = ANTHROPIC_VERSION
        if key:
            headers["x-api-key"] = key
    elif key:
        headers["Authorization"] = "Bearer " + key
    # All networking goes through the project's single transport (agent/http_client.py).
    http = client or HttpClient(base_url=base_url.strip())
    try:
        resp = http.get("/models", headers=headers, timeout=max(3.0, min(float(timeout), 20.0)))
        with resp:
            code = resp.status_code
        return True, f"Connected (HTTP {code})."
    except HttpError as err:
        if err.status_code in (401, 403):
            return False, f"Server reached, but the API key was rejected (HTTP {err.status_code})."
        if err.status_code == 404:
            return True, "Server reached (no /models list, which is fine)."
        return False, f"Server answered HTTP {err.status_code}."
    except NetworkError as err:
        return False, f"Cannot reach the server: {(err.details or err.message)[:80]}"
