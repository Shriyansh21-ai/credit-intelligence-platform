"""Credit application lifecycle models (Phase 5, Milestone 1).

``Application`` is the central workflow entity that ties together a company, its
assessment, documents, approvals, tasks and monitoring. ``ApplicationStatusHistory``
is an append-only trail of every lifecycle transition (actor, reason, comment).
"""

from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from backend.app.db.database import Base

# NB: the lifecycle default is stored as a literal to avoid importing the
# lifecycle service package (which imports this model) at module load time.
# It mirrors ``ApplicationStatus.DRAFT``.
_DEFAULT_STATUS = "draft"


class Application(Base):
    __tablename__ = "applications"

    id = Column(Integer, primary_key=True, index=True)

    # Human-facing reference, e.g. "APP-2026-0001". Populated on create.
    reference = Column(String, nullable=True, unique=True, index=True)

    # Creator / relationship owner and the currently assigned handler.
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    assigned_to = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)

    # Optional link to the enterprise assessment that scored this application.
    assessment_id = Column(
        Integer, ForeignKey("enterprise_assessments.id"), nullable=True, index=True
    )

    # --- Applicant / company profile (denormalised for search & display) ---
    company_name = Column(String, nullable=False, index=True)
    industry = Column(String, nullable=True, index=True)
    gstin = Column(String, nullable=True, index=True)
    pan = Column(String, nullable=True, index=True)
    loan_id = Column(String, nullable=True, index=True)

    requested_amount = Column(Float, nullable=True)
    loan_purpose = Column(String, nullable=True)
    tenure_months = Column(Integer, nullable=True)

    # Snapshot of key risk signals (kept in step with the assessment).
    risk_rating = Column(String, nullable=True, index=True)
    risk_grade = Column(String, nullable=True, index=True)

    # --- Lifecycle ---
    status = Column(
        String, nullable=False, default=_DEFAULT_STATUS, index=True
    )

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    history = relationship(
        "ApplicationStatusHistory",
        back_populates="application",
        order_by="ApplicationStatusHistory.created_at",
        cascade="all, delete-orphan",
    )


class ApplicationStatusHistory(Base):
    __tablename__ = "application_status_history"

    id = Column(Integer, primary_key=True, index=True)
    application_id = Column(
        Integer, ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True
    )

    from_status = Column(String, nullable=True)
    to_status = Column(String, nullable=False)

    # ``transition`` for normal moves, ``rollback`` when reverting.
    kind = Column(String, nullable=False, default="transition")

    actor_id = Column(Integer, nullable=True)
    actor_email = Column(String, nullable=True)

    reason = Column(Text, nullable=True)
    comment = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    application = relationship("Application", back_populates="history")
