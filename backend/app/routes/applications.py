"""Application lifecycle API.

    POST /api/applications create (Draft)
    GET /api/applications list (filter + paginate)
    GET /api/applications/statuses status catalog + transition graph
    GET /api/applications/{id} detail (with timeline)
    PATCH /api/applications/{id} edit fields
    POST /api/applications/{id}/submit Draft -> Submitted
    POST /api/applications/{id}/transition validated status change
    POST /api/applications/{id}/rollback revert to previous status
    POST /api/applications/{id}/cancel cancel
    GET /api/applications/{id}/history status history timeline
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status as http_status
from sqlalchemy.orm import Session

from backend.app.db.database import get_db
from backend.app.models.application import Application
from backend.app.models.user import User
from backend.app.schemas.application import (
    ApplicationCreate,
    ApplicationUpdate,
    RollbackRequest,
    TransitionRequest,
)
from backend.app.services import lifecycle
from backend.app.services.lifecycle.service import get_timeline, serialize
from backend.app.services.lifecycle.state_machine import (
    ALLOWED_TRANSITIONS,
    ApplicationStatus,
    InvalidTransition,
    STATUS_LABELS,
    STATUSES,
    next_statuses,
)
from backend.app.services.rbac import require_permission

router = APIRouter(prefix="/api/applications", tags=["Applications"])


def _get_app(db: Session, application_id: int) -> Application:
    app = db.query(Application).filter(Application.id == application_id).first()
    if app is None:
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="Application not found")
    return app


@router.post("", status_code=http_status.HTTP_201_CREATED)
def create_application(
    payload: ApplicationCreate,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("applications.create")),
):
    app = lifecycle.create_application(
        db,
        actor=actor,
        company_name=payload.company_name,
        industry=payload.industry,
        gstin=payload.gstin,
        pan=payload.pan,
        requested_amount=payload.requested_amount,
        loan_purpose=payload.loan_purpose,
        tenure_months=payload.tenure_months,
        assessment_id=payload.assessment_id,
        assigned_to=payload.assigned_to,
        request=request,
    )
    return serialize(app)


@router.get("")
def list_applications(
    status: Optional[str] = None,
    industry: Optional[str] = None,
    q: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
    db: Session = Depends(get_db),
    _user: User = Depends(require_permission("applications.view")),
):
    query = db.query(Application)
    if status:
        query = query.filter(Application.status == status)
    if industry:
        query = query.filter(Application.industry == industry)
    if q:
        like = f"%{q}%"
        query = query.filter(
            Application.company_name.like(like)
            | Application.reference.like(like)
            | Application.gstin.like(like)
        )
    total = query.count()
    rows = (
        query.order_by(Application.updated_at.desc(), Application.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {
        "items": [serialize(a) for a in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": (total + page_size - 1) // page_size,
    }


@router.get("/statuses")
def list_statuses(
    _user: User = Depends(require_permission("applications.view")),
):
    return {
        "statuses": [
            {
                "value": s,
                "label": STATUS_LABELS.get(s),
                "next": next_statuses(s),
            }
            for s in STATUSES
        ],
        "transitions": {k: sorted(v) for k, v in ALLOWED_TRANSITIONS.items()},
    }


@router.get("/{application_id}")
def get_application(
    application_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(require_permission("applications.view")),
):
    app = _get_app(db, application_id)
    data = serialize(app)
    data["timeline"] = get_timeline(db, app)
    return data


@router.patch("/{application_id}")
def update_application(
    application_id: int,
    payload: ApplicationUpdate,
    db: Session = Depends(get_db),
    _user: User = Depends(require_permission("applications.edit")),
):
    app = _get_app(db, application_id)
    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(app, field, value)
    db.commit()
    db.refresh(app)
    return serialize(app)


@router.post("/{application_id}/submit")
def submit_application(
    application_id: int,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("applications.submit")),
):
    app = _get_app(db, application_id)
    try:
        lifecycle.transition(
            db, app, ApplicationStatus.SUBMITTED, actor=actor,
            reason="Submitted for processing", request=request,
        )
    except InvalidTransition as exc:
        raise HTTPException(status_code=http_status.HTTP_409_CONFLICT, detail=str(exc))
    return serialize(app)


@router.post("/{application_id}/transition")
def transition_application(
    application_id: int,
    payload: TransitionRequest,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("applications.transition")),
):
    app = _get_app(db, application_id)
    try:
        lifecycle.transition(
            db, app, payload.to_status, actor=actor,
            reason=payload.reason, comment=payload.comment, request=request,
        )
    except InvalidTransition as exc:
        raise HTTPException(status_code=http_status.HTTP_409_CONFLICT, detail=str(exc))
    return serialize(app)


@router.post("/{application_id}/rollback")
def rollback_application(
    application_id: int,
    payload: RollbackRequest,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("applications.rollback")),
):
    app = _get_app(db, application_id)
    try:
        lifecycle.rollback(db, app, actor=actor, reason=payload.reason, request=request)
    except InvalidTransition as exc:
        raise HTTPException(status_code=http_status.HTTP_409_CONFLICT, detail=str(exc))
    return serialize(app)


@router.post("/{application_id}/cancel")
def cancel_application(
    application_id: int,
    payload: RollbackRequest,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("applications.cancel")),
):
    app = _get_app(db, application_id)
    try:
        lifecycle.transition(
            db, app, ApplicationStatus.CANCELLED, actor=actor,
            reason=payload.reason or "Cancelled", request=request,
        )
    except InvalidTransition as exc:
        raise HTTPException(status_code=http_status.HTTP_409_CONFLICT, detail=str(exc))
    return serialize(app)


@router.get("/{application_id}/history")
def application_history(
    application_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(require_permission("applications.view")),
):
    app = _get_app(db, application_id)
    return {"application_id": app.id, "timeline": get_timeline(db, app)}
