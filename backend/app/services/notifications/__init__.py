"""Centralized Notification Engine (Phase 5, Milestone 10).

A single ``notify()`` entry point fans an event out across enabled channels.
In-app delivery persists a :class:`Notification`; email and webhook channels are
pluggable and log-only (email-ready / webhook-ready) until a provider is wired in.
"""

from backend.app.services.notifications.catalog import EVENT_TYPES, event_meta
from backend.app.services.notifications.service import (
    get_preferences,
    list_notifications,
    mark_all_read,
    mark_read,
    notify,
    notify_safe,
    set_preference,
    unread_count,
)

__all__ = [
    "EVENT_TYPES",
    "event_meta",
    "notify",
    "notify_safe",
    "list_notifications",
    "mark_read",
    "mark_all_read",
    "unread_count",
    "get_preferences",
    "set_preference",
]
