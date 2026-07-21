"""Automatic Insights Engine (Task 4).

Generates deterministic, rule-based financial observations — no LLM. Each
insight is a plain-language statement paired with an explicit *why* (the ratio
value and range that triggered it). Insights are derived from the computed
ratios and health scores, curated to the notable signals (the standout
strengths and the genuine concerns) rather than restating every metric.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Mapping, Optional, Sequence

from .health_engine import GROWTH, HealthScore
from .ratio_engine import Ratio

POSITIVE = "positive"
NEUTRAL = "neutral"
NEGATIVE = "negative"

# Ratios ranked by how much they matter to a credit view, so the curated list
# leads with the signals an analyst reads first.
_PRIORITY = {
    "dscr": 0, "interest_coverage": 1, "current_ratio": 2, "working_capital": 3,
    "operating_cash_flow_ratio": 4, "free_cash_flow": 5, "net_margin": 6,
    "debt_to_equity": 7, "debt_ratio": 8, "quick_ratio": 9,
}
_SEVERITY_RANK = {"critical": 0, "weak": 1, "excellent": 2, "good": 3, "moderate": 4}


@dataclass
class Insight:
    key: str
    title: str
    detail: str
    category: str
    sentiment: str

    def as_dict(self) -> dict:
        return {
            "key": self.key,
            "title": self.title,
            "detail": self.detail,
            "category": self.category,
            "sentiment": self.sentiment,
        }


def _title(ratio: Ratio) -> str:
    words = {
        "excellent": "is excellent",
        "weak": "is below recommended levels",
        "critical": "is a serious concern",
    }
    return f"{ratio.label} {words[ratio.status]}"


def _sentiment(status: str) -> str:
    if status in ("excellent", "good"):
        return POSITIVE
    if status in ("weak", "critical"):
        return NEGATIVE
    return NEUTRAL


def generate_insights(
    ratios: Sequence[Ratio],
    health: Optional[Mapping[str, HealthScore]] = None,
    max_insights: int = 12,
) -> List[Insight]:
    insights: List[Insight] = []

    # Growth is trend-derived; surface it first when a prior period existed.
    if health and GROWTH in health and health[GROWTH].score is not None:
        g = health[GROWTH]
        insights.append(
            Insight(
                key="growth",
                title=(
                    "Revenue and earnings growth is healthy"
                    if g.status in ("excellent", "good")
                    else "Growth is soft"
                ),
                detail=g.summary,
                category=GROWTH,
                sentiment=_sentiment(g.status),
            )
        )

    notable = [r for r in ratios if r.status in ("excellent", "weak", "critical")]
    notable.sort(key=lambda r: (_SEVERITY_RANK.get(r.status, 9), _PRIORITY.get(r.key, 99)))

    for ratio in notable:
        insights.append(
            Insight(
                key=ratio.key,
                title=_title(ratio),
                detail=ratio.interpretation,   # already carries the "why"
                category=ratio.category,
                sentiment=_sentiment(ratio.status),
            )
        )

    return insights[:max_insights]
