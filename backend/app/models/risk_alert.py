"""Risk alert persistence model (Phase 4, Milestone 7).

Every early-warning alert is stored for history and auditing. A scan supersedes
the previous batch for an assessment (``is_current`` toggled) while keeping older
alerts, so the alert timeline is preserved.
"""

from datetime import datetime

from sqlalchemy import (
    Boolean, Column, DateTime, ForeignKey, Integer, JSON, String,
)

from backend.app.db.database import Base


class RiskAlert(Base):
    __tablename__ = "risk_alerts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    assessment_id = Column(
        Integer, ForeignKey("enterprise_assessments.id"), nullable=True, index=True
    )

    is_current = Column(Boolean, nullable=False, default=True)

    alert_type = Column(String, nullable=False)
    category = Column(String, nullable=False)
    severity = Column(String, nullable=False, index=True)
    priority = Column(Integer, nullable=False, default=4)
    title = Column(String, nullable=False)
    business_impact = Column(String, nullable=True)
    suggested_action = Column(String, nullable=True)
    timeline = Column(String, nullable=True)
    evidence = Column(JSON, nullable=False, default=dict)

    # Analyst workflow status.
    status = Column(String, nullable=False, default="open")

    created_at = Column(DateTime, default=datetime.utcnow)
