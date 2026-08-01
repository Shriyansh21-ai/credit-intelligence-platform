"""Webhook events.

Manages webhook subscriptions and event fan-out. Emitting an event creates a
:class:`WebhookDelivery` per matching subscription and (in this build) marks it
delivered with a signed payload — a real deployment swaps :func:`_deliver` for an
HTTP POST with HMAC signing and retry/backoff. Delivery rows give an auditable
history and a retry surface.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from backend.app.models.integrations import WebhookDelivery, WebhookSubscription

# Canonical event catalog for the Open API platform.
EVENT_TYPES = [
    "snapshot.created", "snapshot.updated", "consent.activated", "consent.revoked",
    "statement.imported", "analytics.completed", "collateral.created",
    "collateral.revalued", "sync.completed", "connector.circuit_open",
]


def create_subscription(db: Session, *, url: str, events: List[str],
                        secret: Optional[str] = None, description: Optional[str] = None) -> WebhookSubscription:
    invalid = [e for e in events if e not in EVENT_TYPES and e != "*"]
    if invalid:
        raise ValueError(f"unknown event types: {invalid}")
    sub = WebhookSubscription(url=url, events=events, secret=secret, description=description, active=True)
    db.add(sub)
    db.commit()
    db.refresh(sub)
    return sub


def list_subscriptions(db: Session) -> List[WebhookSubscription]:
    return db.query(WebhookSubscription).order_by(WebhookSubscription.id.desc()).all()


def set_active(db: Session, subscription_id: int, active: bool) -> WebhookSubscription:
    sub = db.query(WebhookSubscription).get(subscription_id)
    if sub is None:
        raise ValueError("subscription not found")
    sub.active = active
    db.commit()
    db.refresh(sub)
    return sub


def sign_payload(secret: str, payload: Dict[str, Any]) -> str:
    body = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


def emit(db: Session, event: str, payload: Dict[str, Any]) -> List[WebhookDelivery]:
    """Fan an event out to all active subscriptions listening for it."""
    subs = (db.query(WebhookSubscription)
            .filter(WebhookSubscription.active.is_(True)).all())
    deliveries: List[WebhookDelivery] = []
    for sub in subs:
        listens = sub.events or []
        if "*" not in listens and event not in listens:
            continue
        delivery = WebhookDelivery(subscription_id=sub.id, event=event, payload=payload, status="pending")
        db.add(delivery)
        db.flush()
        _deliver(sub, delivery)
        deliveries.append(delivery)
    db.commit()
    for d in deliveries:
        db.refresh(d)
    return deliveries


def _deliver(sub: WebhookSubscription, delivery: WebhookDelivery) -> None:
    """Deliver a webhook. Stubbed: signs + marks delivered (swap for HTTP POST)."""
    delivery.attempts += 1
    try:
        if sub.secret:
            delivery.payload = {**delivery.payload, "_signature": sign_payload(sub.secret, delivery.payload)}
        delivery.status = "delivered"
        delivery.response_code = 200
        delivery.delivered_at = datetime.utcnow()
    except Exception as exc:  # noqa: BLE001
        delivery.status = "failed"
        delivery.last_error = str(exc)


def delivery_history(db: Session, *, subscription_id: Optional[int] = None, limit: int = 100) -> List[WebhookDelivery]:
    q = db.query(WebhookDelivery)
    if subscription_id is not None:
        q = q.filter(WebhookDelivery.subscription_id == subscription_id)
    return q.order_by(WebhookDelivery.id.desc()).limit(limit).all()


def subscription_to_dict(s: WebhookSubscription) -> Dict[str, Any]:
    return {"id": s.id, "url": s.url, "events": s.events, "active": s.active,
            "description": s.description, "has_secret": bool(s.secret),
            "created_at": s.created_at.isoformat() if s.created_at else None}


def delivery_to_dict(d: WebhookDelivery) -> Dict[str, Any]:
    return {"id": d.id, "subscription_id": d.subscription_id, "event": d.event,
            "status": d.status, "attempts": d.attempts, "response_code": d.response_code,
            "last_error": d.last_error,
            "created_at": d.created_at.isoformat() if d.created_at else None,
            "delivered_at": d.delivered_at.isoformat() if d.delivered_at else None}
