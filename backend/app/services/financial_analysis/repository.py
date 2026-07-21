"""Persistence for financial analyses (Task 9).

Versioning mirrors ``DocumentExtraction``: saving a new analysis for an
assessment supersedes the previous ``is_current`` row and inserts an
incremented ``version``, so history is preserved and the table can hold several
periods per company for trend analysis. Headline scores are derived from the
serialized analysis payload and promoted to columns for cheap querying.
"""

from __future__ import annotations

from typing import List, Mapping, Optional

from sqlalchemy.orm import Session

from backend.app.models.financial_analysis import FinancialAnalysis

_SEVERITY_RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3}
_HEALTH_KEYS = (
    "liquidity", "profitability", "leverage", "efficiency",
    "cash_flow", "business_stability", "growth",
)


def _highest_severity(flags: List[Mapping]) -> Optional[str]:
    if not flags:
        return None
    return min((f.get("severity", "low") for f in flags), key=lambda s: _SEVERITY_RANK.get(s, 9))


def _health_score(health_scores: Mapping, key: str) -> Optional[int]:
    entry = health_scores.get(key) if isinstance(health_scores, Mapping) else None
    return entry.get("score") if isinstance(entry, Mapping) else None


def save_analysis(
    db: Session,
    *,
    user_id: int,
    assessment_id: Optional[int],
    analysis: Mapping,
) -> FinancialAnalysis:
    """Persist an analysis payload (the dict from ``AnalysisResult.as_dict``)
    as a new current version, superseding any prior current row for the same
    assessment."""
    period = analysis.get("period", {}) or {}
    overall = analysis.get("overall_health", {}) or {}
    health_scores = analysis.get("health_scores", {}) or {}
    risk_flags = analysis.get("risk_flags", []) or []

    version = 1
    if assessment_id is not None:
        current = (
            db.query(FinancialAnalysis)
            .filter(
                FinancialAnalysis.assessment_id == assessment_id,
                FinancialAnalysis.is_current.is_(True),
            )
            .order_by(FinancialAnalysis.version.desc())
            .first()
        )
        if current is not None:
            version = current.version + 1
            current.is_current = False
            db.add(current)

    record = FinancialAnalysis(
        user_id=user_id,
        assessment_id=assessment_id,
        version=version,
        is_current=True,
        period_label=period.get("label"),
        period_type=period.get("period_type", "annual"),
        fiscal_year=period.get("fiscal_year"),
        overall_health_score=overall.get("score"),
        overall_health_status=overall.get("status"),
        liquidity_health=_health_score(health_scores, "liquidity"),
        profitability_health=_health_score(health_scores, "profitability"),
        leverage_health=_health_score(health_scores, "leverage"),
        efficiency_health=_health_score(health_scores, "efficiency"),
        cash_flow_health=_health_score(health_scores, "cash_flow"),
        business_stability_health=_health_score(health_scores, "business_stability"),
        growth_health=_health_score(health_scores, "growth"),
        risk_flag_count=len(risk_flags),
        highest_severity=_highest_severity(risk_flags),
        statement_snapshot=analysis.get("statement", {}),
        ratios=analysis.get("ratios", []),
        health_scores=health_scores,
        insights=analysis.get("insights", []),
        risk_flags=risk_flags,
        recommendations=analysis.get("recommendations", []),
        engine_version=analysis.get("engine_version", "1.0"),
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def get_current_for_assessment(db: Session, assessment_id: int) -> Optional[FinancialAnalysis]:
    return (
        db.query(FinancialAnalysis)
        .filter(
            FinancialAnalysis.assessment_id == assessment_id,
            FinancialAnalysis.is_current.is_(True),
        )
        .order_by(FinancialAnalysis.version.desc())
        .first()
    )


def latest_for_user(db: Session, user_id: int) -> Optional[FinancialAnalysis]:
    """The most recently created current analysis for a user."""
    return (
        db.query(FinancialAnalysis)
        .filter(
            FinancialAnalysis.user_id == user_id,
            FinancialAnalysis.is_current.is_(True),
        )
        .order_by(FinancialAnalysis.created_at.desc(), FinancialAnalysis.id.desc())
        .first()
    )


def get_by_id(db: Session, analysis_id: int) -> Optional[FinancialAnalysis]:
    return db.query(FinancialAnalysis).filter(FinancialAnalysis.id == analysis_id).first()


def history_for_assessment(db: Session, assessment_id: int) -> List[FinancialAnalysis]:
    return (
        db.query(FinancialAnalysis)
        .filter(FinancialAnalysis.assessment_id == assessment_id)
        .order_by(FinancialAnalysis.version.desc())
        .all()
    )


def periods_for_user(db: Session, user_id: int, limit: int = 20) -> List[FinancialAnalysis]:
    """Current analyses for a user, oldest fiscal year first — the input to the
    trend engine when comparing across periods."""
    rows = (
        db.query(FinancialAnalysis)
        .filter(
            FinancialAnalysis.user_id == user_id,
            FinancialAnalysis.is_current.is_(True),
        )
        .order_by(FinancialAnalysis.fiscal_year.asc().nullslast())
        .limit(limit)
        .all()
    )
    return rows
