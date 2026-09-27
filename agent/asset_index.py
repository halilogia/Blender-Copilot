"""Local asset library index (v1.1 C). Stdlib only, zero bpy.

Scans a user-chosen library dir for .blend/.glb/.obj/.fbx files,
guards path traversal, ranks by substring + local embedding similarity.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

ALLOWED_EXTS = {".blend", ".glb", ".obj", ".fbx"}


def is_safe_path(root: str | Path, candidate: str | Path) -> bool:
    """True if candidate resolves inside root (traversal guard)."""
    try:
        r = Path(root).resolve()
        c = (r / str(candidate)).resolve() if not Path(str(candidate)).is_absolute() else Path(str(candidate)).resolve()
        return r == c or r in c.parents
    except Exception:
        return False


def scan_library(root: str | Path) -> List[Dict[str, str]]:
    """List asset files under root (non-recursive limit: recursive, cap 500)."""
    r = Path(root)
    if not r.is_dir():
        return []
    out: List[Dict[str, str]] = []
    for p in sorted(r.rglob("*")):
        if len(out) >= 500:
            break
        if p.is_file() and p.suffix.lower() in ALLOWED_EXTS:
            try:
                rel = str(p.relative_to(r))
            except Exception:
                continue
            out.append({"name": p.stem, "path": rel, "ext": p.suffix.lower()})
    return out


@dataclass
class AssetLibrary:
    root: str
    _entries: List[Dict[str, str]] = field(default_factory=list)

    def refresh(self) -> int:
        self._entries = scan_library(self.root)
        # Lazy local embedding index rebuilt on search
        try:
            from agent.local_embed import LocalIndex
            self._index = LocalIndex()
            for e in self._entries:
                self._index.add(e["path"], f"{e['name']} {e['ext']}")
        except Exception:
            self._index = None
        return len(self._entries)

    def search(self, query: str, k: int = 5) -> List[Dict[str, object]]:
        """Substring-first, embedding re-rank fallback. Deterministic."""
        q = (query or "").strip().lower()
        if not q:
            return [{"name": e["name"], "path": e["path"], "score": 0.0} for e in self._entries[:k]]
        scored: List[Tuple[float, Dict[str, str]]] = []
        for e in self._entries:
            hay = f"{e['name']} {e['ext']}".lower()
            sub = 1.0 if q in hay else (0.5 if any(t in hay for t in q.split()) else 0.0)
            scored.append((sub, e))
        # Embedding boost for non-exact matches
        try:
            from agent.local_embed import LocalIndex
            idx = LocalIndex()
            for e in self._entries:
                idx.add(e["path"], f"{e['name']} {e['ext']}")
            emb = {doc: s for doc, s in idx.query(query, k=len(self._entries))}
            merged = [((s + emb.get(e["path"], 0.0)) / 2.0, e) for s, e in scored]
            merged.sort(key=lambda t: (-t[0], t[1]["path"]))
            return [{"name": e["name"], "path": e["path"], "score": round(s, 4)} for s, e in merged[:k] if s > 0]
        except Exception:
            scored.sort(key=lambda t: (-t[0], t[1]["path"]))
            return [{"name": e["name"], "path": e["path"], "score": s} for s, e in scored[:k] if s > 0]

    def resolve(self, path: str) -> Optional[str]:
        """Resolve library-relative path to absolute path if safe + exists."""
        if not is_safe_path(self.root, path):
            return None
        abs_p = str((Path(self.root) / path).resolve()) if not Path(path).is_absolute() else str(Path(path).resolve())
        if not is_safe_path(self.root, abs_p):
            return None
        return abs_p if Path(abs_p).is_file() else None
