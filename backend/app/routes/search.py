"""Enterprise search API (Phase 5, Milestone 12).

    GET /api/search   filterable, sortable, paginated application search + facets
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.app.db.database import get_db
from backend.app.models.user import User
from backend.app.services import search
from backend.app.services.rbac import require_permission

router = APIRouter(prefix="/api/search", tags=["Search"])


def _parse_dt(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


@router.get("")
def enterprise_search(
    q: Optional[str] = None,
    company: Optional[str] = None,
    gstin: Optional[str] = None,
    pan: Optional[str] = None,
    application_id: Optional[str] = None,
    loan_id: Optional[str] = None,
    industry: Optional[str] = None,
    rating: Optional[str] = None,
    status: Optional[str] = None,
    risk_grade: Optional[str] = None,
    relationship_manager: Optional[int] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    sort_by: str = "updated_at",
    sort_dir: str = "desc",
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
    db: Session = Depends(get_db),
    _user: User = Depends(require_permission("search.use")),
):
    return search.search_applications(
        db,
        q=q,
        company=company,
        gstin=gstin,
        pan=pan,
        application_id=application_id,
        loan_id=loan_id,
        industry=industry,
        rating=rating,
        status=status,
        risk_grade=risk_grade,
        relationship_manager=relationship_manager,
        date_from=_parse_dt(date_from),
        date_to=_parse_dt(date_to),
        sort_by=sort_by,
        sort_dir=sort_dir,
        page=page,
        page_size=page_size,
    )
