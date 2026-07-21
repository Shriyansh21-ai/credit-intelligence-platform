"""Lifecycle service — the only sanctioned way to change an application's status.

Every transition is validated against the state machine, appended to the status
history (with actor / reason / comment), and audited. Rollback reverts to the
immediately preceding status recorded in history.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from backend.app.models.application import Application, ApplicationStatusHistory
from backend.app.services import audit, notifications
from backend.app.services.lifecycle.state_machine import (
    ApplicationStatus,
    InvalidTransition,
    STATUS_LABELS,
    next_statuses,
    validate_transition,
)


def _reference_for(app_id: int) -> str:
    return f"APP-{app_id:06d}"


def _actor_ids(actor: Any):
    return getattr(actor, "id", None), getattr(actor, "email", None)


def create_application(
    db: Session,
    *,
    actor: Any,
    company_name: str,
    industry: Optional[str] = None,
    gstin: Optional[str] = None,
    pan: Optional[str] = None,
    requested_amount: Optional[float] = None,
    loan_purpose: Optional[str] = None,
    tenure_months: Optional[int] = None,
    assessment_id: Optional[int] = None,
    assigned_to: Optional[int] = None,
    request: Any = None,
) -> Application:
    """Create a Draft application and record the opening history entry."""
    actor_id, actor_email = _actor_ids(actor)
    app = Application(
        user_id=actor_id,
        assigned_to=assigned_to,
        assessment_id=assessment_id,
        company_name=company_name,
        industry=industry,
        gstin=gstin,
        pan=pan,
        requested_amount=requested_amount,
        loan_purpose=loan_purpose,
        tenure_months=tenure_months,
        status=ApplicationStatus.DRAFT,
    )
    db.add(app)
    db.commit()
    db.refresh(app)

    app.reference = _reference_for(app.id)
    db.add(
        ApplicationStatusHistory(
            application_id=app.id,
            from_status=None,
            to_status=ApplicationStatus.DRAFT,
            kind="create",
            actor_id=actor_id,
            actor_email=actor_email,
            reason="Application created",
        )
    )
    db.commit()
    db.refresh(app)

    audit.record_safe(
        db,
        action="application.create",
        actor=actor,
        entity_type="application",
        entity_id=app.id,
        new_value={"status": ApplicationStatus.DRAFT, "company_name": company_name},
        request=request,
    )
    return app


def transition(
    db: Session,
    application: Application,
    to_status: str,
    *,
    actor: Any,
    reason: Optional[str] = None,
    comment: Optional[str] = None,
    request: Any = None,
    kind: str = "transition",
) -> Application:
    """Validate and apply a status change. Raises :class:`InvalidTransition`."""
    from_status = application.status
    validate_transition(from_status, to_status)

    actor_id, actor_email = _actor_ids(actor)
    application.status = to_status
    db.add(
        ApplicationStatusHistory(
            application_id=application.id,
            from_status=from_status,
            to_status=to_status,
            kind=kind,
            actor_id=actor_id,
            actor_email=actor_email,
            reason=reason,
            comment=comment,
        )
    )
    db.commit()
    db.refresh(application)

    audit.record_safe(
        db,
        action="application.transition",
        actor=actor,
        entity_type="application",
        entity_id=application.id,
        previous_value={"status": from_status},
        new_value={"status": to_status},
        reason=reason,
        request=request,
    )

    # Notify the application's owner/handler of the status change (best-effort).
    recipient = application.assigned_to or application.user_id
    actor_id = getattr(actor, "id", None)
    if recipient and recipient != actor_id:
        event = (
            "application_submitted"
            if to_status == ApplicationStatus.SUBMITTED
            else "status_changed"
        )
        notifications.notify_safe(
            db,
            user_id=recipient,
            event_type=event,
            title=f"Application {application.reference or application.id}",
            message=f"Status changed to {STATUS_LABELS.get(to_status, to_status)}",
            entity_type="application",
            entity_id=application.id,
            data={"from": from_status, "to": to_status},
        )
    return application


def rollback(
    db: Session,
    application: Application,
    *,
    actor: Any,
    reason: Optional[str] = None,
    request: Any = None,
) -> Application:
    """Revert to the previous status recorded in history.

    Rollback bypasses the forward state machine on purpose (an undo may not be a
    legal forward move) but is still fully audited and appended to history.
    """
    entries: List[ApplicationStatusHistory] = (
        db.query(ApplicationStatusHistory)
        .filter(ApplicationStatusHistory.application_id == application.id)
        .order_by(ApplicationStatusHistory.created_at, ApplicationStatusHistory.id)
        .all()
    )
    # Find the last entry that actually changed status to the current one.
    previous_status = None
    for entry in reversed(entries):
        if entry.to_status == application.status and entry.from_status is not None:
            previous_status = entry.from_status
            break

    if previous_status is None:
        raise InvalidTransition("Nothing to roll back to.")

    from_status = application.status
    actor_id, actor_email = _actor_ids(actor)
    application.status = previous_status
    db.add(
        ApplicationStatusHistory(
            application_id=application.id,
            from_status=from_status,
            to_status=previous_status,
            kind="rollback",
            actor_id=actor_id,
            actor_email=actor_email,
            reason=reason or "Rollback",
        )
    )
    db.commit()
    db.refresh(application)

    audit.record_safe(
        db,
        action="application.rollback",
        actor=actor,
        entity_type="application",
        entity_id=application.id,
        previous_value={"status": from_status},
        new_value={"status": previous_status},
        reason=reason,
        request=request,
    )
    return application


def get_timeline(db: Session, application: Application) -> List[Dict[str, Any]]:
    entries = (
        db.query(ApplicationStatusHistory)
        .filter(ApplicationStatusHistory.application_id == application.id)
        .order_by(ApplicationStatusHistory.created_at, ApplicationStatusHistory.id)
        .all()
    )
    return [
        {
            "id": e.id,
            "from_status": e.from_status,
            "from_label": STATUS_LABELS.get(e.from_status) if e.from_status else None,
            "to_status": e.to_status,
            "to_label": STATUS_LABELS.get(e.to_status),
            "kind": e.kind,
            "actor_id": e.actor_id,
            "actor_email": e.actor_email,
            "reason": e.reason,
            "comment": e.comment,
            "created_at": e.created_at.isoformat() if e.created_at else None,
        }
        for e in entries
    ]


def serialize(application: Application) -> Dict[str, Any]:
    return {
        "id": application.id,
        "reference": application.reference,
        "user_id": application.user_id,
        "assigned_to": application.assigned_to,
        "assessment_id": application.assessment_id,
        "company_name": application.company_name,
        "industry": application.industry,
        "gstin": application.gstin,
        "pan": application.pan,
        "loan_id": application.loan_id,
        "requested_amount": application.requested_amount,
        "loan_purpose": application.loan_purpose,
        "tenure_months": application.tenure_months,
        "risk_rating": application.risk_rating,
        "risk_grade": application.risk_grade,
        "status": application.status,
        "status_label": STATUS_LABELS.get(application.status),
        "available_transitions": next_statuses(application.status),
        "created_at": application.created_at.isoformat() if application.created_at else None,
        "updated_at": application.updated_at.isoformat() if application.updated_at else None,
    }
