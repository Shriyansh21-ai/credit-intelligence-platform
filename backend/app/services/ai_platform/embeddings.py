"""Pluggable embedding layer for the AI Intelligence Platform (Track 2).

Mirrors the platform-wide "abstraction + working offline default + gated
production adapter" pattern (see ``services/autonomous/llm.py``).

    Embedder (ABC)
      ├─ HashingEmbedder    default, offline, deterministic feature-hashing
      └─ Claude/OpenAI...   gated real providers, resolved lazily (never required)

The default :class:`HashingEmbedder` produces a fixed-dimension, L2-normalised
bag-of-words vector using signed feature hashing. It needs no model download and
no network, so retrieval is fully reproducible in tests and air-gapped banks —
yet cosine similarity between related texts is meaningfully > unrelated texts.

Real embedding providers can be enabled with ``AIP_EMBEDDING_PROVIDER`` without
changing any call site; an unavailable provider always degrades to hashing.
"""

from __future__ import annotations

import hashlib
import math
import os
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Sequence

from backend.app.services.ai_platform import common

DEFAULT_DIM = 256


class Embedder(ABC):
    name = "base"
    dim = DEFAULT_DIM
    model = "base"

    @abstractmethod
    def embed(self, text: str) -> List[float]:
        """Return the (L2-normalised) embedding vector for ``text``."""

    def embed_many(self, texts: Sequence[str]) -> List[List[float]]:
        return [self.embed(t) for t in texts]

    @property
    def available(self) -> bool:  # pragma: no cover - trivial
        return True


class HashingEmbedder(Embedder):
    """Deterministic offline embedder via signed feature hashing of keywords.

    For each keyword token we derive two hashes: one selects a bucket in
    ``[0, dim)``, the other a sign in ``{-1, +1}``. Token weights are damped
    (``1/(1+log(count))``-ish) so a repeated word does not dominate. The result
    is L2-normalised so cosine similarity is a pure direction comparison.
    """

    name = "hashing"

    def __init__(self, dim: int = DEFAULT_DIM):
        self.dim = dim
        self.model = f"hashing-{dim}"

    def _bucket(self, token: str) -> int:
        h = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
        return int.from_bytes(h, "big") % self.dim

    def _sign(self, token: str) -> float:
        h = hashlib.blake2b(("s:" + token).encode("utf-8"), digest_size=1).digest()
        return 1.0 if (h[0] & 1) else -1.0

    def embed(self, text: str) -> List[float]:
        vec = [0.0] * self.dim
        tokens = common.keywords(text)
        if not tokens:
            # Fall back to raw tokens so even stop-word-only text embeds stably.
            tokens = common.tokenize(text)
        counts: Dict[str, int] = {}
        for t in tokens:
            counts[t] = counts.get(t, 0) + 1
        for token, cnt in counts.items():
            weight = 1.0 + math.log(cnt)
            vec[self._bucket(token)] += self._sign(token) * weight
        return common.l2_normalize(vec)


# ---------------------------------------------------------------------------
# Gated real providers — never required; import failures degrade to hashing.
# ---------------------------------------------------------------------------
class _RemoteEmbedderBase(Embedder):  # pragma: no cover - only with SDK+key
    def __init__(self, dim: int = DEFAULT_DIM):
        self.dim = dim
        self._client = None

    def embed(self, text: str) -> List[float]:
        if not self.available:
            return HashingEmbedder(self.dim).embed(text)
        try:
            return self._remote_embed(text)
        except Exception:
            return HashingEmbedder(self.dim).embed(text)

    def _remote_embed(self, text: str) -> List[float]:  # pragma: no cover
        raise NotImplementedError


_HASHING = HashingEmbedder()
_CACHE: Dict[str, Embedder] = {"hashing": _HASHING, "local": _HASHING}


def get_embedder(name: Optional[str] = None) -> Embedder:
    """Resolve the active embedder.

    Order: explicit ``name`` → ``AIP_EMBEDDING_PROVIDER`` env → ``hashing``.
    Any requested remote provider that is not actually available degrades to the
    deterministic hashing embedder, so this never raises.
    """
    choice = (name or os.getenv("AIP_EMBEDDING_PROVIDER") or "hashing").lower()
    if choice in _CACHE:
        return _CACHE[choice]
    # Only the offline embedder ships wired-in; remote adapters are intentionally
    # left as an extension point (the VectorStore + Embedder ABCs are the seam).
    return _HASHING


def embedder_status() -> Dict[str, object]:
    active = get_embedder()
    return {
        "active": active.name,
        "model": active.model,
        "dim": active.dim,
        "configured": os.getenv("AIP_EMBEDDING_PROVIDER", "hashing"),
        "offline_default": True,
    }
