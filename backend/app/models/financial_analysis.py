"""Financial Analysis persistence model (Phase 3, Task 9).

`FinancialAnalysis` stores a complete, versioned financial-intelligence result
for an enterprise assessment. Headline scores are promoted to columns so
analyses are queryable and trend-able without unpacking JSON, while the full
detail (ratios, health scores, insights, risk flags, recommendations and the
normalised statement snapshot) lives in JSON blobs.

Versioning mirrors `DocumentExtraction`: each recompute inserts a new row with
an incremented ``version`` and ``is_current`` toggled, preserving history and
preparing the table to hold multiple periods per company for trend analysis.
"""

from datetime import datetime

from sqlalchemy import (
    Boolean, Column, DateTime, Float, ForeignKey, Integer, JSON, String,
)

from backend.app.db.database import Base


class FinancialAnalysis(Base):
    __tablename__ = "financial_analyses"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    # Optional: analysis can be computed ad-hoc (POST /analysis/compute) without
    # a persisted assessment, so this is nullable.
    assessment_id = Column(
        Integer, ForeignKey("enterprise_assessments.id"), nullable=True, index=True
    )

    version = Column(Integer, nullable=False, default=1)
    is_current = Column(Boolean, nullable=False, default=True)

    # Period the analysed statement covers (for trend queries).
    period_label = Column(String, nullable=True)
    period_type = Column(String, nullable=False, default="annual")
    fiscal_year = Column(Integer, nullable=True, index=True)

    # --- Headline scores (queryable columns) ---
    overall_health_score = Column(Integer, nullable=True)
    overall_health_status = Column(String, nullable=True)
    liquidity_health = Column(Integer, nullable=True)
    profitability_health = Column(Integer, nullable=True)
    leverage_health = Column(Integer, nullable=True)
    efficiency_health = Column(Integer, nullable=True)
    cash_flow_health = Column(Integer, nullable=True)
    business_stability_health = Column(Integer, nullable=True)
    growth_health = Column(Integer, nullable=True)
    risk_flag_count = Column(Integer, nullable=False, default=0)
    highest_severity = Column(String, nullable=True)

    # --- Full detail (JSON blobs) ---
    statement_snapshot = Column(JSON, nullable=False, default=dict)
    ratios = Column(JSON, nullable=False, default=list)
    health_scores = Column(JSON, nullable=False, default=list)
    insights = Column(JSON, nullable=False, default=list)
    risk_flags = Column(JSON, nullable=False, default=list)
    recommendations = Column(JSON, nullable=False, default=list)

    engine_version = Column(String, nullable=False, default="1.0")
    created_at = Column(DateTime, default=datetime.utcnow)
