"""M9 — Enterprise Customer Success Platform.

The customer lifecycle: onboarding, implementation tracking, health scoring
product adoption, usage analytics, milestones, support tickets, training status
renewal tracking and success dashboards, plus AI recommendations carrying
confidence, reasoning, citations and evidence. Backed by ``ent_customers`` and
``ent_customer_events``.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from backend.app.models.enterprise_platform import EntCustomer, EntCustomerEvent
from .common import clamp, confidence_block, iso, mean, safe_div, to_float, utcnow

SEGMENTS = ["enterprise", "mid_market", "smb"]
TIERS = ["standard", "premium", "strategic"]
CUSTOMER_STATUSES = ["prospect", "onboarding", "live", "at_risk", "churned"]
EVENT_TYPES = ["onboarding", "milestone", "ticket", "training", "adoption", "renewal", "qbr"]
ONBOARDING_STAGES = ["kickoff", "provisioning", "integration", "training", "go_live", "adoption"]


def create_customer(db: Session, *, name: str, segment: str = "enterprise", tier: str = "standard",
                    arr: float = 0.0, csm: Optional[str] = None, renewal_date: Optional[str] = None,
                    tenant_id: Optional[int] = None) -> Dict[str, Any]:
    if segment not in SEGMENTS:
        raise ValueError(f"unknown segment '{segment}'")
    if tier not in TIERS:
        raise ValueError(f"unknown tier '{tier}'")
    row = EntCustomer(tenant_id=tenant_id, name=name, segment=segment, tier=tier, arr=to_float(arr),
                      csm=csm, renewal_date=renewal_date, onboarding_stage="kickoff",
                      status="onboarding")
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"customer_id": row.id, "name": row.name, "segment": segment, "tier": tier,
            "status": row.status, "health_score": row.health_score}


def record_event(db: Session, *, customer_id: int, event_type: str, title: str,
                 status: str = "open", impact: Optional[float] = None, detail: Optional[dict] = None,
                 tenant_id: Optional[int] = None) -> Dict[str, Any]:
    if event_type not in EVENT_TYPES:
        raise ValueError(f"unknown event_type '{event_type}'")
    if not db.query(EntCustomer).filter(EntCustomer.id == customer_id).first():
        raise ValueError("customer not found")
    row = EntCustomerEvent(tenant_id=tenant_id, customer_id=customer_id, event_type=event_type,
                           title=title, status=status, impact=impact, detail=detail or {})
    db.add(row)
    db.commit()
    db.refresh(row)
    _recompute_health(db, customer_id)
    return {"event_id": row.id, "customer_id": customer_id, "event_type": event_type, "title": title}


def advance_onboarding(db: Session, *, customer_id: int, stage: Optional[str] = None) -> Dict[str, Any]:
    c = db.query(EntCustomer).filter(EntCustomer.id == customer_id).first()
    if not c:
        raise ValueError("customer not found")
    if stage:
        if stage not in ONBOARDING_STAGES:
            raise ValueError(f"unknown stage '{stage}'")
        c.onboarding_stage = stage
    else:
        cur = c.onboarding_stage or "kickoff"
        idx = ONBOARDING_STAGES.index(cur) if cur in ONBOARDING_STAGES else 0
        c.onboarding_stage = ONBOARDING_STAGES[min(idx + 1, len(ONBOARDING_STAGES) - 1)]
    if c.onboarding_stage in ("go_live", "adoption"):
        c.status = "live"
    db.commit()
    _recompute_health(db, customer_id)
    return {"customer_id": customer_id, "onboarding_stage": c.onboarding_stage, "status": c.status}


def _recompute_health(db: Session, customer_id: int) -> None:
    c = db.query(EntCustomer).filter(EntCustomer.id == customer_id).first()
    if not c:
        return
    events = db.query(EntCustomerEvent).filter(EntCustomerEvent.customer_id == customer_id).all()
    open_tickets = sum(1 for e in events if e.event_type == "ticket" and e.status == "open")
    milestones = sum(1 for e in events if e.event_type == "milestone")
    trainings = sum(1 for e in events if e.event_type == "training" and e.status in ("completed", "done"))
    adoption_events = sum(1 for e in events if e.event_type == "adoption")
    stage_idx = ONBOARDING_STAGES.index(c.onboarding_stage) if c.onboarding_stage in ONBOARDING_STAGES else 0
    # Health: onboarding progress + milestones + training − open tickets.
    score = 55.0
    score += stage_idx * 5
    score += min(milestones * 4, 20)
    score += min(trainings * 3, 12)
    score -= open_tickets * 6
    c.health_score = round(clamp(score, 0.0, 100.0), 1)
    c.adoption_score = round(clamp(40.0 + adoption_events * 8 + stage_idx * 5, 0.0, 100.0), 1)
    if c.health_score < 50 and c.status == "live":
        c.status = "at_risk"
    db.commit()


def get_customer(db: Session, customer_id: int) -> Optional[Dict[str, Any]]:
    c = db.query(EntCustomer).filter(EntCustomer.id == customer_id).first()
    if not c:
        return None
    events = db.query(EntCustomerEvent).filter(EntCustomerEvent.customer_id == customer_id).all()
    return {"customer_id": c.id, "name": c.name, "segment": c.segment, "tier": c.tier,
            "status": c.status, "health_score": c.health_score, "adoption_score": c.adoption_score,
            "arr": c.arr, "onboarding_stage": c.onboarding_stage, "renewal_date": c.renewal_date,
            "csm": c.csm,
            "events": [{"event_id": e.id, "event_type": e.event_type, "title": e.title,
                        "status": e.status} for e in events]}


def list_customers(db: Session, *, status: Optional[str] = None, segment: Optional[str] = None,
                   tenant_id: Optional[int] = None) -> List[Dict[str, Any]]:
    q = db.query(EntCustomer)
    if tenant_id is not None:
        q = q.filter(EntCustomer.tenant_id == tenant_id)
    if status:
        q = q.filter(EntCustomer.status == status)
    if segment:
        q = q.filter(EntCustomer.segment == segment)
    return [{"customer_id": c.id, "name": c.name, "segment": c.segment, "tier": c.tier,
             "status": c.status, "health_score": c.health_score, "adoption_score": c.adoption_score,
             "arr": c.arr, "renewal_date": c.renewal_date}
            for c in q.order_by(EntCustomer.id.desc()).all()]


def recommendations(db: Session, *, customer_id: int) -> Dict[str, Any]:
    """AI success recommendations with confidence, reasoning, citations, evidence."""
    c = get_customer(db, customer_id)
    if not c:
        raise ValueError("customer not found")
    recs = []
    if c["health_score"] < 50:
        recs.append("Schedule an executive business review — health is below the at-risk threshold.")
    if c["adoption_score"] < 50:
        recs.append("Run enablement training to lift product adoption.")
    open_tickets = sum(1 for e in c["events"] if e["event_type"] == "ticket" and e["status"] == "open")
    if open_tickets:
        recs.append(f"Resolve {open_tickets} open support ticket(s) to protect renewal.")
    if not recs:
        recs.append("Account is healthy — pursue expansion / upsell opportunities.")
    confidence = clamp(0.5 + (100 - c["health_score"]) / 200.0, 0.4, 0.95)
    envelope = confidence_block(
        confidence,
        reasoning=(f"Health {c['health_score']} and adoption {c['adoption_score']} with "
                   f"{open_tickets} open tickets drive these actions."),
        citations=[{"source": "ent_customers", "ref": customer_id},
                   {"source": "ent_customer_events", "ref": customer_id}],
        evidence={"health_score": c["health_score"], "adoption_score": c["adoption_score"],
                  "open_tickets": open_tickets})
    return {"customer_id": customer_id, "recommendations": recs, **envelope}


def dashboard(db: Session, *, tenant_id: Optional[int] = None) -> Dict[str, Any]:
    customers = list_customers(db, tenant_id=tenant_id)
    if not customers:
        return {"customers": 0, "total_arr": 0, "avg_health": None, "at_risk": 0}
    by_status: Dict[str, int] = {}
    for c in customers:
        by_status[c["status"]] = by_status.get(c["status"], 0) + 1
    return {"customers": len(customers), "total_arr": round(sum(c["arr"] for c in customers), 2),
            "avg_health": round(mean([c["health_score"] for c in customers]), 1),
            "avg_adoption": round(mean([c["adoption_score"] for c in customers]), 1),
            "by_status": by_status, "at_risk": by_status.get("at_risk", 0),
            "generated_at": iso(utcnow())}
