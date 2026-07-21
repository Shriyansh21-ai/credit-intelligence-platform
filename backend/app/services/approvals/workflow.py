"""Approval workflow configuration and the default multi-stage matrix.

The default workflow maps approval stages onto the lifecycle review pipeline
(analyst review -> senior analyst review -> credit committee -> approved). It is
seeded idempotently and can be edited/replaced via the approvals config API.
"""

from __future__ import annotations

from typing import Any, Dict, List

from sqlalchemy.orm import Session

from backend.app.models.approval import ApprovalWorkflow
from backend.app.services.lifecycle.state_machine import ApplicationStatus

# The approver actions supported at every stage.
ACTIONS = ("approve", "reject", "request_changes", "escalate", "hold", "comment")

# Ordered lifecycle statuses that make up the review pipeline. Approving advances
# to the next entry; the final approve lands on APPROVED.
REVIEW_PIPELINE: List[str] = [
    ApplicationStatus.ANALYST_REVIEW,
    ApplicationStatus.SENIOR_ANALYST_REVIEW,
    ApplicationStatus.CREDIT_COMMITTEE,
]
APPROVED_STATUS = ApplicationStatus.APPROVED

DEFAULT_WORKFLOW: Dict[str, Any] = {
    "name": "Standard Credit Approval",
    "description": "Default multi-stage bank credit approval matrix.",
    "is_default": True,
    "is_active": True,
    "stages": [
        {
            "key": "junior_analyst",
            "name": "Junior Analyst",
            "order": 1,
            "status": ApplicationStatus.ANALYST_REVIEW,
            "permission": "approvals.request_changes",
            "role": "credit_analyst",
        },
        {
            "key": "senior_analyst",
            "name": "Senior Analyst",
            "order": 2,
            "status": ApplicationStatus.SENIOR_ANALYST_REVIEW,
            "permission": "approvals.approve",
            "role": "senior_analyst",
        },
        {
            "key": "risk_manager",
            "name": "Risk Manager",
            "order": 3,
            "status": ApplicationStatus.SENIOR_ANALYST_REVIEW,
            "permission": "approvals.approve",
            "role": "risk_manager",
        },
        {
            "key": "credit_committee",
            "name": "Credit Committee",
            "order": 4,
            "status": ApplicationStatus.CREDIT_COMMITTEE,
            "permission": "approvals.approve",
            "role": "risk_manager",
        },
        {
            "key": "regional_manager",
            "name": "Regional Manager",
            "order": 5,
            "status": ApplicationStatus.CREDIT_COMMITTEE,
            "permission": "approvals.approve",
            "role": "risk_manager",
        },
        {
            "key": "admin_override",
            "name": "Admin Override",
            "order": 6,
            "status": None,
            "permission": "approvals.override",
            "role": "administrator",
        },
    ],
}


def ensure_default_workflow(db: Session) -> ApprovalWorkflow:
    """Create the default workflow if none exists; return the default workflow."""
    existing = db.query(ApprovalWorkflow).filter(ApprovalWorkflow.is_default == True).first()  # noqa: E712
    if existing is not None:
        return existing
    wf = ApprovalWorkflow(
        name=DEFAULT_WORKFLOW["name"],
        description=DEFAULT_WORKFLOW["description"],
        is_default=True,
        is_active=True,
        stages=DEFAULT_WORKFLOW["stages"],
    )
    db.add(wf)
    db.commit()
    db.refresh(wf)
    return wf


def get_default_workflow(db: Session) -> ApprovalWorkflow:
    return ensure_default_workflow(db)


def next_pipeline_status(current_status: str) -> str | None:
    """The lifecycle status an ``approve`` should advance to from ``current``."""
    # Entry points that should drop into the start of the pipeline.
    entry_points = {
        ApplicationStatus.SUBMITTED,
        ApplicationStatus.DOCUMENTS_PENDING,
        ApplicationStatus.UNDER_AI_ANALYSIS,
    }
    if current_status in entry_points:
        return REVIEW_PIPELINE[0]
    if current_status in REVIEW_PIPELINE:
        idx = REVIEW_PIPELINE.index(current_status)
        if idx + 1 < len(REVIEW_PIPELINE):
            return REVIEW_PIPELINE[idx + 1]
        return APPROVED_STATUS
    return None


def target_status_for_action(action: str, current_status: str) -> str | None:
    """Resolve the lifecycle status an action should move the application to.

    Returns ``None`` when the action is non-transitional (hold / comment) or no
    sensible target exists from the current status.
    """
    if action in ("approve", "escalate"):
        return next_pipeline_status(current_status)
    if action == "reject":
        return ApplicationStatus.REJECTED
    if action == "request_changes":
        return ApplicationStatus.DOCUMENTS_PENDING
    return None


def serialize_workflow(wf: ApprovalWorkflow) -> Dict[str, Any]:
    return {
        "id": wf.id,
        "name": wf.name,
        "description": wf.description,
        "is_default": wf.is_default,
        "is_active": wf.is_active,
        "stages": wf.stages,
    }
