"""Explanation data structures.

A single :class:`Explanation` captures everything a credit analyst needs to
understand *why* a borrower received its risk assessment, in a stable,
serialisable shape shared by the service, the persistence layer and the API.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class FeatureContribution:
    """One feature's attributed effect on the prediction."""

    feature: str
    label: str
    value: Optional[float]
    unit: str
    # Signed contribution in log-odds space (risk-increasing > 0).
    contribution: float
    # Signed change in probability of default attributed to this feature,
    # expressed in percentage points (risk-increasing > 0).
    impact_pp: float
    direction: str          # "increases_risk" | "reduces_risk" | "neutral"
    narrative: str

    def as_dict(self) -> dict:
        return {
            "feature": self.feature,
            "label": self.label,
            "value": None if self.value is None else round(self.value, 6),
            "unit": self.unit,
            "contribution": round(self.contribution, 6),
            "impact_pp": round(self.impact_pp, 4),
            "direction": self.direction,
            "narrative": self.narrative,
        }


@dataclass
class WaterfallStep:
    """One step of the base-rate -> final-PD waterfall."""

    label: str
    impact_pp: float
    cumulative_pd: float

    def as_dict(self) -> dict:
        return {
            "label": self.label,
            "impact_pp": round(self.impact_pp, 4),
            "cumulative_pd": round(self.cumulative_pd, 6),
        }


@dataclass
class Explanation:
    model_type: str
    method: str
    probability_of_default: float
    base_probability: float           # the all-neutral base rate
    risk_score: int
    risk_grade: str
    contributions: List[FeatureContribution] = field(default_factory=list)
    top_positive: List[FeatureContribution] = field(default_factory=list)
    top_negative: List[FeatureContribution] = field(default_factory=list)
    waterfall: List[WaterfallStep] = field(default_factory=list)
    global_importance: List[dict] = field(default_factory=list)
    summary: str = ""

    def as_dict(self) -> dict:
        return {
            "model_type": self.model_type,
            "method": self.method,
            "probability_of_default": round(self.probability_of_default, 6),
            "base_probability": round(self.base_probability, 6),
            "risk_score": self.risk_score,
            "risk_grade": self.risk_grade,
            "summary": self.summary,
            "contributions": [c.as_dict() for c in self.contributions],
            "top_positive_contributors": [c.as_dict() for c in self.top_positive],
            "top_negative_contributors": [c.as_dict() for c in self.top_negative],
            "waterfall": [w.as_dict() for w in self.waterfall],
            "global_importance": self.global_importance,
        }
