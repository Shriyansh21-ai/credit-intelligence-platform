"""Persistence for early-warning alerts (Phase 4, Milestone 7)."""

from __future__ import annotations

from typing import List, Mapping, Optional

from sqlalchemy.orm import Session

from backend.app.models.risk_alert import RiskAlert


def save_alerts(
    db: Session,
    *,
    user_id: int,
    assessment_id: Optional[int],
    scan_result: Mapping,
) -> List[RiskAlert]:
    """Persist a scan's alerts as the new current batch, superseding the prior
    current batch for the assessment (history is retained)."""
    if assessment_id is not None:
        (
            db.query(RiskAlert)
            .filter(
                RiskAlert.assessment_id == assessment_id,
                RiskAlert.is_current.is_(True),
            )
            .update({RiskAlert.is_current: False})
        )

    records = []
    for alert in scan_result.get("alerts", []):
        record = RiskAlert(
            user_id=user_id,
            assessment_id=assessment_id,
            is_current=True,
            alert_type=alert.get("alert_type", "unknown"),
            category=alert.get("category", "general"),
            severity=alert.get("severity", "low"),
            priority=alert.get("priority", 4),
            title=alert.get("title", ""),
            business_impact=alert.get("business_impact"),
            suggested_action=alert.get("suggested_action"),
            timeline=alert.get("timeline"),
            evidence=alert.get("evidence", {}),
        )
        db.add(record)
        records.append(record)
    db.commit()
    for record in records:
        db.refresh(record)
    return records


def _serialize(record: RiskAlert) -> dict:
    return {
        "id": record.id,
        "assessment_id": record.assessment_id,
        "alert_type": record.alert_type,
        "category": record.category,
        "severity": record.severity,
        "priority": record.priority,
        "title": record.title,
        "business_impact": record.business_impact,
        "suggested_action": record.suggested_action,
        "timeline": record.timeline,
        "evidence": record.evidence or {},
        "status": record.status,
        "created_at": str(record.created_at) if record.created_at else None,
    }


def current_for_assessment(db: Session, assessment_id: int) -> List[dict]:
    rows = (
        db.query(RiskAlert)
        .filter(
            RiskAlert.assessment_id == assessment_id,
            RiskAlert.is_current.is_(True),
        )
        .order_by(RiskAlert.priority.asc(), RiskAlert.id.asc())
        .all()
    )
    return [_serialize(r) for r in rows]


def current_for_user(db: Session, user_id: int, limit: int = 100) -> List[dict]:
    rows = (
        db.query(RiskAlert)
        .filter(
            RiskAlert.user_id == user_id,
            RiskAlert.is_current.is_(True),
        )
        .order_by(RiskAlert.priority.asc(), RiskAlert.created_at.desc())
        .limit(limit)
        .all()
    )
    return [_serialize(r) for r in rows]


def history_for_assessment(db: Session, assessment_id: int) -> List[dict]:
    rows = (
        db.query(RiskAlert)
        .filter(RiskAlert.assessment_id == assessment_id)
        .order_by(RiskAlert.created_at.desc(), RiskAlert.id.desc())
        .all()
    )
    return [_serialize(r) for r in rows]
