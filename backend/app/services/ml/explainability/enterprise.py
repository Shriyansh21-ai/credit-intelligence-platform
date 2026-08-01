"""Enterprise Explainable AI.

Extends the explanation builder to trained models and adds the
enterprise-grade explainability surface the brief requires

* SHAP — genuine mean-|SHAP| global importance for tree models, with a
  documented fall-back to native importances when SHAP is unavailable.
* Waterfall, decision path, top positive / negative factors — reused from the
  shared :func:`build_explanation` presentation layer.
* Reason codes — adverse-action-style codes derived from the risk-increasing
  drivers, suitable for regulated declines.
* Three narrative tiers — an executive summary, an analyst explanation and a
  business-friendly explanation.

Explanations are persisted to :class:`MLExplanation` so every decision is
auditable and reproducible.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Mapping, Optional

from backend.app.services.ml.models.base import BaseRiskModel
from backend.app.services.ml.models.estimator import ESTIMATOR

from .base import build_explanation
from .explanation import Explanation

_EPS = 1e-9


def _logit(p: float) -> float:
    p = min(1 - _EPS, max(_EPS, p))
    return math.log(p / (1 - p))


# ---------------------------------------------------------------------------
# Trained-model explanation
# ---------------------------------------------------------------------------

def explain_model(features: Mapping[str, Any], model: BaseRiskModel) -> Explanation:
    """Build an :class:`Explanation` for any model (trained or deterministic).

    Trained models are attributed with their own baseline-relative log-odds
    decomposition (the ``_local_contributions`` substrate) and, where possible
    their SHAP global importances; deterministic models fall through to the exact
    additive estimator contributions.
    """
    local = getattr(model, "_local_contributions", None)
    if callable(local):
        pd = model.predict_proba(features)[1]
        contributions = local(features)
        baseline = {name: model._baseline.get(name, 0.0) for name in model._feature_names}
        base_logit = _logit(model.predict_proba(baseline)[1])
        explanation = build_explanation(
            model=model,
            method="trained_logodds_attribution",
            features=features,
            raw_contributions=contributions,
            logit=_logit(pd),
            probability_of_default=pd,
            base_logit=base_logit,
        )
        # Prefer genuine SHAP global importance when the model can provide it.
        shap_importance = getattr(model, "shap_global_importance", lambda: None)()
        if shap_importance:
            explanation.method = "shap"
            explanation.global_importance = _rank_importance(shap_importance)
        return explanation

    # Deterministic estimator: exact additive contributions.
    result = ESTIMATOR.contributions(features)
    return build_explanation(
        model=model,
        method="contribution",
        features=features,
        raw_contributions=result.contributions,
        logit=result.logit,
        probability_of_default=result.probability_of_default,
    )


def _rank_importance(importance: Dict[str, float], top_n: int = 12) -> List[dict]:
    from .base import _label
    ranked = sorted(importance.items(), key=lambda kv: kv[1], reverse=True)[:top_n]
    return [{"feature": f, "label": _label(f), "importance": round(v, 6)} for f, v in ranked]


# ---------------------------------------------------------------------------
# Reason codes
# ---------------------------------------------------------------------------

def reason_codes(explanation: Explanation, *, max_codes: int = 5) -> List[dict]:
    """Adverse-action-style reason codes from the risk-increasing drivers."""
    codes: List[dict] = []
    for i, contrib in enumerate(explanation.top_positive[:max_codes], start=1):
        codes.append({
            "code": f"RC{i:02d}",
            "factor": contrib.feature,
            "label": contrib.label,
            "value": contrib.value,
            "impact_pp": round(contrib.impact_pp, 4),
            "severity": _severity(contrib.impact_pp),
            "statement": f"{contrib.label} contributed adversely to the risk assessment.",
        })
    return codes


def _severity(impact_pp: float) -> str:
    magnitude = abs(impact_pp)
    if magnitude >= 8.0:
        return "high"
    if magnitude >= 3.0:
        return "moderate"
    return "low"


# ---------------------------------------------------------------------------
# Narrative tiers
# ---------------------------------------------------------------------------

def _decision(explanation: Explanation) -> str:
    pd = explanation.probability_of_default
    if pd < 0.10:
        return "approve"
    if pd < 0.20:
        return "approve with conditions"
    if pd < 0.35:
        return "refer for senior review"
    return "decline / restructure"


def executive_summary(explanation: Explanation) -> str:
    pd_pct = explanation.probability_of_default * 100.0
    lead = explanation.top_positive[0].label if explanation.top_positive else "no single dominant risk factor"
    strength = explanation.top_negative[0].label if explanation.top_negative else "limited mitigating strength"
    return (
        f"Recommended action: {_decision(explanation)}. Estimated probability of "
        f"default is {pd_pct:.1f}% (risk grade {explanation.risk_grade}, score "
        f"{explanation.risk_score}). The assessment is driven chiefly by {lead}, "
        f"partially offset by {strength}."
    )


def analyst_explanation(explanation: Explanation) -> str:
    lines: List[str] = [
        f"Model: {explanation.model_type} ({explanation.method}). "
        f"PD {explanation.probability_of_default * 100:.1f}%, grade "
        f"{explanation.risk_grade}, score {explanation.risk_score}.",
    ]
    if explanation.top_positive:
        lines.append("Principal risk-increasing factors:")
        for c in explanation.top_positive:
            lines.append(f"  • {c.label}: {c.impact_pp:+.2f} pp — {c.narrative}")
    if explanation.top_negative:
        lines.append("Principal risk-reducing factors:")
        for c in explanation.top_negative:
            lines.append(f"  • {c.label}: {c.impact_pp:+.2f} pp — {c.narrative}")
    return "\n".join(lines)


def business_summary(explanation: Explanation) -> str:
    pos = ", ".join(c.label for c in explanation.top_positive[:3]) or "no major concerns"
    neg = ", ".join(c.label for c in explanation.top_negative[:3]) or "few offsetting strengths"
    return (
        f"This assessment reflects an estimated repayment risk of "
        f"{explanation.probability_of_default * 100:.0f}%. The areas weighing most "
        f"on the outcome are {pos}. Working in the applicant's favour are {neg}. "
        f"Strengthening the weaker areas would improve the risk profile."
    )


def enterprise_payload(explanation: Explanation) -> Dict[str, Any]:
    """Full explainability payload: presentation + reason codes + narratives."""
    payload = explanation.as_dict()
    payload["reason_codes"] = reason_codes(explanation)
    payload["decision_recommendation"] = _decision(explanation)
    payload["narratives"] = {
        "executive_summary": executive_summary(explanation),
        "analyst_explanation": analyst_explanation(explanation),
        "business_summary": business_summary(explanation),
    }
    # Decision path: cumulative waterfall already encodes it; surface explicitly.
    payload["decision_path"] = [
        {"step": i, "label": w["label"], "cumulative_pd": w["cumulative_pd"]}
        for i, w in enumerate(payload.get("waterfall", []))
    ]
    return payload
