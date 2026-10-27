"""Add audited exception and remediation state to exposure breaches.

Revision ID: c1f5a9d3e7b2
Revises: b7d9e2f4a6c1
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "c1f5a9d3e7b2"
down_revision: Union[str, Sequence[str], None] = "b7d9e2f4a6c1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("portfolio_exposure_breaches") as batch_op:
        batch_op.add_column(sa.Column("exception_status", sa.String(length=16), nullable=True))
        batch_op.add_column(
            sa.Column("exception_justification", sa.String(length=1000), nullable=True)
        )
        batch_op.add_column(
            sa.Column("exception_requested_by", sa.Integer(), nullable=True)
        )
        batch_op.add_column(
            sa.Column("exception_requested_at", sa.DateTime(), nullable=True)
        )
        batch_op.add_column(
            sa.Column("exception_expires_at", sa.DateTime(), nullable=True)
        )
        batch_op.add_column(sa.Column("exception_review_date", sa.Date(), nullable=True))
        batch_op.add_column(
            sa.Column("exception_reviewed_by", sa.Integer(), nullable=True)
        )
        batch_op.add_column(
            sa.Column("exception_reviewed_at", sa.DateTime(), nullable=True)
        )
        batch_op.add_column(
            sa.Column("exception_review_reason", sa.String(length=1000), nullable=True)
        )
        batch_op.add_column(sa.Column("remediation_note", sa.String(length=1000), nullable=True))
        batch_op.create_foreign_key(
            "fk_exposure_breach_exception_requested_by_users",
            "users",
            ["exception_requested_by"],
            ["id"],
        )
        batch_op.create_foreign_key(
            "fk_exposure_breach_exception_reviewed_by_users",
            "users",
            ["exception_reviewed_by"],
            ["id"],
        )
        batch_op.create_check_constraint(
            "ck_exposure_breach_exception_status",
            "exception_status IS NULL OR exception_status IN "
            "('requested', 'approved', 'rejected', 'expired')",
        )
    op.create_index(
        "ix_portfolio_exposure_breaches_exception_status",
        "portfolio_exposure_breaches",
        ["exception_status"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_portfolio_exposure_breaches_exception_status",
        table_name="portfolio_exposure_breaches",
    )
    with op.batch_alter_table("portfolio_exposure_breaches") as batch_op:
        batch_op.drop_constraint("ck_exposure_breach_exception_status", type_="check")
        batch_op.drop_constraint(
            "fk_exposure_breach_exception_reviewed_by_users", type_="foreignkey"
        )
        batch_op.drop_constraint(
            "fk_exposure_breach_exception_requested_by_users", type_="foreignkey"
        )
        batch_op.drop_column("remediation_note")
        batch_op.drop_column("exception_review_reason")
        batch_op.drop_column("exception_reviewed_at")
        batch_op.drop_column("exception_reviewed_by")
        batch_op.drop_column("exception_review_date")
        batch_op.drop_column("exception_expires_at")
        batch_op.drop_column("exception_requested_at")
        batch_op.drop_column("exception_requested_by")
        batch_op.drop_column("exception_justification")
        batch_op.drop_column("exception_status")
