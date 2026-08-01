"""Shared numeric + classification helpers for the AI Brain.

Pure functions only (no DB, no ORM) so they are trivially unit-testable and can
be imported anywhere without side effects. These encode the platform-wide
conventions for severity bands, priority scoring and safe arithmetic that every
 engine reuses (SOLID / no-duplicated-logic requirement).
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, Optional

# Ordered severity ladder shared by monitoring, EWS and recommendations.
SEVERITY_ORDER = ["info", "low", "medium", "high", "critical"]
SEVERITY_WEIGHT = {"info": 0.1, "low": 0.3, "medium": 0.55, "high": 0.8, "critical": 1.0}

# Rating ladder (best -> worst) reused for migration maths across simulation/stress.
RATING_ORDER = ["AAA", "AA", "A", "BBB", "BB", "B", "CCC", "CC", "C", "D"]


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    """Clamp ``value`` into ``[low, high]``."""
    if value < low:
        return low
    if value > high:
        return high
    return value


def safe_div(numerator: Optional[float], denominator: Optional[float]) -> Optional[float]:
    """Division that returns ``None`` on missing/zero denominator (never fabricates)."""
    if numerator is None or denominator in (None, 0):
        return None
    try:
        return numerator / denominator
    except (TypeError, ZeroDivisionError):
        return None


def severity_rank(severity: str) -> int:
    """Integer rank of a severity label; unknown labels sort lowest."""
    try:
        return SEVERITY_ORDER.index(severity)
    except ValueError:
        return 0


def max_severity(severities: Iterable[str]) -> str:
    """Return the highest severity from an iterable (``info`` if empty)."""
    best = "info"
    for s in severities:
        if severity_rank(s) > severity_rank(best):
            best = s
    return best


def severity_from_score(score: float, *, thresholds=(20, 40, 60, 80)) -> str:
    """Map a 0-100 distress score to a severity band.

    ``score`` here means "how bad" — higher is worse. Default cut points give
    info < 20 <= low < 40 <= medium < 60 <= high < 80 <= critical.
    """
    lo, l2, l3, l4 = thresholds
    if score >= l4:
        return "critical"
    if score >= l3:
        return "high"
    if score >= l2:
        return "medium"
    if score >= lo:
        return "low"
    return "info"


def priority_score(severity: str, confidence: float, *, exposure: Optional[float] = None,
                   exposure_cap: float = 1e8) -> float:
    """Blend severity, confidence and (optional) exposure into a 0-100 priority.

    Exposure lifts priority logarithmically so a large loan nudges — but never
    dominates — the ranking. Deterministic and monotonic in each input.
    """
    base = SEVERITY_WEIGHT.get(severity, 0.3) * clamp(confidence)
    exp_factor = 1.0
    if exposure and exposure > 0:
        exp_factor = 1.0 + 0.5 * clamp((exposure / exposure_cap))
    return round(clamp(base * exp_factor) * 100, 2)


def band_from_score(score: float, *, green: float = 30, amber: float = 60) -> str:
    """Traffic-light band for a 0-100 distress score (higher = worse)."""
    if score >= amber:
        return "red"
    if score >= green:
        return "amber"
    return "green"


def pct_change(old: Optional[float], new: Optional[float]) -> Optional[float]:
    """Signed fractional change ``(new-old)/|old|``; ``None`` when undefined."""
    if old is None or new is None or old == 0:
        return None
    return (new - old) / abs(old)


def rating_index(rating: Optional[str]) -> Optional[int]:
    """Index of a letter rating in :data:`RATING_ORDER` (``None`` if unknown)."""
    if not rating:
        return None
    r = rating.strip().upper()
    if r in RATING_ORDER:
        return RATING_ORDER.index(r)
    # tolerate '+'/'-' modifiers by stripping them
    r2 = r.rstrip("+-")
    return RATING_ORDER.index(r2) if r2 in RATING_ORDER else None


def shift_rating(rating: Optional[str], notches: int) -> Optional[str]:
    """Move a rating ``notches`` worse (+) or better (-); clamps at the ends."""
    idx = rating_index(rating)
    if idx is None:
        return rating
    new_idx = int(clamp(idx + notches, 0, len(RATING_ORDER) - 1))
    return RATING_ORDER[new_idx]


def pd_from_score(score: float) -> float:
    """Calibrated PD from a 300-900 enterprise credit score (mirrors ).

    Exponential calibration: a 900 score ≈ 0.2% PD, a 300 score ≈ ~35% PD.
    Used when an assessment lacks a stored PD so downstream engines still work.
    """
    s = clamp((900 - score) / 600, 0, 1)
    return round(0.002 + (0.35 - 0.002) * (s ** 1.6), 4)


def evidence(label: str, value: Any, *, source: str = "platform") -> Dict[str, Any]:
    """Build a standard evidence entry: never fabricates — carries the source."""
    return {"label": label, "value": value, "source": source}
