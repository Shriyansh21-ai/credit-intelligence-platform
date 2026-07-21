"""Approval workflow API (Phase 5, Milestone 2).

    GET  /api/approvals/workflow                       default workflow config
    PUT  /api/approvals/workflow                       edit workflow (approvals.configure)
    GET  /api/approvals/applications/{id}/decisions    approval timeline
    POST /api/approvals/applications/{id}/decisions    submit a decision

Each decision's required permission is derived from its action (approve, reject,
request_changes, escalate, hold, comment).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status as http_status
from sqlalchemy.orm import Session

from backend.app.core.dependencies import get_current_user
from backend.app.db.database import get_db
from backend.app.models.application import Application
from backend.app.models.user import User
from backend.app.schemas.application import DecisionRequest, WorkflowUpdate
from backend.app.services import approvals, audit
from backend.app.services.approvals.service import ApprovalError, get_approval_timeline
from backend.app.services.approvals.workflow import get_default_workflow, serialize_workflow
from backend.app.services.rbac import has_permission, require_permission

router = APIRouter(prefix="/api/approvals", tags=["Approvals"])

# Which permission each approval action requires.
_ACTION_PERMISSION = {
    "approve": "approvals.approve",
    "reject": "approvals.reject",
    "request_changes": "approvals.request_changes",
    "escalate": "approvals.escalate",
    "hold": "approvals.hold",
    "comment": "approvals.view",
}


@router.get("/workflow")
def get_workflow(
    db: Session = Depends(get_db),
    _user: User = Depends(require_permission("approvals.view")),
):
    return serialize_workflow(get_default_workflow(db))


@router.put("/workflow")
def update_workflow(
    payload: WorkflowUpdate,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("approvals.configure")),
):
    wf = get_default_workflow(db)
    before = serialize_workflow(wf)
    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(wf, field, value)
    db.commit()
    db.refresh(wf)
    audit.record_safe(
        db,
        action="approval.configure",
        actor=actor,
        entity_type="approval_workflow",
        entity_id=wf.id,
        previous_value=before,
        new_value=serialize_workflow(wf),
        request=request,
    )
    return serialize_workflow(wf)


def _get_app(db: Session, application_id: int) -> Application:
    app = db.query(Application).filter(Application.id == application_id).first()
    if app is None:
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="Application not found")
    return app


@router.get("/applications/{application_id}/decisions")
def list_decisions(
    application_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(require_permission("approvals.view")),
):
    app = _get_app(db, application_id)
    return {"application_id": app.id, "timeline": get_approval_timeline(db, app)}


@router.post("/applications/{application_id}/decisions")
def submit_decision(
    application_id: int,
    payload: DecisionRequest,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    required = _ACTION_PERMISSION.get(payload.action)
    if required is None:
        raise HTTPException(status_code=http_status.HTTP_400_BAD_REQUEST, detail="Unknown action")
    if not has_permission(db, actor, required):
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail=f"Missing required permission: {required}",
        )

    app = _get_app(db, application_id)
    try:
        result = approvals.submit_decision(
            db, app,
            action=payload.action,
            actor=actor,
            stage_key=payload.stage_key,
            comment=payload.comment,
            request=request,
        )
    except ApprovalError as exc:
        raise HTTPException(status_code=http_status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return result
