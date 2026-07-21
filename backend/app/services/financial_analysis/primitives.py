"""Shared numeric primitives for the Financial Analysis Engine (Task 12).

Every calculation in this package flows through these helpers so that
division-by-zero, missing inputs and out-of-range values are handled in exactly
one place. The engine distinguishes a genuine ``0`` from a *missing* value:
missing / undefined ratios return ``None`` (surfaced to the user as
``"unavailable"``) rather than a fabricated number.

These helpers are intentionally independent of the credit scorecard's own
``safe_divide``/``scale`` (which default a missing denominator to ``0.0``). The
analysis engine needs the opposite contract — an undefined ratio must be
*explicitly* undefined — so the two are kept separate rather than shared.
"""

from __future__ import annotations

from typing import Optional, Sequence, Tuple

Number = Optional[float]


# ---------------------------------------------------------------------------
# Five-tier status vocabulary (shared by ratios and health scores so the
# frontend can map a single set of statuses to a single set of colours).
# ---------------------------------------------------------------------------

EXCELLENT = "excellent"
GOOD = "good"
MODERATE = "moderate"
WEAK = "weak"
CRITICAL = "critical"
UNAVAILABLE = "unavailable"

STATUS_ORDER = (CRITICAL, WEAK, MODERATE, GOOD, EXCELLENT)


def as_float(value: object) -> Number:
    """Coerce loosely-typed input (str with currency symbols/commas, None) to
    ``float`` or ``None``. Never raises."""
    if value is None:
        return None
    if isinstance(value, bool):  # avoid treating True/False as 1/0
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if not text:
        return None
    negative = text.startswith("(") and text.endswith(")")
    cleaned = (
        text.replace(",", "")
        .replace("₹", "")
        .replace("$", "")
        .replace("%", "")
        .replace("(", "")
        .replace(")", "")
    )
    for token in ("rs.", "rs", "inr", "usd"):
        cleaned = cleaned.lower().replace(token, "")
    cleaned = cleaned.strip()
    if not cleaned:
        return None
    try:
        result = float(cleaned)
    except ValueError:
        return None
    return -result if negative else result


def divide(numerator: Number, denominator: Number) -> Number:
    """Safe division. Returns ``None`` when either operand is missing or the
    denominator is zero — the caller renders that as an unavailable metric."""
    if numerator is None or denominator is None:
        return None
    if denominator == 0:
        return None
    return numerator / denominator


def clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def scale(value: Number, lo: float, hi: float) -> Number:
    """Linearly map ``value`` onto 0..100 where ``lo`` -> 0 and ``hi`` -> 100.

    Pass ``lo > hi`` for "lower is better" metrics (e.g. leverage). Returns
    ``None`` for a missing input so scores built on it can decide how to weight
    the gap rather than silently assuming zero.
    """
    if value is None:
        return None
    if hi == lo:
        return 50.0
    return clamp((value - lo) / (hi - lo) * 100.0, 0.0, 100.0)


def score_status(score: Number) -> str:
    """Map a 0..100 health score onto the five-tier status vocabulary."""
    if score is None:
        return UNAVAILABLE
    if score >= 80:
        return EXCELLENT
    if score >= 65:
        return GOOD
    if score >= 45:
        return MODERATE
    if score >= 25:
        return WEAK
    return CRITICAL


def status_from_thresholds(
    value: Number,
    thresholds: Sequence[Tuple[float, str]],
    higher_is_better: bool = True,
) -> str:
    """Grade a raw ratio value against ``(boundary, status)`` pairs.

    ``thresholds`` are ordered best-first. For ``higher_is_better`` the value
    must be ``>= boundary`` to earn that status; otherwise ``<= boundary``. The
    final pair's status is the fallback (its boundary is ignored).
    """
    if value is None:
        return UNAVAILABLE
    for boundary, status in thresholds[:-1]:
        if higher_is_better and value >= boundary:
            return status
        if not higher_is_better and value <= boundary:
            return status
    return thresholds[-1][1]


def mean_ignoring_missing(values: Sequence[Number]) -> Number:
    """Average the present values, ignoring ``None``. Returns ``None`` if all
    are missing."""
    present = [v for v in values if v is not None]
    if not present:
        return None
    return sum(present) / len(present)


def pct_change(current: Number, previous: Number) -> Number:
    """Signed fractional change ``(current - previous) / |previous|``.

    Returns ``None`` when either value is missing or the base is zero (an
    undefined growth rate), keeping the trend engine honest for new borrowers.
    """
    if current is None or previous is None or previous == 0:
        return None
    return (current - previous) / abs(previous)
