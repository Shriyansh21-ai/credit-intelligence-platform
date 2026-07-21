"""Approval workflow models (Phase 5, Milestone 2).

``ApprovalWorkflow`` is a configurable, ordered set of approval stages (stored as
JSON so the matrix can be edited without a migration). ``ApprovalDecision`` is an
append-only record of every action taken by an approver against an application.
"""

from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, JSON, String, Text

from backend.app.db.database import Base


class ApprovalWorkflow(Base):
    __tablename__ = "approval_workflows"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, unique=True)
    description = Column(String, nullable=True)
    is_default = Column(Boolean, nullable=False, default=False)
    is_active = Column(Boolean, nullable=False, default=True)

    # Ordered list of stage dicts:
    # {key, name, order, status, permission, role}.
    stages = Column(JSON, nullable=False, default=list)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ApprovalDecision(Base):
    __tablename__ = "approval_decisions"

    id = Column(Integer, primary_key=True, index=True)
    application_id = Column(
        Integer, ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True
    )
    workflow_id = Column(Integer, ForeignKey("approval_workflows.id"), nullable=True)

    stage_key = Column(String, nullable=True)
    stage_name = Column(String, nullable=True)

    # One of: approve / reject / request_changes / escalate / hold / comment.
    action = Column(String, nullable=False, index=True)

    actor_id = Column(Integer, nullable=True)
    actor_email = Column(String, nullable=True)

    comment = Column(Text, nullable=True)

    # Lifecycle status before/after this decision (after may be null if the
    # decision did not move the application).
    from_status = Column(String, nullable=True)
    to_status = Column(String, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, index=True)
