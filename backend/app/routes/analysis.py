"""Financial Analysis API (Phase 3, Task 8).

    GET  /analysis/{assessment_id}                full analysis (current version)
    GET  /analysis/ratios/{assessment_id}         ratios only
    GET  /analysis/health/{assessment_id}          health scores only
    GET  /analysis/recommendations/{assessment_id} recommendations only
    GET  /analysis/risk-flags/{assessment_id}      risk flags only
    GET  /analysis/{assessment_id}/history         all versions
    POST /analysis/compute                         ad-hoc analysis (optionally persisted)

Analyses are persisted automatically when an enterprise assessment is created
(see ``routes/prediction.enterprise_assessment``); these endpoints read the
stored current version so responses are instant.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.core.dependencies import get_current_user
from backend.app.db.database import get_db
from backend.app.models.financial_analysis import FinancialAnalysis
from backend.app.models.user import User
from backend.app.schemas.analysis import AnalysisComputeRequest
from backend.app.services.financial_analysis import analysis_service, repository

router = APIRouter(prefix="/analysis", tags=["Financial Analysis"])

_NOT_FOUND = (
    "No financial analysis found for this assessment. Analyses are generated "
    "when an assessment is created; older assessments may predate this feature."
)


def _owned_current(db: Session, assessment_id: int, user: User) -> FinancialAnalysis:
    record = repository.get_current_for_assessment(db, assessment_id)
    if record is None or record.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_NOT_FOUND)
    return record


@router.post("/compute")
async def compute_analysis(
    request: AnalysisComputeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if request.document_fields is not None:
        analysis = analysis_service.analyze_document_fields(
            request.document_fields, context=request.context
        )
    else:
        analysis = analysis_service.analyze_mapping(
            request.financials or {}, context=request.context, previous=request.previous
        )

    if request.persist:
        record = repository.save_analysis(
            db,
            user_id=current_user.id,
            assessment_id=request.assessment_id,
            analysis=analysis,
        )
        analysis = {**analysis, "id": record.id, "version": record.version}

    return analysis


@router.get("/latest")
async def get_latest_analysis(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """The user's most recent analysis — the default view for the dashboard."""
    record = repository.latest_for_user(db, current_user.id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No financial analysis yet. Run an enterprise assessment to generate one.",
        )
    return analysis_service.serialize_record(record)


@router.get("/trends")
async def get_trends(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Multi-period trends across the current user's analysed periods."""
    records = repository.periods_for_user(db, current_user.id)
    trends = analysis_service.trends_from_records(records)
    return trends


@router.get("/{assessment_id}")
async def get_analysis(
    assessment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    record = _owned_current(db, assessment_id, current_user)
    return analysis_service.serialize_record(record)


@router.get("/ratios/{assessment_id}")
async def get_ratios(
    assessment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    record = _owned_current(db, assessment_id, current_user)
    return {"assessment_id": assessment_id, "ratios": record.ratios or []}


@router.get("/health/{assessment_id}")
async def get_health(
    assessment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    record = _owned_current(db, assessment_id, current_user)
    return {
        "assessment_id": assessment_id,
        "overall_health": {
            "score": record.overall_health_score,
            "status": record.overall_health_status,
        },
        "health_scores": record.health_scores or {},
    }


@router.get("/recommendations/{assessment_id}")
async def get_recommendations(
    assessment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    record = _owned_current(db, assessment_id, current_user)
    return {"assessment_id": assessment_id, "recommendations": record.recommendations or []}


@router.get("/risk-flags/{assessment_id}")
async def get_risk_flags(
    assessment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    record = _owned_current(db, assessment_id, current_user)
    return {
        "assessment_id": assessment_id,
        "risk_flags": record.risk_flags or [],
        "risk_flag_count": record.risk_flag_count,
        "highest_severity": record.highest_severity,
    }


@router.get("/{assessment_id}/history")
async def get_history(
    assessment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Verify ownership via the current version before returning history.
    _owned_current(db, assessment_id, current_user)
    records = repository.history_for_assessment(db, assessment_id)
    return {
        "assessment_id": assessment_id,
        "versions": [
            {
                "id": r.id,
                "version": r.version,
                "is_current": r.is_current,
                "overall_health_score": r.overall_health_score,
                "risk_flag_count": r.risk_flag_count,
                "created_at": str(r.created_at) if r.created_at else None,
            }
            for r in records
        ],
    }
