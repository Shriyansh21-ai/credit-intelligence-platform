"""Task management and notification tables (Phase 5, M9 & M10)

Revision ID: b4d5e6f7a8c9
Revises: a3c4d5e6f7b8
Create Date: 2026-07-21 15:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "b4d5e6f7a8c9"
down_revision: Union[str, Sequence[str], None] = "a3c4d5e6f7b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "tasks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("application_id", sa.Integer(), sa.ForeignKey("applications.id", ondelete="CASCADE"), nullable=True),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("task_type", sa.String(), nullable=True),
        sa.Column("owner_id", sa.Integer(), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("priority", sa.String(), nullable=False, server_default="medium"),
        sa.Column("status", sa.String(), nullable=False, server_default="open"),
        sa.Column("due_date", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_tasks_application_id", "tasks", ["application_id"])
    op.create_index("ix_tasks_task_type", "tasks", ["task_type"])
    op.create_index("ix_tasks_owner_id", "tasks", ["owner_id"])
    op.create_index("ix_tasks_status", "tasks", ["status"])
    op.create_index("ix_tasks_due_date", "tasks", ["due_date"])

    op.create_table(
        "task_comments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("task_id", sa.Integer(), sa.ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("author_id", sa.Integer(), nullable=True),
        sa.Column("author_email", sa.String(), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_task_comments_task_id", "task_comments", ["task_id"])

    op.create_table(
        "notifications",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("severity", sa.String(), nullable=False, server_default="info"),
        sa.Column("entity_type", sa.String(), nullable=True),
        sa.Column("entity_id", sa.Integer(), nullable=True),
        sa.Column("data", sa.JSON(), nullable=True),
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("read_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_notifications_user_id", "notifications", ["user_id"])
    op.create_index("ix_notifications_event_type", "notifications", ["event_type"])
    op.create_index("ix_notifications_is_read", "notifications", ["is_read"])
    op.create_index("ix_notifications_created_at", "notifications", ["created_at"])

    op.create_table(
        "notification_preferences",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("in_app", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("email", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("webhook", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.UniqueConstraint("user_id", "event_type", name="uq_notif_pref_user_event"),
    )
    op.create_index("ix_notification_preferences_user_id", "notification_preferences", ["user_id"])
    op.create_index("ix_notification_preferences_event_type", "notification_preferences", ["event_type"])


def downgrade() -> None:
    op.drop_table("notification_preferences")
    op.drop_table("notifications")
    op.drop_table("task_comments")
    op.drop_table("tasks")
