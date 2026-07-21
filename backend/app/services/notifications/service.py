"""Notification dispatch + read/preference management.

``notify`` resolves the recipient's channel preferences and delivers through each
enabled channel. In-app is on by default; email/webhook default off. Delivery is
best-effort — a channel failure never propagates to the business action.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from backend.app.models.notification import Notification, NotificationPreference
from backend.app.services.notifications.catalog import event_meta
from backend.app.services.notifications.channels import CHANNELS

# Channel defaults when a user has no explicit preference for an event.
_DEFAULT_CHANNELS = {"in_app": True, "email": False, "webhook": False}


def _preference(db: Session, user_id: int, event_type: str) -> Dict[str, bool]:
    pref = (
        db.query(NotificationPreference)
        .filter(
            NotificationPreference.user_id == user_id,
            NotificationPreference.event_type == event_type,
        )
        .first()
    )
    if pref is None:
        return dict(_DEFAULT_CHANNELS)
    return {"in_app": pref.in_app, "email": pref.email, "webhook": pref.webhook}


def notify(
    db: Session,
    *,
    user_id: Optional[int],
    event_type: str,
    title: Optional[str] = None,
    message: Optional[str] = None,
    severity: Optional[str] = None,
    entity_type: Optional[str] = None,
    entity_id: Optional[int] = None,
    data: Optional[dict] = None,
) -> Optional[Notification]:
    """Dispatch a notification. Returns the in-app row if one was created."""
    if user_id is None:
        return None

    meta = event_meta(event_type)
    payload = {
        "event_type": event_type,
        "title": title or meta["label"],
        "message": message,
        "severity": severity or meta["severity"],
        "entity_type": entity_type,
        "entity_id": entity_id,
        "data": data,
    }

    prefs = _preference(db, user_id, event_type)
    created: Optional[Notification] = None
    for channel_name, enabled in prefs.items():
        if not enabled:
            continue
        channel = CHANNELS.get(channel_name)
        if channel is None:
            continue
        try:
            result = channel.deliver(db, user_id=user_id, payload=payload)
            if channel_name == "in_app" and result is not None:
                created = result
        except Exception:
            db.rollback()
    return created


def notify_safe(db: Session, **kwargs: Any) -> Optional[Notification]:
    """Like :func:`notify` but never raises (safe for cross-module hooks)."""
    try:
        return notify(db, **kwargs)
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
        return None


def list_notifications(
    db: Session,
    user_id: int,
    *,
    unread_only: bool = False,
    page: int = 1,
    page_size: int = 25,
) -> Dict[str, Any]:
    query = db.query(Notification).filter(Notification.user_id == user_id)
    if unread_only:
        query = query.filter(Notification.is_read == False)  # noqa: E712
    total = query.count()
    page = max(1, page)
    page_size = max(1, min(page_size, 200))
    rows = (
        query.order_by(Notification.created_at.desc(), Notification.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {
        "items": [serialize(n) for n in rows],
        "total": total,
        "unread": unread_count(db, user_id),
        "page": page,
        "page_size": page_size,
        "pages": (total + page_size - 1) // page_size,
    }


def unread_count(db: Session, user_id: int) -> int:
    return (
        db.query(Notification)
        .filter(Notification.user_id == user_id, Notification.is_read == False)  # noqa: E712
        .count()
    )


def mark_read(db: Session, user_id: int, notification_id: int) -> Optional[Notification]:
    n = (
        db.query(Notification)
        .filter(Notification.id == notification_id, Notification.user_id == user_id)
        .first()
    )
    if n is None:
        return None
    if not n.is_read:
        n.is_read = True
        n.read_at = datetime.utcnow()
        db.commit()
        db.refresh(n)
    return n


def mark_all_read(db: Session, user_id: int) -> int:
    rows = (
        db.query(Notification)
        .filter(Notification.user_id == user_id, Notification.is_read == False)  # noqa: E712
        .all()
    )
    now = datetime.utcnow()
    for n in rows:
        n.is_read = True
        n.read_at = now
    db.commit()
    return len(rows)


def get_preferences(db: Session, user_id: int) -> List[Dict[str, Any]]:
    from backend.app.services.notifications.catalog import EVENT_TYPES

    existing = {
        p.event_type: p
        for p in db.query(NotificationPreference)
        .filter(NotificationPreference.user_id == user_id)
        .all()
    }
    result = []
    for event_type, meta in EVENT_TYPES.items():
        pref = existing.get(event_type)
        result.append(
            {
                "event_type": event_type,
                "label": meta["label"],
                "in_app": pref.in_app if pref else _DEFAULT_CHANNELS["in_app"],
                "email": pref.email if pref else _DEFAULT_CHANNELS["email"],
                "webhook": pref.webhook if pref else _DEFAULT_CHANNELS["webhook"],
            }
        )
    return result


def set_preference(
    db: Session,
    user_id: int,
    event_type: str,
    *,
    in_app: Optional[bool] = None,
    email: Optional[bool] = None,
    webhook: Optional[bool] = None,
) -> Dict[str, Any]:
    pref = (
        db.query(NotificationPreference)
        .filter(
            NotificationPreference.user_id == user_id,
            NotificationPreference.event_type == event_type,
        )
        .first()
    )
    if pref is None:
        pref = NotificationPreference(
            user_id=user_id,
            event_type=event_type,
            **_DEFAULT_CHANNELS,
        )
        db.add(pref)
    if in_app is not None:
        pref.in_app = in_app
    if email is not None:
        pref.email = email
    if webhook is not None:
        pref.webhook = webhook
    db.commit()
    db.refresh(pref)
    return {
        "event_type": pref.event_type,
        "in_app": pref.in_app,
        "email": pref.email,
        "webhook": pref.webhook,
    }


def serialize(n: Notification) -> Dict[str, Any]:
    return {
        "id": n.id,
        "user_id": n.user_id,
        "event_type": n.event_type,
        "title": n.title,
        "message": n.message,
        "severity": n.severity,
        "entity_type": n.entity_type,
        "entity_id": n.entity_id,
        "data": n.data,
        "is_read": n.is_read,
        "read_at": n.read_at.isoformat() if n.read_at else None,
        "created_at": n.created_at.isoformat() if n.created_at else None,
    }
