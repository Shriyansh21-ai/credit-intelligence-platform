"""Shared, pure helpers for the Banking OS.

No DB / ORM imports — trivially unit-testable and importable anywhere. These
encode platform-wide conventions for text tokenization (search), deterministic
digital signatures (committee votes / prompt approvals) and safe evidence
construction, reusing the helpers where a convention already exists.
"""

from __future__ import annotations

import hashlib
import math
import re
from typing import Any, Dict, Iterable, List, Optional

# Re-export the numeric helpers so code has one import surface.
from backend.app.services.autonomous.common import (  # noqa: F401
    clamp, evidence, pct_change, safe_div, severity_from_score,
)

# Minimal English + banking stopword set (kept small so we never drop signal).
_STOPWORDS = {
    "a", "an", "the", "of", "and", "or", "to", "in", "on", "for", "with", "is",
    "are", "was", "were", "be", "by", "at", "as", "it", "this", "that", "from",
    "has", "have", "had", "will", "shall", "can", "may", "any", "all", "no",
}

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def tokenize(text: Optional[str], *, keep_stopwords: bool = False,
             min_len: int = 2) -> List[str]:
    """Lowercase, split on non-alphanumerics, drop short words + stopwords.

    Deterministic and dependency-free; the same tokenizer is used at index time
    and query time so ranking is consistent.
    """
    if not text:
        return []
    tokens = _TOKEN_RE.findall(text.lower())
    out = []
    for t in tokens:
        if len(t) < min_len:
            continue
        if not keep_stopwords and t in _STOPWORDS:
            continue
        out.append(t)
    return out


def term_frequencies(terms: Iterable[str]) -> Dict[str, int]:
    """Count occurrences of each term."""
    tf: Dict[str, int] = {}
    for t in terms:
        tf[t] = tf.get(t, 0) + 1
    return tf


def bm25_idf(n_docs: int, doc_freq: int) -> float:
    """BM25-style inverse document frequency (never negative)."""
    if n_docs <= 0 or doc_freq <= 0:
        return 0.0
    return max(0.0, math.log(1 + (n_docs - doc_freq + 0.5) / (doc_freq + 0.5)))


def signature(*parts: Any) -> str:
    """Deterministic short digital-signature hash over the given parts.

    Used for committee vote signatures and prompt approvals — reproducible and
    tamper-evident without any external key management.
    """
    payload = "|".join("" if p is None else str(p) for p in parts)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def content_hash(payload: Any) -> str:
    """Stable content hash for dedup/idempotency (sorted-key JSON of ``payload``)."""
    import json
    blob = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def confidence_from_evidence(n_evidence: int, *, base: float = 0.5,
                             per_item: float = 0.1, cap: float = 0.98) -> float:
    """More corroborating evidence -> higher (bounded) confidence."""
    return round(min(cap, base + per_item * max(0, n_evidence)), 3)


def dedupe_preserve_order(items: Iterable[str]) -> List[str]:
    seen: set = set()
    out: List[str] = []
    for it in items:
        if it not in seen:
            seen.add(it)
            out.append(it)
    return out
