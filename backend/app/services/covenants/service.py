"""Covenant service — creation, measurement/evaluation, trend, auto-alerts.

Evaluation applies the covenant's operator to a measured value
    - "min": breach when value < threshold; warning when within 5% above.
    - "max": breach when value > threshold; warning when within 5% below.
A breach automatically raises a :class:`CovenantAlert`.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session

from backend.app.models.application import Application
from backend.app.models.covenant import Covenant, CovenantAlert, CovenantMeasurement
from backend.app.models.tenancy import Tenant, TenantMembership
from backend.app.services import audit, notifications
from backend.app.services.covenants.catalog import metric_definition

_WARNING_BAND = 0.05  # 5% cushion before a breach counts as a warning


class CovenantOwnershipError(PermissionError):
    """Raised when a covenant operation crosses or lacks tenant ownership."""


def _require_tenant_membership(db: Session, actor: Any, tenant_id: int) -> None:
    actor_id = getattr(actor, "id", None)
    if actor_id is None or tenant_id is None:
        raise CovenantOwnershipError("An active tenant membership is required.")

    membership = (
        db.query(TenantMembership.id)
        .join(Tenant, Tenant.id == TenantMembership.tenant_id)
        .filter(
            TenantMembership.user_id == actor_id,
            TenantMembership.tenant_id == tenant_id,
            TenantMembership.status == "active",
            Tenant.status == "active",
        )
        .first()
    )
    if membership is None:
        raise CovenantOwnershipError("An active tenant membership is required.")


def _get_application(db: Session, application_id: int, tenant_id: int) -> Application:
    if tenant_id is None:
        raise CovenantOwnershipError("An active tenant is required.")
    application = (
        db.query(Application)
        .filter(Application.id == application_id, Application.tenant_id == tenant_id)
        .first()
    )
    if application is None:
        raise CovenantOwnershipError("Application not found")
    return application


def get_covenant(db: Session, covenant_id: int, tenant_id: int) -> Optional[Covenant]:
    """Return a covenant only when its parent application belongs to the tenant."""
    if tenant_id is None:
        return None
    return (
        db.query(Covenant)
        .join(Application, Application.id == Covenant.application_id)
        .filter(Covenant.id == covenant_id, Application.tenant_id == tenant_id)
        .first()
    )


def _tenant_alert_query(db: Session, tenant_id: int):
    if tenant_id is None:
        raise CovenantOwnershipError("An active tenant is required.")
    return (
        db.query(CovenantAlert)
        .join(Covenant, Covenant.id == CovenantAlert.covenant_id)
        .join(Application, Application.id == Covenant.application_id)
        .outerjoin(CovenantMeasurement, CovenantMeasurement.id == CovenantAlert.measurement_id)
        .filter(
            Application.tenant_id == tenant_id,
            CovenantAlert.application_id == Application.id,
            or_(
                CovenantAlert.measurement_id.is_(None),
                CovenantMeasurement.covenant_id == Covenant.id,
            ),
        )
    )


def _notify_owner(db: Session, application_id: int, tenant_id: int, message: str) -> None:
    """Best-effort covenant-breach notification to the application's owner."""
    app = (
        db.query(Application)
        .filter(Application.id == application_id, Application.tenant_id == tenant_id)
        .first()
    )
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
    tenant_id: int,
    metric_key: str,
    threshold: float,
    operator: Optional[str] = None,
    name: Optional[str] = None,
    unit: Optional[str] = None,
    description: Optional[str] = None,
    actor: Any = None,
) -> Covenant:
    _require_tenant_membership(db, actor, tenant_id)
    _get_application(db, application_id, tenant_id)
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
    tenant_id: int,
    actor: Any = None,
) -> Dict[str, Any]:
    """Record a measurement, evaluate it, and auto-raise an alert on breach."""
    _require_tenant_membership(db, actor, tenant_id)
    owned_covenant = get_covenant(db, covenant.id, tenant_id)
    if owned_covenant is None:
        raise CovenantOwnershipError("Covenant not found")

    result = evaluate_covenant(owned_covenant.operator, owned_covenant.threshold, value)
    measurement = CovenantMeasurement(
        covenant_id=owned_covenant.id,
        value=value,
        status=result["status"],
        headroom=result["headroom"],
        period=period,
        source=source,
        note=note,
    )
    db.add(measurement)
    db.flush()

    alert = None
    if result["status"] == "breach":
        alert = CovenantAlert(
            covenant_id=owned_covenant.id,
            application_id=owned_covenant.application_id,
            measurement_id=measurement.id,
            severity="high",
            message=(
                f"Covenant breach: {owned_covenant.name} = {value} "
                f"({'>' if owned_covenant.operator == 'max' else '<'} threshold {owned_covenant.threshold})"
            ),
            status="open",
        )
        db.add(alert)
    db.commit()
    db.refresh(measurement)
    if alert is not None:
        db.refresh(alert)
        audit.record_safe(
            db,
            action="covenant.breach",
            actor=actor,
            entity_type="covenant",
            entity_id=owned_covenant.id,
            new_value={"value": value, "threshold": owned_covenant.threshold},
            reason=alert.message,
        )
        _notify_owner(db, owned_covenant.application_id, tenant_id, alert.message)

    return {
        "measurement": serialize_measurement(measurement),
        "alert": serialize_alert(alert) if alert else None,
    }


def covenant_trend(
    db: Session, covenant: Covenant, *, tenant_id: int, limit: int = 12
) -> Dict[str, Any]:
    """Recent measurements and a simple direction signal."""
    owned_covenant = get_covenant(db, covenant.id, tenant_id)
    if owned_covenant is None:
        raise CovenantOwnershipError("Covenant not found")
    rows: List[CovenantMeasurement] = (
        db.query(CovenantMeasurement)
        .join(Covenant, Covenant.id == CovenantMeasurement.covenant_id)
        .join(Application, Application.id == Covenant.application_id)
        .filter(CovenantMeasurement.covenant_id == covenant.id)
        .filter(Application.tenant_id == tenant_id)
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
            improving = delta > 0 if owned_covenant.operator == "min" else delta < 0
            direction = "improving" if improving else "deteriorating"

    return {
        "covenant_id": owned_covenant.id,
        "metric_key": owned_covenant.metric_key,
        "operator": owned_covenant.operator,
        "threshold": owned_covenant.threshold,
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


def list_covenants(db: Session, application_id: int, *, tenant_id: int) -> List[Covenant]:
    _get_application(db, application_id, tenant_id)
    return (
        db.query(Covenant)
        .filter(Covenant.application_id == application_id)
        .order_by(Covenant.id)
        .all()
    )


def list_alerts(
    db: Session,
    *,
    tenant_id: int,
    application_id: Optional[int] = None,
    status: Optional[str] = None,
) -> List[CovenantAlert]:
    query = _tenant_alert_query(db, tenant_id)
    if application_id is not None:
        _get_application(db, application_id, tenant_id)
        query = query.filter(CovenantAlert.application_id == application_id)
    if status:
        query = query.filter(CovenantAlert.status == status)
    return query.order_by(CovenantAlert.created_at.desc(), CovenantAlert.id.desc()).all()


def get_alert(db: Session, alert_id: int, tenant_id: int) -> Optional[CovenantAlert]:
    return _tenant_alert_query(db, tenant_id).filter(CovenantAlert.id == alert_id).first()


def count_alerts(
    db: Session, *, tenant_id: int, status: Optional[str] = None
) -> int:
    query = _tenant_alert_query(db, tenant_id)
    if status is not None:
        query = query.filter(CovenantAlert.status == status)
    return query.count()


def update_alert_status(
    db: Session, alert_id: int, status: str, *, tenant_id: int, actor: Any
) -> CovenantAlert:
    _require_tenant_membership(db, actor, tenant_id)
    alert = get_alert(db, alert_id, tenant_id)
    if alert is None:
        raise CovenantOwnershipError("Alert not found")
    alert.status = status
    db.commit()
    db.refresh(alert)
    return alert


def latest_measurement(
    db: Session, covenant: Covenant, *, tenant_id: int
) -> Optional[CovenantMeasurement]:
    if tenant_id is None:
        return None
    return (
        db.query(CovenantMeasurement)
        .join(Covenant, Covenant.id == CovenantMeasurement.covenant_id)
        .join(Application, Application.id == Covenant.application_id)
        .filter(
            CovenantMeasurement.covenant_id == covenant.id,
            Covenant.id == covenant.id,
            Application.tenant_id == tenant_id,
        )
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


def serialize_covenant(db: Session, cov: Covenant, *, tenant_id: int) -> Dict[str, Any]:
    owned_covenant = get_covenant(db, cov.id, tenant_id)
    if owned_covenant is None:
        raise CovenantOwnershipError("Covenant not found")
    latest = latest_measurement(db, owned_covenant, tenant_id=tenant_id)
    return {
        "id": owned_covenant.id,
        "application_id": owned_covenant.application_id,
        "metric_key": owned_covenant.metric_key,
        "name": owned_covenant.name,
        "operator": owned_covenant.operator,
        "threshold": owned_covenant.threshold,
        "unit": owned_covenant.unit,
        "description": owned_covenant.description,
        "is_active": owned_covenant.is_active,
        "current_value": latest.value if latest else None,
        "current_status": latest.status if latest else "unknown",
        "current_headroom": latest.headroom if latest else None,
    }
