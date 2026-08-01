"""Portfolio data access — assessments -> positions.

Reads the current user's enterprise assessments (each a portfolio exposure)
applies optional filters, and maps them into positions for the aggregation
engine. Only the latest assessment per company is counted, so re-assessing a
client updates rather than duplicates its exposure.
"""

from __future__ import annotations

from typing import List, Optional

from sqlalchemy.orm import Session

from backend.app.models.enterprise_assessment import EnterpriseAssessment

from .portfolio_intelligence import Position, position_from_assessment


def positions_for_user(
    db: Session,
    user_id: int,
    *,
    industry: Optional[str] = None,
    rating: Optional[str] = None,
    region: Optional[str] = None,
) -> List[Position]:
    query = db.query(EnterpriseAssessment).filter(EnterpriseAssessment.user_id == user_id)
    if industry:
        query = query.filter(EnterpriseAssessment.industry == industry)
    if rating:
        query = query.filter(EnterpriseAssessment.risk_rating == rating)
    if region:
        query = query.filter(EnterpriseAssessment.country == region)

    records = query.order_by(EnterpriseAssessment.created_at.desc(),
                             EnterpriseAssessment.id.desc()).all()

    # Keep only the most recent assessment per company.
    latest_by_company = {}
    for record in records:
        key = (record.company_name or "").strip().lower() or f"__id_{record.id}"
        if key not in latest_by_company:
            latest_by_company[key] = record

    return [position_from_assessment(r) for r in latest_by_company.values()]
