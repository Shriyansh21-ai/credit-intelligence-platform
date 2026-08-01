"""Application lifecycle and approval workflow tables

Revision ID: f2b3c4d5e6a7
Revises: e1f2a3b4c5d6
Create Date: 2026-07-21 13:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "f2b3c4d5e6a7"
down_revision: Union[str, Sequence[str], None] = "e1f2a3b4c5d6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "applications",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("reference", sa.String(), nullable=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("assigned_to", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("assessment_id", sa.Integer(), sa.ForeignKey("enterprise_assessments.id"), nullable=True),
        sa.Column("company_name", sa.String(), nullable=False),
        sa.Column("industry", sa.String(), nullable=True),
        sa.Column("gstin", sa.String(), nullable=True),
        sa.Column("pan", sa.String(), nullable=True),
        sa.Column("loan_id", sa.String(), nullable=True),
        sa.Column("requested_amount", sa.Float(), nullable=True),
        sa.Column("loan_purpose", sa.String(), nullable=True),
        sa.Column("tenure_months", sa.Integer(), nullable=True),
        sa.Column("risk_rating", sa.String(), nullable=True),
        sa.Column("risk_grade", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="draft"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_applications_reference", "applications", ["reference"], unique=True)
    op.create_index("ix_applications_user_id", "applications", ["user_id"])
    op.create_index("ix_applications_assigned_to", "applications", ["assigned_to"])
    op.create_index("ix_applications_assessment_id", "applications", ["assessment_id"])
    op.create_index("ix_applications_company_name", "applications", ["company_name"])
    op.create_index("ix_applications_industry", "applications", ["industry"])
    op.create_index("ix_applications_gstin", "applications", ["gstin"])
    op.create_index("ix_applications_pan", "applications", ["pan"])
    op.create_index("ix_applications_loan_id", "applications", ["loan_id"])
    op.create_index("ix_applications_risk_rating", "applications", ["risk_rating"])
    op.create_index("ix_applications_risk_grade", "applications", ["risk_grade"])
    op.create_index("ix_applications_status", "applications", ["status"])

    op.create_table(
        "application_status_history",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("application_id", sa.Integer(), sa.ForeignKey("applications.id", ondelete="CASCADE"), nullable=False),
        sa.Column("from_status", sa.String(), nullable=True),
        sa.Column("to_status", sa.String(), nullable=False),
        sa.Column("kind", sa.String(), nullable=False, server_default="transition"),
        sa.Column("actor_id", sa.Integer(), nullable=True),
        sa.Column("actor_email", sa.String(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_ash_application_id", "application_status_history", ["application_id"])
    op.create_index("ix_ash_created_at", "application_status_history", ["created_at"])

    op.create_table(
        "approval_workflows",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("stages", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("name", name="uq_approval_workflows_name"),
    )

    op.create_table(
        "approval_decisions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("application_id", sa.Integer(), sa.ForeignKey("applications.id", ondelete="CASCADE"), nullable=False),
        sa.Column("workflow_id", sa.Integer(), sa.ForeignKey("approval_workflows.id"), nullable=True),
        sa.Column("stage_key", sa.String(), nullable=True),
        sa.Column("stage_name", sa.String(), nullable=True),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("actor_id", sa.Integer(), nullable=True),
        sa.Column("actor_email", sa.String(), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("from_status", sa.String(), nullable=True),
        sa.Column("to_status", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_approval_decisions_application_id", "approval_decisions", ["application_id"])
    op.create_index("ix_approval_decisions_action", "approval_decisions", ["action"])
    op.create_index("ix_approval_decisions_created_at", "approval_decisions", ["created_at"])

    # Seed the default approval workflow.
    from backend.app.services.approvals.workflow import DEFAULT_WORKFLOW
    import json

    wf_t = sa.table(
        "approval_workflows",
        sa.column("name", sa.String),
        sa.column("description", sa.String),
        sa.column("is_default", sa.Boolean),
        sa.column("is_active", sa.Boolean),
        sa.column("stages", sa.JSON),
    )
    op.get_bind().execute(
        wf_t.insert().values(
            name=DEFAULT_WORKFLOW["name"],
            description=DEFAULT_WORKFLOW["description"],
            is_default=True,
            is_active=True,
            stages=DEFAULT_WORKFLOW["stages"],
        )
    )


def downgrade() -> None:
    op.drop_table("approval_decisions")
    op.drop_table("approval_workflows")
    op.drop_table("application_status_history")
    op.drop_table("applications")
