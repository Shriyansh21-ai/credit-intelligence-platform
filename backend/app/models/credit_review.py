"""Tenant-scoped credit review and decision history."""

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import (
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)

from backend.app.db.database import Base


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class CreditReviewCase(Base):
    __tablename__ = "credit_review_cases"
    __table_args__ = (
        UniqueConstraint("tenant_id", "reference", name="uq_credit_review_tenant_reference"),
    )

    id = Column(Integer, primary_key=True, index=True)
    reference = Column(String(36), nullable=False, default=lambda: str(uuid4()), index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False)
    review_type = Column(String(40), nullable=False)
    title = Column(String(200), nullable=False)
    purpose = Column(Text, nullable=True)
    status = Column(String(32), nullable=False, default="draft", index=True)
    cycle_number = Column(Integer, nullable=False, default=1)
    analyst_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    reviewer_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    due_date = Column(Date, nullable=True)
    reporting_periods = Column(JSON, nullable=False, default=list)
    financial_record_ids = Column(JSON, nullable=False, default=list)
    revision = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime, nullable=False, default=_utcnow)
    updated_at = Column(DateTime, nullable=False, default=_utcnow, onupdate=_utcnow)


class CreditReviewAssessment(Base):
    __tablename__ = "credit_review_assessments"
    __table_args__ = (
        UniqueConstraint("case_id", "version", name="uq_credit_review_assessment_version"),
    )

    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(
        Integer, ForeignKey("credit_review_cases.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    version = Column(Integer, nullable=False)
    summary = Column(Text, nullable=False)
    strengths = Column(JSON, nullable=False, default=list)
    weaknesses = Column(JSON, nullable=False, default=list)
    risk_indicators = Column(JSON, nullable=False, default=list)
    data_quality_concerns = Column(JSON, nullable=False, default=list)
    mitigations = Column(JSON, nullable=False, default=list)
    outstanding_questions = Column(JSON, nullable=False, default=list)
    evidence_refs = Column(JSON, nullable=False, default=dict)
    recommendation = Column(String(40), nullable=False)
    recommendation_rationale = Column(Text, nullable=False)
    author_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    submitted_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=_utcnow)


class CreditReviewDecision(Base):
    __tablename__ = "credit_review_decisions"

    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(
        Integer, ForeignKey("credit_review_cases.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    assessment_id = Column(
        Integer, ForeignKey("credit_review_assessments.id", ondelete="RESTRICT"), nullable=False
    )
    previous_decision_id = Column(
        Integer, ForeignKey("credit_review_decisions.id", ondelete="RESTRICT"), nullable=True
    )
    outcome = Column(String(40), nullable=False)
    cycle_number = Column(Integer, nullable=False, default=1)
    rationale = Column(Text, nullable=False)
    conditions_snapshot = Column(JSON, nullable=False, default=list)
    evidence_refs = Column(JSON, nullable=False, default=dict)
    reporting_periods = Column(JSON, nullable=False, default=list)
    policy_version = Column(String(80), nullable=True)
    actor_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, nullable=False, default=_utcnow, index=True)


class CreditReviewCondition(Base):
    __tablename__ = "credit_review_conditions"

    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(
        Integer, ForeignKey("credit_review_cases.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    decision_id = Column(
        Integer, ForeignKey("credit_review_decisions.id", ondelete="RESTRICT"), nullable=False
    )
    description = Column(Text, nullable=False)
    responsible_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    due_date = Column(Date, nullable=True)
    status = Column(String(20), nullable=False, default="open", index=True)
    completion_notes = Column(Text, nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, nullable=False, default=_utcnow)
    updated_at = Column(DateTime, nullable=False, default=_utcnow, onupdate=_utcnow)


class CreditReviewConditionEvent(Base):
    __tablename__ = "credit_review_condition_events"

    id = Column(Integer, primary_key=True, index=True)
    condition_id = Column(
        Integer,
        ForeignKey("credit_review_conditions.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    actor_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    action = Column(String(20), nullable=False)
    previous_value = Column(JSON, nullable=True)
    new_value = Column(JSON, nullable=False)
    reason = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=_utcnow)
