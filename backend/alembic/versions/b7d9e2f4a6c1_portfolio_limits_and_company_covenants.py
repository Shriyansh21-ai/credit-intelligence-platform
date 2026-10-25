"""Add managed exposure limits and company-scoped covenant evaluations.

Revision ID: b7d9e2f4a6c1
Revises: a6c4e8f1b203
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "b7d9e2f4a6c1"
down_revision: Union[str, Sequence[str], None] = "a6c4e8f1b203"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("portfolio_exposures") as batch_op:
        batch_op.add_column(sa.Column("currency", sa.String(length=3), nullable=True))

    op.create_table(
        "portfolio_exposure_limits",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("scope", sa.String(length=16), nullable=False),
        sa.Column("scope_key", sa.String(length=200), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("threshold", sa.Float(), nullable=False),
        sa.Column("approaching_ratio", sa.Float(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "scope IN ('portfolio', 'company', 'sector')", name="ck_exposure_limit_scope"
        ),
        sa.CheckConstraint("threshold > 0", name="ck_exposure_limit_positive_threshold"),
        sa.CheckConstraint(
            "approaching_ratio IS NULL OR (approaching_ratio > 0 AND approaching_ratio < 1)",
            name="ck_exposure_limit_approaching_ratio",
        ),
        sa.UniqueConstraint(
            "tenant_id", "scope", "scope_key", "currency",
            name="uq_exposure_limit_scope_currency",
        ),
    )
    op.create_index(
        "ix_portfolio_exposure_limits_tenant_id",
        "portfolio_exposure_limits",
        ["tenant_id"],
    )
    op.create_index(
        "ix_portfolio_exposure_limits_is_active",
        "portfolio_exposure_limits",
        ["is_active"],
    )

    op.create_table(
        "portfolio_exposure_breaches",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "limit_id",
            sa.Integer(),
            sa.ForeignKey("portfolio_exposure_limits.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("observed_exposure", sa.Float(), nullable=False),
        sa.Column("supporting_exposure_ids", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("supporting_company_ids", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="open"),
        sa.Column("first_detected_at", sa.DateTime(), nullable=False),
        sa.Column("last_observed_at", sa.DateTime(), nullable=False),
        sa.Column("acknowledged_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("acknowledged_at", sa.DateTime(), nullable=True),
        sa.Column("acknowledgement_reason", sa.String(length=1000), nullable=True),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("limit_id", name="uq_exposure_breach_limit"),
    )
    op.create_index(
        "ix_portfolio_exposure_breaches_limit_id",
        "portfolio_exposure_breaches",
        ["limit_id"],
    )
    op.create_index(
        "ix_portfolio_exposure_breaches_status",
        "portfolio_exposure_breaches",
        ["status"],
    )

    op.create_table(
        "portfolio_exposure_limit_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "limit_id",
            sa.Integer(),
            sa.ForeignKey("portfolio_exposure_limits.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "breach_id",
            sa.Integer(),
            sa.ForeignKey("portfolio_exposure_breaches.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("actor_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("action", sa.String(length=32), nullable=False),
        sa.Column("reason", sa.String(length=1000), nullable=True),
        sa.Column("previous_value", sa.String(length=2000), nullable=True),
        sa.Column("new_value", sa.String(length=2000), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index(
        "ix_portfolio_exposure_limit_events_limit_id",
        "portfolio_exposure_limit_events",
        ["limit_id"],
    )
    op.create_index(
        "ix_portfolio_exposure_limit_events_breach_id",
        "portfolio_exposure_limit_events",
        ["breach_id"],
    )
    op.create_index(
        "ix_portfolio_exposure_limit_events_created_at",
        "portfolio_exposure_limit_events",
        ["created_at"],
    )

    op.create_table(
        "company_covenants",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column(
            "company_id",
            sa.Integer(),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("metric_key", sa.String(length=40), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("operator", sa.String(length=3), nullable=False),
        sa.Column("threshold", sa.Float(), nullable=False),
        sa.Column("unit", sa.String(length=20), nullable=False),
        sa.Column("effective_date", sa.Date(), nullable=True),
        sa.Column("review_frequency_months", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.String(length=12), nullable=False, server_default="active"),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("threshold > 0", name="ck_company_covenant_positive_threshold"),
        sa.CheckConstraint(
            "metric_key IN ('current_ratio_min', 'debt_to_equity_max', 'debt_to_ebitda_max')",
            name="ck_company_covenant_supported_metric",
        ),
        sa.UniqueConstraint(
            "tenant_id", "company_id", "metric_key", "name",
            name="uq_company_covenant_tenant_company_metric_name",
        ),
    )
    op.create_index("ix_company_covenants_tenant_id", "company_covenants", ["tenant_id"])
    op.create_index("ix_company_covenants_company_id", "company_covenants", ["company_id"])
    op.create_index("ix_company_covenants_metric_key", "company_covenants", ["metric_key"])
    op.create_index("ix_company_covenants_is_active", "company_covenants", ["is_active"])

    op.create_table(
        "company_covenant_evaluations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "covenant_id",
            sa.Integer(),
            sa.ForeignKey("company_covenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("evidence_key", sa.String(length=80), nullable=False),
        sa.Column(
            "financial_record_id",
            sa.Integer(),
            sa.ForeignKey("company_financials.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "source_document_id",
            sa.Integer(),
            sa.ForeignKey("documents.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "source_document_extraction_id",
            sa.Integer(),
            sa.ForeignKey("document_extractions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("evidence_snapshot", sa.JSON(), nullable=False),
        sa.Column("fiscal_year", sa.Integer(), nullable=True),
        sa.Column("calculated_value", sa.Float(), nullable=True),
        sa.Column("threshold", sa.Float(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("evidence_status", sa.String(length=32), nullable=False),
        sa.Column("acknowledged_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("acknowledged_at", sa.DateTime(), nullable=True),
        sa.Column("acknowledgement_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint(
            "covenant_id", "evidence_key", name="uq_company_covenant_evaluation_evidence"
        ),
    )
    op.create_index(
        "ix_company_covenant_evaluations_covenant_id",
        "company_covenant_evaluations",
        ["covenant_id"],
    )
    op.create_index(
        "ix_company_covenant_evaluations_fiscal_year",
        "company_covenant_evaluations",
        ["fiscal_year"],
    )
    op.create_index(
        "ix_company_covenant_evaluations_created_at",
        "company_covenant_evaluations",
        ["created_at"],
    )


def downgrade() -> None:
    op.drop_table("company_covenant_evaluations")
    op.drop_table("company_covenants")
    op.drop_table("portfolio_exposure_limit_events")
    op.drop_table("portfolio_exposure_breaches")
    op.drop_table("portfolio_exposure_limits")
    with op.batch_alter_table("portfolio_exposures") as batch_op:
        batch_op.drop_column("currency")
