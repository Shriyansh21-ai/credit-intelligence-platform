"""M8 — Relationship Manager Workspace.

A single pane for an RM to manage a customer: interaction timeline (calls, emails,
meetings, visits, notes), loan/assessment history, cross-sell opportunities, AI
recommendations, a composite customer-health score, open alerts and a concrete
"next best action". Interactions + opportunities are first-class rows; everything
else is aggregated read-only from existing platform data.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from backend.app.models.autonomous import RMInteraction, RMOpportunity
from . import alerts as alerts_svc
from . import data_access, ews, recommendations
from .common import clamp

INTERACTION_TYPES = ["call", "email", "meeting", "visit", "note", "task"]
# Cross-sell product catalog with simple eligibility heuristics.
_PRODUCTS = [
    ("working_capital_loan", "Working Capital Loan", lambda p: (p.get("health") or {}).get("working_capital", 100) < 60),
    ("term_loan", "Term Loan", lambda p: (p.get("pd") or 1) < 0.06),
    ("trade_finance", "Trade Finance / LC", lambda p: (p.get("industry") or "").lower() in
     ("manufacturing", "textile", "trading", "import", "export", "wholesale")),
    ("treasury_fx", "Treasury / FX Hedging", lambda p: (p.get("country") or "IN") != "IN" or (p.get("exposure") or 0) > 5e7),
    ("cash_management", "Cash Management Services", lambda p: (p.get("pd") or 1) < 0.08),
    ("insurance", "Business Insurance", lambda p: True),
]


# ---------------------------------------------------------------------------
# Interactions
# ---------------------------------------------------------------------------
def log_interaction(db: Session, company_ref: str, interaction_type: str, *,
                    subject: Optional[str] = None, detail: Optional[str] = None,
                    outcome: Optional[str] = None, rm_user_id: Optional[int] = None,
                    payload: Optional[dict] = None, tenant_id: Optional[int] = None) -> RMInteraction:
    if interaction_type not in INTERACTION_TYPES:
        raise ValueError(f"invalid interaction_type: {interaction_type}")
    row = RMInteraction(tenant_id=tenant_id, company_ref=company_ref, rm_user_id=rm_user_id,
                        interaction_type=interaction_type, subject=subject, detail=detail,
                        outcome=outcome, payload=payload or {})
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def list_interactions(db: Session, company_ref: str, *, tenant_id: Optional[int] = None,
                      limit: int = 100) -> List[RMInteraction]:
    return (db.query(RMInteraction)
            .filter(RMInteraction.tenant_id == tenant_id, RMInteraction.company_ref == company_ref)
            .order_by(RMInteraction.occurred_at.desc()).limit(limit).all())


# ---------------------------------------------------------------------------
# Opportunities
# ---------------------------------------------------------------------------
def add_opportunity(db: Session, company_ref: str, product: str, *, rationale: Optional[str] = None,
                    estimated_value: Optional[float] = None, confidence: float = 0.5,
                    tenant_id: Optional[int] = None) -> RMOpportunity:
    row = RMOpportunity(tenant_id=tenant_id, company_ref=company_ref, product=product,
                        rationale=rationale, estimated_value=estimated_value,
                        confidence=clamp(confidence))
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def identify_opportunities(db: Session, company_ref: str, *, persist: bool = False,
                           tenant_id: Optional[int] = None) -> List[Dict[str, Any]]:
    """Deterministic cross-sell suggestions from the customer's profile."""
    prof = data_access.profile(data_access.latest_assessment_for_company(db, company_ref))
    if not prof:
        return []
    out = []
    exposure = prof.get("exposure") or 1e7
    for code, name, eligible in _PRODUCTS:
        try:
            ok = eligible(prof)
        except Exception:
            ok = False
        if not ok:
            continue
        conf = 0.75 if (prof.get("pd") or 1) < 0.05 else 0.5
        est = round(exposure * 0.3, 2)
        rationale = f"Profile fits {name} (industry={prof.get('industry')}, PD={prof.get('pd')})."
        out.append({"product": code, "name": name, "confidence": conf,
                    "estimated_value": est, "rationale": rationale})
        if persist:
            add_opportunity(db, company_ref, code, rationale=rationale,
                            estimated_value=est, confidence=conf, tenant_id=tenant_id)
    return out


def list_opportunities(db: Session, company_ref: str, *, tenant_id: Optional[int] = None) -> List[RMOpportunity]:
    return (db.query(RMOpportunity)
            .filter(RMOpportunity.tenant_id == tenant_id, RMOpportunity.company_ref == company_ref)
            .order_by(RMOpportunity.created_at.desc()).all())


# ---------------------------------------------------------------------------
# Customer health + timeline + workspace
# ---------------------------------------------------------------------------
def customer_health(db: Session, company_ref: str, *, tenant_id: Optional[int] = None) -> Dict[str, Any]:
    """Composite 0-100 health blending assessment health, PD and open alerts."""
    prof = data_access.profile(data_access.latest_assessment_for_company(db, company_ref))
    health_dims = (prof or {}).get("health") or {}
    dim_vals = [v for v in health_dims.values() if isinstance(v, (int, float))]
    dim_avg = sum(dim_vals) / len(dim_vals) if dim_vals else 60.0
    pd = (prof or {}).get("pd") or 0.08
    pd_component = clamp((1 - pd) * 100, 0, 100)
    open_alerts = alerts_svc.list_alerts(db, company_ref=company_ref, status="open",
                                         tenant_id=tenant_id, limit=100)
    penalty = min(len(open_alerts) * 6, 30)
    score = round(clamp(0.5 * dim_avg + 0.5 * pd_component - penalty, 0, 100), 1)
    band = "healthy" if score >= 70 else "watch" if score >= 45 else "at_risk"
    return {"company_ref": company_ref, "health_score": score, "band": band,
            "dimension_avg": round(dim_avg, 1), "pd_component": round(pd_component, 1),
            "open_alerts": len(open_alerts)}


def timeline(db: Session, company_ref: str, *, tenant_id: Optional[int] = None,
             limit: int = 50) -> List[Dict[str, Any]]:
    events: List[Dict[str, Any]] = []
    for i in list_interactions(db, company_ref, tenant_id=tenant_id, limit=limit):
        events.append({"at": i.occurred_at.isoformat() if i.occurred_at else None,
                       "type": i.interaction_type, "detail": i.subject or i.detail or "",
                       "kind": "interaction"})
    prof = data_access.latest_assessment_for_company(db, company_ref)
    if prof is not None:
        events.append({"at": prof.created_at.isoformat() if prof.created_at else None,
                       "type": "assessment", "kind": "assessment",
                       "detail": f"Assessment: {prof.risk_rating} rating, score {prof.enterprise_credit_score}"})
    for a in alerts_svc.list_alerts(db, company_ref=company_ref, tenant_id=tenant_id, limit=20):
        events.append({"at": a.created_at.isoformat() if a.created_at else None,
                       "type": f"alert:{a.severity}", "kind": "alert", "detail": a.title})
    events.sort(key=lambda e: e["at"] or "", reverse=True)
    return events[:limit]


def next_best_action(db: Session, company_ref: str, *, tenant_id: Optional[int] = None) -> Dict[str, Any]:
    open_alerts = alerts_svc.list_alerts(db, company_ref=company_ref, status="open",
                                         tenant_id=tenant_id, limit=5)
    if open_alerts:
        a = open_alerts[0]
        return {"action": "resolve_alert", "priority": a.severity,
                "detail": a.recommended_action or a.title, "source": "alert", "ref_id": a.id}
    recs = recommendations.recommend(db, company_ref=company_ref, persist=False)
    if recs.get("recommendations"):
        r = recs["recommendations"][0]
        return {"action": r["action"], "priority": r["priority"], "detail": r["title"],
                "source": "recommendation", "confidence": r["confidence"]}
    return {"action": "maintain_relationship", "priority": "low",
            "detail": "No open items — schedule a periodic review call.", "source": "default"}


def workspace(db: Session, company_ref: str, *, tenant_id: Optional[int] = None) -> Dict[str, Any]:
    """The full RM cockpit for a customer."""
    prof = data_access.profile(data_access.latest_assessment_for_company(db, company_ref))
    return {
        "company_ref": company_ref,
        "profile": prof,
        "health": customer_health(db, company_ref, tenant_id=tenant_id),
        "timeline": timeline(db, company_ref, tenant_id=tenant_id),
        "opportunities": identify_opportunities(db, company_ref, tenant_id=tenant_id),
        "recommendations": recommendations.recommend(db, company_ref=company_ref, persist=False).get("recommendations", []),
        "open_alerts": [alerts_svc.as_dict(a) for a in
                        alerts_svc.list_alerts(db, company_ref=company_ref, status="open", tenant_id=tenant_id)],
        "next_best_action": next_best_action(db, company_ref, tenant_id=tenant_id),
        "ews": ews.evaluate(db, company_ref=company_ref, persist=False, escalate=False),
    }
