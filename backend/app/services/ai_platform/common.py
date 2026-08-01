"""Pure, dependency-free helpers shared across the AI Intelligence Platform.

Nothing in this module touches the database, the network or any LLM. Everything
here is deterministic and safe to import from migrations, tests and services
alike, mirroring the ``services/autonomous/common.py`` convention from .
"""

from __future__ import annotations

import hashlib
import math
import re
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

# ---------------------------------------------------------------------------
# Time
# ---------------------------------------------------------------------------

def utcnow() -> datetime:
    """Timezone-naive UTC now (matches the rest of the codebase's DateTime cols)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def iso(dt: Optional[datetime]) -> Optional[str]:
    return dt.isoformat() if dt else None


# ---------------------------------------------------------------------------
# Numeric
# ---------------------------------------------------------------------------

def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def safe_div(numerator: float, denominator: float) -> Optional[float]:
    if not denominator:
        return None
    return numerator / denominator


def round_opt(value: Optional[float], ndigits: int = 4) -> Optional[float]:
    return round(value, ndigits) if value is not None else None


# ---------------------------------------------------------------------------
# Hashing / identity (deterministic — used for content addressing & lineage)
# ---------------------------------------------------------------------------

def content_hash(*parts: Any) -> str:
    """Stable SHA-256 hex digest over the string form of ``parts``."""
    h = hashlib.sha256()
    for p in parts:
        h.update(str(p).encode("utf-8", errors="replace"))
        h.update(b"\x00")
    return h.hexdigest()


def short_hash(*parts: Any, length: int = 12) -> str:
    return content_hash(*parts)[:length]


# ---------------------------------------------------------------------------
# Text
# ---------------------------------------------------------------------------

_TOKEN_RE = re.compile(r"[a-z0-9]+")
_SENT_RE = re.compile(r"(?<=[.!?])\s+")

# A compact English stop-word set — enough to make keyword scoring meaningful
# without pulling in NLTK. Deterministic and offline.
STOPWORDS = frozenset(
    """a an the and or but if then else for to of in on at by with from as is are was
    were be been being this that these those it its it's we you they he she i me my our
    your their his her not no nor so than too very can will just should would could may
    might must do does did have has had having about into over under again further once
    here there all any both each few more most other some such only own same up down out
    off above below""".split()
)


def tokenize(text: str) -> List[str]:
    return _TOKEN_RE.findall((text or "").lower())


def keywords(text: str) -> List[str]:
    return [t for t in tokenize(text) if t not in STOPWORDS and len(t) > 1]


def split_sentences(text: str) -> List[str]:
    text = (text or "").strip()
    if not text:
        return []
    return [s.strip() for s in _SENT_RE.split(text) if s.strip()]


def chunk_text(
    text: str,
    *,
    chunk_size: int = 900,
    overlap: int = 150,
) -> List[Tuple[int, str]]:
    """Split ``text`` into overlapping, sentence-aware chunks.

    Returns ``(ordinal, chunk_text)`` pairs. Sentences are packed greedily up to
    ``chunk_size`` characters; the final ``overlap`` characters of a chunk are
    prepended to the next so retrieval never loses context across a boundary.
    Purely deterministic.
    """
    text = (text or "").strip()
    if not text:
        return []
    sentences = split_sentences(text) or [text]
    chunks: List[str] = []
    current = ""
    for sent in sentences:
        if not current:
            current = sent
        elif len(current) + 1 + len(sent) <= chunk_size:
            current = f"{current} {sent}"
        else:
            chunks.append(current)
            tail = current[-overlap:] if overlap else ""
            current = f"{tail} {sent}".strip() if tail else sent
        # A single monster sentence larger than chunk_size is hard-split.
        while len(current) > chunk_size:
            chunks.append(current[:chunk_size])
            current = current[chunk_size - overlap:] if overlap else current[chunk_size:]
    if current.strip():
        chunks.append(current.strip())
    return list(enumerate(chunks))


def token_count(text: str) -> int:
    """Cheap, deterministic token estimate (~4 chars/token heuristic)."""
    if not text:
        return 0
    return max(len(tokenize(text)), math.ceil(len(text) / 4))


def truncate(text: str, limit: int = 4000) -> str:
    text = text or ""
    return text if len(text) <= limit else text[: limit - 1] + "…"


# ---------------------------------------------------------------------------
# Vector math (pure Python — no numpy dependency required)
# ---------------------------------------------------------------------------

def dot(a: Sequence[float], b: Sequence[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


def norm(a: Sequence[float]) -> float:
    return math.sqrt(sum(x * x for x in a))


def l2_normalize(a: Sequence[float]) -> List[float]:
    n = norm(a)
    if not n:
        return list(a)
    return [x / n for x in a]


def cosine(a: Sequence[float], b: Sequence[float]) -> float:
    na, nb = norm(a), norm(b)
    if not na or not nb:
        return 0.0
    return clamp(dot(a, b) / (na * nb), -1.0, 1.0)


# ---------------------------------------------------------------------------
# Lexical similarity (used by hybrid search & groundedness checks)
# ---------------------------------------------------------------------------

def jaccard(a: Iterable[str], b: Iterable[str]) -> float:
    sa, sb = set(a), set(b)
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def bm25_lite(query_tokens: Sequence[str], doc_tokens: Sequence[str],
              *, k1: float = 1.5, b: float = 0.75, avg_len: float = 120.0) -> float:
    """A single-document BM25-style lexical score (corpus IDF folded to 1.0).

    Deterministic and dependency-free; good enough to rank chunks lexically for
    the hybrid retriever without maintaining a global corpus index.
    """
    if not query_tokens or not doc_tokens:
        return 0.0
    dl = len(doc_tokens)
    counts: Dict[str, int] = {}
    for t in doc_tokens:
        counts[t] = counts.get(t, 0) + 1
    score = 0.0
    for q in set(query_tokens):
        f = counts.get(q, 0)
        if not f:
            continue
        denom = f + k1 * (1 - b + b * dl / max(avg_len, 1.0))
        score += (f * (k1 + 1)) / denom
    return score


def minmax_scale(values: Sequence[float]) -> List[float]:
    if not values:
        return []
    lo, hi = min(values), max(values)
    if hi - lo < 1e-12:
        return [1.0 for _ in values]
    return [(v - lo) / (hi - lo) for v in values]
