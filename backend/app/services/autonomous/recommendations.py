"""M11 — Enterprise Recommendation Engine.

Turns a company's assessment profile (plus optional EWS/monitoring context) into
concrete credit actions — approve, reject, manual review, increase/decrease limit
restructure, additional collateral, site visit, portfolio rebalance, relationship
expansion — each with a confidence, a plain-English reason, supporting metrics and
evidence. Deterministic rule engine grounded in real figures.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from backend.app.models.autonomous import Recommendation
from . import data_access
from .common import clamp, evidence, rating_index

ACTIONS = [
    "approve", "reject", "manual_review", "increase_limit", "decrease_limit",
    "restructure", "additional_collateral", "site_visit", "portfolio_rebalance",
    "relationship_expansion",
]


def _rec(action: str, title: str, reason: str, confidence: float, priority: str,
         ev: List[dict], metrics: Dict[str, Any]) -> Dict[str, Any]:
    return {"action": action, "title": title, "reason": reason,
            "confidence": round(clamp(confidence), 2), "priority": priority,
            "evidence": ev, "supporting_metrics": metrics}


def _rules(prof: Dict[str, Any], ctx: Dict[str, Any]) -> List[Dict[str, Any]]:
    pd = prof.get("pd") or 0.05
    rating = prof.get("rating") or "BBB"
    ridx = rating_index(rating) or 3
    health = prof.get("health") or {}
    liq = health.get("liquidity")
    debt = health.get("debt")
    exposure = prof.get("exposure") or 0.0
    metrics = {"pd": round(pd, 4), "rating": rating, "credit_score": prof.get("credit_score"),
               "exposure": exposure, "liquidity_health": liq, "debt_health": debt}
    out: List[Dict[str, Any]] = []

    # Headline decision
    if pd >= 0.20 or ridx >= 7:  # CCC or worse
        out.append(_rec("reject", "Decline / do not increase exposure",
                        f"PD of {pd:.1%} and {rating} rating breach risk appetite.",
                        0.85, "high", [evidence("pd", pd), evidence("rating", rating)], metrics))
    elif pd >= 0.10 or ridx >= 5:  # BB/B
        out.append(_rec("manual_review", "Route to senior manual review",
                        f"Elevated PD ({pd:.1%}) / {rating} rating warrants human underwriting.",
                        0.8, "high", [evidence("pd", pd)], metrics))
    elif pd <= 0.03 and ridx <= 3:
        out.append(_rec("approve", "Approve within delegated authority",
                        f"Strong profile: PD {pd:.1%}, {rating} rating.",
                        0.85, "medium", [evidence("pd", pd), evidence("rating", rating)], metrics))
    else:
        out.append(_rec("approve", "Approve with standard conditions",
                        f"Acceptable risk: PD {pd:.1%}, {rating} rating.",
                        0.7, "medium", [evidence("pd", pd)], metrics))

    # Limit sizing
    if pd <= 0.03 and ridx <= 3 and exposure > 0:
        out.append(_rec("increase_limit", "Consider a limit increase",
                        "Low PD and strong rating support additional capacity.",
                        0.65, "low", [evidence("pd", pd)], metrics))
    if pd >= 0.10:
        out.append(_rec("decrease_limit", "Reduce sanctioned limit",
                        f"PD of {pd:.1%} suggests trimming exposure.",
                        0.7, "medium", [evidence("pd", pd)], metrics))

    # Collateral / covenants
    if debt is not None and debt < 40:
        out.append(_rec("additional_collateral", "Seek additional collateral",
                        f"Weak debt health ({debt}/100) increases LGD.",
                        0.7, "medium", [evidence("debt_health", debt)], metrics))

    # Site visit / liquidity
    if liq is not None and liq < 40:
        out.append(_rec("site_visit", "Schedule a site visit",
                        f"Low liquidity health ({liq}/100) needs on-ground verification.",
                        0.6, "medium", [evidence("liquidity_health", liq)], metrics))

    # Restructure on deterioration / EWS
    if ctx.get("ews_band") == "red" or ctx.get("trend") == "deteriorating":
        out.append(_rec("restructure", "Evaluate loan restructuring",
                        "Early-warning signals indicate stress; restructuring may preserve value.",
                        0.65, "high", [evidence("ews_band", ctx.get("ews_band"))], metrics))

    # Relationship expansion for strong, under-served names
    if pd <= 0.04 and ridx <= 3:
        out.append(_rec("relationship_expansion", "Explore cross-sell / relationship expansion",
                        "High-quality relationship — candidate for additional products.",
                        0.55, "low", [evidence("rating", rating)], metrics))

    return out


def recommend(db: Session, *, company_ref: Optional[str] = None, assessment_id: Optional[int] = None,
              context: Optional[Dict[str, Any]] = None, tenant_id: Optional[int] = None,
              persist: bool = False) -> Dict[str, Any]:
    assessment = data_access.resolve(db, assessment_id=assessment_id, company_ref=company_ref)
    prof = data_access.profile(assessment)
    if not prof:
        return {"company_ref": company_ref, "recommendations": [],
                "summary": "No assessment found; cannot generate grounded recommendations."}
    recs = _rules(prof, context or {})
    ref = prof.get("company_ref")

    if persist:
        stored = []
        for r in recs:
            row = Recommendation(tenant_id=tenant_id, company_ref=ref,
                                 assessment_id=prof.get("assessment_id"), action=r["action"],
                                 title=r["title"], reason=r["reason"], confidence=r["confidence"],
                                 priority=r["priority"], evidence=r["evidence"],
                                 supporting_metrics=r["supporting_metrics"])
            db.add(row)
            stored.append(row)
        db.commit()
        for row, r in zip(stored, recs):
            db.refresh(row)
            r["id"] = row.id

    primary = recs[0] if recs else None
    summary = (f"Primary recommendation for {ref}: {primary['title']} "
               f"({int(primary['confidence']*100)}% confidence)." if primary
               else f"No recommendation for {ref}.")
    return {"company_ref": ref, "assessment_id": prof.get("assessment_id"),
            "recommendations": recs, "summary": summary}


def list_recommendations(db: Session, *, company_ref: Optional[str] = None,
                         action: Optional[str] = None, status: Optional[str] = None,
                         tenant_id: Optional[int] = None, limit: int = 100) -> List[Recommendation]:
    q = db.query(Recommendation).filter(Recommendation.tenant_id == tenant_id)
    if company_ref:
        q = q.filter(Recommendation.company_ref == company_ref)
    if action:
        q = q.filter(Recommendation.action == action)
    if status:
        q = q.filter(Recommendation.status == status)
    return q.order_by(Recommendation.created_at.desc()).limit(limit).all()


def set_status(db: Session, rec_id: int, status: str) -> Recommendation:
    if status not in ("proposed", "accepted", "rejected", "expired"):
        raise ValueError("invalid status")
    row = db.query(Recommendation).filter(Recommendation.id == rec_id).first()
    if row is None:
        raise ValueError("recommendation not found")
    row.status = status
    db.commit()
    db.refresh(row)
    return row


def as_dict(r: Recommendation) -> Dict[str, Any]:
    return {"id": r.id, "company_ref": r.company_ref, "action": r.action, "title": r.title,
            "reason": r.reason, "confidence": r.confidence, "priority": r.priority,
            "evidence": r.evidence, "supporting_metrics": r.supporting_metrics,
            "status": r.status, "assessment_id": r.assessment_id,
            "created_at": r.created_at.isoformat() if r.created_at else None}
