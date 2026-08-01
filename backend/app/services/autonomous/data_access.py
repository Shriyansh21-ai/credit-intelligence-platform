"""Read-only loaders over existing platform tables for the AI Brain.

Every engine is grounded in *real* platform data — this module is the
single, defensive read layer that turns :class:`EnterpriseAssessment` rows (and
their stored ``engine_input``) into normalized profile dicts. Keeping all reads
here means no engine fabricates numbers and there is no duplicated query logic.

All functions tolerate a missing table / empty DB (return ``None`` / ``[]``) so
isolated unit tests and fresh tenants keep working.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from backend.app.models.enterprise_assessment import EnterpriseAssessment
from .common import pd_from_score


def _safe(query_fn, default):
    try:
        return query_fn()
    except Exception:
        return default


def get_assessment(db: Session, assessment_id: int) -> Optional[EnterpriseAssessment]:
    return _safe(lambda: db.query(EnterpriseAssessment)
                 .filter(EnterpriseAssessment.id == assessment_id).first(), None)


def latest_assessment_for_company(db: Session, company_ref: str) -> Optional[EnterpriseAssessment]:
    """Most recent assessment matching a company name (case-insensitive)."""
    def q():
        ref = (company_ref or "").strip().lower()
        rows = (db.query(EnterpriseAssessment)
                .order_by(EnterpriseAssessment.created_at.desc().nullslast()
                          if hasattr(EnterpriseAssessment.created_at, "desc") else EnterpriseAssessment.id.desc())
                .all())
        for r in rows:
            if (r.company_name or "").strip().lower() == ref:
                return r
        return None
    return _safe(q, None)


def all_assessments(db: Session) -> List[EnterpriseAssessment]:
    return _safe(lambda: db.query(EnterpriseAssessment)
                 .order_by(EnterpriseAssessment.id.desc()).all(), [])


def latest_per_company(db: Session) -> List[EnterpriseAssessment]:
    """Latest assessment per distinct company — the portfolio position set."""
    seen: Dict[str, EnterpriseAssessment] = {}
    for a in all_assessments(db):  # already newest-first
        key = (a.company_name or f"#{a.id}").strip().lower()
        if key not in seen:
            seen[key] = a
    return list(seen.values())


def resolve(db: Session, *, assessment_id: Optional[int] = None,
            company_ref: Optional[str] = None) -> Optional[EnterpriseAssessment]:
    """Resolve an assessment by id first, else by latest-for-company."""
    if assessment_id is not None:
        a = get_assessment(db, assessment_id)
        if a is not None:
            return a
    if company_ref:
        return latest_assessment_for_company(db, company_ref)
    return None


def profile(assessment: Optional[EnterpriseAssessment]) -> Optional[Dict[str, Any]]:
    """Normalize an assessment into a flat, defensive profile dict.

    Returns ``None`` when there is no assessment. Never invents missing figures
    unknown fields stay ``None`` (except PD, which is calibrated from the score
    when a stored PD is absent, mirroring the scorecard).
    """
    if assessment is None:
        return None
    a = assessment
    engine = a.engine_input if isinstance(a.engine_input, dict) else {}
    score = a.enterprise_credit_score
    pd = a.probability_of_default
    if pd is None and score is not None:
        pd = pd_from_score(score)
    return {
        "assessment_id": a.id,
        "company_ref": a.company_name,
        "company_name": a.company_name,
        "industry": a.industry,
        "country": getattr(a, "country", None),
        "business_type": getattr(a, "business_type", None),
        "years_in_business": getattr(a, "years_in_business", None),
        "employee_count": getattr(a, "employee_count", None),
        "credit_score": score,
        "pd": pd,
        "lgd": a.loss_given_default,
        "expected_loss": a.expected_loss,
        "rating": a.risk_rating,
        "exposure": a.recommended_loan_amount,
        "interest_rate": getattr(a, "recommended_interest_rate", None),
        "working_capital": getattr(a, "working_capital", None),
        "health": {
            "liquidity": getattr(a, "liquidity_health", None),
            "debt": getattr(a, "debt_health", None),
            "working_capital": getattr(a, "working_capital_health", None),
            "business_stability": getattr(a, "business_stability", None),
        },
        "engine_input": engine,
        "created_at": a.created_at.isoformat() if getattr(a, "created_at", None) else None,
    }


def portfolio_profiles(db: Session) -> List[Dict[str, Any]]:
    """Normalized profiles for the latest assessment per company."""
    return [profile(a) for a in latest_per_company(db) if a is not None]
