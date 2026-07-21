"""Covenant monitoring API (Phase 5, Milestone 5).

    GET  /api/covenants/metrics                              metric catalog
    GET  /api/covenants/applications/{app_id}                covenants for an app
    POST /api/covenants/applications/{app_id}                create a covenant
    POST /api/covenants/{covenant_id}/measurements           record a measurement
    GET  /api/covenants/{covenant_id}/trend                  trend + points
    GET  /api/covenants/applications/{app_id}/alerts         breach alerts
    PATCH /api/covenants/alerts/{alert_id}                   update alert status
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status as http_status
from sqlalchemy.orm import Session

from backend.app.db.database import get_db
from backend.app.models.covenant import Covenant, CovenantAlert
from backend.app.models.user import User
from backend.app.schemas.covenant import (
    AlertStatusUpdate,
    BatchMeasurementRequest,
    CovenantCreate,
    MeasurementCreate,
)
from backend.app.services import covenants
from backend.app.services.covenants.catalog import COVENANT_METRICS
from backend.app.services.covenants.service import serialize_alert
from backend.app.services.rbac import require_permission

router = APIRouter(prefix="/api/covenants", tags=["Covenants"])


def _get_covenant(db: Session, covenant_id: int) -> Covenant:
    cov = db.query(Covenant).filter(Covenant.id == covenant_id).first()
    if cov is None:
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="Covenant not found")
    return cov


@router.get("/metrics")
def list_metrics(_user: User = Depends(require_permission("covenants.view"))):
    return {
        "metrics": [
            {"key": key, **definition} for key, definition in COVENANT_METRICS.items()
        ]
    }


@router.get("/applications/{application_id}")
def list_for_application(
    application_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(require_permission("covenants.view")),
):
    rows = covenants.list_covenants(db, application_id)
    return {"covenants": [covenants.serialize_covenant(db, c) for c in rows]}


@router.post("/applications/{application_id}", status_code=http_status.HTTP_201_CREATED)
def create_covenant(
    application_id: int,
    payload: CovenantCreate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("covenants.manage")),
):
    cov = covenants.create_covenant(
        db,
        application_id=application_id,
        metric_key=payload.metric_key,
        threshold=payload.threshold,
        operator=payload.operator,
        name=payload.name,
        unit=payload.unit,
        description=payload.description,
        actor=actor,
    )
    return covenants.serialize_covenant(db, cov)


@router.post("/{covenant_id}/measurements")
def add_measurement(
    covenant_id: int,
    payload: MeasurementCreate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("covenants.manage")),
):
    cov = _get_covenant(db, covenant_id)
    return covenants.record_measurement(
        db, cov,
        value=payload.value,
        period=payload.period,
        source=payload.source,
        note=payload.note,
        actor=actor,
    )


@router.post("/batch-measurements")
def add_measurements_batch(
    payload: BatchMeasurementRequest,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("covenants.manage")),
):
    """Record measurements for many covenants in one call (batch processing)."""
    results = []
    breaches = 0
    for item in payload.items:
        cov = db.query(Covenant).filter(Covenant.id == item.covenant_id).first()
        if cov is None:
            results.append({"covenant_id": item.covenant_id, "error": "not found"})
            continue
        outcome = covenants.record_measurement(
            db, cov, value=item.value, period=item.period, source=item.source, actor=actor
        )
        if outcome["measurement"]["status"] == "breach":
            breaches += 1
        results.append({"covenant_id": item.covenant_id, **outcome})
    return {"processed": len(results), "breaches": breaches, "results": results}


@router.get("/{covenant_id}/trend")
def covenant_trend(
    covenant_id: int,
    limit: int = 12,
    db: Session = Depends(get_db),
    _user: User = Depends(require_permission("covenants.view")),
):
    cov = _get_covenant(db, covenant_id)
    return covenants.covenant_trend(db, cov, limit=limit)


@router.get("/applications/{application_id}/alerts")
def application_alerts(
    application_id: int,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    _user: User = Depends(require_permission("covenants.view")),
):
    rows = covenants.list_alerts(db, application_id=application_id, status=status)
    return {"alerts": [serialize_alert(a) for a in rows]}


@router.patch("/alerts/{alert_id}")
def update_alert(
    alert_id: int,
    payload: AlertStatusUpdate,
    db: Session = Depends(get_db),
    _user: User = Depends(require_permission("covenants.manage")),
):
    alert = db.query(CovenantAlert).filter(CovenantAlert.id == alert_id).first()
    if alert is None:
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="Alert not found")
    alert.status = payload.status
    db.commit()
    db.refresh(alert)
    return serialize_alert(alert)
