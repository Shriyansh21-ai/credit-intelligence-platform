"""Covenant service — creation, measurement/evaluation, trend, auto-alerts.

Evaluation applies the covenant's operator to a measured value
    - "min": breach when value < threshold; warning when within 5% above.
    - "max": breach when value > threshold; warning when within 5% below.
A breach automatically raises a :class:`CovenantAlert`.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from backend.app.models.application import Application
from backend.app.models.covenant import Covenant, CovenantAlert, CovenantMeasurement
from backend.app.services import audit, notifications
from backend.app.services.covenants.catalog import metric_definition

_WARNING_BAND = 0.05  # 5% cushion before a breach counts as a warning


def _notify_owner(db: Session, application_id: int, message: str) -> None:
    """Best-effort covenant-breach notification to the application's owner."""
    app = db.query(Application).filter(Application.id == application_id).first()
    if app is None:
        return
    recipient = app.assigned_to or app.user_id
    if recipient:
        notifications.notify_safe(
            db,
            user_id=recipient,
            event_type="covenant_breach",
            title="Covenant breach",
            message=message,
            entity_type="application",
            entity_id=application_id,
        )


def create_covenant(
    db: Session,
    *,
    application_id: int,
    metric_key: str,
    threshold: float,
    operator: Optional[str] = None,
    name: Optional[str] = None,
    unit: Optional[str] = None,
    description: Optional[str] = None,
    actor: Any = None,
) -> Covenant:
    definition = metric_definition(metric_key)
    cov = Covenant(
        application_id=application_id,
        metric_key=metric_key,
        name=name or definition["label"],
        operator=operator or definition["operator"],
        threshold=threshold,
        unit=unit or definition.get("unit"),
        description=description or definition.get("help"),
    )
    db.add(cov)
    db.commit()
    db.refresh(cov)
    audit.record_safe(
        db,
        action="covenant.create",
        actor=actor,
        entity_type="covenant",
        entity_id=cov.id,
        new_value={"metric": metric_key, "threshold": threshold, "operator": cov.operator},
    )
    return cov


def evaluate_covenant(operator: str, threshold: float, value: Optional[float]) -> Dict[str, Any]:
    """Return ``{status, headroom}`` for a value against a threshold."""
    if value is None:
        return {"status": "unknown", "headroom": None}

    if operator == "max":
        headroom = threshold - value  # positive => compliant
        if value > threshold:
            status = "breach"
        elif value >= threshold * (1 - _WARNING_BAND):
            status = "warning"
        else:
            status = "ok"
    else:  # "min"
        headroom = value - threshold  # positive => compliant
        if value < threshold:
            status = "breach"
        elif value <= threshold * (1 + _WARNING_BAND):
            status = "warning"
        else:
            status = "ok"
    return {"status": status, "headroom": round(headroom, 4)}


def record_measurement(
    db: Session,
    covenant: Covenant,
    *,
    value: Optional[float],
    period: Optional[str] = None,
    source: Optional[str] = None,
    note: Optional[str] = None,
    actor: Any = None,
) -> Dict[str, Any]:
    """Record a measurement, evaluate it, and auto-raise an alert on breach."""
    result = evaluate_covenant(covenant.operator, covenant.threshold, value)
    measurement = CovenantMeasurement(
        covenant_id=covenant.id,
        value=value,
        status=result["status"],
        headroom=result["headroom"],
        period=period,
        source=source,
        note=note,
    )
    db.add(measurement)
    db.commit()
    db.refresh(measurement)

    alert = None
    if result["status"] == "breach":
        alert = CovenantAlert(
            covenant_id=covenant.id,
            application_id=covenant.application_id,
            measurement_id=measurement.id,
            severity="high",
            message=(
                f"Covenant breach: {covenant.name} = {value} "
                f"({'>' if covenant.operator == 'max' else '<'} threshold {covenant.threshold})"
            ),
            status="open",
        )
        db.add(alert)
        db.commit()
        db.refresh(alert)
        audit.record_safe(
            db,
            action="covenant.breach",
            actor=actor,
            entity_type="covenant",
            entity_id=covenant.id,
            new_value={"value": value, "threshold": covenant.threshold},
            reason=alert.message,
        )
        _notify_owner(db, covenant.application_id, alert.message)

    return {
        "measurement": serialize_measurement(measurement),
        "alert": serialize_alert(alert) if alert else None,
    }


def covenant_trend(db: Session, covenant: Covenant, limit: int = 12) -> Dict[str, Any]:
    """Recent measurements and a simple direction signal."""
    rows: List[CovenantMeasurement] = (
        db.query(CovenantMeasurement)
        .filter(CovenantMeasurement.covenant_id == covenant.id)
        .order_by(CovenantMeasurement.measured_at.desc(), CovenantMeasurement.id.desc())
        .limit(limit)
        .all()
    )
    rows = list(reversed(rows))
    values = [r.value for r in rows if r.value is not None]

    direction = "flat"
    if len(values) >= 2:
        delta = values[-1] - values[0]
        if abs(delta) > 1e-9:
            improving = delta > 0 if covenant.operator == "min" else delta < 0
            direction = "improving" if improving else "deteriorating"

    return {
        "covenant_id": covenant.id,
        "metric_key": covenant.metric_key,
        "operator": covenant.operator,
        "threshold": covenant.threshold,
        "direction": direction,
        "points": [
            {
                "value": r.value,
                "status": r.status,
                "period": r.period,
                "measured_at": r.measured_at.isoformat() if r.measured_at else None,
            }
            for r in rows
        ],
    }


def list_covenants(db: Session, application_id: int) -> List[Covenant]:
    return (
        db.query(Covenant)
        .filter(Covenant.application_id == application_id)
        .order_by(Covenant.id)
        .all()
    )


def list_alerts(
    db: Session, *, application_id: Optional[int] = None, status: Optional[str] = None
) -> List[CovenantAlert]:
    query = db.query(CovenantAlert)
    if application_id is not None:
        query = query.filter(CovenantAlert.application_id == application_id)
    if status:
        query = query.filter(CovenantAlert.status == status)
    return query.order_by(CovenantAlert.created_at.desc(), CovenantAlert.id.desc()).all()


def latest_measurement(db: Session, covenant: Covenant) -> Optional[CovenantMeasurement]:
    return (
        db.query(CovenantMeasurement)
        .filter(CovenantMeasurement.covenant_id == covenant.id)
        .order_by(CovenantMeasurement.measured_at.desc(), CovenantMeasurement.id.desc())
        .first()
    )


def serialize_measurement(m: CovenantMeasurement) -> Dict[str, Any]:
    return {
        "id": m.id,
        "covenant_id": m.covenant_id,
        "value": m.value,
        "status": m.status,
        "headroom": m.headroom,
        "period": m.period,
        "source": m.source,
        "note": m.note,
        "measured_at": m.measured_at.isoformat() if m.measured_at else None,
    }


def serialize_alert(a: CovenantAlert) -> Dict[str, Any]:
    return {
        "id": a.id,
        "covenant_id": a.covenant_id,
        "application_id": a.application_id,
        "measurement_id": a.measurement_id,
        "severity": a.severity,
        "message": a.message,
        "status": a.status,
        "created_at": a.created_at.isoformat() if a.created_at else None,
    }


def serialize_covenant(db: Session, cov: Covenant) -> Dict[str, Any]:
    latest = latest_measurement(db, cov)
    return {
        "id": cov.id,
        "application_id": cov.application_id,
        "metric_key": cov.metric_key,
        "name": cov.name,
        "operator": cov.operator,
        "threshold": cov.threshold,
        "unit": cov.unit,
        "description": cov.description,
        "is_active": cov.is_active,
        "current_value": latest.value if latest else None,
        "current_status": latest.status if latest else "unknown",
        "current_headroom": latest.headroom if latest else None,
    }
