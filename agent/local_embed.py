"""Local deterministic text embedding — stdlib only.

Hashed char-trigram + token TF vector with L2 normalization and cosine search.
Zero third-party deps, zero bpy, zero network. Deterministic across runs.
Used for scene / memory / asset semantic ranking (v1.1 A3).
"""

from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass, field
from typing import Dict, List, Sequence, Tuple

EMBED_DIM: int = 256
MAX_TEXT_CHARS: int = 2000

_TOKEN_RE = re.compile(r"[a-z0-9_çğıöşü]+", re.IGNORECASE)


def tokenize(text: str) -> List[str]:
    """Lowercase alphanumeric (+TR) tokenization, capped for determinism."""
    if not isinstance(text, str):
        text = str(text or "")
    text = text.lower()[:MAX_TEXT_CHARS]
    return _TOKEN_RE.findall(text)


def featurize(text: str) -> List[str]:
    """Token + char-trigram features for fuzzy matching (e.g. 'küp' vs 'kup')."""
    feats: List[str] = []
    for tok in tokenize(text):
        feats.append(f"t:{tok}")
        padded = f" {tok} "
        for i in range(len(padded) - 2):
            feats.append(f"g:{padded[i:i+3]}")
    return feats


def _feature_index(feat: str, dim: int = EMBED_DIM) -> int:
    digest = hashlib.md5(feat.encode("utf-8")).digest()
    return int.from_bytes(digest[:4], "big") % dim


def embed_text(text: str, dim: int = EMBED_DIM) -> Tuple[float, ...]:
    """Embed text into L2-normalized hashed vector. Empty -> zero vector."""
    vec = [0.0] * dim
    feats = featurize(text)
    if not feats:
        return tuple(vec)
    for f in feats:
        vec[_feature_index(f, dim)] += 1.0
    norm = math.sqrt(sum(v * v for v in vec))
    if norm <= 0:
        return tuple(vec)
    return tuple(v / norm for v in vec)


def cosine_sim(a: Sequence[float], b: Sequence[float]) -> float:
    """Cosine similarity for L2-normalized vectors (0.0 for zero vectors)."""
    if len(a) != len(b) or not a:
        raise ValueError(f"Vector length mismatch: {len(a)} vs {len(b)}.")
    dot = sum(x * y for x, y in zip(a, b))
    # Clamp for float safety
    return max(-1.0, min(1.0, dot))


def top_k(query: str, docs: Sequence[str], k: int = 5) -> List[Tuple[int, float]]:
    """Rank doc indices by cosine similarity to query (desc, index tie-break)."""
    if k <= 0:
        raise ValueError(f"k must be positive, got {k}.")
    qv = embed_text(query)
    scored = [(i, cosine_sim(qv, embed_text(d))) for i, d in enumerate(docs)]
    scored.sort(key=lambda t: (-t[1], t[0]))
    return scored[:k]


@dataclass
class LocalIndex:
    """Tiny in-memory id->text index with deterministic semantic search."""

    dim: int = EMBED_DIM
    _texts: Dict[str, str] = field(default_factory=dict)

    def add(self, doc_id: str, text: str) -> None:
        if not isinstance(doc_id, str) or not doc_id.strip():
            raise ValueError("doc_id must be a non-empty string.")
        self._texts[doc_id.strip()] = text or ""

    def remove(self, doc_id: str) -> None:
        self._texts.pop(doc_id, None)

    def clear(self) -> None:
        self._texts.clear()

    def query(self, q: str, k: int = 5) -> List[Tuple[str, float]]:
        """Return [(doc_id, score)] sorted by score desc, doc_id asc tie-break."""
        if k <= 0:
            raise ValueError(f"k must be positive, got {k}.")
        qv = embed_text(q, self.dim)
        scored = [
            (doc_id, cosine_sim(qv, embed_text(t, self.dim)))
            for doc_id, t in self._texts.items()
        ]
        scored.sort(key=lambda t: (-t[1], t[0]))
        return scored[:k]

    def to_dict(self) -> Dict[str, str]:
        return dict(sorted(self._texts.items()))

    @classmethod
    def from_dict(cls, data: Dict[str, str]) -> "LocalIndex":
        idx = cls()
        if isinstance(data, dict):
            for k, v in data.items():
                if isinstance(k, str) and isinstance(v, str):
                    idx._texts[k] = v[:MAX_TEXT_CHARS]
        return idx
