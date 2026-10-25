"""Tenant-scoped company / portfolio domain.

These tables back the seed system and the "Load Demo Portfolio" feature. Unlike
the legacy ``predictions`` / ``enterprise_assessments`` tables (scoped by
``user_id`` only), every row here carries a ``tenant_id`` — the isolation key
already used across the SaaS layer (:mod:`backend.app.models.tenancy`). A user
from one organization can therefore never see or modify another organization's
book.

The domain is deliberately provider-agnostic: rows are persisted by the seed /
demo-portfolio service from whatever :class:`DataProvider` is active, and every
row records ``is_demo`` + ``data_source`` so synthetic records are clearly
distinguishable from real financial data in the UI and in queries.

Schema is owned by Alembic (migration ``e3f4a5b6c7d8``); ``create_all`` is only
used by the test harness.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    CheckConstraint,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from backend.app.db.database import Base


class Company(Base):
    """A borrower / counterparty in a tenant's portfolio."""

    __tablename__ = "companies"
    __table_args__ = (
        # Stable identity per tenant → idempotent seeding (load twice, no dupes).
        UniqueConstraint("tenant_id", "external_id", name="uq_company_tenant_external"),
    )

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)

    # Stable synthetic/business identifier used for idempotency.
    external_id = Column(String, nullable=False, index=True)

    # --- Profile ---
    name = Column(String, nullable=False)
    legal_name = Column(String, nullable=True)
    industry = Column(String, nullable=False, index=True)
    sector = Column(String, nullable=True)
    country = Column(String, nullable=True)
    currency = Column(String(3), nullable=True)
    region = Column(String, nullable=True)
    incorporation_year = Column(Integer, nullable=True)
    employee_count = Column(Integer, nullable=True)
    annual_revenue = Column(Float, nullable=True)
    business_status = Column(String, nullable=True)

    # Synthetic regulatory identifiers (India-style) for realism.
    gstin = Column(String, nullable=True)
    pan = Column(String, nullable=True)
    cin = Column(String, nullable=True)

    # --- Provenance / labelling ---
    is_demo = Column(Boolean, nullable=False, default=True, index=True)
    data_source = Column(String, nullable=False, default="demo")

    created_at = Column(DateTime, default=datetime.utcnow)

    financials = relationship(
        "CompanyFinancials",
        back_populates="company",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    credit_profile = relationship(
        "CreditProfile",
        back_populates="company",
        uselist=False,
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    exposure = relationship(
        "PortfolioExposure",
        back_populates="company",
        uselist=False,
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class CompanyFinancials(Base):
    """One fiscal-year financial statement for a company (time-series)."""

    __tablename__ = "company_financials"
    __table_args__ = (
        UniqueConstraint("company_id", "fiscal_year", name="uq_financials_company_year"),
    )

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    company_id = Column(
        Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )

    fiscal_year = Column(Integer, nullable=False)
    currency = Column(String(3), nullable=True)
    unit = Column(String, nullable=False, default="units")
    source_document_id = Column(Integer, ForeignKey("documents.id"), nullable=True, index=True)
    source_document_extraction_id = Column(
        Integer, ForeignKey("document_extractions.id"), nullable=True
    )
    reviewed_by = Column(Integer, ForeignKey("users.id"), nullable=True)

    # --- Income statement ---
    revenue = Column(Float, nullable=True)
    ebitda = Column(Float, nullable=True)
    ebit = Column(Float, nullable=True)
    net_income = Column(Float, nullable=True)
    operating_margin = Column(Float, nullable=True)
    net_margin = Column(Float, nullable=True)

    # --- Balance sheet ---
    total_assets = Column(Float, nullable=True)
    total_liabilities = Column(Float, nullable=True)
    equity = Column(Float, nullable=True)
    current_assets = Column(Float, nullable=True)
    current_liabilities = Column(Float, nullable=True)
    cash = Column(Float, nullable=True)
    debt = Column(Float, nullable=True)
    working_capital = Column(Float, nullable=True)

    # --- Cash flow ---
    operating_cash_flow = Column(Float, nullable=True)
    free_cash_flow = Column(Float, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    company = relationship("Company", back_populates="financials")


class CreditProfile(Base):
    """Risk + credit terms for a company (one current profile per company)."""

    __tablename__ = "credit_profiles"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    company_id = Column(
        Integer,
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    # --- Risk ---
    credit_score = Column(Integer, nullable=True)
    probability_of_default = Column(Float, nullable=True)
    risk_grade = Column(String, nullable=True, index=True)
    expected_loss = Column(Float, nullable=True)
    debt_to_equity = Column(Float, nullable=True)
    current_ratio = Column(Float, nullable=True)
    quick_ratio = Column(Float, nullable=True)
    interest_coverage = Column(Float, nullable=True)
    dscr = Column(Float, nullable=True)
    leverage = Column(Float, nullable=True)
    liquidity_score = Column(Float, nullable=True)

    # --- Credit terms ---
    requested_loan_amount = Column(Float, nullable=True)
    recommended_loan_amount = Column(Float, nullable=True)
    interest_rate = Column(Float, nullable=True)
    collateral_value = Column(Float, nullable=True)
    loan_tenure_months = Column(Integer, nullable=True)
    repayment_history = Column(String, nullable=True)
    approval_status = Column(String, nullable=True, index=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    company = relationship("Company", back_populates="credit_profile")


class PortfolioExposure(Base):
    """A company's exposure/position within the tenant's portfolio book."""

    __tablename__ = "portfolio_exposures"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    company_id = Column(
        Integer,
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    exposure = Column(Float, nullable=True)
    outstanding_amount = Column(Float, nullable=True)
    currency = Column(String(3), nullable=True)
    utilization = Column(Float, nullable=True)
    repayment_performance = Column(Float, nullable=True)
    delinquency_days = Column(Integer, nullable=True)
    is_delinquent = Column(Boolean, nullable=False, default=False)
    sector_classification = Column(String, nullable=True, index=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    company = relationship("Company", back_populates="exposure")


class PortfolioExposureLimit(Base):
    """Tenant-scoped company, sector, or whole-portfolio exposure threshold."""

    __tablename__ = "portfolio_exposure_limits"
    __table_args__ = (
        CheckConstraint(
            "scope IN ('portfolio', 'company', 'sector')",
            name="ck_exposure_limit_scope",
        ),
        CheckConstraint("threshold > 0", name="ck_exposure_limit_positive_threshold"),
        CheckConstraint(
            "approaching_ratio IS NULL OR (approaching_ratio > 0 AND approaching_ratio < 1)",
            name="ck_exposure_limit_approaching_ratio",
        ),
        UniqueConstraint(
            "tenant_id", "scope", "scope_key", "currency",
            name="uq_exposure_limit_scope_currency",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    scope = Column(String(16), nullable=False)
    # "*" for portfolio, company id for company, normalized sector for sector.
    scope_key = Column(String(200), nullable=False)
    currency = Column(String(3), nullable=False)
    threshold = Column(Float, nullable=False)
    approaching_ratio = Column(Float, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True, index=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class PortfolioExposureBreach(Base):
    """Current breach state for one limit; event rows preserve transitions."""

    __tablename__ = "portfolio_exposure_breaches"
    __table_args__ = (
        UniqueConstraint("limit_id", name="uq_exposure_breach_limit"),
    )

    id = Column(Integer, primary_key=True, index=True)
    limit_id = Column(
        Integer,
        ForeignKey("portfolio_exposure_limits.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    observed_exposure = Column(Float, nullable=False)
    supporting_exposure_ids = Column(JSON, nullable=False, default=list)
    supporting_company_ids = Column(JSON, nullable=False, default=list)
    status = Column(String(16), nullable=False, default="open", index=True)
    first_detected_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    last_observed_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    acknowledged_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    acknowledged_at = Column(DateTime, nullable=True)
    acknowledgement_reason = Column(String(1000), nullable=True)
    resolved_at = Column(DateTime, nullable=True)


class PortfolioExposureLimitEvent(Base):
    """Auditable, append-only limit and breach lifecycle event."""

    __tablename__ = "portfolio_exposure_limit_events"

    id = Column(Integer, primary_key=True, index=True)
    limit_id = Column(
        Integer,
        ForeignKey("portfolio_exposure_limits.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    breach_id = Column(
        Integer,
        ForeignKey("portfolio_exposure_breaches.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    actor_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    action = Column(String(32), nullable=False)
    reason = Column(String(1000), nullable=True)
    previous_value = Column(String(2000), nullable=True)
    new_value = Column(String(2000), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
