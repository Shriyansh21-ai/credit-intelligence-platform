"""AI Intelligence Platform tables

Fully additive: creates the RAG, multi-agent, memory, prompt-engineering
evaluation, investigation, report, workflow, conversational, research
continuous-learning, governance, explainability and monitoring tables. Nothing
from Phases 1-11 / is altered or dropped.

The table set is derived from the ORM metadata for the ``aip_*`` tables defined
in :mod:`backend.app.models.ai_platform`, so the migration can never drift from
the models. It creates/drops **only** those tables (``checkfirst=True`` keeps it
idempotent and safe to run over an existing database).

Revision ID: f3a4b5c6d7e8
Revises: e2f3a4b5c6d7
Create Date: 2026-07-29 10:00:00.000000
"""
from typing import Sequence, Union

from alembic import op

# Import the models module so every aip_* table is registered on the shared
# metadata, then select just those tables.
import backend.app.models.ai_platform  # noqa: F401
from backend.app.db.database import Base

revision: str = "f3a4b5c6d7e8"
down_revision: Union[str, Sequence[str], None] = "e2f3a4b5c6d7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _aip_tables():
    """Return the ``aip_*`` Table objects in dependency (FK-safe) order."""
    tables = [t for name, t in Base.metadata.tables.items() if name.startswith("aip_")]
    # metadata.sorted_tables orders parents before children (FK-safe for create).
    return [t for t in Base.metadata.sorted_tables if t in tables]


def upgrade() -> None:
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind, tables=_aip_tables(), checkfirst=True)


def downgrade() -> None:
    bind = op.get_bind()
    # Drop children before parents.
    for table in reversed(_aip_tables()):
        table.drop(bind=bind, checkfirst=True)
