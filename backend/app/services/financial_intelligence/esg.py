"""M5 — Climate & ESG Intelligence.

Enterprise ESG platform: environmental / social / governance scoring, carbon
exposure & industry emissions, transition and physical climate risk, green-
financing eligibility, sustainable-lending signals, climate stress testing and
portfolio ESG analytics — with actionable ESG recommendations. Deterministic and
grounded in industry emission factors plus company profile signals.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from backend.app.models.financial_intelligence import FinESGAssessment
from . import data_access as da
from .common import checksum, clamp, grounding_block, iso, pct, safe_div, to_float, utcnow

# Industry carbon intensity (tCO2e per INR mn revenue) & transition exposure (0-1).
INDUSTRY_EMISSIONS: Dict[str, Dict[str, float]] = {
    "energy": {"intensity": 45.0, "transition": 0.90, "physical": 0.55},
    "utilities": {"intensity": 38.0, "transition": 0.80, "physical": 0.50},
    "cement": {"intensity": 42.0, "transition": 0.85, "physical": 0.45},
    "steel": {"intensity": 40.0, "transition": 0.82, "physical": 0.45},
    "manufacturing": {"intensity": 18.0, "transition": 0.55, "physical": 0.40},
    "transport": {"intensity": 25.0, "transition": 0.70, "physical": 0.50},
    "agriculture": {"intensity": 22.0, "transition": 0.45, "physical": 0.80},
    "textiles": {"intensity": 15.0, "transition": 0.50, "physical": 0.45},
    "retail": {"intensity": 6.0, "transition": 0.30, "physical": 0.30},
    "technology": {"intensity": 3.0, "transition": 0.20, "physical": 0.25},
    "services": {"intensity": 4.0, "transition": 0.25, "physical": 0.25},
    "financial": {"intensity": 2.0, "transition": 0.30, "physical": 0.20},
    "general": {"intensity": 12.0, "transition": 0.45, "physical": 0.40},
}
CARBON_PRICE = 3000.0  # INR per tCO2e baseline for stress testing


def _emissions(industry: Optional[str]) -> Dict[str, float]:
    return INDUSTRY_EMISSIONS.get((industry or "general").lower(), INDUSTRY_EMISSIONS["general"])


def _score_from_signals(prof: Optional[Dict[str, Any]], industry: str,
                        overrides: Dict[str, float]) -> Dict[str, float]:
    em = _emissions(industry)
    # Environmental: inverse of transition + physical exposure.
    env = overrides.get("environmental_score",
                        clamp(1.0 - 0.6 * em["transition"] - 0.2 * em["physical"], 0.0, 1.0) * 100)
    # Governance proxy from credit rating / stability.
    rating = (prof or {}).get("rating") or "BBB"
    gov_map = {"AAA": 92, "AA": 88, "A": 82, "BBB": 72, "BB": 60, "B": 48, "CCC": 35}
    gov = overrides.get("governance_score", gov_map.get(rating, 65))
    # Social proxy from employee base & years in business.
    yib = to_float((prof or {}).get("years_in_business"), 8)
    emp = to_float((prof or {}).get("employee_count"), 100)
    soc = overrides.get("social_score", clamp(50 + min(yib, 30) + min(emp / 50.0, 20), 0, 100))
    return {"environmental_score": round(env, 1), "social_score": round(soc, 1),
            "governance_score": round(gov, 1)}


def assess(db: Session, *, subject_ref: str, assessment_id: Optional[int] = None,
           revenue: Optional[float] = None, industry: Optional[str] = None,
           overrides: Optional[Dict[str, float]] = None, tenant_id: Optional[int] = None,
           created_by: Optional[str] = None) -> Dict[str, Any]:
    """Full ESG assessment with E/S/G scores, carbon exposure and recommendations."""
    prof = da.company_or_none(db, assessment_id=assessment_id, company_ref=subject_ref)
    industry = industry or (prof or {}).get("industry") or "general"
    revenue = to_float(revenue if revenue is not None else
                       (prof or {}).get("engine_input", {}).get("revenue"), 100.0)
    em = _emissions(industry)
    scores = _score_from_signals(prof, industry, overrides or {})
    esg = round(0.4 * scores["environmental_score"] + 0.3 * scores["social_score"] +
                0.3 * scores["governance_score"], 1)
    carbon_tonnes = revenue * em["intensity"]
    rating_band = ("AAA" if esg >= 80 else "AA" if esg >= 70 else "A" if esg >= 60
                   else "BBB" if esg >= 50 else "BB" if esg >= 40 else "B")
    recommendations = []
    if scores["environmental_score"] < 55:
        recommendations.append("Adopt a science-based emissions-reduction target and disclose Scope 1-2.")
    if em["transition"] > 0.6:
        recommendations.append("High transition risk — build a decarbonisation capex plan and covenant it.")
    if scores["governance_score"] < 60:
        recommendations.append("Strengthen board independence and ESG oversight before further lending.")
    green_eligible = scores["environmental_score"] >= 60 and em["transition"] < 0.5
    if green_eligible:
        recommendations.append("Eligible for green/sustainability-linked financing at preferential pricing.")
    if not recommendations:
        recommendations.append("ESG profile is sound; maintain disclosure cadence.")

    results = {
        "industry": industry, "revenue": revenue,
        "esg_score": esg, "esg_band": rating_band,
        **scores,
        "carbon_intensity": em["intensity"],
        "estimated_carbon_tonnes": round(carbon_tonnes, 1),
        "transition_risk": em["transition"], "physical_risk": em["physical"],
        "green_financing_eligible": green_eligible,
        "sustainable_lending_signal": "positive" if esg >= 60 else "neutral" if esg >= 45 else "negative",
    }
    g = grounding_block("ESG Assessment", results)
    row = FinESGAssessment(
        tenant_id=tenant_id, subject_ref=subject_ref, assessment_id=assessment_id,
        industry=industry, esg_score=esg, environmental_score=scores["environmental_score"],
        social_score=scores["social_score"], governance_score=scores["governance_score"],
        carbon_intensity=em["intensity"], transition_risk=em["transition"],
        physical_risk=em["physical"], inputs={"revenue": revenue, "overrides": overrides or {}},
        results={**results, "grounding": g}, recommendations=recommendations,
        narrative=f"ESG score {esg} ({rating_band}); {'green-eligible' if green_eligible else 'transition-exposed'}.",
        created_by=created_by)
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"esg_id": row.id, "subject_ref": subject_ref, **results,
            "recommendations": recommendations}


def climate_stress(db: Session, *, subject_ref: Optional[str] = None,
                   carbon_price: float = CARBON_PRICE, price_shock_multiple: float = 3.0,
                   revenue: Optional[float] = None, industry: Optional[str] = None,
                   tenant_id: Optional[int] = None, created_by: Optional[str] = None) -> Dict[str, Any]:
    """Climate transition stress: carbon-price shock → cost & margin impact."""
    if subject_ref:
        prof = da.company_or_none(db, company_ref=subject_ref)
        industry = industry or (prof or {}).get("industry") or "general"
        revenue = to_float(revenue if revenue is not None else
                           (prof or {}).get("engine_input", {}).get("revenue"), 100.0)
    else:
        industry = industry or "general"
        revenue = to_float(revenue, 100.0)
    em = _emissions(industry)
    carbon_tonnes = revenue * em["intensity"]
    base_cost = carbon_tonnes * carbon_price
    stressed_cost = carbon_tonnes * carbon_price * price_shock_multiple
    margin_hit = safe_div(stressed_cost - base_cost, revenue * 1_000_000.0, 0.0)  # revenue in mn
    results = {
        "industry": industry, "carbon_tonnes": round(carbon_tonnes, 1),
        "base_carbon_cost": round(base_cost, 0), "stressed_carbon_cost": round(stressed_cost, 0),
        "carbon_price": carbon_price, "price_shock_multiple": price_shock_multiple,
        "incremental_cost": round(stressed_cost - base_cost, 0),
        "margin_impact_pct": pct(margin_hit),
        "transition_risk": em["transition"],
        "severity": "high" if em["transition"] > 0.6 else "moderate" if em["transition"] > 0.4 else "low",
    }
    g = grounding_block("Climate Stress Test", results)
    row = FinESGAssessment(
        tenant_id=tenant_id, subject_ref=subject_ref or f"industry:{industry}", industry=industry,
        transition_risk=em["transition"], physical_risk=em["physical"],
        inputs={"carbon_price": carbon_price, "price_shock_multiple": price_shock_multiple},
        results={**results, "grounding": g},
        recommendations=["Model a carbon-price pathway into base-case cash flows and covenants."],
        narrative=f"A {price_shock_multiple}× carbon-price shock costs {results['incremental_cost']:,.0f}.",
        created_by=created_by)
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"climate_id": row.id, **results}


def portfolio_esg(db: Session, *, tenant_id: Optional[int] = None) -> Dict[str, Any]:
    """Aggregate ESG posture across the live exposure set (exposure-weighted)."""
    exposures = da.portfolio_exposures(db)
    if not exposures:
        return {"exposures": 0, "weighted_esg_score": None, "high_transition_ead_pct": None}
    total_ead = sum(e["ead"] for e in exposures) or 1.0
    wscore = 0.0
    high_transition_ead = 0.0
    by_industry: Dict[str, float] = {}
    for e in exposures:
        em = _emissions(e["industry"])
        scores = _score_from_signals(None, e["industry"], {})
        esg = 0.4 * scores["environmental_score"] + 0.3 * scores["social_score"] + 0.3 * scores["governance_score"]
        wscore += esg * e["ead"]
        if em["transition"] > 0.6:
            high_transition_ead += e["ead"]
        by_industry[e["industry"]] = by_industry.get(e["industry"], 0.0) + e["ead"]
    return {
        "exposures": len(exposures),
        "weighted_esg_score": round(wscore / total_ead, 1),
        "high_transition_ead": round(high_transition_ead, 2),
        "high_transition_ead_pct": pct(high_transition_ead / total_ead),
        "exposure_by_industry": {k: round(v, 2) for k, v in by_industry.items()},
        "generated_at": iso(utcnow()),
    }


def list_assessments(db: Session, *, subject_ref: Optional[str] = None, limit: int = 50,
                     tenant_id: Optional[int] = None) -> List[Dict[str, Any]]:
    q = db.query(FinESGAssessment)
    if tenant_id is not None:
        q = q.filter(FinESGAssessment.tenant_id == tenant_id)
    if subject_ref:
        q = q.filter(FinESGAssessment.subject_ref == subject_ref)
    return [{"esg_id": a.id, "subject_ref": a.subject_ref, "industry": a.industry,
             "esg_score": a.esg_score, "transition_risk": a.transition_risk,
             "created_at": iso(a.created_at)}
            for a in q.order_by(FinESGAssessment.id.desc()).limit(limit).all()]
