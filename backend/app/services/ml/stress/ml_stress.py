"""ML-driven Stress Testing (Phase 6, Milestone 12).

Applies macroeconomic scenarios directly to model features, re-scores the book
through the trained model, and measures the model-predicted portfolio impact —
a complement to the deterministic Phase 4 stress engine (:mod:`stress_engine`),
which shocks raw financials.

A scenario is a set of feature operations (additive or multiplicative shifts)
scaled by a severity. Re-scoring the stressed features gives the change in
portfolio default rate and expected loss under each scenario/severity — exactly
the shape of a supervisory stress test.
"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional

from sqlalchemy.orm import Session

from backend.app.services.ml.portfolio.ml_portfolio import portfolio_metrics, score_positions

# Severity multipliers applied to each scenario's shock magnitudes.
SEVERITIES = {"optimistic": 0.4, "expected": 1.0, "worst": 1.8}

# Feature clamps so a shock never pushes a value out of its plausible range.
_UNIT_INTERVAL = {"industry_risk_score", "geographical_risk_score",
                  "customer_concentration_score", "compliance_score", "expansion_stage_score"}


def _op(feature: str, kind: str, value: float) -> Dict[str, Any]:
    return {"feature": feature, "op": kind, "value": value}


# Macro scenarios → feature shocks (calibrated at the "expected" severity).
MACRO_SCENARIOS: Dict[str, Dict[str, Any]] = {
    "gdp_decline": {
        "label": "GDP Decline",
        "description": "Broad output contraction depressing growth and earnings.",
        "shocks": [_op("revenue_growth", "add", -0.15), _op("net_margin", "mul", 0.70),
                   _op("interest_coverage", "mul", 0.75), _op("operating_cash_flow_ratio", "mul", 0.80)],
    },
    "interest_rate_hike": {
        "label": "Interest Rate Hike",
        "description": "Higher borrowing costs eroding debt-service capacity.",
        "shocks": [_op("interest_coverage", "mul", 0.60), _op("debt_to_ebitda", "mul", 1.30),
                   _op("emi_to_inflow", "mul", 1.40), _op("cash_flow_to_debt", "mul", 0.80)],
    },
    "inflation": {
        "label": "Inflation Shock",
        "description": "Sustained cost inflation compressing operating margins.",
        "shocks": [_op("net_margin", "add", -0.05), _op("ebitda_margin", "add", -0.05),
                   _op("operating_cash_flow_ratio", "mul", 0.85)],
    },
    "currency_depreciation": {
        "label": "Currency Depreciation",
        "description": "FX weakness lifting import costs and FX-linked leverage.",
        "shocks": [_op("net_margin", "add", -0.04), _op("debt_to_ebitda", "mul", 1.20),
                   _op("ebitda_margin", "add", -0.03)],
    },
    "sector_downturn": {
        "label": "Sector Downturn",
        "description": "Industry-wide revenue softness and elevated sector risk.",
        "shocks": [_op("industry_risk_score", "add", 0.25), _op("revenue_growth", "add", -0.12),
                   _op("net_margin", "mul", 0.80)],
    },
    "supply_chain_disruption": {
        "label": "Supply Chain Disruption",
        "description": "Input disruption draining cash and working capital.",
        "shocks": [_op("operating_cash_flow_ratio", "mul", 0.70), _op("cash_flow_to_debt", "mul", 0.70),
                   _op("working_capital_to_revenue", "mul", 0.70)],
    },
    "commodity_shock": {
        "label": "Commodity Shock",
        "description": "Input-cost spike compressing gross and EBITDA margins.",
        "shocks": [_op("ebitda_margin", "add", -0.06), _op("net_margin", "add", -0.05),
                   _op("interest_coverage", "mul", 0.85)],
    },
}


def available_scenarios() -> List[dict]:
    return [{"name": k, "label": v["label"], "description": v["description"]}
            for k, v in MACRO_SCENARIOS.items()]


def apply_scenario(features: Mapping[str, Any], scenario: str, severity: str = "expected") -> Dict[str, Any]:
    """Return a shocked copy of ``features`` under ``scenario`` at ``severity``."""
    if scenario not in MACRO_SCENARIOS:
        raise ValueError(f"Unknown scenario '{scenario}'. Available: {list(MACRO_SCENARIOS)}")
    scale = SEVERITIES.get(severity, 1.0)
    shocked = dict(features)
    for op in MACRO_SCENARIOS[scenario]["shocks"]:
        feature, kind, value = op["feature"], op["op"], op["value"]
        current = features.get(feature)
        if current is None:
            continue
        current = float(current)
        if kind == "add":
            new_value = current + value * scale
        else:  # multiplicative: scale the deviation from 1 by severity
            new_value = current * (1.0 + (value - 1.0) * scale)
        if feature in _UNIT_INTERVAL:
            new_value = max(0.0, min(1.0, new_value))
        shocked[feature] = new_value
    return shocked


def stress_portfolio(
    db: Session,
    positions: List[Mapping[str, Any]],
    scenario: str,
    *,
    severities: Optional[List[str]] = None,
    model_id: Optional[int] = None,
    model_key: Optional[str] = None,
) -> Dict[str, Any]:
    """Stress a portfolio under one scenario across severities."""
    severities = severities or ["optimistic", "expected", "worst"]
    baseline = portfolio_metrics(score_positions(db, positions, model_id=model_id, model_key=model_key))

    results: List[Dict[str, Any]] = []
    for severity in severities:
        stressed_positions = [
            {**(p if isinstance(p, Mapping) else {"features": p}),
             "features": apply_scenario(
                 (p.get("features", p) if isinstance(p, Mapping) else p), scenario, severity)}
            for p in positions
        ]
        metrics = portfolio_metrics(score_positions(db, stressed_positions, model_id=model_id, model_key=model_key))
        results.append({
            "severity": severity,
            "metrics": metrics,
            "impact": _impact(baseline, metrics),
        })
    return {
        "scenario": scenario,
        "label": MACRO_SCENARIOS[scenario]["label"],
        "baseline": baseline,
        "cases": results,
    }


def stress_all(
    db: Session,
    positions: List[Mapping[str, Any]],
    *,
    severity: str = "worst",
    model_id: Optional[int] = None,
    model_key: Optional[str] = None,
) -> Dict[str, Any]:
    """Run every macro scenario at one severity and rank by portfolio impact."""
    baseline = portfolio_metrics(score_positions(db, positions, model_id=model_id, model_key=model_key))
    scenarios = []
    for name in MACRO_SCENARIOS:
        stressed_positions = [
            {**(p if isinstance(p, Mapping) else {"features": p}),
             "features": apply_scenario(
                 (p.get("features", p) if isinstance(p, Mapping) else p), name, severity)}
            for p in positions
        ]
        metrics = portfolio_metrics(score_positions(db, stressed_positions, model_id=model_id, model_key=model_key))
        scenarios.append({
            "scenario": name, "label": MACRO_SCENARIOS[name]["label"],
            "metrics": metrics, "impact": _impact(baseline, metrics),
        })
    scenarios.sort(key=lambda s: s["impact"].get("expected_loss_change", 0) or 0, reverse=True)
    return {"severity": severity, "baseline": baseline, "scenarios": scenarios}


def _impact(baseline: Dict[str, Any], stressed: Dict[str, Any]) -> Dict[str, Any]:
    def delta(key):
        b, s = baseline.get(key), stressed.get(key)
        if b is None or s is None:
            return None
        return round(s - b, 6)
    return {
        "default_rate_change": delta("portfolio_default_rate"),
        "average_pd_change": delta("average_pd"),
        "expected_loss_change": delta("expected_loss"),
        "expected_loss_rate_change": delta("expected_loss_rate"),
        "expected_loss_multiplier": (
            round(stressed["expected_loss"] / baseline["expected_loss"], 4)
            if baseline.get("expected_loss") else None
        ),
    }
