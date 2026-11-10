"""Covenant monitoring API.

    GET /api/covenants/metrics metric catalog
    GET /api/covenants/applications/{app_id} covenants for an app
    POST /api/covenants/applications/{app_id} create a covenant
    POST /api/covenants/{covenant_id}/measurements record a measurement
    GET /api/covenants/{covenant_id}/trend trend + points
    GET /api/covenants/applications/{app_id}/alerts breach alerts
    PATCH /api/covenants/alerts/{alert_id} update alert status
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status as http_status
from sqlalchemy.orm import Session

from backend.app.core.dependencies import get_current_tenant_id
from backend.app.db.database import get_db
from backend.app.models.covenant import Covenant
from backend.app.models.user import User
from backend.app.schemas.covenant import (
    AlertStatusUpdate,
    BatchMeasurementRequest,
    CovenantCreate,
    MeasurementCreate,
)
from backend.app.services import covenants
from backend.app.services.covenants.catalog import COVENANT_METRICS
from backend.app.services.covenants.service import (
    CovenantOwnershipError,
    serialize_alert,
)
from backend.app.services.rbac import require_permission

router = APIRouter(prefix="/api/covenants", tags=["Covenants"])


def _get_covenant(db: Session, covenant_id: int, tenant_id: int) -> Covenant:
    cov = covenants.get_covenant(db, covenant_id, tenant_id)
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
    tenant_id: int = Depends(get_current_tenant_id),
    _user: User = Depends(require_permission("covenants.view")),
):
    try:
        rows = covenants.list_covenants(db, application_id, tenant_id=tenant_id)
    except CovenantOwnershipError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND, detail="Application not found"
        ) from exc
    return {
        "covenants": [
            covenants.serialize_covenant(db, covenant, tenant_id=tenant_id)
            for covenant in rows
        ]
    }


@router.post("/applications/{application_id}", status_code=http_status.HTTP_201_CREATED)
def create_covenant(
    application_id: int,
    payload: CovenantCreate,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    actor: User = Depends(require_permission("covenants.manage")),
):
    try:
        cov = covenants.create_covenant(
            db,
            application_id=application_id,
            tenant_id=tenant_id,
            metric_key=payload.metric_key,
            threshold=payload.threshold,
            operator=payload.operator,
            name=payload.name,
            unit=payload.unit,
            description=payload.description,
            actor=actor,
        )
    except CovenantOwnershipError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND, detail="Application not found"
        ) from exc
    return covenants.serialize_covenant(db, cov, tenant_id=tenant_id)


@router.post("/{covenant_id}/measurements")
def add_measurement(
    covenant_id: int,
    payload: MeasurementCreate,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    actor: User = Depends(require_permission("covenants.manage")),
):
    cov = _get_covenant(db, covenant_id, tenant_id)
    try:
        return covenants.record_measurement(
            db,
            cov,
            tenant_id=tenant_id,
            value=payload.value,
            period=payload.period,
            source=payload.source,
            note=payload.note,
            actor=actor,
        )
    except CovenantOwnershipError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND, detail="Covenant not found"
        ) from exc


@router.post("/batch-measurements")
def add_measurements_batch(
    payload: BatchMeasurementRequest,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    actor: User = Depends(require_permission("covenants.manage")),
):
    """Record measurements for many covenants in one call (batch processing)."""
    owned_covenants = {}
    for item in payload.items:
        if item.covenant_id not in owned_covenants:
            owned_covenants[item.covenant_id] = covenants.get_covenant(
                db, item.covenant_id, tenant_id
            )
        if owned_covenants[item.covenant_id] is None:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND, detail="Covenant not found"
            )

    results = []
    breaches = 0
    for item in payload.items:
        cov = owned_covenants[item.covenant_id]
        try:
            outcome = covenants.record_measurement(
                db,
                cov,
                tenant_id=tenant_id,
                value=item.value,
                period=item.period,
                source=item.source,
                actor=actor,
            )
        except CovenantOwnershipError as exc:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND, detail="Covenant not found"
            ) from exc
        if outcome["measurement"]["status"] == "breach":
            breaches += 1
        results.append({"covenant_id": item.covenant_id, **outcome})
    return {"processed": len(results), "breaches": breaches, "results": results}


@router.get("/{covenant_id}/trend")
def covenant_trend(
    covenant_id: int,
    limit: int = 12,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    _user: User = Depends(require_permission("covenants.view")),
):
    cov = _get_covenant(db, covenant_id, tenant_id)
    try:
        return covenants.covenant_trend(db, cov, tenant_id=tenant_id, limit=limit)
    except CovenantOwnershipError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND, detail="Covenant not found"
        ) from exc


@router.get("/applications/{application_id}/alerts")
def application_alerts(
    application_id: int,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    _user: User = Depends(require_permission("covenants.view")),
):
    try:
        rows = covenants.list_alerts(
            db,
            tenant_id=tenant_id,
            application_id=application_id,
            status=status,
        )
    except CovenantOwnershipError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND, detail="Application not found"
        ) from exc
    return {"alerts": [serialize_alert(a) for a in rows]}


@router.patch("/alerts/{alert_id}")
def update_alert(
    alert_id: int,
    payload: AlertStatusUpdate,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    actor: User = Depends(require_permission("covenants.manage")),
):
    try:
        alert = covenants.update_alert_status(
            db, alert_id, payload.status, tenant_id=tenant_id, actor=actor
        )
    except CovenantOwnershipError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND, detail="Alert not found"
        ) from exc
    return serialize_alert(alert)
