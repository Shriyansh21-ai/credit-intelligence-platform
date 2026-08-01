"""Feature vector persistence model.

``FeatureVector`` stores a complete, versioned ML-ready feature set for an
enterprise assessment. Headline coverage/quality metrics are promoted to columns
so vectors are queryable without unpacking JSON, while the full feature list
category breakdown and a self-describing registry snapshot live in JSON blobs.

Versioning mirrors ``FinancialAnalysis``: each recompute inserts a new row with
an incremented ``version`` and ``is_current`` toggled, preserving the full
history of feature generations for auditing and future model training.
"""

from datetime import datetime

from sqlalchemy import (
    Boolean, Column, DateTime, Float, ForeignKey, Integer, JSON, String,
)

from backend.app.db.database import Base


class FeatureVector(Base):
    __tablename__ = "feature_vectors"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    # Vectors can be produced ad-hoc without a persisted assessment.
    assessment_id = Column(
        Integer, ForeignKey("enterprise_assessments.id"), nullable=True, index=True
    )

    version = Column(Integer, nullable=False, default=1)
    is_current = Column(Boolean, nullable=False, default=True)

    feature_set_version = Column(String, nullable=False, default="1.0")
    generated_time = Column(String, nullable=True)

    # Period the underlying statement covers (for trend queries).
    period_label = Column(String, nullable=True)
    period_type = Column(String, nullable=False, default="annual")
    fiscal_year = Column(Integer, nullable=True, index=True)

    # --- Coverage / quality (queryable columns) ---
    feature_count = Column(Integer, nullable=False, default=0)
    populated_count = Column(Integer, nullable=False, default=0)
    low_confidence_count = Column(Integer, nullable=False, default=0)
    coverage = Column(Float, nullable=False, default=0.0)

    # --- Full detail (JSON blobs) ---
    features = Column(JSON, nullable=False, default=list)
    features_by_category = Column(JSON, nullable=False, default=dict)
    category_summary = Column(JSON, nullable=False, default=dict)
    registry_metadata = Column(JSON, nullable=False, default=dict)

    created_at = Column(DateTime, default=datetime.utcnow)
