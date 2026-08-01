"""Monitoring service — records, health timeline, risk trend, auto-alerts.

Adding a record triggers deterioration detection against the prior record
    - health_score drop beyond a tolerance -> "deterioration" alert
    - rating downgrade (worse rating band) -> "rating_downgrade" alert
    - payment_status of late/default -> "payment_delay" alert
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from backend.app.models.application import Application
from backend.app.models.monitoring import MonitoringAlert, MonitoringRecord
from backend.app.services import audit, notifications

RECORD_TYPES = (
    "financial_update",
    "quarterly_statement",
    "annual_report",
    "gst",
    "bank_statement",
    "payment_behaviour",
    "rating_change",
)

# Lower index = stronger credit. Used to detect downgrades.
_RATING_ORDER = [
    "AAA", "AA", "A", "BBB", "BB", "B", "CCC", "CC", "C", "D",
]
_HEALTH_DROP_TOLERANCE = 5.0  # points


def _rating_rank(rating: Optional[str]) -> Optional[int]:
    if not rating:
        return None
    key = rating.strip().upper()
    return _RATING_ORDER.index(key) if key in _RATING_ORDER else None


def _previous_record(db: Session, application_id: int) -> Optional[MonitoringRecord]:
    return (
        db.query(MonitoringRecord)
        .filter(MonitoringRecord.application_id == application_id)
        .order_by(MonitoringRecord.recorded_at.desc(), MonitoringRecord.id.desc())
        .first()
    )


def add_record(
    db: Session,
    *,
    application_id: int,
    record_type: str,
    period: Optional[str] = None,
    health_score: Optional[float] = None,
    risk_rating: Optional[str] = None,
    payment_status: Optional[str] = None,
    data: Optional[dict] = None,
    note: Optional[str] = None,
    actor: Any = None,
) -> Dict[str, Any]:
    """Append a monitoring record and raise deterioration alerts as needed."""
    previous = _previous_record(db, application_id)

    record = MonitoringRecord(
        application_id=application_id,
        record_type=record_type,
        period=period,
        health_score=health_score,
        risk_rating=risk_rating,
        payment_status=payment_status,
        data=data,
        note=note,
        recorded_by=getattr(actor, "id", None),
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    alerts: List[MonitoringAlert] = []

    # 1) Health-score deterioration.
    if health_score is not None and previous is not None and previous.health_score is not None:
        drop = previous.health_score - health_score
        if drop >= _HEALTH_DROP_TOLERANCE:
            alerts.append(
                MonitoringAlert(
                    application_id=application_id,
                    record_id=record.id,
                    category="deterioration",
                    severity="high" if drop >= 15 else "medium",
                    message=f"Health score fell {round(drop, 1)} pts "
                    f"({previous.health_score} -> {health_score}).",
                )
            )

    # 2) Rating downgrade.
    new_rank = _rating_rank(risk_rating)
    prev_rank = _rating_rank(previous.risk_rating) if previous else None
    if new_rank is not None and prev_rank is not None and new_rank > prev_rank:
        alerts.append(
            MonitoringAlert(
                application_id=application_id,
                record_id=record.id,
                category="rating_downgrade",
                severity="high",
                message=f"Rating downgraded {previous.risk_rating} -> {risk_rating}.",
            )
        )

    # 3) Payment behaviour.
    if payment_status in ("late", "default"):
        alerts.append(
            MonitoringAlert(
                application_id=application_id,
                record_id=record.id,
                category="payment_delay",
                severity="high" if payment_status == "default" else "medium",
                message=f"Payment status reported as '{payment_status}'.",
            )
        )

    for alert in alerts:
        db.add(alert)
    if alerts:
        db.commit()
        for alert in alerts:
            db.refresh(alert)
        audit.record_safe(
            db,
            action="monitoring.deterioration",
            actor=actor,
            entity_type="application",
            entity_id=application_id,
            new_value={"alerts": [a.category for a in alerts]},
        )
        app = db.query(Application).filter(Application.id == application_id).first()
        recipient = (app.assigned_to or app.user_id) if app else None
        if recipient:
            notifications.notify_safe(
                db,
                user_id=recipient,
                event_type="monitoring_alert",
                title="Monitoring alert",
                message="; ".join(a.message for a in alerts),
                entity_type="application",
                entity_id=application_id,
            )

    return {
        "record": serialize_record(record),
        "alerts": [serialize_alert(a) for a in alerts],
    }


def health_timeline(db: Session, application_id: int) -> List[Dict[str, Any]]:
    rows = (
        db.query(MonitoringRecord)
        .filter(
            MonitoringRecord.application_id == application_id,
            MonitoringRecord.health_score.isnot(None),
        )
        .order_by(MonitoringRecord.recorded_at, MonitoringRecord.id)
        .all()
    )
    return [
        {
            "record_id": r.id,
            "period": r.period,
            "health_score": r.health_score,
            "risk_rating": r.risk_rating,
            "recorded_at": r.recorded_at.isoformat() if r.recorded_at else None,
        }
        for r in rows
    ]


def risk_trend(db: Session, application_id: int, window: int = 6) -> Dict[str, Any]:
    timeline = health_timeline(db, application_id)
    scores = [p["health_score"] for p in timeline][-window:]
    direction = "flat"
    change = None
    if len(scores) >= 2:
        change = round(scores[-1] - scores[0], 2)
        if change > 1:
            direction = "improving"
        elif change < -1:
            direction = "deteriorating"
    return {
        "application_id": application_id,
        "direction": direction,
        "change": change,
        "latest": scores[-1] if scores else None,
        "points": scores,
    }


def deterioration_alerts(
    db: Session, application_id: int, status: Optional[str] = None
) -> List[Dict[str, Any]]:
    query = db.query(MonitoringAlert).filter(MonitoringAlert.application_id == application_id)
    if status:
        query = query.filter(MonitoringAlert.status == status)
    rows = query.order_by(MonitoringAlert.created_at.desc(), MonitoringAlert.id.desc()).all()
    return [serialize_alert(a) for a in rows]


def records_for(db: Session, application_id: int) -> List[MonitoringRecord]:
    return (
        db.query(MonitoringRecord)
        .filter(MonitoringRecord.application_id == application_id)
        .order_by(MonitoringRecord.recorded_at.desc(), MonitoringRecord.id.desc())
        .all()
    )


def serialize_record(r: MonitoringRecord) -> Dict[str, Any]:
    return {
        "id": r.id,
        "application_id": r.application_id,
        "record_type": r.record_type,
        "period": r.period,
        "health_score": r.health_score,
        "risk_rating": r.risk_rating,
        "payment_status": r.payment_status,
        "data": r.data,
        "note": r.note,
        "recorded_by": r.recorded_by,
        "recorded_at": r.recorded_at.isoformat() if r.recorded_at else None,
    }


def serialize_alert(a: MonitoringAlert) -> Dict[str, Any]:
    return {
        "id": a.id,
        "application_id": a.application_id,
        "record_id": a.record_id,
        "category": a.category,
        "severity": a.severity,
        "message": a.message,
        "status": a.status,
        "created_at": a.created_at.isoformat() if a.created_at else None,
    }
