"""Add tenant-scoped credit review and decision workflow.

Revision ID: a6c4e8f1b203
Revises: 9f4c2a7b1d6e
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "a6c4e8f1b203"
down_revision: Union[str, Sequence[str], None] = "9f4c2a7b1d6e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "credit_review_cases",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("reference", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column(
            "company_id", sa.Integer(), sa.ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False
        ),
        sa.Column("review_type", sa.String(length=40), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("purpose", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="draft"),
        sa.Column("cycle_number", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("analyst_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("reviewer_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("reporting_periods", sa.JSON(), nullable=False),
        sa.Column("financial_record_ids", sa.JSON(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("tenant_id", "reference", name="uq_credit_review_tenant_reference"),
    )
    op.create_index("ix_credit_review_cases_reference", "credit_review_cases", ["reference"])
    op.create_index("ix_credit_review_cases_tenant_id", "credit_review_cases", ["tenant_id"])
    op.create_index("ix_credit_review_cases_company_id", "credit_review_cases", ["company_id"])
    op.create_index("ix_credit_review_cases_status", "credit_review_cases", ["status"])
    op.create_index("ix_credit_review_cases_analyst_id", "credit_review_cases", ["analyst_id"])
    op.create_index("ix_credit_review_cases_reviewer_id", "credit_review_cases", ["reviewer_id"])
    op.create_index(
        "ix_credit_review_cases_tenant_status",
        "credit_review_cases",
        ["tenant_id", "status"],
    )

    op.create_table(
        "credit_review_assessments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "case_id",
            sa.Integer(),
            sa.ForeignKey("credit_review_cases.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("strengths", sa.JSON(), nullable=False),
        sa.Column("weaknesses", sa.JSON(), nullable=False),
        sa.Column("risk_indicators", sa.JSON(), nullable=False),
        sa.Column("data_quality_concerns", sa.JSON(), nullable=False),
        sa.Column("mitigations", sa.JSON(), nullable=False),
        sa.Column("outstanding_questions", sa.JSON(), nullable=False),
        sa.Column("evidence_refs", sa.JSON(), nullable=False),
        sa.Column("recommendation", sa.String(length=40), nullable=False),
        sa.Column("recommendation_rationale", sa.Text(), nullable=False),
        sa.Column("author_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("submitted_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("case_id", "version", name="uq_credit_review_assessment_version"),
    )
    op.create_index("ix_credit_review_assessments_case_id", "credit_review_assessments", ["case_id"])

    op.create_table(
        "credit_review_decisions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "case_id",
            sa.Integer(),
            sa.ForeignKey("credit_review_cases.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "assessment_id",
            sa.Integer(),
            sa.ForeignKey("credit_review_assessments.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "previous_decision_id",
            sa.Integer(),
            sa.ForeignKey("credit_review_decisions.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("outcome", sa.String(length=40), nullable=False),
        sa.Column("cycle_number", sa.Integer(), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("conditions_snapshot", sa.JSON(), nullable=False),
        sa.Column("evidence_refs", sa.JSON(), nullable=False),
        sa.Column("reporting_periods", sa.JSON(), nullable=False),
        sa.Column("policy_version", sa.String(length=80), nullable=True),
        sa.Column("actor_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_credit_review_decisions_case_id", "credit_review_decisions", ["case_id"])
    op.create_index("ix_credit_review_decisions_created_at", "credit_review_decisions", ["created_at"])

    op.create_table(
        "credit_review_conditions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "case_id",
            sa.Integer(),
            sa.ForeignKey("credit_review_cases.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "decision_id",
            sa.Integer(),
            sa.ForeignKey("credit_review_decisions.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("responsible_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="open"),
        sa.Column("completion_notes", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_credit_review_conditions_case_id", "credit_review_conditions", ["case_id"])
    op.create_index("ix_credit_review_conditions_status", "credit_review_conditions", ["status"])

    op.create_table(
        "credit_review_condition_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "condition_id",
            sa.Integer(),
            sa.ForeignKey("credit_review_conditions.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("actor_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("action", sa.String(length=20), nullable=False),
        sa.Column("previous_value", sa.JSON(), nullable=True),
        sa.Column("new_value", sa.JSON(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index(
        "ix_credit_review_condition_events_condition_id",
        "credit_review_condition_events",
        ["condition_id"],
    )


def downgrade() -> None:
    op.drop_table("credit_review_condition_events")
    op.drop_table("credit_review_conditions")
    op.drop_table("credit_review_decisions")
    op.drop_table("credit_review_assessments")
    op.drop_table("credit_review_cases")
