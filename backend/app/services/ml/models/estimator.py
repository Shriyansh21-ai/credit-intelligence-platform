"""Deterministic risk estimator — the explainable inference core.

Until real models are trained, every model in the engine shares this estimator
so predictions are **deterministic, monotonic and fully explainable** — never
random or fabricated. It is a transparent additive log-odds model:

    logit(PD) = intercept + Σ  wᵢ · dirᵢ · squash((xᵢ − centerᵢ) / scaleᵢ)

Each term is a signed contribution in log-odds space; risk-increasing features
push the logit up. Because the contributions are additive and exact, they double
as the ground truth for the explainability layer (Milestone 3) — no separate
SHAP approximation is needed for the placeholder model, and a trained model can
later expose true SHAP values through the same contribution contract.

Missing features contribute exactly zero: an absent signal never invents risk.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List, Mapping, Optional, Tuple

Number = Optional[float]

# Score band aligned with the enterprise scorecard (Phase 1).
SCORE_MIN, SCORE_MAX = 300, 900


@dataclass(frozen=True)
class Weight:
    """One feature's role in the risk model."""

    feature: str
    weight: float           # magnitude of influence (non-negative)
    direction: int          # +1 = higher value raises risk, -1 = lowers risk
    center: float           # neutral value (zero contribution)
    scale: float            # spread that maps to one standardised unit
    label: str              # human-facing driver label


# The reference risk driver set. Deliberately curated from the feature registry
# and grounded in commercial-lending intuition. Tuning happens here only.
_WEIGHTS: Tuple[Weight, ...] = (
    Weight("current_ratio", 0.45, -1, 1.5, 1.0, "Current Ratio"),
    Weight("quick_ratio", 0.35, -1, 1.0, 0.7, "Quick Ratio"),
    Weight("debt_to_equity", 0.55, +1, 1.5, 1.5, "Debt-to-Equity"),
    Weight("debt_ratio", 0.45, +1, 0.5, 0.3, "Debt Ratio"),
    Weight("debt_to_ebitda", 0.65, +1, 3.0, 2.5, "Debt / EBITDA"),
    Weight("interest_coverage", 0.60, -1, 4.0, 4.0, "Interest Coverage"),
    Weight("net_margin", 0.55, -1, 0.06, 0.10, "Net Profit Margin"),
    Weight("ebitda_margin", 0.45, -1, 0.12, 0.10, "EBITDA Margin"),
    Weight("return_on_equity", 0.40, -1, 0.12, 0.12, "Return on Equity"),
    Weight("operating_cash_flow_ratio", 0.55, -1, 0.60, 0.50, "Operating Cash Flow Ratio"),
    Weight("cash_flow_to_debt", 0.60, -1, 0.30, 0.30, "Cash Flow to Debt"),
    Weight("collateral_coverage", 0.70, -1, 1.50, 1.00, "Collateral Coverage"),
    Weight("working_capital_to_revenue", 0.35, -1, 0.15, 0.15, "Working Capital / Revenue"),
    Weight("revenue_growth", 0.40, -1, 0.05, 0.15, "Revenue Growth"),
    Weight("credit_utilization", 0.40, +1, 40.0, 30.0, "Credit Utilisation"),
    Weight("emi_to_inflow", 0.45, +1, 0.20, 0.20, "EMI Burden on Inflow"),
    Weight("prior_defaults_flag", 1.20, +1, 0.0, 1.0, "Prior Defaults"),
    Weight("industry_risk_score", 0.45, +1, 0.50, 0.30, "Industry Risk"),
    Weight("geographical_risk_score", 0.25, +1, 0.40, 0.30, "Geographic Risk"),
    Weight("customer_concentration_score", 0.35, +1, 0.50, 0.30, "Customer Concentration"),
    Weight("compliance_score", 0.55, -1, 1.00, 0.50, "Tax / GST Compliance"),
    Weight("expansion_stage_score", 0.30, -1, 0.70, 0.30, "Business Lifecycle Stage"),
    Weight("years_in_business", 0.30, -1, 8.0, 8.0, "Years in Business"),
)

# Baseline log-odds at an all-neutral profile -> PD ≈ sigmoid(-1.6) ≈ 16.6%.
_INTERCEPT = -1.6

# Clamp standardised deviations so a single extreme input can't dominate.
_Z_CLAMP = 3.0


def _sigmoid(x: float) -> float:
    if x >= 0:
        z = math.exp(-x)
        return 1.0 / (1.0 + z)
    z = math.exp(x)
    return z / (1.0 + z)


def _squash(z: float) -> float:
    return max(-_Z_CLAMP, min(_Z_CLAMP, z))


@dataclass
class EstimatorResult:
    probability_of_default: float
    logit: float
    contributions: Dict[str, float]      # feature_name -> signed log-odds contribution
    driver_labels: Dict[str, str]


class DeterministicRiskEstimator:
    """Additive log-odds risk estimator over registry features."""

    weights: Tuple[Weight, ...] = _WEIGHTS
    intercept: float = _INTERCEPT

    def contributions(self, features: Mapping[str, Number]) -> EstimatorResult:
        contribs: Dict[str, float] = {}
        labels: Dict[str, str] = {}
        logit = self.intercept
        for w in self.weights:
            value = features.get(w.feature)
            if value is None:
                continue
            z = _squash((float(value) - w.center) / w.scale) if w.scale else 0.0
            contribution = w.weight * w.direction * z
            contribs[w.feature] = contribution
            labels[w.feature] = w.label
            logit += contribution
        return EstimatorResult(
            probability_of_default=_sigmoid(logit),
            logit=logit,
            contributions=contribs,
            driver_labels=labels,
        )

    def probability_of_default(self, features: Mapping[str, Number]) -> float:
        return self.contributions(features).probability_of_default

    def global_importance(self) -> Dict[str, float]:
        """Model-level importances: the absolute influence weight of each driver,
        normalised to sum to 1. Deterministic and independent of any single
        borrower — the placeholder analogue of a trained model's importances."""
        total = sum(abs(w.weight) for w in self.weights) or 1.0
        return {w.feature: abs(w.weight) / total for w in self.weights}


def pd_to_score(probability_of_default: float) -> int:
    """Map PD to the 300-900 credit-score band (monotonic, lower PD = higher
    score)."""
    creditworthiness = 1.0 - max(0.0, min(1.0, probability_of_default))
    score = SCORE_MIN + creditworthiness * (SCORE_MAX - SCORE_MIN)
    return int(round(max(SCORE_MIN, min(SCORE_MAX, score))))


# Shared singleton — the estimator is stateless.
ESTIMATOR = DeterministicRiskEstimator()
