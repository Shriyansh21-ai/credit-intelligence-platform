"""System configuration table

Revision ID: d6f7a8b9c0e1
Revises: c5e6f7a8b9d0
Create Date: 2026-07-21 17:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from backend.app.services.config.catalog import CONFIG_DEFAULTS


revision: str = "d6f7a8b9c0e1"
down_revision: Union[str, Sequence[str], None] = "c5e6f7a8b9d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "system_config",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("key", sa.String(), nullable=False),
        sa.Column("value", sa.JSON(), nullable=True),
        sa.Column("value_type", sa.String(), nullable=False, server_default="json"),
        sa.Column("category", sa.String(), nullable=False, server_default="General"),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("updated_by", sa.Integer(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("key", name="uq_system_config_key"),
    )
    op.create_index("ix_system_config_key", "system_config", ["key"], unique=True)
    op.create_index("ix_system_config_category", "system_config", ["category"])

    cfg_t = sa.table(
        "system_config",
        sa.column("key", sa.String),
        sa.column("value", sa.JSON),
        sa.column("value_type", sa.String),
        sa.column("category", sa.String),
        sa.column("description", sa.Text),
    )
    op.get_bind().execute(
        cfg_t.insert(),
        [
            {
                "key": key,
                "value": spec["value"],
                "value_type": spec.get("value_type", "json"),
                "category": spec.get("category", "General"),
                "description": spec.get("description"),
            }
            for key, spec in CONFIG_DEFAULTS.items()
        ],
    )


def downgrade() -> None:
    op.drop_index("ix_system_config_key", table_name="system_config")
    op.drop_table("system_config")
