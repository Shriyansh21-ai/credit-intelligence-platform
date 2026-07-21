"""Enterprise search service over applications.

Combines a free-text query (``q``) across identity fields with structured
filters, ordered by a whitelisted sort field, and returns paginated results plus
facet counts for the common filter dimensions.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.app.models.application import Application
from backend.app.services.lifecycle.service import serialize as serialize_application

# Whitelisted sort columns (guards against arbitrary attribute injection).
SEARCH_SORT_FIELDS = {
    "created_at": Application.created_at,
    "updated_at": Application.updated_at,
    "company_name": Application.company_name,
    "requested_amount": Application.requested_amount,
    "status": Application.status,
    "risk_rating": Application.risk_rating,
}


def _facets(query) -> Dict[str, List[Dict[str, Any]]]:
    """Facet counts for the current (unpaginated) filtered result set."""

    def counts(column):
        rows = (
            query.with_entities(column, func.count(Application.id))
            .group_by(column)
            .all()
        )
        return [{"value": v, "count": c} for v, c in rows if v is not None]

    return {
        "status": counts(Application.status),
        "industry": counts(Application.industry),
        "risk_rating": counts(Application.risk_rating),
        "risk_grade": counts(Application.risk_grade),
    }


def search_applications(
    db: Session,
    *,
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
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    sort_by: str = "updated_at",
    sort_dir: str = "desc",
    page: int = 1,
    page_size: int = 25,
    with_facets: bool = True,
) -> Dict[str, Any]:
    query = db.query(Application)

    if q:
        like = f"%{q}%"
        query = query.filter(
            Application.company_name.like(like)
            | Application.gstin.like(like)
            | Application.pan.like(like)
            | Application.reference.like(like)
            | Application.loan_id.like(like)
        )
    if company:
        query = query.filter(Application.company_name.like(f"%{company}%"))
    if gstin:
        query = query.filter(Application.gstin == gstin)
    if pan:
        query = query.filter(Application.pan == pan)
    if application_id:
        # Match either the human reference or the numeric id.
        if application_id.isdigit():
            query = query.filter(
                (Application.reference == application_id)
                | (Application.id == int(application_id))
            )
        else:
            query = query.filter(Application.reference == application_id)
    if loan_id:
        query = query.filter(Application.loan_id == loan_id)
    if industry:
        query = query.filter(Application.industry == industry)
    if rating:
        query = query.filter(Application.risk_rating == rating)
    if status:
        query = query.filter(Application.status == status)
    if risk_grade:
        query = query.filter(Application.risk_grade == risk_grade)
    if relationship_manager is not None:
        query = query.filter(
            (Application.assigned_to == relationship_manager)
            | (Application.user_id == relationship_manager)
        )
    if date_from is not None:
        query = query.filter(Application.created_at >= date_from)
    if date_to is not None:
        query = query.filter(Application.created_at <= date_to)

    total = query.count()
    facets = _facets(query) if with_facets else {}

    column = SEARCH_SORT_FIELDS.get(sort_by, Application.updated_at)
    column = column.asc() if sort_dir == "asc" else column.desc()

    page = max(1, page)
    page_size = max(1, min(page_size, 200))
    rows = (
        query.order_by(column, Application.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return {
        "items": [serialize_application(a) for a in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": (total + page_size - 1) // page_size,
        "facets": facets,
        "sort": {"by": sort_by, "dir": sort_dir},
    }
