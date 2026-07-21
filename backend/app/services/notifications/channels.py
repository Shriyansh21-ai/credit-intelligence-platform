"""Notification delivery channels.

``InAppChannel`` persists a :class:`Notification` row. ``EmailChannel`` and
``WebhookChannel`` implement the same interface but only log their intent — the
architecture is delivery-ready; plugging in SES/SMTP or an HTTP webhook is a
matter of filling in ``deliver``.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from backend.app.models.notification import Notification

logger = logging.getLogger("notifications")


class NotificationChannel:
    name = "base"

    def deliver(self, db: Session, *, user_id: int, payload: Dict[str, Any]) -> Optional[Notification]:
        raise NotImplementedError


class InAppChannel(NotificationChannel):
    name = "in_app"

    def deliver(self, db: Session, *, user_id: int, payload: Dict[str, Any]) -> Optional[Notification]:
        notification = Notification(
            user_id=user_id,
            event_type=payload["event_type"],
            title=payload["title"],
            message=payload.get("message"),
            severity=payload.get("severity", "info"),
            entity_type=payload.get("entity_type"),
            entity_id=payload.get("entity_id"),
            data=payload.get("data"),
        )
        db.add(notification)
        db.commit()
        db.refresh(notification)
        return notification


class EmailChannel(NotificationChannel):
    name = "email"

    def deliver(self, db: Session, *, user_id: int, payload: Dict[str, Any]) -> Optional[Notification]:
        # Email-ready: enqueue/send here. Intentionally a no-op stub for now.
        logger.info("[email] would notify user=%s event=%s", user_id, payload.get("event_type"))
        return None


class WebhookChannel(NotificationChannel):
    name = "webhook"

    def deliver(self, db: Session, *, user_id: int, payload: Dict[str, Any]) -> Optional[Notification]:
        # Webhook-ready: POST to the subscriber's endpoint here. No-op stub.
        logger.info("[webhook] would notify user=%s event=%s", user_id, payload.get("event_type"))
        return None


CHANNELS = {
    "in_app": InAppChannel(),
    "email": EmailChannel(),
    "webhook": WebhookChannel(),
}
