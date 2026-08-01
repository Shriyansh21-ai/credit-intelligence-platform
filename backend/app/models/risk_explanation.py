"""Risk explanation persistence model.

Stores a versioned, auditable explanation for an assessment's risk prediction
the probability of default, its base rate, the full per-feature contributions and
the top risk drivers, plus the waterfall and global importance. Headline fields
are promoted to columns; the rich detail lives in JSON.
"""

from datetime import datetime

from sqlalchemy import (
    Boolean, Column, DateTime, Float, ForeignKey, Integer, JSON, String,
)

from backend.app.db.database import Base


class RiskExplanation(Base):
    __tablename__ = "risk_explanations"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    assessment_id = Column(
        Integer, ForeignKey("enterprise_assessments.id"), nullable=True, index=True
    )

    version = Column(Integer, nullable=False, default=1)
    is_current = Column(Boolean, nullable=False, default=True)

    model_type = Column(String, nullable=False)
    method = Column(String, nullable=False)

    probability_of_default = Column(Float, nullable=True)
    base_probability = Column(Float, nullable=True)
    risk_score = Column(Integer, nullable=True)
    risk_grade = Column(String, nullable=True)
    summary = Column(String, nullable=True)

    contributions = Column(JSON, nullable=False, default=list)
    top_positive = Column(JSON, nullable=False, default=list)
    top_negative = Column(JSON, nullable=False, default=list)
    waterfall = Column(JSON, nullable=False, default=list)
    global_importance = Column(JSON, nullable=False, default=list)

    created_at = Column(DateTime, default=datetime.utcnow)
