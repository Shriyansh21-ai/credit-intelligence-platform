"""Explainer abstraction + shared explanation builder.

``BaseExplainer`` is the interface every explanation method (contribution / SHAP
/ LIME) implements. The heavy lifting — converting signed log-odds contributions
into PD-attributed, narrated, waterfall-ready :class:`Explanation` objects — is
shared here, so each explainer only has to *produce contributions*; the
presentation is identical across methods.
"""

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from typing import Dict, List, Mapping, Optional

from backend.app.services.enterprise_assessment import map_grade
from backend.app.services.ml.features.feature_registry import get_definition
from backend.app.services.ml.models.base import BaseRiskModel
from backend.app.services.ml.models.estimator import ESTIMATOR, pd_to_score

from .explanation import Explanation, FeatureContribution, WaterfallStep
from .narrative import feature_narrative, summary_narrative

Number = Optional[float]

_TOP_N = 5
_WATERFALL_N = 8

# Driver labels come from the estimator's weight table (authoritative labels).
_LABELS: Dict[str, str] = {w.feature: w.label for w in ESTIMATOR.weights}


def _sigmoid(x: float) -> float:
    if x >= 0:
        return 1.0 / (1.0 + math.exp(-x))
    z = math.exp(x)
    return z / (1.0 + z)


def _label(feature: str) -> str:
    return _LABELS.get(feature, feature.replace("_", " ").title())


def _unit(feature: str) -> str:
    defn = get_definition(feature)
    return defn.unit if defn else "ratio"


def build_explanation(
    *,
    model: BaseRiskModel,
    method: str,
    features: Mapping[str, Number],
    raw_contributions: Mapping[str, float],
    logit: float,
    probability_of_default: float,
    base_logit: Optional[float] = None,
) -> Explanation:
    """Assemble a full :class:`Explanation` from signed log-odds contributions.

    ``raw_contributions`` maps feature -> log-odds contribution; the mechanics of
    *how* they were derived (exact additive, SHAP, LIME) are the explainer's
    concern, not this builder's.

    ``base_logit`` is the model's neutral/expected-value log-odds. It defaults to
    the deterministic estimator's intercept (preserving the Phase 4 behaviour);
    trained-model explainers pass the SHAP expected value so the waterfall starts
    from the model's true base rate.
    """
    reference_logit = ESTIMATOR.intercept if base_logit is None else base_logit
    base_probability = _sigmoid(reference_logit)
    total_logit_delta = logit - reference_logit
    total_pd_delta = probability_of_default - base_probability

    contribs: List[FeatureContribution] = []
    for feature, contribution in raw_contributions.items():
        # Attribute the (non-linear) PD change proportionally to each feature's
        # (linear) log-odds share, so the parts sum exactly to the whole.
        if total_logit_delta:
            impact_pp = (contribution / total_logit_delta) * total_pd_delta * 100.0
        else:
            impact_pp = 0.0
        if contribution > 1e-9:
            direction = "increases_risk"
        elif contribution < -1e-9:
            direction = "reduces_risk"
        else:
            direction = "neutral"
        value = features.get(feature)
        unit = _unit(feature)
        label = _label(feature)
        contribs.append(FeatureContribution(
            feature=feature,
            label=label,
            value=None if value is None else float(value),
            unit=unit,
            contribution=contribution,
            impact_pp=impact_pp,
            direction=direction,
            narrative=feature_narrative(label, value, unit, impact_pp, direction),
        ))

    contribs.sort(key=lambda c: abs(c.contribution), reverse=True)
    top_positive = [c for c in contribs if c.direction == "increases_risk"][:_TOP_N]
    top_negative = [c for c in contribs if c.direction == "reduces_risk"][:_TOP_N]

    waterfall = _build_waterfall(base_probability, probability_of_default, contribs)

    risk_score = pd_to_score(probability_of_default)
    global_importance = _global_importance(model)

    return Explanation(
        model_type=model.model_metadata().model_type,
        method=method,
        probability_of_default=probability_of_default,
        base_probability=base_probability,
        risk_score=risk_score,
        risk_grade=map_grade(risk_score),
        contributions=contribs,
        top_positive=top_positive,
        top_negative=top_negative,
        waterfall=waterfall,
        global_importance=global_importance,
        summary=summary_narrative(probability_of_default, map_grade(risk_score),
                                  top_positive, top_negative),
    )


def _build_waterfall(base_pd: float, final_pd: float,
                     contribs: List[FeatureContribution]) -> List[WaterfallStep]:
    steps = [WaterfallStep(label="Base rate", impact_pp=0.0, cumulative_pd=base_pd)]
    cumulative = base_pd
    for c in contribs[:_WATERFALL_N]:
        cumulative += c.impact_pp / 100.0
        steps.append(WaterfallStep(label=c.label, impact_pp=c.impact_pp,
                                   cumulative_pd=cumulative))
    # Aggregate the remaining drivers so the waterfall ends exactly at final PD.
    remaining = final_pd - cumulative
    if abs(remaining) > 1e-9 and len(contribs) > _WATERFALL_N:
        steps.append(WaterfallStep(label="Other factors", impact_pp=remaining * 100.0,
                                   cumulative_pd=final_pd))
    else:
        steps.append(WaterfallStep(label="Final", impact_pp=0.0, cumulative_pd=final_pd))
    return steps


def _global_importance(model: BaseRiskModel, top_n: int = 10) -> List[dict]:
    importance = model.feature_importance()
    ranked = sorted(importance.items(), key=lambda kv: kv[1], reverse=True)[:top_n]
    return [
        {"feature": f, "label": _label(f), "importance": round(v, 6)}
        for f, v in ranked
    ]


class BaseExplainer(ABC):
    """Interface for an explanation method."""

    method: str = "base"

    @abstractmethod
    def explain(self, features: Mapping[str, Number], model: BaseRiskModel) -> Explanation:
        """Produce a full explanation for ``features`` under ``model``."""
