"""Pure, DB-free helpers shared across the Security & Compliance services.

Deterministic scoring and grading primitives — no I/O, no randomness — so every
assessment is reproducible and safe to import from migrations, tests and the
runtime alike.
"""

from __future__ import annotations

from typing import Dict, Iterable, List, Mapping

# Severity -> numeric weight used when reducing a set of findings to a score.
SEVERITY_WEIGHT: Dict[str, int] = {
    "critical": 40,
    "high": 20,
    "medium": 8,
    "low": 3,
    "info": 0,
}

SEVERITY_ORDER: List[str] = ["critical", "high", "medium", "low", "info"]

# Control-assessment status -> fractional credit toward a compliance score.
CONTROL_CREDIT: Dict[str, float] = {
    "satisfied": 1.0,
    "implemented": 1.0,
    "partial": 0.5,
    "planned": 0.25,
    "gap": 0.0,
    "not_applicable": 1.0,  # excluded from denominator by callers when desired
}


def clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    """Bound ``value`` to the inclusive ``[low, high]`` range."""
    return max(low, min(high, value))


def grade_from_score(score: float) -> str:
    """Map a 0-100 posture/readiness score to a letter grade."""
    if score >= 97:
        return "A+"
    if score >= 93:
        return "A"
    if score >= 90:
        return "A-"
    if score >= 87:
        return "B+"
    if score >= 83:
        return "B"
    if score >= 80:
        return "B-"
    if score >= 75:
        return "C+"
    if score >= 70:
        return "C"
    if score >= 60:
        return "D"
    return "F"


def score_from_findings(findings: Iterable[Mapping[str, object]], *, base: float = 100.0) -> float:
    """Reduce a set of findings to a 0-100 score by subtracting severity weights.

    Deterministic and monotonic: more/severe findings always lower the score.
    """
    penalty = 0.0
    for f in findings:
        sev = str(f.get("severity", "info")).lower()
        penalty += SEVERITY_WEIGHT.get(sev, 0)
    return round(clamp(base - penalty), 1)


def severity_counts(findings: Iterable[Mapping[str, object]]) -> Dict[str, int]:
    """Count findings by severity, always returning every severity key."""
    counts = {s: 0 for s in SEVERITY_ORDER}
    for f in findings:
        sev = str(f.get("severity", "info")).lower()
        if sev in counts:
            counts[sev] += 1
    return counts


def readiness_label(score: float) -> str:
    """Compliance readiness bucket from a 0-100 score."""
    if score >= 90:
        return "ready"
    if score >= 75:
        return "substantial"
    if score >= 50:
        return "partial"
    return "not_ready"


def compliance_score(results: Iterable[Mapping[str, object]]) -> float:
    """Weighted 0-100 readiness score from per-control results.

    ``not_applicable`` controls are excluded from the denominator so scoping a
    control out never penalises the score.
    """
    numerator = 0.0
    denominator = 0
    for r in results:
        status = str(r.get("status", "gap")).lower()
        if status == "not_applicable":
            continue
        numerator += CONTROL_CREDIT.get(status, 0.0)
        denominator += 1
    if denominator == 0:
        return 0.0
    return round(clamp(100.0 * numerator / denominator), 1)


def risk_score(likelihood: int, impact: int) -> int:
    """5x5 risk matrix score (1-25)."""
    return max(1, min(5, int(likelihood))) * max(1, min(5, int(impact)))


def risk_level(score: int) -> str:
    """Map a 1-25 risk score to a qualitative level."""
    if score >= 20:
        return "critical"
    if score >= 12:
        return "high"
    if score >= 6:
        return "medium"
    return "low"


def weighted_average(dimensions: Mapping[str, float], weights: Mapping[str, float] | None = None) -> float:
    """Weighted average of dimension scores (equal weight when unspecified)."""
    if not dimensions:
        return 0.0
    total_w = 0.0
    acc = 0.0
    for name, value in dimensions.items():
        w = 1.0 if weights is None else float(weights.get(name, 1.0))
        acc += value * w
        total_w += w
    return round(acc / total_w, 1) if total_w else 0.0
