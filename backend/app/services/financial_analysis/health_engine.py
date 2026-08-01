"""Business Health Engine (Task 2).

Produces seven independent 0-100 health scores, each with a five-tier status
(Excellent / Good / Moderate / Weak / Critical) and a one-line summary

    liquidity, profitability, leverage, efficiency, cash_flow
    business_stability, growth

Scores are continuous (built from scaled ratio values via
:func:`primitives.scale`) rather than status buckets, so they are smooth enough
to feed the future ML risk engine as features. Dimensions whose inputs are
absent (e.g. ``growth`` with a single period, or ``business_stability`` with no
company profile) return ``score=None`` / ``status="unavailable"`` and are
excluded from the composite — the engine never invents a score.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional

from .primitives import (
    Number,
    UNAVAILABLE,
    mean_ignoring_missing,
    pct_change,
    scale,
    score_status,
)
from .statement import FinancialStatement

LIQUIDITY = "liquidity"
PROFITABILITY = "profitability"
LEVERAGE = "leverage"
EFFICIENCY = "efficiency"
CASH_FLOW = "cash_flow"
BUSINESS_STABILITY = "business_stability"
GROWTH = "growth"

# Composite weights (renormalised over available dimensions).
DIMENSION_WEIGHTS = {
    LIQUIDITY: 0.18,
    PROFITABILITY: 0.20,
    LEVERAGE: 0.20,
    EFFICIENCY: 0.12,
    CASH_FLOW: 0.18,
    BUSINESS_STABILITY: 0.07,
    GROWTH: 0.05,
}

_LABELS = {
    LIQUIDITY: "Liquidity Health",
    PROFITABILITY: "Profitability Health",
    LEVERAGE: "Leverage Health",
    EFFICIENCY: "Efficiency Health",
    CASH_FLOW: "Cash Flow Health",
    BUSINESS_STABILITY: "Business Stability",
    GROWTH: "Growth Health",
}

_STAGE_SCORE = {
    "mature": 90.0, "expansion": 78.0, "growth": 70.0,
    "startup": 40.0, "decline": 25.0,
}

# Human phrasing per status for dimension summaries.
_STATUS_WORD = {
    "excellent": "excellent", "good": "healthy", "moderate": "moderate",
    "weak": "weak", "critical": "critical", UNAVAILABLE: "not assessable",
}


@dataclass
class HealthScore:
    key: str
    label: str
    score: Optional[int]
    status: str
    summary: str

    def as_dict(self) -> dict:
        return {
            "key": self.key,
            "label": self.label,
            "score": self.score,
            "status": self.status,
            "summary": self.summary,
        }


def _finalise(score: Number) -> tuple[Optional[int], str]:
    if score is None:
        return None, UNAVAILABLE
    return int(round(score)), score_status(score)


def _liquidity(s: FinancialStatement) -> Number:
    from .ratio_engine import ratios_by_key  # local import to avoid cycle at import time

    r = ratios_by_key(s)
    return mean_ignoring_missing([
        scale(r["current_ratio"].value, 0.8, 2.5),
        scale(r["quick_ratio"].value, 0.5, 1.5),
        scale(r["cash_ratio"].value, 0.05, 0.5),
    ])


def _profitability(s: FinancialStatement) -> Number:
    from .ratio_engine import ratios_by_key

    r = ratios_by_key(s)
    return mean_ignoring_missing([
        scale(r["net_margin"].value, -0.05, 0.20),
        scale(r["gross_margin"].value, 0.05, 0.45),
        scale(r["operating_margin"].value, 0.0, 0.25),
        scale(r["return_on_equity"].value, 0.0, 0.20),
    ])


def _leverage(s: FinancialStatement) -> Number:
    from .ratio_engine import ratios_by_key

    r = ratios_by_key(s)
    return mean_ignoring_missing([
        scale(r["debt_to_equity"].value, 3.0, 0.3),        # lower is better
        scale(r["debt_ratio"].value, 0.8, 0.2),            # lower is better
        scale(r["interest_coverage"].value, 1.0, 8.0),
        scale(r["dscr"].value, 1.0, 2.5),
    ])


def _efficiency(s: FinancialStatement) -> Number:
    from .ratio_engine import ratios_by_key

    r = ratios_by_key(s)
    return mean_ignoring_missing([
        scale(r["asset_turnover"].value, 0.3, 1.5),
        scale(r["inventory_turnover"].value, 1.0, 8.0),
        scale(r["receivable_turnover"].value, 3.0, 12.0),
    ])


def _cash_flow(s: FinancialStatement) -> Number:
    from .ratio_engine import ratios_by_key

    r = ratios_by_key(s)
    fcf_margin = None
    if s.free_cash_flow_value is not None and s.revenue not in (None, 0):
        fcf_margin = s.free_cash_flow_value / s.revenue
    ocf_margin = None
    if s.operating_cash_flow is not None and s.revenue not in (None, 0):
        ocf_margin = s.operating_cash_flow / s.revenue
    return mean_ignoring_missing([
        scale(r["operating_cash_flow_ratio"].value, 0.2, 1.0),
        scale(r["dscr"].value, 1.0, 2.5),
        scale(ocf_margin, -0.05, 0.20),
        scale(fcf_margin, -0.05, 0.15),
    ])


def _business_stability(context: Optional[Mapping[str, Any]]) -> Number:
    if not context:
        return None
    years = context.get("years_in_business")
    employees = context.get("employee_count")
    stage = str(context.get("business_expansion_stage", "")).strip().lower() or None
    parts: List[Number] = []
    if years is not None:
        parts.append(scale(float(years), 0.0, 15.0))
    if employees is not None:
        parts.append(scale(math.log10(max(float(employees), 1.0)), 0.0, math.log10(500.0)))
    if stage is not None:
        parts.append(_STAGE_SCORE.get(stage, 60.0))
    return mean_ignoring_missing(parts)


def _growth(current: FinancialStatement, previous: Optional[FinancialStatement]) -> Number:
    if previous is None:
        return None
    parts = [
        scale(pct_change(current.revenue, previous.revenue), -0.10, 0.30),
        scale(pct_change(current.net_profit, previous.net_profit), -0.15, 0.40),
        scale(pct_change(current.ebitda, previous.ebitda), -0.15, 0.40),
    ]
    return mean_ignoring_missing(parts)


def _summary(key: str, status: str, score: Optional[int]) -> str:
    label = _LABELS[key]
    if status == UNAVAILABLE:
        if key == GROWTH:
            return f"{label} needs a prior period for year-over-year comparison."
        if key == BUSINESS_STABILITY:
            return f"{label} needs company profile inputs (age, size, stage)."
        return f"{label} could not be assessed from the available data."
    return f"{label} scores {score}/100 — {_STATUS_WORD[status]}."


def compute_health(
    statement: FinancialStatement,
    context: Optional[Mapping[str, Any]] = None,
    previous: Optional[FinancialStatement] = None,
) -> Dict[str, HealthScore]:
    """Compute all seven health dimensions.

    ``context`` optionally supplies company-profile inputs (``years_in_business``
    ``employee_count``, ``business_expansion_stage``) for business stability.
    ``previous`` optionally supplies the prior-period statement for growth.
    """
    raw = {
        LIQUIDITY: _liquidity(statement),
        PROFITABILITY: _profitability(statement),
        LEVERAGE: _leverage(statement),
        EFFICIENCY: _efficiency(statement),
        CASH_FLOW: _cash_flow(statement),
        BUSINESS_STABILITY: _business_stability(context),
        GROWTH: _growth(statement, previous),
    }

    scores: Dict[str, HealthScore] = {}
    for key, value in raw.items():
        score, status = _finalise(value)
        scores[key] = HealthScore(key, _LABELS[key], score, status, _summary(key, status, score))
    return scores


def overall_health(scores: Mapping[str, HealthScore]) -> HealthScore:
    """Weighted composite over the *available* dimensions."""
    weighted: List[Number] = []
    total_weight = 0.0
    acc = 0.0
    for key, weight in DIMENSION_WEIGHTS.items():
        hs = scores.get(key)
        if hs and hs.score is not None:
            acc += hs.score * weight
            total_weight += weight
    composite = acc / total_weight if total_weight else None
    score, status = _finalise(composite)
    summary = (
        "Overall financial health could not be assessed."
        if score is None
        else f"Overall financial health is {_STATUS_WORD[status]} at {score}/100."
    )
    return HealthScore("overall", "Overall Financial Health", score, status, summary)
