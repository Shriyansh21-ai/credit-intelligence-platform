"""Real-time platform.

An in-process pub/sub hub backing WebSocket delivery, a durable activity stream
and presence tracking. Producers anywhere in the app call :func:`publish`
(synchronous, safe off the event loop) which

* persists an :class:`ActivityEvent` (the durable feed / activity stream), and
* fans the event out to every subscribed live connection's queue (best-effort).

The WebSocket route (``routes/saas.py``) drives connections through
:meth:`RealtimeHub.connect` / :meth:`RealtimeHub.stream`. The hub is transport-
agnostic: the same publish path could push to Redis pub/sub or a message bus by
swapping the fan-out sink — producers never change.
"""

from __future__ import annotations

import asyncio
import uuid
from collections import deque
from datetime import datetime
from typing import Any, Deque, Dict, List, Optional, Set

from sqlalchemy.orm import Session

from backend.app.models.platform_ops import ActivityEvent, PresenceRecord

_RECENT_MAX = 200


class _Connection:
    __slots__ = ("id", "tenant_id", "channels", "queue", "user_id")

    def __init__(self, tenant_id: Optional[int], channels: Set[str], user_id: Optional[int]):
        self.id = uuid.uuid4().hex
        self.tenant_id = tenant_id
        self.channels = channels
        self.user_id = user_id
        self.queue: "asyncio.Queue[dict]" = asyncio.Queue()


class RealtimeHub:
    def __init__(self):
        self._connections: Dict[str, _Connection] = {}
        # Recent events per (tenant, channel) for replay on connect.
        self._recent: Dict[str, Deque[dict]] = {}

    # -- connection lifecycle ------------------------------------------
    def connect(self, *, tenant_id: Optional[int], channels: Optional[Set[str]] = None,
                user_id: Optional[int] = None) -> _Connection:
        conn = _Connection(tenant_id, channels or {"global"}, user_id)
        self._connections[conn.id] = conn
        return conn

    def disconnect(self, conn_id: str) -> None:
        self._connections.pop(conn_id, None)

    def connection_count(self) -> int:
        return len(self._connections)

    def _recent_key(self, tenant_id: Optional[int], channel: str) -> str:
        return f"{tenant_id}:{channel}"

    def recent(self, tenant_id: Optional[int], channel: str, limit: int = 50) -> List[dict]:
        key = self._recent_key(tenant_id, channel)
        return list(self._recent.get(key, deque()))[-limit:]

    # -- fan-out --------------------------------------------------------
    def dispatch(self, event: dict) -> int:
        """Push ``event`` to matching live connections + recent buffer. Returns
        the number of connections notified."""
        channel = event.get("channel", "global")
        tenant_id = event.get("tenant_id")
        key = self._recent_key(tenant_id, channel)
        buf = self._recent.setdefault(key, deque(maxlen=_RECENT_MAX))
        buf.append(event)
        notified = 0
        for conn in list(self._connections.values()):
            if channel not in conn.channels and "*" not in conn.channels:
                continue
            if conn.tenant_id is not None and tenant_id is not None and conn.tenant_id != tenant_id:
                continue
            try:
                conn.queue.put_nowait(event)
                notified += 1
            except Exception:
                pass
        return notified

    async def stream(self, conn: _Connection):
        """Async generator yielding events for a connection (used by the WS route)."""
        while True:
            event = await conn.queue.get()
            yield event


hub = RealtimeHub()


# ===========================================================================
# Public API
# ===========================================================================
def publish(db: Session, *, channel: str, event_type: str,
            tenant_id: Optional[int] = None, actor: Optional[str] = None,
            subject: Optional[str] = None, payload: Optional[Dict[str, Any]] = None,
            persist: bool = True) -> Dict[str, Any]:
    """Emit a real-time event: persist to the activity stream and fan out live."""
    created = datetime.utcnow()
    event = {
        "channel": channel, "event_type": event_type, "tenant_id": tenant_id,
        "actor": actor, "subject": subject, "payload": payload or {},
        "created_at": created.isoformat(),
    }
    if persist:
        row = ActivityEvent(
            tenant_id=tenant_id, channel=channel, event_type=event_type,
            actor=actor, subject=subject, payload=payload or {},
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        event["id"] = row.id
    hub.dispatch(event)
    return event


def recent_activity(db: Session, *, tenant_id: Optional[int] = None,
                    channel: Optional[str] = None, limit: int = 50) -> List[ActivityEvent]:
    q = db.query(ActivityEvent)
    if tenant_id is not None:
        q = q.filter(ActivityEvent.tenant_id == tenant_id)
    if channel:
        q = q.filter(ActivityEvent.channel == channel)
    return q.order_by(ActivityEvent.id.desc()).limit(limit).all()


# ===========================================================================
# Presence
# ===========================================================================
def mark_presence(db: Session, tenant_id: Optional[int], user_id: int, *,
                  status: str = "online", context: Optional[Dict] = None) -> PresenceRecord:
    rec = (
        db.query(PresenceRecord)
        .filter(PresenceRecord.user_id == user_id,
                PresenceRecord.tenant_id == tenant_id)
        .first()
    )
    if rec is None:
        rec = PresenceRecord(tenant_id=tenant_id, user_id=user_id)
        db.add(rec)
    rec.status = status
    rec.last_seen_at = datetime.utcnow()
    rec.context = context or {}
    db.commit()
    db.refresh(rec)
    # Presence change is itself a real-time event.
    publish(db, channel="presence", event_type=f"presence.{status}",
            tenant_id=tenant_id, subject=str(user_id), persist=False)
    return rec


def online_users(db: Session, tenant_id: Optional[int] = None) -> List[PresenceRecord]:
    q = db.query(PresenceRecord).filter(PresenceRecord.status == "online")
    if tenant_id is not None:
        q = q.filter(PresenceRecord.tenant_id == tenant_id)
    return q.all()
