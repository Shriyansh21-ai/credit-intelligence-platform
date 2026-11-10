"""Add nullable tenant ownership to legacy applications.

Revision ID: d2e3f4a5b6c7
Revises: c1f5a9d3e7b2
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "d2e3f4a5b6c7"
down_revision: Union[str, Sequence[str], None] = "c1f5a9d3e7b2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("applications") as batch_op:
        batch_op.add_column(sa.Column("tenant_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_applications_tenant_id_tenants",
            "tenants",
            ["tenant_id"],
            ["id"],
            ondelete="RESTRICT",
        )
    op.create_index("ix_applications_tenant_id", "applications", ["tenant_id"])


def downgrade() -> None:
    op.drop_index("ix_applications_tenant_id", table_name="applications")
    with op.batch_alter_table("applications") as batch_op:
        batch_op.drop_constraint("fk_applications_tenant_id_tenants", type_="foreignkey")
        batch_op.drop_column("tenant_id")
