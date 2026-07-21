"""Covenant monitoring and post-disbursement monitoring tables (Phase 5, M5 & M6)

Revision ID: a3c4d5e6f7b8
Revises: f2b3c4d5e6a7
Create Date: 2026-07-21 14:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "a3c4d5e6f7b8"
down_revision: Union[str, Sequence[str], None] = "f2b3c4d5e6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "covenants",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("application_id", sa.Integer(), sa.ForeignKey("applications.id", ondelete="CASCADE"), nullable=False),
        sa.Column("metric_key", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("operator", sa.String(), nullable=False, server_default="min"),
        sa.Column("threshold", sa.Float(), nullable=False),
        sa.Column("unit", sa.String(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.String(), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_covenants_application_id", "covenants", ["application_id"])
    op.create_index("ix_covenants_metric_key", "covenants", ["metric_key"])

    op.create_table(
        "covenant_measurements",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("covenant_id", sa.Integer(), sa.ForeignKey("covenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("value", sa.Float(), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="ok"),
        sa.Column("headroom", sa.Float(), nullable=True),
        sa.Column("period", sa.String(), nullable=True),
        sa.Column("source", sa.String(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("measured_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_covenant_measurements_covenant_id", "covenant_measurements", ["covenant_id"])
    op.create_index("ix_covenant_measurements_measured_at", "covenant_measurements", ["measured_at"])

    op.create_table(
        "covenant_alerts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("covenant_id", sa.Integer(), sa.ForeignKey("covenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("application_id", sa.Integer(), sa.ForeignKey("applications.id", ondelete="CASCADE"), nullable=False),
        sa.Column("measurement_id", sa.Integer(), sa.ForeignKey("covenant_measurements.id"), nullable=True),
        sa.Column("severity", sa.String(), nullable=False, server_default="high"),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="open"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_covenant_alerts_covenant_id", "covenant_alerts", ["covenant_id"])
    op.create_index("ix_covenant_alerts_application_id", "covenant_alerts", ["application_id"])
    op.create_index("ix_covenant_alerts_created_at", "covenant_alerts", ["created_at"])

    op.create_table(
        "monitoring_records",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("application_id", sa.Integer(), sa.ForeignKey("applications.id", ondelete="CASCADE"), nullable=False),
        sa.Column("record_type", sa.String(), nullable=False),
        sa.Column("period", sa.String(), nullable=True),
        sa.Column("health_score", sa.Float(), nullable=True),
        sa.Column("risk_rating", sa.String(), nullable=True),
        sa.Column("payment_status", sa.String(), nullable=True),
        sa.Column("data", sa.JSON(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("recorded_by", sa.Integer(), nullable=True),
        sa.Column("recorded_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_monitoring_records_application_id", "monitoring_records", ["application_id"])
    op.create_index("ix_monitoring_records_record_type", "monitoring_records", ["record_type"])
    op.create_index("ix_monitoring_records_recorded_at", "monitoring_records", ["recorded_at"])

    op.create_table(
        "monitoring_alerts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("application_id", sa.Integer(), sa.ForeignKey("applications.id", ondelete="CASCADE"), nullable=False),
        sa.Column("record_id", sa.Integer(), sa.ForeignKey("monitoring_records.id"), nullable=True),
        sa.Column("category", sa.String(), nullable=False),
        sa.Column("severity", sa.String(), nullable=False, server_default="medium"),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="open"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_monitoring_alerts_application_id", "monitoring_alerts", ["application_id"])
    op.create_index("ix_monitoring_alerts_created_at", "monitoring_alerts", ["created_at"])


def downgrade() -> None:
    op.drop_table("monitoring_alerts")
    op.drop_table("monitoring_records")
    op.drop_table("covenant_alerts")
    op.drop_table("covenant_measurements")
    op.drop_table("covenants")
