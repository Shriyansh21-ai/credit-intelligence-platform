"""Versioned snapshot store for imported external data (M2, M3, M6, M7, M8).

External payloads (GST profile/returns, MCA master, bureau report, ERP
financials, payment analytics) are persisted as :class:`IntegrationSnapshot`
rows. Snapshots are **versioned** and **content-hashed**

* Saving identical content again is a no-op that returns the existing current
  snapshot (idempotent refresh — no version churn when nothing changed).
* Saving changed content appends ``version + 1`` and flips ``is_current``.

This gives an auditable history of what each provider said about an entity over
time, and lets callers diff versions.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from backend.app.models.integrations import IntegrationSnapshot


def content_hash(payload: Any) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()


def save_snapshot(
    db: Session,
    *,
    connector_key: str,
    provider: str,
    mode: str,
    dataset: str,
    entity_ref: str,
    payload: Any,
    application_id: Optional[int] = None,
    created_by: Optional[str] = None,
    refresh_after_days: Optional[int] = None,
) -> IntegrationSnapshot:
    """Append a new version unless the content is byte-identical to the current one."""
    digest = content_hash(payload)
    current = current_snapshot(db, connector_key=connector_key, entity_ref=entity_ref, dataset=dataset)

    if current is not None and current.content_hash == digest:
        # Idempotent: refresh the fetched timestamp/window but keep the version.
        current.fetched_at = datetime.utcnow()
        if refresh_after_days is not None:
            current.refresh_due_at = datetime.utcnow() + timedelta(days=refresh_after_days)
        db.commit()
        db.refresh(current)
        return current

    next_version = (current.version + 1) if current is not None else 1
    if current is not None:
        current.is_current = False

    snap = IntegrationSnapshot(
        connector_key=connector_key,
        provider=provider,
        mode=mode,
        dataset=dataset,
        entity_ref=entity_ref,
        application_id=application_id,
        version=next_version,
        is_current=True,
        status="active",
        payload=payload,
        content_hash=digest,
        fetched_at=datetime.utcnow(),
        refresh_due_at=(datetime.utcnow() + timedelta(days=refresh_after_days))
        if refresh_after_days is not None else None,
        created_by=created_by,
    )
    db.add(snap)
    db.commit()
    db.refresh(snap)
    return snap


def current_snapshot(
    db: Session, *, connector_key: str, entity_ref: str, dataset: str = "default",
) -> Optional[IntegrationSnapshot]:
    return (
        db.query(IntegrationSnapshot)
        .filter(
            IntegrationSnapshot.connector_key == connector_key,
            IntegrationSnapshot.entity_ref == entity_ref,
            IntegrationSnapshot.dataset == dataset,
            IntegrationSnapshot.is_current.is_(True),
        )
        .order_by(IntegrationSnapshot.version.desc())
        .first()
    )


def snapshot_versions(
    db: Session, *, connector_key: str, entity_ref: str, dataset: str = "default",
) -> List[IntegrationSnapshot]:
    return (
        db.query(IntegrationSnapshot)
        .filter(
            IntegrationSnapshot.connector_key == connector_key,
            IntegrationSnapshot.entity_ref == entity_ref,
            IntegrationSnapshot.dataset == dataset,
        )
        .order_by(IntegrationSnapshot.version.desc())
        .all()
    )


def due_for_refresh(db: Session, *, now: Optional[datetime] = None, limit: int = 100) -> List[IntegrationSnapshot]:
    """Current snapshots whose scheduled refresh time has passed."""
    now = now or datetime.utcnow()
    return (
        db.query(IntegrationSnapshot)
        .filter(
            IntegrationSnapshot.is_current.is_(True),
            IntegrationSnapshot.refresh_due_at.isnot(None),
            IntegrationSnapshot.refresh_due_at <= now,
        )
        .order_by(IntegrationSnapshot.refresh_due_at.asc())
        .limit(limit)
        .all()
    )


def snapshot_to_dict(snap: IntegrationSnapshot) -> Dict[str, Any]:
    return {
        "id": snap.id,
        "connector_key": snap.connector_key,
        "provider": snap.provider,
        "mode": snap.mode,
        "dataset": snap.dataset,
        "entity_ref": snap.entity_ref,
        "application_id": snap.application_id,
        "version": snap.version,
        "is_current": snap.is_current,
        "status": snap.status,
        "payload": snap.payload,
        "content_hash": snap.content_hash,
        "fetched_at": snap.fetched_at.isoformat() if snap.fetched_at else None,
        "refresh_due_at": snap.refresh_due_at.isoformat() if snap.refresh_due_at else None,
        "created_at": snap.created_at.isoformat() if snap.created_at else None,
    }
