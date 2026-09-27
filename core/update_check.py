"""Check-only auto-update helper (v1.1 B).

Stdlib only, zero bpy. Never downloads or installs anything.
Network I/O strictly via agent/http_client.HttpClient (hardening invariant).
All transport errors fold into UpdateStatus (no exceptions to UI).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable, Dict, Optional, Tuple

DEFAULT_REPO = "halilogia/Blender-AI-Sidebar"
RELEASES_PATH = "/repos/{repo}/releases/latest"
_VERSION_RE = re.compile(r"(\d+)\.(\d+)\.(\d+)")


def parse_version(text: str) -> Tuple[int, int, int]:
    """Parse 'v1.2.3' / '1.2.3' -> (1,2,3). Raises ValueError if absent."""
    m = _VERSION_RE.search(str(text or ""))
    if not m:
        raise ValueError(f"No semantic version found in '{text}'.")
    return (int(m.group(1)), int(m.group(2)), int(m.group(3)))


def is_newer(current: str, latest: str) -> bool:
    """True if latest > current (tuple compare)."""
    return parse_version(latest) > parse_version(current)


@dataclass(frozen=True)
class UpdateStatus:
    current: str
    latest: Optional[str]
    update_available: bool
    notes: str = ""
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, object]:
        return {"current": self.current, "latest": self.latest,
                "update_available": self.update_available,
                "notes": self.notes, "error": self.error}


def check_for_updates(
    current_version: str,
    repo: str = DEFAULT_REPO,
    timeout: float = 10.0,
    fetcher: Optional[Callable[[str], Dict]] = None,
    http_client=None,
) -> UpdateStatus:
    """Check GitHub latest release. Never raises; errors fold into UpdateStatus."""
    try:
        if fetcher is not None:
            data = fetcher(f"https://api.github.com{RELEASES_PATH.format(repo=repo)}")
        else:
            from agent.http_client import HttpClient
            client = http_client or HttpClient(base_url="https://api.github.com", timeout=timeout)
            data = client.get_json(RELEASES_PATH.format(repo=repo),
                                   headers={"User-Agent": "blender-copilot-update-check"},
                                   timeout=timeout)
        if not isinstance(data, dict):
            raise ValueError("Unexpected release payload.")
        tag = str(data.get("tag_name", "") or data.get("name", ""))
        latest = "%d.%d.%d" % parse_version(tag)
        available = is_newer(current_version, latest)
        notes = str(data.get("body", "") or "")[:500]
        return UpdateStatus(current=current_version, latest=latest,
                            update_available=available, notes=notes)
    except Exception as exc:
        return UpdateStatus(current=current_version, latest=None,
                            update_available=False, error=f"{type(exc).__name__}: {exc}")
