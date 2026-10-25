"""Tenant-scoped credit review, assessment, decision, and condition APIs."""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.app.core.dependencies import get_current_tenant_id
from backend.app.db.database import get_db
from backend.app.models.company import Company
from backend.app.models.tenancy import TenantMembership
from backend.app.models.user import User
from backend.app.schemas.credit_review import (
    AssessmentDraft,
    ConditionUpdate,
    CreditReviewAssignment,
    CreditReviewCreate,
    CreditReviewDecisionRequest,
    ResumeReviewRequest,
)
from backend.app.services.credit_reviews import service as credit_reviews
from backend.app.services.credit_reviews.service import (
    ReviewConflict,
    ReviewError,
    ReviewForbidden,
    ReviewNotFound,
)
from backend.app.services import portfolio_risk
from backend.app.services.rbac import has_permission, require_permission

router = APIRouter(prefix="/api/credit-reviews", tags=["Credit Reviews"])


def _call(operation: Any, *args: Any, **kwargs: Any) -> Any:
    try:
        return operation(*args, **kwargs)
    except ReviewNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ReviewForbidden as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except ReviewConflict as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except ReviewError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc


def _case_summary(db: Session, tenant_id: int, case):
    company = (
        db.query(Company)
        .filter(
            Company.id == case.company_id,
            Company.tenant_id == tenant_id,
        )
        .first()
    )
    return {
        "id": case.id,
        "reference": case.reference,
        "company_id": case.company_id,
        "company_name": company.name if company else None,
        "review_type": case.review_type,
        "title": case.title,
        "status": case.status,
        "analyst_id": case.analyst_id,
        "reviewer_id": case.reviewer_id,
        "due_date": case.due_date.isoformat() if case.due_date else None,
        "reporting_periods": case.reporting_periods,
        "updated_at": case.updated_at.isoformat() if case.updated_at else None,
    }


def _case_detail(db: Session, tenant_id: int, case_id: int, actor: User):
    detail = _call(credit_reviews.case_detail, db, tenant_id, case_id)
    detail["portfolio_risk_evidence"] = _call(
        portfolio_risk.company_review_evidence,
        db,
        tenant_id,
        detail["company"]["id"],
    )
    permissions = {
        name: has_permission(db, actor, f"credit_reviews.{name}")
        for name in ("create", "assess", "assign", "submit", "decide", "conditions", "reopen")
    }
    status_value = detail["status"]
    latest_assessment = detail["assessments"][-1] if detail["assessments"] else None
    detail["actions"] = {
        "can_assess": (
            permissions["assess"]
            and actor.id == detail["analyst_id"]
            and status_value in {"draft", "in_review", "returned_for_revision"}
        ),
        "can_assign": permissions["assign"] and status_value not in {"approved", "declined"},
        "can_submit_for_approval": (
            permissions["submit"]
            and actor.id == detail["analyst_id"]
            and status_value == "in_review"
            and latest_assessment is not None
            and latest_assessment["submitted_at"] is not None
        ),
        "can_decide": (
            permissions["decide"]
            and status_value == "pending_approval"
            and actor.id != detail["analyst_id"]
            and (detail["reviewer_id"] is None or detail["reviewer_id"] == actor.id)
        ),
        "can_resume": permissions["submit"]
        and actor.id == detail["analyst_id"]
        and status_value in {"deferred", "returned_for_revision"},
        "can_reopen": permissions["reopen"] and status_value in {"approved", "declined"},
        "can_manage_conditions": permissions["conditions"],
    }
    return detail


@router.get("/companies")
def companies_for_review(
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    _actor: User = Depends(require_permission("credit_reviews.view")),
):
    return [
        {
            "id": company.id,
            "name": company.name,
            "industry": company.industry,
            "is_demo": company.is_demo,
        }
        for company in credit_reviews.list_companies(db, tenant_id)
    ]


@router.get("/assignment-candidates")
def assignment_candidates(
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    _actor: User = Depends(require_permission("credit_reviews.assign")),
):
    return [
        {
            "id": user.id,
            "name": user.full_name,
            "email": user.email,
            "can_be_analyst": has_permission(db, user, "credit_reviews.assess"),
            "can_be_reviewer": has_permission(db, user, "credit_reviews.decide"),
        }
        for user in (
            db.query(User)
            .join(TenantMembership, TenantMembership.user_id == User.id)
            .filter(
                TenantMembership.tenant_id == tenant_id,
                TenantMembership.status == "active",
            )
            .order_by(User.full_name, User.email)
            .all()
        )
    ]


@router.get("/dashboard")
def review_dashboard(
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    actor: User = Depends(require_permission("credit_reviews.view")),
):
    cases = credit_reviews.list_cases(db, tenant_id, assigned_to="mine", actor_id=actor.id)
    approval_cases = credit_reviews.list_cases(
        db, tenant_id, status="pending_approval"
    )
    can_decide = has_permission(db, actor, "credit_reviews.decide")
    approval_queue = [
        case
        for case in approval_cases
        if can_decide
        and case.analyst_id != actor.id
        and (case.reviewer_id is None or case.reviewer_id == actor.id)
    ]
    return {
        "counts": credit_reviews.dashboard_counts(db, tenant_id),
        "my_cases": [_case_summary(db, tenant_id, case) for case in cases],
        "approval_queue": [_case_summary(db, tenant_id, case) for case in approval_queue],
        "can_create": has_permission(db, actor, "credit_reviews.create"),
    }


@router.get("/cases")
def list_review_cases(
    status_filter: Optional[str] = Query(default=None, alias="status"),
    review_type: Optional[str] = None,
    company_id: Optional[int] = Query(default=None, gt=0),
    assigned_to: Optional[str] = Query(default=None, pattern="^(mine|all)$"),
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    actor: User = Depends(require_permission("credit_reviews.view")),
):
    cases = credit_reviews.list_cases(
        db,
        tenant_id,
        status=status_filter,
        review_type=review_type,
        company_id=company_id,
        assigned_to=assigned_to,
        actor_id=actor.id,
    )
    return {"items": [_case_summary(db, tenant_id, case) for case in cases], "total": len(cases)}


@router.post("/cases", status_code=status.HTTP_201_CREATED)
def create_review_case(
    payload: CreditReviewCreate,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    actor: User = Depends(require_permission("credit_reviews.create")),
):
    case = _call(
        credit_reviews.create_case,
        db,
        tenant_id,
        actor,
        company_id=payload.company_id,
        review_type=payload.review_type,
        title=payload.title,
        purpose=payload.purpose,
        due_date=payload.due_date,
    )
    return _case_detail(db, tenant_id, case.id, actor)


@router.get("/cases/{case_id}")
def get_review_case(
    case_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    actor: User = Depends(require_permission("credit_reviews.view")),
):
    return _case_detail(db, tenant_id, case_id, actor)


@router.patch("/cases/{case_id}/assignment")
def assign_review_case(
    case_id: int,
    payload: CreditReviewAssignment,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    actor: User = Depends(require_permission("credit_reviews.assign")),
):
    _call(
        credit_reviews.assign_case,
        db,
        tenant_id,
        case_id,
        actor,
        analyst_id=payload.analyst_id,
        reviewer_id=payload.reviewer_id,
    )
    return _case_detail(db, tenant_id, case_id, actor)


@router.post("/cases/{case_id}/assessments", status_code=status.HTTP_201_CREATED)
def save_review_assessment(
    case_id: int,
    payload: AssessmentDraft,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    actor: User = Depends(require_permission("credit_reviews.assess")),
):
    _call(
        credit_reviews.save_assessment,
        db,
        tenant_id,
        case_id,
        actor,
        payload.model_dump(),
    )
    return _case_detail(db, tenant_id, case_id, actor)


@router.post("/cases/{case_id}/submit-for-approval")
def submit_review_for_approval(
    case_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    actor: User = Depends(require_permission("credit_reviews.submit")),
):
    _call(credit_reviews.submit_for_approval, db, tenant_id, case_id, actor)
    return _case_detail(db, tenant_id, case_id, actor)


@router.post("/cases/{case_id}/decisions", status_code=status.HTTP_201_CREATED)
def record_review_decision(
    case_id: int,
    payload: CreditReviewDecisionRequest,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    actor: User = Depends(require_permission("credit_reviews.decide")),
):
    _call(
        credit_reviews.decide,
        db,
        tenant_id,
        case_id,
        actor,
        outcome=payload.outcome,
        rationale=payload.rationale,
        conditions=[condition.model_dump() for condition in payload.conditions],
    )
    return _case_detail(db, tenant_id, case_id, actor)


@router.post("/cases/{case_id}/resume")
def resume_review_case(
    case_id: int,
    payload: ResumeReviewRequest,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    actor: User = Depends(require_permission("credit_reviews.submit")),
):
    _call(
        credit_reviews.resume_case,
        db,
        tenant_id,
        case_id,
        actor,
        reason=payload.reason,
    )
    return _case_detail(db, tenant_id, case_id, actor)


@router.post("/cases/{case_id}/reopen")
def reopen_review_case(
    case_id: int,
    payload: ResumeReviewRequest,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    actor: User = Depends(require_permission("credit_reviews.reopen")),
):
    _call(
        credit_reviews.reopen_case,
        db,
        tenant_id,
        case_id,
        actor,
        reason=payload.reason,
    )
    return _case_detail(db, tenant_id, case_id, actor)


@router.patch("/cases/{case_id}/conditions/{condition_id}")
def update_review_condition(
    case_id: int,
    condition_id: int,
    payload: ConditionUpdate,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    actor: User = Depends(require_permission("credit_reviews.conditions")),
):
    _call(
        credit_reviews.update_condition,
        db,
        tenant_id,
        case_id,
        condition_id,
        actor,
        status=payload.status,
        notes=payload.notes,
    )
    return _case_detail(db, tenant_id, case_id, actor)
