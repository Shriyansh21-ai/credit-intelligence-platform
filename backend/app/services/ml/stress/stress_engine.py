"""Stress-test engine — regulatory cases + comparisons.

Combines the selected macro scenarios into the four supervisory cases and, for
each scenario, its per-severity impact. All computation goes through the
scenario engine's deterministic snapshot, so results are reproducible.
"""

from __future__ import annotations

from typing import Any, List, Mapping, Optional

from backend.app.services.ml.scenario.factors import apply_adjustments
from backend.app.services.ml.scenario.scenario_engine import _delta, snapshot

from .scenarios import CASES, STRESS_SCENARIOS


def _combined_adjustments(scenarios, case: str) -> List[dict]:
    combined: List[dict] = []
    for scn in scenarios:
        combined.extend(scn.severities.get(case, []))
    return combined


def _case_result(engine_input: Mapping[str, Any], adjustments: List[dict],
                 baseline: dict, model_type: Optional[str]) -> dict:
    adjusted = apply_adjustments(dict(engine_input), adjustments)
    snap = snapshot(adjusted, model_type=model_type)
    return {"snapshot": snap, "delta": _delta(baseline, snap)}


def run_stress_test(
    engine_input: Mapping[str, Any],
    scenario_names: Optional[List[str]] = None,
    model_type: Optional[str] = None,
) -> dict:
    """Run a full stress test and return cases, per-scenario detail and
    comparison series."""
    if scenario_names:
        selected = [STRESS_SCENARIOS[n] for n in scenario_names if n in STRESS_SCENARIOS]
    else:
        selected = list(STRESS_SCENARIOS.values())
    if not selected:
        selected = list(STRESS_SCENARIOS.values())

    baseline = snapshot(engine_input, model_type=model_type)

    # The four supervisory cases (base = no shock).
    cases = {"base": {"snapshot": baseline, "delta": _delta(baseline, baseline)}}
    for case in CASES:
        adjustments = _combined_adjustments(selected, case)
        cases[case] = _case_result(engine_input, adjustments, baseline, model_type)

    # Per-scenario, per-severity detail (for scenario-comparison charts).
    per_scenario = []
    for scn in selected:
        scn_cases = {
            case: _case_result(engine_input, scn.severities.get(case, []), baseline, model_type)
            for case in CASES
        }
        per_scenario.append({
            "name": scn.name,
            "label": scn.label,
            "description": scn.description,
            "cases": scn_cases,
        })

    comparison = _build_comparison(cases, per_scenario)

    return {
        "base_case": cases["base"],
        "optimistic_case": cases["optimistic"],
        "expected_case": cases["expected"],
        "worst_case": cases["worst"],
        "scenarios": per_scenario,
        "comparison": comparison,
    }


def _build_comparison(cases: dict, per_scenario: list) -> dict:
    order = ("base", "optimistic", "expected", "worst")
    metric_keys = (
        "enterprise_credit_score", "probability_of_default", "expected_loss",
        "loss_given_default",
    )
    case_series = {
        metric: [
            {"case": case, "value": cases[case]["snapshot"][metric]}
            for case in order
        ]
        for metric in metric_keys
    }
    case_series["decision"] = [
        {"case": case, "value": cases[case]["snapshot"]["decision"]} for case in order
    ]
    case_series["health_scores"] = [
        {"case": case, "value": cases[case]["snapshot"]["health_scores"]} for case in order
    ]

    # Worst-case impact ranked by scenario (which macro shock hurts most).
    by_scenario = sorted(
        (
            {
                "scenario": s["name"],
                "label": s["label"],
                "worst_probability_of_default": s["cases"]["worst"]["snapshot"]["probability_of_default"],
                "worst_expected_loss": s["cases"]["worst"]["snapshot"]["expected_loss"],
                "worst_score": s["cases"]["worst"]["snapshot"]["enterprise_credit_score"],
                "score_impact": s["cases"]["worst"]["delta"].get("enterprise_credit_score", 0),
            }
            for s in per_scenario
        ),
        key=lambda x: x["worst_expected_loss"],
        reverse=True,
    )

    return {"by_case": case_series, "by_scenario": by_scenario}
