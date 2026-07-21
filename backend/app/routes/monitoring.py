"""Post-disbursement monitoring API (Phase 5, Milestone 6).

    GET   /api/monitoring/record-types                       supported record types
    GET   /api/monitoring/applications/{app_id}/records      all monitoring records
    POST  /api/monitoring/applications/{app_id}/records      add a record (auto-alerts)
    GET   /api/monitoring/applications/{app_id}/health        health timeline
    GET   /api/monitoring/applications/{app_id}/trend         risk trend
    GET   /api/monitoring/applications/{app_id}/alerts        deterioration alerts
    PATCH /api/monitoring/alerts/{alert_id}                   update alert status
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status as http_status
from sqlalchemy.orm import Session

from backend.app.db.database import get_db
from backend.app.models.monitoring import MonitoringAlert
from backend.app.models.user import User
from backend.app.schemas.monitoring import MonitoringAlertUpdate, MonitoringRecordCreate
from backend.app.services import monitoring
from backend.app.services.monitoring.service import records_for, serialize_alert
from backend.app.services.rbac import require_permission

router = APIRouter(prefix="/api/monitoring", tags=["Monitoring"])


@router.get("/record-types")
def record_types(_user: User = Depends(require_permission("monitoring.view"))):
    return {"record_types": list(monitoring.RECORD_TYPES)}


@router.get("/applications/{application_id}/records")
def list_records(
    application_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(require_permission("monitoring.view")),
):
    rows = records_for(db, application_id)
    return {"records": [monitoring.serialize_record(r) for r in rows]}


@router.post("/applications/{application_id}/records", status_code=http_status.HTTP_201_CREATED)
def add_record(
    application_id: int,
    payload: MonitoringRecordCreate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("monitoring.manage")),
):
    return monitoring.add_record(
        db,
        application_id=application_id,
        record_type=payload.record_type,
        period=payload.period,
        health_score=payload.health_score,
        risk_rating=payload.risk_rating,
        payment_status=payload.payment_status,
        data=payload.data,
        note=payload.note,
        actor=actor,
    )


@router.get("/applications/{application_id}/health")
def health(
    application_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(require_permission("monitoring.view")),
):
    return {"application_id": application_id, "timeline": monitoring.health_timeline(db, application_id)}


@router.get("/applications/{application_id}/trend")
def trend(
    application_id: int,
    window: int = 6,
    db: Session = Depends(get_db),
    _user: User = Depends(require_permission("monitoring.view")),
):
    return monitoring.risk_trend(db, application_id, window=window)


@router.get("/applications/{application_id}/alerts")
def alerts(
    application_id: int,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    _user: User = Depends(require_permission("monitoring.view")),
):
    return {"alerts": monitoring.deterioration_alerts(db, application_id, status=status)}


@router.patch("/alerts/{alert_id}")
def update_alert(
    alert_id: int,
    payload: MonitoringAlertUpdate,
    db: Session = Depends(get_db),
    _user: User = Depends(require_permission("monitoring.manage")),
):
    alert = db.query(MonitoringAlert).filter(MonitoringAlert.id == alert_id).first()
    if alert is None:
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="Alert not found")
    alert.status = payload.status
    db.commit()
    db.refresh(alert)
    return serialize_alert(alert)
