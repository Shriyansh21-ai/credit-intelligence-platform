"""Collaboration System.

Internal notes, threaded comments, @mentions (with notifications), pinned notes
file attachments, and a unified activity feed aggregated across the platform.
"""

from backend.app.services.collaboration.service import (
    activity_feed,
    add_attachment,
    create_note,
    delete_note,
    edit_note,
    list_notes,
    resolve_mentions,
    serialize_note,
    set_pinned,
)

__all__ = [
    "activity_feed",
    "add_attachment",
    "create_note",
    "delete_note",
    "edit_note",
    "list_notes",
    "resolve_mentions",
    "serialize_note",
    "set_pinned",
]
