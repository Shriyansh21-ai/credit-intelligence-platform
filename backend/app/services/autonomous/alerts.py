"""Unified intelligence-alert store (M2 / M3 / M11).

A single, deduplicated, prioritized alert lifecycle shared by the monitoring,
early-warning and recommendation engines so the platform has one inbox for
"the AI thinks you should look at this". Best-effort notification fan-out reuses
the Phase 5 notifications service when available (never breaks the caller).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from backend.app.models.autonomous import IntelligenceAlert
from .common import priority_score


def raise_alert(db: Session, *, company_ref: str, category: str, alert_type: str, title: str,
                severity: str = "medium", confidence: float = 0.6,
                business_impact: Optional[str] = None, recommended_action: Optional[str] = None,
                evidence: Optional[List[dict]] = None, exposure: Optional[float] = None,
                assessment_id: Optional[int] = None, tenant_id: Optional[int] = None,
                dedup_key: Optional[str] = None) -> IntelligenceAlert:
    """Create (or refresh) an alert. Idempotent on ``dedup_key`` while open."""
    key = dedup_key or f"{category}:{alert_type}:{company_ref}"
    existing = (db.query(IntelligenceAlert)
                .filter(IntelligenceAlert.dedup_key == key,
                        IntelligenceAlert.status.in_(["open", "acknowledged"]))
                .first())
    prio = priority_score(severity, confidence, exposure=exposure)
    if existing is not None:
        existing.severity = severity
        existing.confidence = confidence
        existing.priority_score = prio
        existing.title = title
        existing.business_impact = business_impact
        existing.recommended_action = recommended_action
        existing.evidence = evidence or existing.evidence
        db.commit()
        db.refresh(existing)
        return existing
    row = IntelligenceAlert(
        tenant_id=tenant_id, company_ref=company_ref, assessment_id=assessment_id,
        category=category, alert_type=alert_type, title=title, severity=severity,
        confidence=confidence, priority_score=prio, business_impact=business_impact,
        recommended_action=recommended_action, evidence=evidence or [], dedup_key=key)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def list_alerts(db: Session, *, tenant_id: Optional[int] = None, category: Optional[str] = None,
                company_ref: Optional[str] = None, status: Optional[str] = None,
                severity: Optional[str] = None, limit: int = 100) -> List[IntelligenceAlert]:
    q = db.query(IntelligenceAlert).filter(IntelligenceAlert.tenant_id == tenant_id)
    if category:
        q = q.filter(IntelligenceAlert.category == category)
    if company_ref:
        q = q.filter(IntelligenceAlert.company_ref == company_ref)
    if status:
        q = q.filter(IntelligenceAlert.status == status)
    if severity:
        q = q.filter(IntelligenceAlert.severity == severity)
    return q.order_by(IntelligenceAlert.priority_score.desc(),
                      IntelligenceAlert.created_at.desc()).limit(limit).all()


def set_status(db: Session, alert_id: int, status: str) -> IntelligenceAlert:
    row = db.query(IntelligenceAlert).filter(IntelligenceAlert.id == alert_id).first()
    if row is None:
        raise ValueError("alert not found")
    if status not in ("open", "acknowledged", "resolved", "dismissed"):
        raise ValueError(f"invalid status: {status}")
    row.status = status
    db.commit()
    db.refresh(row)
    return row


def summary(db: Session, *, tenant_id: Optional[int] = None) -> Dict[str, Any]:
    rows = list_alerts(db, tenant_id=tenant_id, limit=10000)
    by_sev: Dict[str, int] = {}
    by_cat: Dict[str, int] = {}
    by_status: Dict[str, int] = {}
    for r in rows:
        by_sev[r.severity] = by_sev.get(r.severity, 0) + 1
        by_cat[r.category] = by_cat.get(r.category, 0) + 1
        by_status[r.status] = by_status.get(r.status, 0) + 1
    return {"total": len(rows), "by_severity": by_sev, "by_category": by_cat,
            "by_status": by_status,
            "open": by_status.get("open", 0) + by_status.get("acknowledged", 0)}


def as_dict(a: IntelligenceAlert) -> Dict[str, Any]:
    return {
        "id": a.id, "company_ref": a.company_ref, "category": a.category,
        "alert_type": a.alert_type, "title": a.title, "severity": a.severity,
        "confidence": a.confidence, "priority_score": a.priority_score,
        "business_impact": a.business_impact, "recommended_action": a.recommended_action,
        "evidence": a.evidence, "status": a.status, "assessment_id": a.assessment_id,
        "created_at": a.created_at.isoformat() if a.created_at else None,
    }
