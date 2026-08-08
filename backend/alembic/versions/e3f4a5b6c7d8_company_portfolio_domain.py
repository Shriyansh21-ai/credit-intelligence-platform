"""Tenant-scoped company / portfolio domain.

Additive: creates the ``companies``, ``company_financials``, ``credit_profiles``
and ``portfolio_exposures`` tables that back the seed system and the "Load Demo
Portfolio" feature. Every row carries a ``tenant_id`` (FK ``tenants.id``) so the
book is isolated per organization, and ``is_demo`` / ``data_source`` so
synthetic records are clearly distinguishable from real financial data. Nothing
existing is modified or dropped.

Revision ID: e3f4a5b6c7d8
Revises: d1e2f3a4b5c6
Create Date: 2026-08-08 10:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "e3f4a5b6c7d8"
down_revision: Union[str, Sequence[str], None] = "d1e2f3a4b5c6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "companies",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("external_id", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("legal_name", sa.String(), nullable=True),
        sa.Column("industry", sa.String(), nullable=False),
        sa.Column("sector", sa.String(), nullable=True),
        sa.Column("country", sa.String(), nullable=True),
        sa.Column("region", sa.String(), nullable=True),
        sa.Column("incorporation_year", sa.Integer(), nullable=True),
        sa.Column("employee_count", sa.Integer(), nullable=True),
        sa.Column("annual_revenue", sa.Float(), nullable=True),
        sa.Column("business_status", sa.String(), nullable=True),
        sa.Column("gstin", sa.String(), nullable=True),
        sa.Column("pan", sa.String(), nullable=True),
        sa.Column("cin", sa.String(), nullable=True),
        sa.Column("is_demo", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("data_source", sa.String(), nullable=False, server_default="demo"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("tenant_id", "external_id", name="uq_company_tenant_external"),
    )
    op.create_index("ix_companies_tenant_id", "companies", ["tenant_id"])
    op.create_index("ix_companies_external_id", "companies", ["external_id"])
    op.create_index("ix_companies_industry", "companies", ["industry"])
    op.create_index("ix_companies_is_demo", "companies", ["is_demo"])

    op.create_table(
        "company_financials",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column(
            "company_id",
            sa.Integer(),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("fiscal_year", sa.Integer(), nullable=False),
        sa.Column("revenue", sa.Float(), nullable=True),
        sa.Column("ebitda", sa.Float(), nullable=True),
        sa.Column("ebit", sa.Float(), nullable=True),
        sa.Column("net_income", sa.Float(), nullable=True),
        sa.Column("operating_margin", sa.Float(), nullable=True),
        sa.Column("net_margin", sa.Float(), nullable=True),
        sa.Column("total_assets", sa.Float(), nullable=True),
        sa.Column("total_liabilities", sa.Float(), nullable=True),
        sa.Column("equity", sa.Float(), nullable=True),
        sa.Column("current_assets", sa.Float(), nullable=True),
        sa.Column("current_liabilities", sa.Float(), nullable=True),
        sa.Column("cash", sa.Float(), nullable=True),
        sa.Column("debt", sa.Float(), nullable=True),
        sa.Column("working_capital", sa.Float(), nullable=True),
        sa.Column("operating_cash_flow", sa.Float(), nullable=True),
        sa.Column("free_cash_flow", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("company_id", "fiscal_year", name="uq_financials_company_year"),
    )
    op.create_index("ix_company_financials_tenant_id", "company_financials", ["tenant_id"])
    op.create_index("ix_company_financials_company_id", "company_financials", ["company_id"])

    op.create_table(
        "credit_profiles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column(
            "company_id",
            sa.Integer(),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("credit_score", sa.Integer(), nullable=True),
        sa.Column("probability_of_default", sa.Float(), nullable=True),
        sa.Column("risk_grade", sa.String(), nullable=True),
        sa.Column("expected_loss", sa.Float(), nullable=True),
        sa.Column("debt_to_equity", sa.Float(), nullable=True),
        sa.Column("current_ratio", sa.Float(), nullable=True),
        sa.Column("quick_ratio", sa.Float(), nullable=True),
        sa.Column("interest_coverage", sa.Float(), nullable=True),
        sa.Column("dscr", sa.Float(), nullable=True),
        sa.Column("leverage", sa.Float(), nullable=True),
        sa.Column("liquidity_score", sa.Float(), nullable=True),
        sa.Column("requested_loan_amount", sa.Float(), nullable=True),
        sa.Column("recommended_loan_amount", sa.Float(), nullable=True),
        sa.Column("interest_rate", sa.Float(), nullable=True),
        sa.Column("collateral_value", sa.Float(), nullable=True),
        sa.Column("loan_tenure_months", sa.Integer(), nullable=True),
        sa.Column("repayment_history", sa.String(), nullable=True),
        sa.Column("approval_status", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("company_id", name="uq_credit_profile_company"),
    )
    op.create_index("ix_credit_profiles_tenant_id", "credit_profiles", ["tenant_id"])
    op.create_index("ix_credit_profiles_company_id", "credit_profiles", ["company_id"])
    op.create_index("ix_credit_profiles_risk_grade", "credit_profiles", ["risk_grade"])
    op.create_index("ix_credit_profiles_approval_status", "credit_profiles", ["approval_status"])

    op.create_table(
        "portfolio_exposures",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column(
            "company_id",
            sa.Integer(),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("exposure", sa.Float(), nullable=True),
        sa.Column("outstanding_amount", sa.Float(), nullable=True),
        sa.Column("utilization", sa.Float(), nullable=True),
        sa.Column("repayment_performance", sa.Float(), nullable=True),
        sa.Column("delinquency_days", sa.Integer(), nullable=True),
        sa.Column("is_delinquent", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("sector_classification", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("company_id", name="uq_exposure_company"),
    )
    op.create_index("ix_portfolio_exposures_tenant_id", "portfolio_exposures", ["tenant_id"])
    op.create_index("ix_portfolio_exposures_company_id", "portfolio_exposures", ["company_id"])
    op.create_index(
        "ix_portfolio_exposures_sector", "portfolio_exposures", ["sector_classification"]
    )


def downgrade() -> None:
    op.drop_table("portfolio_exposures")
    op.drop_table("credit_profiles")
    op.drop_table("company_financials")
    op.drop_table("companies")
