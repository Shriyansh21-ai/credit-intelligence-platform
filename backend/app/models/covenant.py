"""Covenant monitoring models.

A ``Covenant`` is a threshold condition attached to an application/loan (e.g.
"Minimum DSCR >= 1.25"). Each ``CovenantMeasurement`` records the metric's value
at a point in time and its pass/breach status. Breaches raise a ``CovenantAlert``.
"""

from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from backend.app.db.database import Base


class Covenant(Base):
    __tablename__ = "covenants"

    id = Column(Integer, primary_key=True, index=True)
    application_id = Column(
        Integer, ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True
    )

    metric_key = Column(String, nullable=False, index=True)  # dscr, debt_ratio, ...
    name = Column(String, nullable=False)
    # "min" => breach when value < threshold; "max" => breach when value > threshold.
    operator = Column(String, nullable=False, default="min")
    threshold = Column(Float, nullable=False)
    unit = Column(String, nullable=True)
    description = Column(Text, nullable=True)

    is_active = Column(String, nullable=False, default="active")  # active / waived / closed
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    measurements = relationship(
        "CovenantMeasurement",
        back_populates="covenant",
        order_by="CovenantMeasurement.measured_at",
        cascade="all, delete-orphan",
    )


class CovenantMeasurement(Base):
    __tablename__ = "covenant_measurements"

    id = Column(Integer, primary_key=True, index=True)
    covenant_id = Column(
        Integer, ForeignKey("covenants.id", ondelete="CASCADE"), nullable=False, index=True
    )

    value = Column(Float, nullable=True)
    status = Column(String, nullable=False, default="ok")  # ok / warning / breach / unknown
    headroom = Column(Float, nullable=True)  # signed distance from threshold
    period = Column(String, nullable=True)
    source = Column(String, nullable=True)
    note = Column(Text, nullable=True)
    measured_at = Column(DateTime, default=datetime.utcnow, index=True)

    covenant = relationship("Covenant", back_populates="measurements")


class CovenantAlert(Base):
    __tablename__ = "covenant_alerts"

    id = Column(Integer, primary_key=True, index=True)
    covenant_id = Column(Integer, ForeignKey("covenants.id", ondelete="CASCADE"), nullable=False, index=True)
    application_id = Column(Integer, ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True)
    measurement_id = Column(Integer, ForeignKey("covenant_measurements.id"), nullable=True)

    severity = Column(String, nullable=False, default="high")
    message = Column(Text, nullable=False)
    status = Column(String, nullable=False, default="open")  # open / acknowledged / resolved
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class CompanyCovenant(Base):
    """Explicit financial covenant scoped to one tenant-owned company."""

    __tablename__ = "company_covenants"
    __table_args__ = (
        CheckConstraint("threshold > 0", name="ck_company_covenant_positive_threshold"),
        CheckConstraint(
            "metric_key IN ('current_ratio_min', 'debt_to_equity_max', 'debt_to_ebitda_max')",
            name="ck_company_covenant_supported_metric",
        ),
        UniqueConstraint(
            "tenant_id", "company_id", "metric_key", "name",
            name="uq_company_covenant_tenant_company_metric_name",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    company_id = Column(
        Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    metric_key = Column(String(40), nullable=False, index=True)
    name = Column(String(200), nullable=False)
    operator = Column(String(3), nullable=False)
    threshold = Column(Float, nullable=False)
    unit = Column(String(20), nullable=False)
    effective_date = Column(Date, nullable=True)
    review_frequency_months = Column(Integer, nullable=True)
    is_active = Column(String(12), nullable=False, default="active", index=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class CompanyCovenantEvaluation(Base):
    """Append-only evaluation result tied to approved financial evidence."""

    __tablename__ = "company_covenant_evaluations"
    __table_args__ = (
        UniqueConstraint(
            "covenant_id", "evidence_key", name="uq_company_covenant_evaluation_evidence"
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    covenant_id = Column(
        Integer,
        ForeignKey("company_covenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    evidence_key = Column(String(80), nullable=False)
    financial_record_id = Column(
        Integer, ForeignKey("company_financials.id", ondelete="SET NULL"), nullable=True
    )
    source_document_id = Column(Integer, ForeignKey("documents.id", ondelete="SET NULL"), nullable=True)
    source_document_extraction_id = Column(
        Integer, ForeignKey("document_extractions.id", ondelete="SET NULL"), nullable=True
    )
    evidence_snapshot = Column(JSON, nullable=False, default=dict)
    fiscal_year = Column(Integer, nullable=True, index=True)
    calculated_value = Column(Float, nullable=True)
    threshold = Column(Float, nullable=False)
    status = Column(String(24), nullable=False)
    evidence_status = Column(String(32), nullable=False)
    acknowledged_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    acknowledged_at = Column(DateTime, nullable=True)
    acknowledgement_reason = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
