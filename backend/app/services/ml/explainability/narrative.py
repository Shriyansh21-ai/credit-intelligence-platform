"""Plain-language narratives for explanations.

Produces the analyst-/business-facing sentences the phase brief calls for, e.g.
"Debt Service Coverage reduced overall risk by 11%." Impacts are expressed as
signed changes in probability of default (in percentage points).
"""

from __future__ import annotations

from typing import List, Optional


def _fmt_value(value: Optional[float], unit: str) -> str:
    if value is None:
        return "n/a"
    if unit == "percent":
        return f"{value * 100:.1f}%"
    if unit == "currency":
        return f"{value:,.0f}"
    if unit == "days":
        return f"{value:.0f} days"
    if unit == "count":
        return f"{value:.0f}"
    if unit == "years":
        return f"{value:.0f} yrs"
    if unit == "score":
        return f"{value:.2f}"
    return f"{value:.2f}"


def feature_narrative(label: str, value: Optional[float], unit: str,
                      impact_pp: float, direction: str) -> str:
    magnitude = abs(impact_pp)
    at = f" (at {_fmt_value(value, unit)})" if value is not None else ""
    if direction == "reduces_risk":
        return f"{label}{at} reduced overall risk by {magnitude:.1f}%."
    if direction == "increases_risk":
        return f"{label}{at} increased overall risk by {magnitude:.1f}%."
    return f"{label}{at} had no material effect on risk."


def summary_narrative(pd: float, grade: str, top_positive: List, top_negative: List) -> str:
    parts = [
        f"Estimated probability of default is {pd * 100:.2f}% (grade {grade})."
    ]
    if top_negative:
        parts.append(
            f"The strongest mitigant is {top_negative[0].label}, "
            f"lowering risk by {abs(top_negative[0].impact_pp):.1f}%."
        )
    if top_positive:
        parts.append(
            f"The primary concern is {top_positive[0].label}, "
            f"raising risk by {abs(top_positive[0].impact_pp):.1f}%."
        )
    return " ".join(parts)
