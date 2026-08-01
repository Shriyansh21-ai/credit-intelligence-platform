"""Enterprise Productization & Commercial Readiness tables

Fully additive: creates the UX, workspace, developer, marketplace, integration
data-management, operations, security, customer-success, deployment, monitoring
BI and launch-readiness tables. Nothing from Phases 1-11 / Tracks 1-3 is altered
or dropped.

The table set is derived from the ORM metadata for the ``ent_*`` tables defined
in :mod:`backend.app.models.enterprise_platform`, so the migration can never
drift from the models. It creates/drops **only** those tables
(``checkfirst=True`` keeps it idempotent and safe over an existing database).

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-07-30 12:00:00.000000
"""
from typing import Sequence, Union

from alembic import op

import backend.app.models.enterprise_platform  # noqa: F401
from backend.app.db.database import Base

revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _ent_tables():
    """Return the ``ent_*`` Table objects in dependency (FK-safe) order."""
    tables = [t for name, t in Base.metadata.tables.items() if name.startswith("ent_")]
    return [t for t in Base.metadata.sorted_tables if t in tables]


def upgrade() -> None:
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind, tables=_ent_tables(), checkfirst=True)


def downgrade() -> None:
    bind = op.get_bind()
    for table in reversed(_ent_tables()):
        table.drop(bind=bind, checkfirst=True)
