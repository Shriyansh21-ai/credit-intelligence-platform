"""Tenant-scoped exposure limits and company covenant monitoring."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.core.dependencies import get_current_tenant_id
from backend.app.db.database import get_db
from backend.app.models.company import PortfolioExposureLimit
from backend.app.models.covenant import CompanyCovenantEvaluation
from backend.app.models.user import User
from backend.app.schemas.portfolio_risk import (
    BreachAcknowledge,
    CompanyCovenantCreate,
    CompanyCovenantUpdate,
    CovenantEvaluationAcknowledge,
    ExposureLimitCreate,
    ExposureLimitUpdate,
)
from backend.app.services import portfolio_risk
from backend.app.services.rbac import has_permission, require_permission

router = APIRouter(prefix="/api/portfolio-risk", tags=["Portfolio Risk"])


def _risk_call(operation, *args, **kwargs):
    try:
        return operation(*args, **kwargs)
    except portfolio_risk.PortfolioRiskNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except portfolio_risk.PortfolioRiskError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc


def _event_view(event) -> dict:
    return {
        "id": event.id,
        "breach_id": event.breach_id,
        "actor_id": event.actor_id,
        "action": event.action,
        "reason": event.reason,
        "previous_value": event.previous_value,
        "new_value": event.new_value,
        "created_at": event.created_at.isoformat(),
    }


def _evaluation_view(evaluation: CompanyCovenantEvaluation) -> dict:
    return {
        "id": evaluation.id,
        "financial_record_id": evaluation.financial_record_id,
        "source_document_id": evaluation.source_document_id,
        "source_document_extraction_id": evaluation.source_document_extraction_id,
        "evidence_snapshot": evaluation.evidence_snapshot,
        "fiscal_year": evaluation.fiscal_year,
        "calculated_value": evaluation.calculated_value,
        "threshold": evaluation.threshold,
        "status": evaluation.status,
        "evidence_status": evaluation.evidence_status,
        "acknowledged_by": evaluation.acknowledged_by,
        "acknowledged_at": (
            evaluation.acknowledged_at.isoformat() if evaluation.acknowledged_at else None
        ),
        "acknowledgement_reason": evaluation.acknowledgement_reason,
        "created_at": evaluation.created_at.isoformat(),
    }


@router.get("/overview")
def overview(
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    _user: User = Depends(require_permission("portfolio.view")),
):
    return portfolio_risk.portfolio_overview(db, tenant_id)


@router.get("/companies")
def list_companies(
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    _user: User = Depends(require_permission("portfolio.view")),
):
    return {
        "companies": portfolio_risk.list_companies(
            db, tenant_id, limit=limit, offset=offset
        )
    }


@router.get("/limits")
def list_limits(
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    actor: User = Depends(require_permission("portfolio.view")),
):
    limits = (
        db.query(PortfolioExposureLimit)
        .filter(PortfolioExposureLimit.tenant_id == tenant_id)
        .order_by(PortfolioExposureLimit.id)
        .all()
    )
    return {
        "limits": [portfolio_risk.serialize_limit(db, tenant_id, row) for row in limits],
        "can_manage": has_permission(db, actor, "portfolio.limits.manage"),
    }


@router.post("/limits", status_code=status.HTTP_201_CREATED)
def create_limit(
    payload: ExposureLimitCreate,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    actor: User = Depends(require_permission("portfolio.limits.manage")),
):
    try:
        limit = portfolio_risk.create_limit(
            db,
            tenant_id,
            actor.id,
            scope=payload.scope,
            company_id=payload.company_id,
            sector=payload.sector,
            currency=payload.currency,
            threshold=payload.threshold,
            approaching_ratio=payload.approaching_ratio,
        )
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A limit already exists for this scope and currency.",
        ) from exc
    except portfolio_risk.PortfolioRiskNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except portfolio_risk.PortfolioRiskError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc
    return portfolio_risk.serialize_limit(db, tenant_id, limit)


@router.patch("/limits/{limit_id}")
def update_limit(
    limit_id: int,
    payload: ExposureLimitUpdate,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    actor: User = Depends(require_permission("portfolio.limits.manage")),
):
    result = _risk_call(
        portfolio_risk.update_limit,
        db,
        tenant_id,
        actor.id,
        limit_id,
        threshold=payload.threshold,
        approaching_ratio=payload.approaching_ratio,
        clear_approaching_ratio=payload.clear_approaching_ratio,
        is_active=payload.is_active,
        reason=payload.reason,
    )
    return portfolio_risk.serialize_limit(db, tenant_id, result)


@router.post("/limits/evaluate")
def evaluate_limits(
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    actor: User = Depends(require_permission("portfolio.limits.manage")),
):
    return {"results": portfolio_risk.evaluate_limits(db, tenant_id, actor.id)}


@router.get("/limits/{limit_id}/events")
def get_limit_events(
    limit_id: int,
    limit: int = Query(default=100, ge=1, le=200),
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    _user: User = Depends(require_permission("portfolio.view")),
):
    events = _risk_call(portfolio_risk.limit_events, db, tenant_id, limit_id, limit)
    return {"events": [_event_view(event) for event in events]}


@router.post("/breaches/{breach_id}/acknowledge")
def acknowledge_breach(
    breach_id: int,
    payload: BreachAcknowledge,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    actor: User = Depends(require_permission("portfolio.limits.manage")),
):
    breach = _risk_call(
        portfolio_risk.acknowledge_breach,
        db,
        tenant_id,
        breach_id,
        actor.id,
        payload.reason,
    )
    return portfolio_risk.serialize_breach(breach)


@router.get("/companies/{company_id}/covenants")
def list_company_covenants(
    company_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    actor: User = Depends(require_permission("covenants.view")),
):
    return {
        "covenants": _risk_call(
            portfolio_risk.list_company_covenants, db, tenant_id, company_id
        ),
        "can_manage": has_permission(db, actor, "covenants.manage"),
    }


@router.post(
    "/companies/{company_id}/covenants",
    status_code=status.HTTP_201_CREATED,
)
def create_company_covenant(
    company_id: int,
    payload: CompanyCovenantCreate,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    actor: User = Depends(require_permission("covenants.manage")),
):
    try:
        covenant = portfolio_risk.create_company_covenant(
            db,
            tenant_id,
            company_id,
            actor.id,
            metric_key=payload.metric_key,
            name=payload.name,
            threshold=payload.threshold,
            effective_date=payload.effective_date,
            review_frequency_months=payload.review_frequency_months,
        )
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A covenant with this name and metric already exists.",
        ) from exc
    except portfolio_risk.PortfolioRiskNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return {
        "covenant": portfolio_risk.serialize_company_covenant(covenant, [])
    }


@router.patch("/covenants/{covenant_id}")
def update_company_covenant(
    covenant_id: int,
    payload: CompanyCovenantUpdate,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    actor: User = Depends(require_permission("covenants.manage")),
):
    covenant = _risk_call(
        portfolio_risk.update_company_covenant,
        db,
        tenant_id,
        covenant_id,
        actor.id,
        threshold=payload.threshold,
        is_active=payload.is_active,
        reason=payload.reason,
    )
    return {
        "covenant": portfolio_risk.serialize_company_covenant(covenant, [])
    }


@router.post("/covenants/{covenant_id}/evaluate")
def evaluate_company_covenant(
    covenant_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    _user: User = Depends(require_permission("covenants.manage")),
):
    evaluation = _risk_call(
        portfolio_risk.evaluate_company_covenant,
        db,
        tenant_id,
        covenant_id,
    )
    return {"evaluation": _evaluation_view(evaluation)}


@router.post("/covenant-evaluations/{evaluation_id}/acknowledge")
def acknowledge_company_covenant(
    evaluation_id: int,
    payload: CovenantEvaluationAcknowledge,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    actor: User = Depends(require_permission("covenants.manage")),
):
    evaluation = _risk_call(
        portfolio_risk.acknowledge_company_covenant_evaluation,
        db,
        tenant_id,
        evaluation_id,
        actor.id,
        payload.reason,
    )
    return {"evaluation": _evaluation_view(evaluation)}
