"""Add tenant-scoped portfolio import tracking.

Revision ID: f4b6c8d0e2a4
Revises: e3f4a5b6c7d8
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "f4b6c8d0e2a4"
down_revision: Union[str, Sequence[str], None] = "e3f4a5b6c7d8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("companies", sa.Column("currency", sa.String(length=3), nullable=True))
    op.create_table(
        "portfolio_imports",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("uploaded_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("file_format", sa.String(length=8), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="awaiting_mapping"),
        sa.Column("worksheet", sa.String(length=255), nullable=True),
        sa.Column("column_mapping", sa.JSON(), nullable=False),
        sa.Column("staged_data", sa.JSON(), nullable=True),
        sa.Column("findings", sa.JSON(), nullable=False),
        sa.Column("total_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("valid_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("invalid_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("warning_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("imported_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("skipped_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_summary", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_portfolio_imports_tenant_id", "portfolio_imports", ["tenant_id"])
    op.create_index("ix_portfolio_imports_uploaded_by", "portfolio_imports", ["uploaded_by"])
    op.create_index("ix_portfolio_imports_status", "portfolio_imports", ["status"])
    op.create_index("ix_portfolio_imports_tenant_created", "portfolio_imports", ["tenant_id", "created_at"])


def downgrade() -> None:
    op.drop_table("portfolio_imports")
    op.drop_column("companies", "currency")