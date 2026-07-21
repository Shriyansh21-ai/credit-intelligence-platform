"""Early-warning rules.

Each rule is a pure function ``(features, engine_input) -> Optional[Alert]``.
A rule fires only when its signal is present and breaches a threshold; a missing
input never fabricates an alert. Severity escalates with the magnitude of the
breach.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Mapping, Optional

SEVERITY_PRIORITY = {"critical": 1, "high": 2, "medium": 3, "low": 4}
_TIMELINE = {
    "critical": "Immediate (0-7 days)",
    "high": "Near-term (within 30 days)",
    "medium": "This quarter",
    "low": "Routine monitoring",
}


@dataclass
class Alert:
    alert_type: str
    category: str
    severity: str
    title: str
    business_impact: str
    suggested_action: str
    evidence: Dict = field(default_factory=dict)

    @property
    def priority(self) -> int:
        return SEVERITY_PRIORITY.get(self.severity, 4)

    @property
    def timeline(self) -> str:
        return _TIMELINE.get(self.severity, "Routine monitoring")

    def as_dict(self) -> dict:
        return {
            "alert_type": self.alert_type,
            "category": self.category,
            "severity": self.severity,
            "priority": self.priority,
            "title": self.title,
            "business_impact": self.business_impact,
            "suggested_action": self.suggested_action,
            "timeline": self.timeline,
            "evidence": self.evidence,
        }


def _f(features: Mapping, name: str) -> Optional[float]:
    v = features.get(name)
    try:
        return None if v is None else float(v)
    except (TypeError, ValueError):
        return None


def _tier(value: float, thresholds) -> Optional[str]:
    """thresholds: ordered [(bound, severity), ...] most-severe first, for a
    'lower/higher than bound' breach already established by the caller."""
    for bound, severity in thresholds:
        if value <= bound:
            return severity
    return None


# ---------------------------------------------------------------------------
# Rules
# ---------------------------------------------------------------------------

def _revenue_decline(features, ei) -> Optional[Alert]:
    rg = _f(features, "revenue_growth")
    if rg is None or rg >= -0.05:
        return None
    severity = _tier(rg, [(-0.25, "critical"), (-0.15, "high"), (-0.05, "medium")])
    return Alert(
        "revenue_decline", "financial", severity,
        f"Revenue declined {abs(rg) * 100:.0f}% period-over-period",
        "Falling top line pressures debt-servicing capacity and covenant headroom.",
        "Review order book and pipeline; reassess facility sizing and covenants.",
        {"revenue_growth": round(rg, 4)},
    )


def _margin_deterioration(features, ei) -> Optional[Alert]:
    nmt = _f(features, "net_margin_trend")
    if nmt is None or nmt >= -0.02:
        return None
    severity = "high" if nmt < -0.05 else "medium"
    return Alert(
        "margin_deterioration", "financial", severity,
        "Net margin is deteriorating versus the prior period",
        "Margin compression erodes retained cash flow and repayment capacity.",
        "Investigate cost base and pricing; request an updated management P&L.",
        {"net_margin_trend": round(nmt, 4)},
    )


def _cash_flow_deterioration(features, ei) -> Optional[Alert]:
    ocfm = _f(features, "operating_cash_flow_margin")
    if ocfm is None or ocfm >= 0:
        return None
    severity = "critical" if ocfm < -0.05 else "high"
    return Alert(
        "cash_flow_deterioration", "cash_flow", severity,
        "Operating cash flow is negative",
        "The business is not self-funding operations; liquidity runway is shrinking.",
        "Obtain a 13-week cash-flow forecast; tighten monitoring and drawdown control.",
        {"operating_cash_flow_margin": round(ocfm, 4)},
    )


def _rising_leverage(features, ei) -> Optional[Alert]:
    dte = _f(features, "debt_to_ebitda")
    lt = _f(features, "leverage_trend")
    if dte is not None and dte >= 5.0:
        severity = "critical" if dte >= 7.0 else "high"
        return Alert(
            "rising_leverage", "leverage", severity,
            f"Leverage elevated at {dte:.1f}x Debt/EBITDA",
            "High leverage reduces resilience to earnings shocks and raises default risk.",
            "Reassess debt capacity; consider deleveraging covenants before new exposure.",
            {"debt_to_ebitda": round(dte, 4), "leverage_trend": lt},
        )
    if lt is not None and lt > 0.5:
        return Alert(
            "rising_leverage", "leverage", "medium",
            "Leverage is trending upward",
            "Increasing leverage signals deteriorating balance-sheet strength.",
            "Confirm the driver of new borrowing and its servicing plan.",
            {"leverage_trend": round(lt, 4)},
        )
    return None


def _weak_coverage(features, ei) -> Optional[Alert]:
    ic = _f(features, "interest_coverage")
    if ic is None or ic >= 1.5:
        return None
    severity = "critical" if ic < 1.0 else "high"
    return Alert(
        "weak_coverage", "leverage", severity,
        f"Interest coverage thin at {ic:.2f}x",
        "Earnings barely cover interest — a small shock could trigger a covenant breach.",
        "Stress-test coverage; require enhanced reporting and a remediation plan.",
        {"interest_coverage": round(ic, 4)},
    )


def _working_capital_erosion(features, ei) -> Optional[Alert]:
    wc = _f(features, "working_capital")
    if wc is None or wc >= 0:
        return None
    return Alert(
        "working_capital_erosion", "working_capital", "high",
        "Working capital is negative",
        "Negative working capital indicates potential short-term funding gaps.",
        "Review current-liability maturities and available liquidity lines.",
        {"working_capital": round(wc, 2)},
    )


def _liquidity_stress(features, ei) -> Optional[Alert]:
    cr = _f(features, "current_ratio")
    if cr is None or cr >= 1.0:
        return None
    severity = "critical" if cr < 0.8 else "high"
    return Alert(
        "liquidity_stress", "liquidity", severity,
        f"Current ratio below 1.0 ({cr:.2f}x)",
        "Short-term obligations exceed short-term assets; liquidity is stressed.",
        "Confirm access to committed lines; monitor daily cash position.",
        {"current_ratio": round(cr, 4)},
    )


def _compliance_issue(features, ei) -> Optional[Alert]:
    cs = _f(features, "compliance_score")
    if cs is None or cs >= 1.0:
        return None
    severity = "high" if cs < 0.5 else "medium"
    return Alert(
        "compliance_late_filings", "conduct", severity,
        "Tax / GST compliance is not fully clean",
        "Filing gaps can signal administrative stress and create regulatory risk.",
        "Request up-to-date filing evidence; flag for covenant compliance review.",
        {"compliance_score": round(cs, 4)},
    )


def _fraud_indicators(features, ei) -> Optional[Alert]:
    bounces = _f(features, "cheque_bounce_count")
    crr = _f(features, "cash_realization_ratio")
    if bounces is not None and bounces >= 3:
        return Alert(
            "fraud_indicators", "conduct", "high",
            f"{int(bounces)} cheque bounce(s) on record",
            "Repeated payment failures are a leading indicator of distress or misconduct.",
            "Escalate to credit control; verify banking conduct with the relationship bank.",
            {"cheque_bounce_count": int(bounces)},
        )
    # Profit reported but cash not realised -> earnings-quality / fraud red flag.
    if crr is not None and crr < 0:
        return Alert(
            "earnings_quality", "conduct", "high",
            "Reported profit is not converting to cash",
            "Divergence between profit and cash flow can indicate aggressive accounting.",
            "Reconcile earnings to cash; scrutinise receivables and revenue recognition.",
            {"cash_realization_ratio": round(crr, 4)},
        )
    return None


def _industry_decline(features, ei) -> Optional[Alert]:
    irs = _f(features, "industry_risk_score")
    if irs is None or irs < 0.85:
        return None
    return Alert(
        "industry_decline", "external", "medium",
        "Operating in a high-risk industry",
        "Sector headwinds raise correlated default risk across the exposure.",
        "Apply sector overlay; monitor industry leading indicators.",
        {"industry_risk_score": round(irs, 4)},
    )


def _prior_defaults(features, ei) -> Optional[Alert]:
    flag = _f(features, "prior_defaults_flag")
    if not flag:
        return None
    return Alert(
        "prior_defaults", "conduct", "critical",
        "Prior defaults on record",
        "A default history materially raises the probability of recurrence.",
        "Do not extend new credit without senior credit-committee sign-off.",
        {"prior_defaults_flag": 1},
    )


RuleFn = Callable[[Mapping, Mapping], Optional[Alert]]

RULES: List[RuleFn] = [
    _prior_defaults,
    _revenue_decline,
    _cash_flow_deterioration,
    _weak_coverage,
    _liquidity_stress,
    _rising_leverage,
    _working_capital_erosion,
    _margin_deterioration,
    _fraud_indicators,
    _compliance_issue,
    _industry_decline,
]
