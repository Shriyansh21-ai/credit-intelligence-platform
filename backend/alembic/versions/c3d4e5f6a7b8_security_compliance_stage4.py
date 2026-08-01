"""Enterprise Security & Compliance tables (Stage 4)

Fully additive: creates the security-scan, findings, compliance-assessment
risk-register, privacy-request, posture-snapshot and secret-record tables.
Nothing from Stages 1-3 (Phases 1-10 + Tracks 2-4) is altered or dropped.

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-08-01 10:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, Sequence[str], None] = "b2c3d4e5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # -- sec_scans ----------------------------------------------------------
    op.create_table(
        "sec_scans",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), nullable=True),
        sa.Column("scan_type", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="completed"),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("grade", sa.String(), nullable=True),
        sa.Column("summary", sa.JSON(), nullable=False),
        sa.Column("findings_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("critical_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("high_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("triggered_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_sec_scans_tenant_id", "sec_scans", ["tenant_id"])
    op.create_index("ix_sec_scans_scan_type", "sec_scans", ["scan_type"])
    op.create_index("ix_sec_scans_created_at", "sec_scans", ["created_at"])

    # -- sec_findings -------------------------------------------------------
    op.create_table(
        "sec_findings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), nullable=True),
        sa.Column("scan_id", sa.Integer(), sa.ForeignKey("sec_scans.id"), nullable=True),
        sa.Column("code", sa.String(), nullable=False),
        sa.Column("category", sa.String(), nullable=False),
        sa.Column("severity", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("recommendation", sa.Text(), nullable=False, server_default=""),
        sa.Column("reference", sa.String(), nullable=True),
        sa.Column("component", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="open"),
        sa.Column("evidence", sa.JSON(), nullable=False),
        sa.Column("resolved_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_sec_findings_tenant_id", "sec_findings", ["tenant_id"])
    op.create_index("ix_sec_findings_scan_id", "sec_findings", ["scan_id"])
    op.create_index("ix_sec_findings_code", "sec_findings", ["code"])
    op.create_index("ix_sec_findings_category", "sec_findings", ["category"])
    op.create_index("ix_sec_findings_severity", "sec_findings", ["severity"])
    op.create_index("ix_sec_findings_status", "sec_findings", ["status"])
    op.create_index("ix_sec_findings_created_at", "sec_findings", ["created_at"])

    # -- sec_compliance_assessments ----------------------------------------
    op.create_table(
        "sec_compliance_assessments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), nullable=True),
        sa.Column("framework", sa.String(), nullable=False),
        sa.Column("version", sa.String(), nullable=True),
        sa.Column("score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("readiness", sa.String(), nullable=False, server_default="not_ready"),
        sa.Column("total_controls", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("satisfied", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("partial", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("gaps", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("results", sa.JSON(), nullable=False),
        sa.Column("gap_items", sa.JSON(), nullable=False),
        sa.Column("assessed_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_sec_compliance_assessments_tenant_id", "sec_compliance_assessments", ["tenant_id"])
    op.create_index("ix_sec_compliance_assessments_framework", "sec_compliance_assessments", ["framework"])
    op.create_index("ix_sec_compliance_assessments_created_at", "sec_compliance_assessments", ["created_at"])

    # -- sec_risk_register --------------------------------------------------
    op.create_table(
        "sec_risk_register",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), nullable=True),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("category", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("likelihood", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("impact", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("inherent_score", sa.Integer(), nullable=False, server_default="9"),
        sa.Column("treatment", sa.String(), nullable=False, server_default="mitigate"),
        sa.Column("residual_likelihood", sa.Integer(), nullable=False, server_default="2"),
        sa.Column("residual_impact", sa.Integer(), nullable=False, server_default="2"),
        sa.Column("residual_score", sa.Integer(), nullable=False, server_default="4"),
        sa.Column("mitigations", sa.JSON(), nullable=False),
        sa.Column("owner", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="open"),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_sec_risk_register_tenant_id", "sec_risk_register", ["tenant_id"])
    op.create_index("ix_sec_risk_register_category", "sec_risk_register", ["category"])
    op.create_index("ix_sec_risk_register_status", "sec_risk_register", ["status"])
    op.create_index("ix_sec_risk_register_created_at", "sec_risk_register", ["created_at"])

    # -- sec_privacy_requests ----------------------------------------------
    op.create_table(
        "sec_privacy_requests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), nullable=True),
        sa.Column("subject_ref", sa.String(), nullable=False),
        sa.Column("request_type", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="received"),
        sa.Column("legal_basis", sa.String(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=False, server_default=""),
        sa.Column("due_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_sec_privacy_requests_tenant_id", "sec_privacy_requests", ["tenant_id"])
    op.create_index("ix_sec_privacy_requests_subject_ref", "sec_privacy_requests", ["subject_ref"])
    op.create_index("ix_sec_privacy_requests_request_type", "sec_privacy_requests", ["request_type"])
    op.create_index("ix_sec_privacy_requests_status", "sec_privacy_requests", ["status"])
    op.create_index("ix_sec_privacy_requests_created_at", "sec_privacy_requests", ["created_at"])

    # -- sec_posture_snapshots ---------------------------------------------
    op.create_table(
        "sec_posture_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), nullable=True),
        sa.Column("overall_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("grade", sa.String(), nullable=False, server_default="F"),
        sa.Column("dimensions", sa.JSON(), nullable=False),
        sa.Column("open_findings", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("open_critical", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_sec_posture_snapshots_tenant_id", "sec_posture_snapshots", ["tenant_id"])
    op.create_index("ix_sec_posture_snapshots_created_at", "sec_posture_snapshots", ["created_at"])

    # -- sec_secret_records -------------------------------------------------
    op.create_table(
        "sec_secret_records",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), nullable=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("provider", sa.String(), nullable=False, server_default="env"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("rotated_at", sa.DateTime(), nullable=True),
        sa.Column("rotation_interval_days", sa.Integer(), nullable=False, server_default="90"),
        sa.Column("strong", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("status", sa.String(), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("tenant_id", "name", name="uq_sec_secret_name"),
    )
    op.create_index("ix_sec_secret_records_tenant_id", "sec_secret_records", ["tenant_id"])
    op.create_index("ix_sec_secret_records_name", "sec_secret_records", ["name"])


def downgrade() -> None:
    op.drop_table("sec_secret_records")
    op.drop_table("sec_posture_snapshots")
    op.drop_table("sec_privacy_requests")
    op.drop_table("sec_risk_register")
    op.drop_table("sec_compliance_assessments")
    op.drop_table("sec_findings")
    op.drop_table("sec_scans")
