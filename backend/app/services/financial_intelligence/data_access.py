"""Read-only platform data access for Financial Intelligence.

 is grounded in *real* platform data. Rather than duplicate query logic
this module re-exports the read layer (:mod:`autonomous.data_access`)
which normalizes :class:`EnterpriseAssessment` rows into profile dicts, and adds
a couple of Track-3-specific conveniences (exposure/PD extraction with sane
fallbacks). Every helper tolerates a missing table / empty DB.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from backend.app.services.autonomous.data_access import (  # noqa: F401 (re-export)
    all_assessments, get_assessment, latest_assessment_for_company,
    latest_per_company, portfolio_profiles, profile, resolve,
)
from .common import pd_from_score, to_float


def exposure_of(prof: Dict[str, Any], default: float = 1_000_000.0) -> float:
    """Best-effort exposure (EAD) for a company profile."""
    exp = prof.get("exposure")
    if exp:
        return to_float(exp, default)
    ei = prof.get("engine_input") or {}
    for k in ("exposure", "loan_amount", "outstanding", "revenue", "total_assets"):
        if ei.get(k):
            return to_float(ei[k], default)
    return default


def pd_of(prof: Dict[str, Any]) -> float:
    pd = prof.get("pd")
    if pd is not None:
        return to_float(pd, 0.05)
    return pd_from_score(prof.get("credit_score"))


def lgd_of(prof: Dict[str, Any], default: float = 0.45) -> float:
    lgd = prof.get("lgd")
    return to_float(lgd, default) if lgd is not None else default


def portfolio_exposures(db: Session) -> List[Dict[str, Any]]:
    """Compact per-company exposure rows: ref, industry, country, ead, pd, lgd, rating."""
    out: List[Dict[str, Any]] = []
    for prof in portfolio_profiles(db):
        if not prof:
            continue
        out.append({
            "company_ref": prof.get("company_ref"),
            "industry": (prof.get("industry") or "general"),
            "country": (prof.get("country") or "IN"),
            "rating": prof.get("rating"),
            "credit_score": prof.get("credit_score"),
            "ead": exposure_of(prof),
            "pd": pd_of(prof),
            "lgd": lgd_of(prof),
        })
    return out


def company_or_none(db: Session, *, assessment_id: Optional[int] = None,
                    company_ref: Optional[str] = None) -> Optional[Dict[str, Any]]:
    return profile(resolve(db, assessment_id=assessment_id, company_ref=company_ref))
