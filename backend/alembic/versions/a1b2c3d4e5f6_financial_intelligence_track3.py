"""Advanced Financial Intelligence Platform tables

Fully additive: creates the treasury, portfolio, Basel/IFRS9, economic-scenario
ESG, market, alternative-data, forecasting, quantitative-risk, benchmarking
executive, optimization, digital-twin and strategic-intelligence tables. Nothing
from Phases 1-11 / Tracks 1-2 is altered or dropped.

The table set is derived from the ORM metadata for the ``fin_*`` tables defined
in :mod:`backend.app.models.financial_intelligence`, so the migration can never
drift from the models. It creates/drops **only** those tables
(``checkfirst=True`` keeps it idempotent and safe over an existing database).

Revision ID: a1b2c3d4e5f6
Revises: f3a4b5c6d7e8
Create Date: 2026-07-30 10:00:00.000000
"""
from typing import Sequence, Union

from alembic import op

# Import the models module so every fin_* table is registered on the shared
# metadata, then select just those tables.
import backend.app.models.financial_intelligence  # noqa: F401
from backend.app.db.database import Base

revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "f3a4b5c6d7e8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _fin_tables():
    """Return the ``fin_*`` Table objects in dependency (FK-safe) order."""
    tables = [t for name, t in Base.metadata.tables.items() if name.startswith("fin_")]
    return [t for t in Base.metadata.sorted_tables if t in tables]


def upgrade() -> None:
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind, tables=_fin_tables(), checkfirst=True)


def downgrade() -> None:
    bind = op.get_bind()
    for table in reversed(_fin_tables()):
        table.drop(bind=bind, checkfirst=True)
