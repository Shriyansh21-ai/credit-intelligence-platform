"""Audit query layer — searchable, filterable, paginated.

Powers the audit dashboard. All filters are optional and combine with AND.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.app.models.audit import AuditLog


def _serialize(row: AuditLog) -> Dict[str, Any]:
    return {
        "id": row.id,
        "user_id": row.user_id,
        "user_email": row.user_email,
        "timestamp": row.timestamp.isoformat() if row.timestamp else None,
        "ip_address": row.ip_address,
        "user_agent": row.user_agent,
        "http_method": row.http_method,
        "path": row.path,
        "action": row.action,
        "entity_type": row.entity_type,
        "entity_id": row.entity_id,
        "previous_value": row.previous_value,
        "new_value": row.new_value,
        "reason": row.reason,
        "status": row.status,
        "meta": row.meta,
    }


def search_audit(
    db: Session,
    *,
    user_id: Optional[int] = None,
    user_email: Optional[str] = None,
    action: Optional[str] = None,
    entity_type: Optional[str] = None,
    entity_id: Optional[int] = None,
    status: Optional[str] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    q: Optional[str] = None,
    page: int = 1,
    page_size: int = 50,
) -> Dict[str, Any]:
    """Return ``{items, total, page, page_size, pages}`` newest-first."""
    query = db.query(AuditLog)

    if user_id is not None:
        query = query.filter(AuditLog.user_id == user_id)
    if user_email:
        query = query.filter(AuditLog.user_email == user_email)
    if action:
        query = query.filter(AuditLog.action.like(f"{action}%"))
    if entity_type:
        query = query.filter(AuditLog.entity_type == entity_type)
    if entity_id is not None:
        query = query.filter(AuditLog.entity_id == entity_id)
    if status:
        query = query.filter(AuditLog.status == status)
    if date_from is not None:
        query = query.filter(AuditLog.timestamp >= date_from)
    if date_to is not None:
        query = query.filter(AuditLog.timestamp <= date_to)
    if q:
        like = f"%{q}%"
        query = query.filter(
            AuditLog.action.like(like)
            | AuditLog.reason.like(like)
            | AuditLog.path.like(like)
            | AuditLog.user_email.like(like)
        )

    total = query.count()

    page = max(1, page)
    page_size = max(1, min(page_size, 500))
    rows = (
        query.order_by(AuditLog.timestamp.desc(), AuditLog.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    pages = (total + page_size - 1) // page_size
    return {
        "items": [_serialize(r) for r in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": pages,
    }


def audit_stats(db: Session) -> Dict[str, Any]:
    """Aggregate counts for the audit dashboard header."""
    total = db.query(func.count(AuditLog.id)).scalar() or 0

    by_action = (
        db.query(AuditLog.action, func.count(AuditLog.id))
        .group_by(AuditLog.action)
        .order_by(func.count(AuditLog.id).desc())
        .limit(20)
        .all()
    )
    by_status = (
        db.query(AuditLog.status, func.count(AuditLog.id))
        .group_by(AuditLog.status)
        .all()
    )
    return {
        "total": total,
        "by_action": [{"action": a, "count": c} for a, c in by_action],
        "by_status": [{"status": s, "count": c} for s, c in by_status],
    }


def list_actions(db: Session) -> List[str]:
    rows = db.query(AuditLog.action).distinct().order_by(AuditLog.action).all()
    return [r[0] for r in rows]
