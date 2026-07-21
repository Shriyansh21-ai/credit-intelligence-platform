"""Versioned persistence for risk explanations (Phase 4, Milestone 3)."""

from __future__ import annotations

from typing import List, Mapping, Optional

from sqlalchemy.orm import Session

from backend.app.models.risk_explanation import RiskExplanation


def save_explanation(
    db: Session,
    *,
    user_id: int,
    assessment_id: Optional[int],
    explanation: Mapping,
) -> RiskExplanation:
    """Persist an explanation payload as a new current version, superseding any
    prior current row for the same assessment."""
    version = 1
    if assessment_id is not None:
        current = (
            db.query(RiskExplanation)
            .filter(
                RiskExplanation.assessment_id == assessment_id,
                RiskExplanation.is_current.is_(True),
            )
            .order_by(RiskExplanation.version.desc())
            .first()
        )
        if current is not None:
            version = current.version + 1
            current.is_current = False
            db.add(current)

    record = RiskExplanation(
        user_id=user_id,
        assessment_id=assessment_id,
        version=version,
        is_current=True,
        model_type=explanation.get("model_type", "scorecard"),
        method=explanation.get("method", "contribution"),
        probability_of_default=explanation.get("probability_of_default"),
        base_probability=explanation.get("base_probability"),
        risk_score=explanation.get("risk_score"),
        risk_grade=explanation.get("risk_grade"),
        summary=explanation.get("summary"),
        contributions=explanation.get("contributions", []),
        top_positive=explanation.get("top_positive_contributors", []),
        top_negative=explanation.get("top_negative_contributors", []),
        waterfall=explanation.get("waterfall", []),
        global_importance=explanation.get("global_importance", []),
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def get_current_for_assessment(db: Session, assessment_id: int) -> Optional[RiskExplanation]:
    return (
        db.query(RiskExplanation)
        .filter(
            RiskExplanation.assessment_id == assessment_id,
            RiskExplanation.is_current.is_(True),
        )
        .order_by(RiskExplanation.version.desc())
        .first()
    )


def serialize_record(record: RiskExplanation) -> dict:
    return {
        "id": record.id,
        "assessment_id": record.assessment_id,
        "version": record.version,
        "created_at": str(record.created_at) if record.created_at else None,
        "model_type": record.model_type,
        "method": record.method,
        "probability_of_default": record.probability_of_default,
        "base_probability": record.base_probability,
        "risk_score": record.risk_score,
        "risk_grade": record.risk_grade,
        "summary": record.summary,
        "contributions": record.contributions or [],
        "top_positive_contributors": record.top_positive or [],
        "top_negative_contributors": record.top_negative or [],
        "waterfall": record.waterfall or [],
        "global_importance": record.global_importance or [],
    }
