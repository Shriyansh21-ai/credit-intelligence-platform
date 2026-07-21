"""Approval decision service.

Records an approver's action against an application and, where the action implies
a lifecycle move, drives the state machine through the lifecycle service so the
transition is validated, historised and audited exactly once.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from backend.app.models.application import Application
from backend.app.models.approval import ApprovalDecision, ApprovalWorkflow
from backend.app.services import audit, lifecycle, notifications
from backend.app.services.approvals.workflow import (
    ACTIONS,
    get_default_workflow,
    target_status_for_action,
)
from backend.app.services.lifecycle.state_machine import InvalidTransition


class ApprovalError(ValueError):
    """Raised for an unknown action or an otherwise invalid decision."""


def _stage(workflow: Optional[ApprovalWorkflow], stage_key: Optional[str]) -> Dict[str, Any]:
    if workflow is None or not stage_key:
        return {}
    for stage in workflow.stages or []:
        if stage.get("key") == stage_key:
            return stage
    return {}


def submit_decision(
    db: Session,
    application: Application,
    *,
    action: str,
    actor: Any,
    stage_key: Optional[str] = None,
    comment: Optional[str] = None,
    workflow: Optional[ApprovalWorkflow] = None,
    request: Any = None,
) -> Dict[str, Any]:
    """Record a decision and apply any implied lifecycle transition.

    Returns ``{decision, status_changed, application}``. If the implied
    transition is illegal from the current status, the decision is still recorded
    (audit trail matters) but the status is left unchanged.
    """
    if action not in ACTIONS:
        raise ApprovalError(f"Unknown approval action: {action!r}")

    workflow = workflow or get_default_workflow(db)
    stage = _stage(workflow, stage_key)
    from_status = application.status

    target = target_status_for_action(action, from_status)
    status_changed = False
    transition_error: Optional[str] = None

    if target is not None:
        try:
            lifecycle.transition(
                db,
                application,
                target,
                actor=actor,
                reason=f"Approval action: {action}",
                comment=comment,
                request=request,
            )
            status_changed = True
        except InvalidTransition as exc:
            transition_error = str(exc)

    to_status = application.status if status_changed else None

    decision = ApprovalDecision(
        application_id=application.id,
        workflow_id=workflow.id if workflow else None,
        stage_key=stage_key,
        stage_name=stage.get("name"),
        action=action,
        actor_id=getattr(actor, "id", None),
        actor_email=getattr(actor, "email", None),
        comment=comment,
        from_status=from_status,
        to_status=to_status,
    )
    db.add(decision)
    db.commit()
    db.refresh(decision)

    audit.record_safe(
        db,
        action=f"approval.{action}",
        actor=actor,
        entity_type="application",
        entity_id=application.id,
        previous_value={"status": from_status},
        new_value={"status": to_status} if status_changed else None,
        reason=comment,
        request=request,
        meta={"stage": stage_key, "transition_error": transition_error},
    )

    # Notify the application owner of the decision (best-effort).
    recipient = application.assigned_to or application.user_id
    actor_id = getattr(actor, "id", None)
    if recipient and recipient != actor_id:
        notifications.notify_safe(
            db,
            user_id=recipient,
            event_type="approval_required" if action in ("request_changes",) else "status_changed",
            title=f"Approval: {action}",
            message=f"{stage.get('name') or stage_key or 'Stage'} — {action}",
            entity_type="application",
            entity_id=application.id,
        )

    return {
        "decision": serialize_decision(decision),
        "status_changed": status_changed,
        "transition_error": transition_error,
        "application": lifecycle.service.serialize(application),
    }


def serialize_decision(d: ApprovalDecision) -> Dict[str, Any]:
    return {
        "id": d.id,
        "application_id": d.application_id,
        "workflow_id": d.workflow_id,
        "stage_key": d.stage_key,
        "stage_name": d.stage_name,
        "action": d.action,
        "actor_id": d.actor_id,
        "actor_email": d.actor_email,
        "comment": d.comment,
        "from_status": d.from_status,
        "to_status": d.to_status,
        "created_at": d.created_at.isoformat() if d.created_at else None,
    }


def get_approval_timeline(db: Session, application: Application) -> List[Dict[str, Any]]:
    rows = (
        db.query(ApprovalDecision)
        .filter(ApprovalDecision.application_id == application.id)
        .order_by(ApprovalDecision.created_at, ApprovalDecision.id)
        .all()
    )
    return [serialize_decision(r) for r in rows]
