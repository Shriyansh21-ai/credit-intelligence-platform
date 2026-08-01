"""Collaboration tables: notes, mentions, attachments

Revision ID: c5e6f7a8b9d0
Revises: b4d5e6f7a8c9
Create Date: 2026-07-21 16:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "c5e6f7a8b9d0"
down_revision: Union[str, Sequence[str], None] = "b4d5e6f7a8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "notes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("application_id", sa.Integer(), sa.ForeignKey("applications.id", ondelete="CASCADE"), nullable=False),
        sa.Column("parent_id", sa.Integer(), sa.ForeignKey("notes.id", ondelete="CASCADE"), nullable=True),
        sa.Column("author_id", sa.Integer(), nullable=True),
        sa.Column("author_email", sa.String(), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("is_pinned", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_notes_application_id", "notes", ["application_id"])
    op.create_index("ix_notes_parent_id", "notes", ["parent_id"])
    op.create_index("ix_notes_author_id", "notes", ["author_id"])
    op.create_index("ix_notes_is_pinned", "notes", ["is_pinned"])
    op.create_index("ix_notes_is_deleted", "notes", ["is_deleted"])
    op.create_index("ix_notes_created_at", "notes", ["created_at"])

    op.create_table(
        "note_mentions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("note_id", sa.Integer(), sa.ForeignKey("notes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
    )
    op.create_index("ix_note_mentions_note_id", "note_mentions", ["note_id"])
    op.create_index("ix_note_mentions_user_id", "note_mentions", ["user_id"])

    op.create_table(
        "note_attachments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("note_id", sa.Integer(), sa.ForeignKey("notes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("filename", sa.String(), nullable=False),
        sa.Column("mime_type", sa.String(), nullable=True),
        sa.Column("size_bytes", sa.Integer(), nullable=True),
        sa.Column("storage_uri", sa.String(), nullable=False),
        sa.Column("uploaded_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_note_attachments_note_id", "note_attachments", ["note_id"])


def downgrade() -> None:
    op.drop_table("note_attachments")
    op.drop_table("note_mentions")
    op.drop_table("notes")
