"""Pure, dependency-free helpers shared across Track 4 (Enterprise Productization).

Nothing here touches the database, network or any LLM. Deterministic and safe to
import from migrations, tests and services alike — mirroring the
``services/financial_intelligence/common.py`` and Track 2 conventions.

Track 4 is a *productization* layer, so the primitives here lean toward product
plumbing: slugs, content-addressed identity, API-key hashing, health scoring,
status roll-ups and grounding blocks, rather than heavy numerics.
"""

from __future__ import annotations

import hashlib
import json
import re
import secrets
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Sequence

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


def safe_div(numerator: float, denominator: float, default: Optional[float] = None) -> Optional[float]:
    if not denominator:
        return default
    return numerator / denominator


def pct(value: Optional[float], ndigits: int = 2) -> Optional[float]:
    return round(value * 100.0, ndigits) if value is not None else None


def to_float(value: Any, default: float = 0.0) -> float:
    try:
        return default if value is None else float(value)
    except (TypeError, ValueError):
        return default


def mean(xs: Sequence[float]) -> float:
    xs = list(xs)
    return sum(xs) / len(xs) if xs else 0.0


# ---------------------------------------------------------------------------
# Identity / slugs / hashing
# ---------------------------------------------------------------------------

def slugify(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (text or "").strip().lower())
    return re.sub(r"-+", "-", s).strip("-") or "item"


def checksum(obj: Any) -> str:
    """Stable SHA-256 over a JSON-serialisable object (sorted keys)."""
    payload = json.dumps(obj, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def stable_id(*parts: Any) -> str:
    return hashlib.sha256("|".join(str(p) for p in parts).encode()).hexdigest()[:16]


def generate_api_key(prefix: str = "sk_live") -> Dict[str, str]:
    """Return a one-time secret plus its stored prefix + hash.

    The plaintext secret is shown to the caller **once**; only the SHA-256 hash
    and a short display prefix are persisted, mirroring how real API-key vaults
    store credentials.
    """
    secret = secrets.token_urlsafe(24)
    full = f"{prefix}_{secret}"
    return {"secret": full, "prefix": full[: len(prefix) + 7],
            "hash": hashlib.sha256(full.encode()).hexdigest()}


def hash_secret(secret: str) -> str:
    return hashlib.sha256((secret or "").encode()).hexdigest()


def generate_signing_secret() -> str:
    return f"whsec_{secrets.token_urlsafe(24)}"


# ---------------------------------------------------------------------------
# Health / status roll-ups
# ---------------------------------------------------------------------------

# Ordered worst → best so a roll-up can take the worst member status.
STATUS_ORDER = ["down", "critical", "degraded", "warning", "healthy", "unknown"]
STATUS_RANK = {"down": 0, "critical": 1, "degraded": 2, "warning": 3, "healthy": 4, "unknown": 5}


def rollup_status(statuses: Iterable[str]) -> str:
    """Worst-of roll-up across component statuses (unknown ignored if others exist)."""
    ranked = [s for s in statuses if s in STATUS_RANK]
    concrete = [s for s in ranked if s != "unknown"]
    pool = concrete or ranked
    if not pool:
        return "unknown"
    return min(pool, key=lambda s: STATUS_RANK[s])


def health_band(score: float) -> str:
    """Map a 0-100 health score to a status band."""
    if score >= 90:
        return "healthy"
    if score >= 75:
        return "warning"
    if score >= 50:
        return "degraded"
    if score >= 25:
        return "critical"
    return "down"


def score_to_grade(score: float) -> str:
    if score >= 90:
        return "A"
    if score >= 80:
        return "B"
    if score >= 70:
        return "C"
    if score >= 60:
        return "D"
    return "F"


# ---------------------------------------------------------------------------
# Grounding — product analytics stay auditable/reproducible too.
# ---------------------------------------------------------------------------

def grounding_block(title: str, facts: Dict[str, Any]) -> Dict[str, Any]:
    return {"title": title, "facts": facts, "checksum": checksum(facts),
            "generated_at": iso(utcnow())}


def confidence_block(score: float, reasoning: str, citations: Optional[List[Dict[str, Any]]] = None,
                     evidence: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Standard AI envelope: confidence + reasoning + citations + evidence.

    Track 4's quality bar requires every AI response to carry confidence,
    reasoning, citations and evidence; this is the shared envelope used by the
    customer-success, operations and BI recommendation surfaces.
    """
    return {
        "confidence": round(clamp(score, 0.0, 1.0), 3),
        "reasoning": reasoning,
        "citations": citations or [],
        "evidence": evidence or {},
        "generated_at": iso(utcnow()),
    }
