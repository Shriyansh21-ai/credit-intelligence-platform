"""M5 — Scenario Simulation Engine.

Re-scores a company under one or more what-if shocks and reports the new PD,
rating, recommended limit and recommendations, plus a side-by-side comparison
and financial impact. Deterministic elasticity model: each scenario maps its
magnitude to a bounded impact on the 300-900 credit score; the score change then
drives PD (calibrated), rating migration and limit sizing.

Composable — multiple scenarios combine additively (with diminishing returns via
score clamping), so "revenue drop + interest increase" is one run.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from backend.app.models.autonomous import SimulationRun
from . import data_access
from .common import clamp, pd_from_score, shift_rating

# Each scenario: label, unit ("fraction"|"pct"|"count"|"flag"), and a function
# magnitude -> score_delta (negative = worse). Score band is 300-900 (600 span).
SCENARIOS: Dict[str, Dict[str, Any]] = {
    "revenue_drop": {"label": "Revenue drop", "unit": "fraction",
                     "impact": lambda m: -min(m, 1.0) * 220},
    "interest_increase": {"label": "Interest rate increase", "unit": "fraction",
                          "impact": lambda m: -min(m, 0.5) * 240},
    "fx_movement": {"label": "Adverse FX movement", "unit": "fraction",
                    "impact": lambda m: -min(abs(m), 0.5) * 120},
    "commodity_price_change": {"label": "Commodity price change", "unit": "fraction",
                               "impact": lambda m: -min(abs(m), 1.0) * 100},
    "salary_increase": {"label": "Salary / wage increase", "unit": "fraction",
                        "impact": lambda m: -min(m, 0.5) * 90},
    "working_capital_delay": {"label": "Working capital delays", "unit": "days",
                              "impact": lambda m: -min(m, 180) / 180 * 130},
    "customer_default": {"label": "Key customer default", "unit": "fraction",
                         "impact": lambda m: -min(m, 1.0) * 180},
    "supplier_loss": {"label": "Supplier loss", "unit": "fraction",
                      "impact": lambda m: -min(m, 1.0) * 90},
    "market_recession": {"label": "Market recession", "unit": "severity",
                         "impact": lambda m: -min(m, 1.0) * 200},
    "new_loan_request": {"label": "New loan request", "unit": "fraction",
                         "impact": lambda m: -min(m, 2.0) * 70},
    "acquisition": {"label": "Acquisition", "unit": "fraction",
                    "impact": lambda m: -min(m, 1.0) * 60 + 15},
    "merger": {"label": "Merger", "unit": "fraction",
               "impact": lambda m: -min(m, 1.0) * 50 + 20},
}


def available_scenarios() -> List[Dict[str, Any]]:
    return [{"key": k, "label": v["label"], "unit": v["unit"]} for k, v in SCENARIOS.items()]


def _baseline(prof: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if prof:
        score = prof.get("credit_score") or 650
        pd = prof.get("pd")
        if pd is None:
            pd = pd_from_score(score)
        return {"credit_score": score, "pd": pd, "rating": prof.get("rating") or "BBB",
                "exposure": prof.get("exposure") or 0.0, "lgd": prof.get("lgd") or 0.45,
                "company_ref": prof.get("company_ref")}
    # neutral synthetic baseline when no assessment exists
    return {"credit_score": 650, "pd": pd_from_score(650), "rating": "BBB",
            "exposure": 0.0, "lgd": 0.45, "company_ref": None}


def simulate(db: Session, shocks: Dict[str, float], *, company_ref: Optional[str] = None,
             assessment_id: Optional[int] = None, user_id: Optional[int] = None,
             tenant_id: Optional[int] = None, persist: bool = True) -> Dict[str, Any]:
    """Apply ``shocks`` (``{scenario_key: magnitude}``) and return the new profile."""
    assessment = data_access.resolve(db, assessment_id=assessment_id, company_ref=company_ref)
    prof = data_access.profile(assessment)
    base = _baseline(prof)

    total_delta = 0.0
    applied: List[Dict[str, Any]] = []
    for key, magnitude in (shocks or {}).items():
        spec = SCENARIOS.get(key)
        if spec is None or magnitude is None:
            continue
        delta = float(spec["impact"](float(magnitude)))
        total_delta += delta
        applied.append({"scenario": key, "label": spec["label"], "magnitude": magnitude,
                        "score_impact": round(delta, 1)})

    new_score = int(clamp(base["credit_score"] + total_delta, 300, 900))
    new_pd = pd_from_score(new_score)
    # rating migration: ~1 notch per 60 score points of deterioration
    notches = int(round(-total_delta / 60)) if total_delta < 0 else int(round(-total_delta / 90))
    new_rating = shift_rating(base["rating"], notches)
    # limit sizing: scale inversely with PD growth (never increases on deterioration)
    pd_ratio = (base["pd"] / new_pd) if new_pd else 1.0
    new_limit = round((base["exposure"] or 0.0) * clamp(pd_ratio, 0.2, 1.5), 2)
    new_el = round(new_pd * (base["lgd"] or 0.45) * (new_limit or base["exposure"] or 0.0), 2)
    base_el = round(base["pd"] * (base["lgd"] or 0.45) * (base["exposure"] or 0.0), 2)

    result = {
        "credit_score": new_score, "pd": new_pd, "rating": new_rating,
        "recommended_limit": new_limit, "expected_loss": new_el,
    }
    baseline_out = {
        "credit_score": base["credit_score"], "pd": round(base["pd"], 4),
        "rating": base["rating"], "recommended_limit": base["exposure"],
        "expected_loss": base_el,
    }
    delta = {
        "score_change": new_score - base["credit_score"],
        "pd_change": round(new_pd - base["pd"], 4),
        "rating_notches": notches,
        "limit_change": round((new_limit or 0) - (base["exposure"] or 0), 2),
        "expected_loss_change": round(new_el - base_el, 2),
    }
    recommendations = _recommend(delta, new_rating)
    comparison = _comparison(baseline_out, result)

    out = {
        "company_ref": base["company_ref"] or company_ref,
        "scenario_types": list((shocks or {}).keys()), "shocks": shocks,
        "applied": applied, "baseline": baseline_out, "result": result,
        "delta": delta, "recommendations": recommendations, "comparison": comparison,
    }

    if persist:
        row = SimulationRun(tenant_id=tenant_id, user_id=user_id,
                            company_ref=out["company_ref"],
                            assessment_id=prof.get("assessment_id") if prof else assessment_id,
                            scenario_types=out["scenario_types"], shocks=shocks or {},
                            baseline=baseline_out, result=result, delta=delta)
        db.add(row)
        db.commit()
        db.refresh(row)
        out["id"] = row.id
    return out


def _recommend(delta: Dict[str, Any], rating: str) -> List[str]:
    recs = []
    if delta["score_change"] <= -100:
        recs.append("Severe deterioration — escalate to credit committee and freeze new exposure.")
    elif delta["score_change"] <= -40:
        recs.append("Material deterioration — reassess limit and tighten covenants.")
    if delta["rating_notches"] >= 2:
        recs.append(f"Rating migrates {delta['rating_notches']} notches to {rating}; reprice the facility.")
    if delta["limit_change"] < 0:
        recs.append(f"Reduce recommended limit by {abs(delta['limit_change']):,.0f}.")
    if not recs:
        recs.append("Impact is contained; maintain current terms with standard monitoring.")
    return recs


def _comparison(baseline: Dict[str, Any], result: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows = []
    for key, label in [("credit_score", "Credit score"), ("pd", "PD"),
                       ("rating", "Rating"), ("recommended_limit", "Recommended limit"),
                       ("expected_loss", "Expected loss")]:
        rows.append({"metric": label, "baseline": baseline.get(key), "stressed": result.get(key)})
    return rows


def get_run(db: Session, run_id: int) -> Optional[SimulationRun]:
    return db.query(SimulationRun).filter(SimulationRun.id == run_id).first()


def list_runs(db: Session, *, company_ref: Optional[str] = None, tenant_id: Optional[int] = None,
              limit: int = 50) -> List[SimulationRun]:
    q = db.query(SimulationRun).filter(SimulationRun.tenant_id == tenant_id)
    if company_ref:
        q = q.filter(SimulationRun.company_ref == company_ref)
    return q.order_by(SimulationRun.created_at.desc()).limit(limit).all()
