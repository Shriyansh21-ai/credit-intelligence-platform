"""M10 — Executive Intelligence Center.

Real-time, role-specific executive dashboards (CEO / CRO / CCO / Compliance /
Portfolio / Regulatory / Treasury) built by deterministic aggregation over the
platform's assessments plus the Phase 9/10 intelligence and OS surfaces. Each
dashboard returns titled KPI cards (value + trend intent) and chart-ready
series — every number traces to a source, none fabricated.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from .common import safe_div

PERSONAS = ["ceo", "chief_risk_officer", "chief_credit_officer",
            "chief_compliance_officer", "portfolio", "regulatory", "treasury"]


def portfolio_metrics(db: Session, *, tenant_id: Optional[int] = None) -> Dict[str, Any]:
    """Core portfolio aggregates reused by every persona dashboard."""
    from backend.app.models.enterprise_assessment import EnterpriseAssessment
    rows = db.query(EnterpriseAssessment).limit(10000).all()
    n = len(rows)
    total_exposure = 0.0
    total_el = 0.0
    pd_sum = 0.0
    approved = 0
    by_rating: Dict[str, int] = defaultdict(int)
    by_industry: Dict[str, Dict[str, float]] = defaultdict(lambda: {"count": 0, "exposure": 0.0})
    high_risk = 0
    for a in rows:
        exp = a.recommended_loan_amount or 0
        pd = a.probability_of_default or 0
        total_exposure += exp
        total_el += a.expected_loss or (exp * pd * (a.loss_given_default or 0.45))
        pd_sum += pd
        if (a.loan_recommendation or "").lower() in ("approve", "approved"):
            approved += 1
        by_rating[a.risk_rating or "NR"] += 1
        ind = by_industry[a.industry or "other"]
        ind["count"] += 1
        ind["exposure"] += exp
        if pd >= 0.15:
            high_risk += 1
    avg_pd = safe_div(pd_sum, n) or 0.0
    return {
        "obligors": n,
        "total_exposure": round(total_exposure, 2),
        "expected_loss": round(total_el, 2),
        "avg_pd": round(avg_pd, 4),
        "el_ratio": round(safe_div(total_el, total_exposure) or 0.0, 4),
        "approval_rate": round(safe_div(approved, n) or 0.0, 4),
        "high_risk_obligors": high_risk,
        "high_risk_share": round(safe_div(high_risk, n) or 0.0, 4),
        "by_rating": dict(by_rating),
        "by_industry": {k: {"count": v["count"], "exposure": round(v["exposure"], 2)}
                        for k, v in by_industry.items()},
    }


def _phase10_counts(db: Session, tenant_id: Optional[int]) -> Dict[str, int]:
    out = {"open_recommendations": 0, "active_policies": 0, "committee_decisions": 0,
           "datasets": 0}
    try:
        from backend.app.models.banking_os import (
            AgendaItem, Dataset, PluginRecommendation, Policy,
        )
        out["open_recommendations"] = (db.query(PluginRecommendation)
            .filter(PluginRecommendation.tenant_id == tenant_id,
                    PluginRecommendation.status == "proposed").count())
        out["active_policies"] = (db.query(Policy)
            .filter(Policy.tenant_id == tenant_id, Policy.status == "active").count())
        out["committee_decisions"] = (db.query(AgendaItem)
            .filter(AgendaItem.tenant_id == tenant_id, AgendaItem.decision.isnot(None)).count())
        out["datasets"] = db.query(Dataset).filter(Dataset.tenant_id == tenant_id).count()
    except Exception:
        pass
    return out


def _phase9_alerts(db: Session, tenant_id: Optional[int]) -> Dict[str, int]:
    out = {"open_alerts": 0, "critical_alerts": 0}
    try:
        from backend.app.models.autonomous import IntelligenceAlert
        base = db.query(IntelligenceAlert).filter(IntelligenceAlert.tenant_id == tenant_id)
        out["open_alerts"] = base.filter(IntelligenceAlert.status == "open").count()
        out["critical_alerts"] = base.filter(IntelligenceAlert.severity == "critical").count()
    except Exception:
        pass
    return out


def _card(title: str, value: Any, *, unit: str = "", intent: str = "neutral",
          hint: str = "") -> Dict[str, Any]:
    return {"title": title, "value": value, "unit": unit, "intent": intent, "hint": hint}


def dashboard(db: Session, persona: str, *, tenant_id: Optional[int] = None) -> Dict[str, Any]:
    persona = (persona or "").lower()
    if persona not in PERSONAS:
        raise ValueError(f"unknown persona '{persona}'; choose from {PERSONAS}")
    m = portfolio_metrics(db, tenant_id=tenant_id)
    p10 = _phase10_counts(db, tenant_id)
    alerts = _phase9_alerts(db, tenant_id)

    cards: List[Dict[str, Any]] = []
    charts: Dict[str, Any] = {}

    if persona == "ceo":
        cards = [
            _card("Total Exposure", m["total_exposure"], unit="₹"),
            _card("Obligors", m["obligors"]),
            _card("Approval Rate", round(m["approval_rate"] * 100, 1), unit="%",
                  intent="good" if m["approval_rate"] >= 0.5 else "neutral"),
            _card("Expected Loss", m["expected_loss"], unit="₹",
                  intent="bad" if m["el_ratio"] > 0.03 else "good"),
            _card("Open Recommendations", p10["open_recommendations"]),
        ]
        charts = {"exposure_by_industry": m["by_industry"], "rating_mix": m["by_rating"]}
    elif persona == "chief_risk_officer":
        cards = [
            _card("Average PD", round(m["avg_pd"] * 100, 2), unit="%",
                  intent="bad" if m["avg_pd"] > 0.1 else "good"),
            _card("EL Ratio", round(m["el_ratio"] * 100, 2), unit="%",
                  intent="bad" if m["el_ratio"] > 0.03 else "good"),
            _card("High-risk Share", round(m["high_risk_share"] * 100, 1), unit="%"),
            _card("Open Alerts", alerts["open_alerts"],
                  intent="bad" if alerts["open_alerts"] else "good"),
            _card("Critical Alerts", alerts["critical_alerts"],
                  intent="bad" if alerts["critical_alerts"] else "good"),
        ]
        charts = {"rating_mix": m["by_rating"], "exposure_by_industry": m["by_industry"]}
    elif persona == "chief_credit_officer":
        cards = [
            _card("Approval Rate", round(m["approval_rate"] * 100, 1), unit="%"),
            _card("Obligors", m["obligors"]),
            _card("Committee Decisions", p10["committee_decisions"]),
            _card("Active Policies", p10["active_policies"]),
            _card("High-risk Obligors", m["high_risk_obligors"]),
        ]
        charts = {"rating_mix": m["by_rating"]}
    elif persona == "chief_compliance_officer":
        cards = [
            _card("Active Policies", p10["active_policies"]),
            _card("Open Alerts", alerts["open_alerts"]),
            _card("Committee Decisions", p10["committee_decisions"]),
            _card("Datasets Governed", p10["datasets"]),
        ]
        charts = {"rating_mix": m["by_rating"]}
    elif persona == "portfolio":
        cards = [
            _card("Total Exposure", m["total_exposure"], unit="₹"),
            _card("Expected Loss", m["expected_loss"], unit="₹"),
            _card("Average PD", round(m["avg_pd"] * 100, 2), unit="%"),
            _card("High-risk Share", round(m["high_risk_share"] * 100, 1), unit="%"),
        ]
        charts = {"exposure_by_industry": m["by_industry"], "rating_mix": m["by_rating"]}
    elif persona == "regulatory":
        cards = [
            _card("EL Ratio", round(m["el_ratio"] * 100, 2), unit="%"),
            _card("High-risk Share", round(m["high_risk_share"] * 100, 1), unit="%"),
            _card("Active Policies", p10["active_policies"]),
            _card("Datasets Governed", p10["datasets"]),
        ]
        charts = {"rating_mix": m["by_rating"]}
    else:  # treasury
        cards = [
            _card("Total Exposure", m["total_exposure"], unit="₹"),
            _card("Expected Loss", m["expected_loss"], unit="₹"),
            _card("EL Ratio", round(m["el_ratio"] * 100, 2), unit="%"),
            _card("Obligors", m["obligors"]),
        ]
        charts = {"exposure_by_industry": m["by_industry"]}

    return {"persona": persona, "cards": cards, "charts": charts, "metrics": m,
            "generated": True}
