"""Scenario engine — recompute the full risk picture under adjustments.

Reuses the established, explainable engines
* the Phase-1 enterprise scorecard (score, PD, LGD, EL, health, recommendation
  loan sizing and pricing), and
* the Phase-4 ML estimator (a second, feature-based PD signal + contributions).

A scenario returns the baseline snapshot, the adjusted snapshot and the delta
between them, so the frontend can render an instant before/after without a
page refresh.
"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional

from backend.app.services.enterprise_assessment import evaluate_enterprise_assessment
from backend.app.services.ml.features import feature_pipeline
from backend.app.services.ml.inference import run_inference

from .factors import FACTORS, apply_adjustments

# Health dimensions the scorecard exposes.
_HEALTH_KEYS = (
    "liquidity_health", "debt_health", "working_capital_health", "business_stability",
)


def available_factors() -> List[dict]:
    """Metadata for every scenario factor — powers the simulator UI controls."""
    return [
        {"factor": f.name, "label": f.label, "description": f.description,
         "value_unit": f.value_unit}
        for f in FACTORS.values()
    ]


def snapshot(engine_input: Mapping[str, Any], model_type: Optional[str] = None) -> dict:
    """Compute a compact risk snapshot for one set of inputs."""
    result = evaluate_enterprise_assessment(dict(engine_input))
    health = result.get("health_metrics", {})
    vector = feature_pipeline.build_from_engine_input(dict(engine_input))
    ml_pred = run_inference(vector, model_type=model_type)

    return {
        "enterprise_credit_score": result["enterprise_credit_score"],
        "risk_grade": result["risk_rating"],
        "probability_of_default": result["probability_of_default"],
        "loss_given_default": result["loss_given_default"],
        "expected_loss": result["expected_loss"],
        "recommended_loan_amount": result["summary"]["recommended_loan_amount"],
        "recommended_interest_rate": result["summary"]["recommended_interest_rate"],
        "decision": result["recommendation"]["decision"],
        "health_scores": {k: (health.get(k) or {}).get("score") for k in _HEALTH_KEYS},
        "ml_probability_of_default": round(ml_pred.probability_of_default, 6),
    }


def _delta(base: dict, scen: dict) -> dict:
    numeric_keys = (
        "enterprise_credit_score", "probability_of_default", "loss_given_default",
        "expected_loss", "recommended_loan_amount", "recommended_interest_rate",
        "ml_probability_of_default",
    )
    deltas = {
        key: round(scen[key] - base[key], 6)
        for key in numeric_keys
        if isinstance(base.get(key), (int, float)) and isinstance(scen.get(key), (int, float))
    }
    deltas["risk_grade_changed"] = base["risk_grade"] != scen["risk_grade"]
    deltas["decision_changed"] = base["decision"] != scen["decision"]
    deltas["health_scores"] = {
        k: (
            (scen["health_scores"].get(k) or 0) - (base["health_scores"].get(k) or 0)
        )
        for k in _HEALTH_KEYS
    }
    return deltas


def simulate(
    engine_input: Mapping[str, Any],
    adjustments: List[Dict],
    model_type: Optional[str] = None,
) -> dict:
    """Run a single what-if scenario and return baseline / scenario / delta."""
    baseline = snapshot(engine_input, model_type=model_type)
    adjusted_input = apply_adjustments(dict(engine_input), adjustments)
    scenario = snapshot(adjusted_input, model_type=model_type)
    return {
        "adjustments": adjustments,
        "baseline": baseline,
        "scenario": scenario,
        "delta": _delta(baseline, scenario),
    }


def simulate_many(
    engine_input: Mapping[str, Any],
    adjustment_sets: List[List[Dict]],
    model_type: Optional[str] = None,
) -> dict:
    """Run many adjustment sets against one baseline.

    This is the substrate for future Monte-Carlo simulation: a sampler produces
    ``adjustment_sets`` from factor distributions and this returns one scenario
    per draw, sharing a single baseline computation.
    """
    baseline = snapshot(engine_input, model_type=model_type)
    scenarios = []
    for adjustments in adjustment_sets:
        adjusted_input = apply_adjustments(dict(engine_input), adjustments)
        scen = snapshot(adjusted_input, model_type=model_type)
        scenarios.append({
            "adjustments": adjustments,
            "scenario": scen,
            "delta": _delta(baseline, scen),
        })
    return {"baseline": baseline, "scenarios": scenarios}
