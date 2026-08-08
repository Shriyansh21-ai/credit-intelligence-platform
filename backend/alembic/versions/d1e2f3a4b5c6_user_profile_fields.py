"""Add profile fields to users and backfill demo accounts.

Fully additive: adds ``full_name``, ``job_title``, ``department``,
``organization_name`` and ``avatar_url`` to the ``users`` table (all nullable),
then backfills realistic profiles for the known demo accounts so logging in as
any of them shows a distinct identity and organisation. Nothing is dropped.

Revision ID: d1e2f3a4b5c6
Revises: c3d4e5f6a7b8
Create Date: 2026-08-07 12:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "d1e2f3a4b5c6"
down_revision: Union[str, Sequence[str], None] = "c3d4e5f6a7b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# email -> (full_name, job_title, department, organization_name)
DEMO_PROFILES = {
    "priya.sharma@hdfcbank.com": ("Priya Sharma", "Senior Credit Analyst", "Credit Risk", "HDFC Bank"),
    "rahul.mehta@icicibank.com": ("Rahul Mehta", "Chief Risk Officer", "Risk Management", "ICICI Bank"),
    "anita.desai@sbi.co.in": ("Anita Desai", "Credit Manager", "Corporate Credit", "State Bank of India"),
    "vikram.nair@axisbank.com": ("Vikram Nair", "Head of Credit", "Credit Risk", "Axis Bank"),
    "sneha.iyer@kotak.com": ("Sneha Iyer", "Risk Analyst", "Risk Analytics", "Kotak Mahindra Bank"),
    "arjun.rao@yesbank.in": ("Arjun Rao", "Portfolio Manager", "Portfolio Management", "Yes Bank"),
    "demo@bank.com": ("Demo User", "Credit Analyst", "Credit Risk", "Demo Bank"),
    "demo@test.com": ("Demo Analyst", "Credit Analyst", "Credit Risk", "Test Organization"),
    "e2e_admin@test.com": ("Platform Admin", "Administrator", "Platform", "Test Organization"),
}


def upgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("full_name", sa.String(), nullable=True))
        batch.add_column(sa.Column("job_title", sa.String(), nullable=True))
        batch.add_column(sa.Column("department", sa.String(), nullable=True))
        batch.add_column(sa.Column("organization_name", sa.String(), nullable=True))
        batch.add_column(sa.Column("avatar_url", sa.String(), nullable=True))

    # Backfill known demo accounts. Only fills columns that are still empty so a
    # re-run (or a user who already edited their profile) is never clobbered.
    users = sa.table(
        "users",
        sa.column("email", sa.String),
        sa.column("full_name", sa.String),
        sa.column("job_title", sa.String),
        sa.column("department", sa.String),
        sa.column("organization_name", sa.String),
    )
    conn = op.get_bind()
    for email, (full_name, job_title, department, org) in DEMO_PROFILES.items():
        conn.execute(
            users.update()
            .where(users.c.email == email)
            .where(users.c.full_name.is_(None))
            .values(
                full_name=full_name,
                job_title=job_title,
                department=department,
                organization_name=org,
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.drop_column("avatar_url")
        batch.drop_column("organization_name")
        batch.drop_column("department")
        batch.drop_column("job_title")
        batch.drop_column("full_name")
