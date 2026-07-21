"""Notification models (Phase 5, Milestone 10).

``Notification`` is an in-app message for a single recipient. ``NotificationPreference``
stores per-user, per-event channel toggles (in-app / email / webhook) so the
dispatcher can honour user choices. Email and webhook delivery are architected
(pluggable channels) but not wired to a live provider.
"""

from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Integer, JSON, String, Text, UniqueConstraint

from backend.app.db.database import Base


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)  # recipient

    event_type = Column(String, nullable=False, index=True)
    title = Column(String, nullable=False)
    message = Column(Text, nullable=True)
    severity = Column(String, nullable=False, default="info")  # info / warning / critical

    entity_type = Column(String, nullable=True)
    entity_id = Column(Integer, nullable=True)

    data = Column(JSON, nullable=True)

    is_read = Column(Boolean, nullable=False, default=False, index=True)
    read_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class NotificationPreference(Base):
    __tablename__ = "notification_preferences"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    event_type = Column(String, nullable=False, index=True)

    in_app = Column(Boolean, nullable=False, default=True)
    email = Column(Boolean, nullable=False, default=False)
    webhook = Column(Boolean, nullable=False, default=False)

    __table_args__ = (
        UniqueConstraint("user_id", "event_type", name="uq_notif_pref_user_event"),
    )
