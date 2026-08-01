"""RBAC and audit tables

Creates the roles / permissions / association tables and the audit log, then
seeds the canonical RBAC catalog and backfills existing users with the default
role so no account is locked out after RBAC goes live.

Revision ID: e1f2a3b4c5d6
Revises: d4a1c8f5b3e2
Create Date: 2026-07-21 12:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from backend.app.services.rbac import catalog


# revision identifiers, used by Alembic.
revision: str = "e1f2a3b4c5d6"
down_revision: Union[str, Sequence[str], None] = "d4a1c8f5b3e2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "permissions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(), nullable=False),
        sa.Column("category", sa.String(), nullable=False, server_default="General"),
        sa.Column("description", sa.String(), nullable=True),
    )
    op.create_index("ix_permissions_code", "permissions", ["code"], unique=True)

    op.create_table(
        "roles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("display_name", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("name", name="uq_roles_name"),
    )
    op.create_index("ix_roles_name", "roles", ["name"], unique=True)

    op.create_table(
        "role_permissions",
        sa.Column("role_id", sa.Integer(), sa.ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("permission_id", sa.Integer(), sa.ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True),
    )

    op.create_table(
        "user_roles",
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("role_id", sa.Integer(), sa.ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
    )

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("user_email", sa.String(), nullable=True),
        sa.Column("timestamp", sa.DateTime(), nullable=True),
        sa.Column("ip_address", sa.String(), nullable=True),
        sa.Column("user_agent", sa.String(), nullable=True),
        sa.Column("http_method", sa.String(), nullable=True),
        sa.Column("path", sa.String(), nullable=True),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("entity_type", sa.String(), nullable=True),
        sa.Column("entity_id", sa.Integer(), nullable=True),
        sa.Column("previous_value", sa.JSON(), nullable=True),
        sa.Column("new_value", sa.JSON(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="success"),
        sa.Column("meta", sa.JSON(), nullable=True),
    )
    op.create_index("ix_audit_logs_user_id", "audit_logs", ["user_id"])
    op.create_index("ix_audit_logs_user_email", "audit_logs", ["user_email"])
    op.create_index("ix_audit_logs_timestamp", "audit_logs", ["timestamp"])
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"])
    op.create_index("ix_audit_logs_entity_type", "audit_logs", ["entity_type"])
    op.create_index("ix_audit_logs_entity_id", "audit_logs", ["entity_id"])

    _seed(op.get_bind())


def _seed(conn) -> None:
    """Seed permissions, roles, mappings; backfill existing users."""
    perms_t = sa.table(
        "permissions",
        sa.column("id", sa.Integer),
        sa.column("code", sa.String),
        sa.column("category", sa.String),
        sa.column("description", sa.String),
    )
    roles_t = sa.table(
        "roles",
        sa.column("id", sa.Integer),
        sa.column("name", sa.String),
        sa.column("display_name", sa.String),
        sa.column("description", sa.String),
    )
    role_perms_t = sa.table(
        "role_permissions",
        sa.column("role_id", sa.Integer),
        sa.column("permission_id", sa.Integer),
    )
    user_roles_t = sa.table(
        "user_roles",
        sa.column("user_id", sa.Integer),
        sa.column("role_id", sa.Integer),
    )

    conn.execute(
        perms_t.insert(),
        [
            {"code": code, "category": category, "description": desc}
            for code, category, desc in catalog.PERMISSIONS
        ],
    )
    conn.execute(
        roles_t.insert(),
        [
            {"name": name, "display_name": display, "description": desc}
            for name, display, desc in catalog.ROLES
        ],
    )

    perm_ids = {row.code: row.id for row in conn.execute(sa.select(perms_t.c.code, perms_t.c.id))}
    role_ids = {row.name: row.id for row in conn.execute(sa.select(roles_t.c.name, roles_t.c.id))}

    mappings = []
    for role_name, role_id in role_ids.items():
        for code in catalog.resolved_role_permissions(role_name):
            pid = perm_ids.get(code)
            if pid is not None:
                mappings.append({"role_id": role_id, "permission_id": pid})
    if mappings:
        conn.execute(role_perms_t.insert(), mappings)

    # Backfill existing users with the default role.
    backfill_role_id = role_ids.get(catalog.DEFAULT_BACKFILL_ROLE)
    if backfill_role_id is not None:
        users_t = sa.table("users", sa.column("id", sa.Integer))
        user_ids = [row.id for row in conn.execute(sa.select(users_t.c.id))]
        if user_ids:
            conn.execute(
                user_roles_t.insert(),
                [{"user_id": uid, "role_id": backfill_role_id} for uid in user_ids],
            )


def downgrade() -> None:
    op.drop_table("audit_logs")
    op.drop_table("user_roles")
    op.drop_table("role_permissions")
    op.drop_index("ix_roles_name", table_name="roles")
    op.drop_table("roles")
    op.drop_index("ix_permissions_code", table_name="permissions")
    op.drop_table("permissions")
