"""Audit dashboard API.

    GET /api/audit searchable, filterable, paginated audit log
    GET /api/audit/stats aggregate counts for the dashboard header
    GET /api/audit/actions distinct action names (for filter dropdowns)

All endpoints require the ``audit.view`` permission.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.app.db.database import get_db
from backend.app.models.user import User
from backend.app.services import audit
from backend.app.services.audit.query import list_actions
from backend.app.services.rbac import require_permission

router = APIRouter(prefix="/api/audit", tags=["Audit"])


def _parse_dt(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


@router.get("")
def get_audit(
    user_id: Optional[int] = None,
    user_email: Optional[str] = None,
    action: Optional[str] = None,
    entity_type: Optional[str] = None,
    entity_id: Optional[int] = None,
    status: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    q: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
    _user: User = Depends(require_permission("audit.view")),
):
    return audit.search_audit(
        db,
        user_id=user_id,
        user_email=user_email,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        status=status,
        date_from=_parse_dt(date_from),
        date_to=_parse_dt(date_to),
        q=q,
        page=page,
        page_size=page_size,
    )


@router.get("/stats")
def get_audit_stats(
    db: Session = Depends(get_db),
    _user: User = Depends(require_permission("audit.view")),
):
    return audit.audit_stats(db)


@router.get("/actions")
def get_audit_actions(
    db: Session = Depends(get_db),
    _user: User = Depends(require_permission("audit.view")),
):
    return {"actions": list_actions(db)}
