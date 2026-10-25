"""Tenant-scoped credit review workflow and immutable history."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Optional

from sqlalchemy import func, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, attributes

from backend.app.models.audit import AuditLog
from backend.app.models.company import Company, CompanyFinancials, CreditProfile, PortfolioExposure
from backend.app.models.credit_review import (
    CreditReviewAssessment,
    CreditReviewCase,
    CreditReviewCondition,
    CreditReviewConditionEvent,
    CreditReviewDecision,
)
from backend.app.models.document import Document
from backend.app.models.tenancy import TenantMembership
from backend.app.models.user import User
from backend.app.services.rbac import has_permission


class ReviewError(ValueError):
    """Invalid review request or workflow operation."""


class ReviewConflict(ReviewError):
    """The requested operation conflicts with the current review state."""


class ReviewForbidden(ReviewError):
    """The actor is not permitted to perform this review operation."""


class ReviewNotFound(ReviewError):
    """A tenant-scoped review or linked record does not exist."""


ALLOWED_TRANSITIONS = {
    "draft": {"in_review"},
    "in_review": {"pending_approval"},
    "pending_approval": {
        "approved",
        "declined",
        "deferred",
        "returned_for_revision",
    },
    "returned_for_revision": {"in_review"},
    "deferred": {"in_review"},
    "approved": {"in_review"},
    "declined": {"in_review"},
}

RECOMMENDATIONS = {
    "recommend_approval",
    "recommend_approval_with_conditions",
    "recommend_decline",
    "request_information",
    "escalate",
}
FINAL_STATUSES = {"approved", "declined"}


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _audit(
    db: Session,
    case: CreditReviewCase,
    actor: User,
    action: str,
    *,
    previous: Any = None,
    current: Any = None,
    reason: Optional[str] = None,
) -> None:
    db.add(
        AuditLog(
            user_id=actor.id,
            user_email=actor.email,
            timestamp=_now(),
            action=f"credit_review.{action}",
            entity_type="credit_review_case",
            entity_id=case.id,
            previous_value=previous,
            new_value=current,
            reason=reason,
            status="success",
            meta={"tenant_id": case.tenant_id, "case_reference": case.reference},
        )
    )


def _company(db: Session, tenant_id: int, company_id: int) -> Company:
    company = (
        db.query(Company)
        .filter(Company.id == company_id, Company.tenant_id == tenant_id)
        .first()
    )
    if company is None:
        raise ReviewNotFound("Company not found.")
    return company


def _member(db: Session, tenant_id: int, user_id: int) -> User:
    membership = (
        db.query(TenantMembership.id)
        .filter(
            TenantMembership.tenant_id == tenant_id,
            TenantMembership.user_id == user_id,
            TenantMembership.status == "active",
        )
        .first()
    )
    user = db.query(User).filter(User.id == user_id).first() if membership else None
    if user is None:
        raise ReviewNotFound("User is not an active member of this tenant.")
    return user


def _approved_financial_rows(
    db: Session, tenant_id: int, company_id: int
) -> list[tuple[CompanyFinancials, Document]]:
    return (
        db.query(CompanyFinancials, Document)
        .join(Document, Document.id == CompanyFinancials.source_document_id)
        .filter(
            CompanyFinancials.tenant_id == tenant_id,
            CompanyFinancials.company_id == company_id,
            Document.tenant_id == tenant_id,
            Document.company_id == company_id,
            Document.status == "approved",
        )
        .order_by(CompanyFinancials.fiscal_year.desc(), CompanyFinancials.id.desc())
        .all()
    )


def _case(db: Session, tenant_id: int, case_id: int) -> CreditReviewCase:
    case = (
        db.query(CreditReviewCase)
        .filter(CreditReviewCase.id == case_id, CreditReviewCase.tenant_id == tenant_id)
        .first()
    )
    if case is None:
        raise ReviewNotFound("Credit review case not found.")
    return case


def _latest_assessment(db: Session, case_id: int) -> Optional[CreditReviewAssessment]:
    return (
        db.query(CreditReviewAssessment)
        .filter(CreditReviewAssessment.case_id == case_id)
        .order_by(CreditReviewAssessment.version.desc())
        .first()
    )


def _latest_decision(db: Session, case_id: int) -> Optional[CreditReviewDecision]:
    return (
        db.query(CreditReviewDecision)
        .filter(CreditReviewDecision.case_id == case_id)
        .order_by(CreditReviewDecision.created_at.desc(), CreditReviewDecision.id.desc())
        .first()
    )


def _transition(
    db: Session,
    case: CreditReviewCase,
    target: str,
    actor: User,
    *,
    reason: str,
    increment_cycle: bool = False,
) -> None:
    if target not in ALLOWED_TRANSITIONS.get(case.status, set()):
        raise ReviewConflict(f"Cannot move a case from {case.status} to {target}.")
    previous = case.status
    values: dict[str, Any] = {
        "status": target,
        "revision": case.revision + 1,
        "updated_at": _now(),
    }
    if increment_cycle:
        values["cycle_number"] = case.cycle_number + 1
    result = db.execute(
        update(CreditReviewCase)
        .where(
            CreditReviewCase.id == case.id,
            CreditReviewCase.tenant_id == case.tenant_id,
            CreditReviewCase.status == previous,
            CreditReviewCase.revision == case.revision,
        )
        .values(**values)
    )
    if result.rowcount != 1:
        raise ReviewConflict("The case changed concurrently; reload and retry.")
    attributes.set_committed_value(case, "status", target)
    attributes.set_committed_value(case, "revision", case.revision + 1)
    attributes.set_committed_value(case, "updated_at", _now())
    if increment_cycle:
        attributes.set_committed_value(case, "cycle_number", case.cycle_number + 1)
    _audit(
        db,
        case,
        actor,
        "transition",
        previous={"status": previous},
        current={"status": target},
        reason=reason,
    )


def create_case(
    db: Session,
    tenant_id: int,
    actor: User,
    *,
    company_id: int,
    review_type: str,
    title: str,
    purpose: Optional[str],
    due_date: Any,
) -> CreditReviewCase:
    if not title.strip():
        raise ReviewError("A case title is required.")
    company = _company(db, tenant_id, company_id)
    financials = _approved_financial_rows(db, tenant_id, company.id)
    periods = sorted({record.fiscal_year for record, _ in financials})
    case = CreditReviewCase(
        tenant_id=tenant_id,
        company_id=company.id,
        review_type=review_type,
        title=title.strip(),
        purpose=purpose.strip() if purpose else None,
        status="draft",
        analyst_id=actor.id,
        created_by=actor.id,
        due_date=due_date,
        reporting_periods=periods,
        financial_record_ids=[record.id for record, _ in financials],
    )
    db.add(case)
    try:
        db.flush()
        _audit(
            db,
            case,
            actor,
            "created",
            current={"company_id": company.id, "status": case.status, "review_type": review_type},
        )
        db.commit()
        db.refresh(case)
        return case
    except IntegrityError as exc:
        db.rollback()
        raise ReviewConflict("Could not create the review case; retry the request.") from exc
    except Exception:
        db.rollback()
        raise


def list_companies(db: Session, tenant_id: int) -> list[Company]:
    return db.query(Company).filter(Company.tenant_id == tenant_id).order_by(Company.name).all()


def list_cases(
    db: Session,
    tenant_id: int,
    *,
    status: Optional[str] = None,
    review_type: Optional[str] = None,
    company_id: Optional[int] = None,
    assigned_to: Optional[str] = None,
    actor_id: Optional[int] = None,
) -> list[CreditReviewCase]:
    query = db.query(CreditReviewCase).filter(CreditReviewCase.tenant_id == tenant_id)
    if status:
        query = query.filter(CreditReviewCase.status == status)
    if review_type:
        query = query.filter(CreditReviewCase.review_type == review_type)
    if company_id:
        query = query.filter(CreditReviewCase.company_id == company_id)
    if assigned_to == "mine" and actor_id is not None:
        query = query.filter(
            (CreditReviewCase.analyst_id == actor_id) | (CreditReviewCase.reviewer_id == actor_id)
        )
    return query.order_by(CreditReviewCase.updated_at.desc(), CreditReviewCase.id.desc()).all()


def dashboard_counts(db: Session, tenant_id: int) -> dict[str, int]:
    counts = dict(
        db.query(CreditReviewCase.status, func.count(CreditReviewCase.id))
        .filter(CreditReviewCase.tenant_id == tenant_id)
        .group_by(CreditReviewCase.status)
        .all()
    )
    return {
        "draft": counts.get("draft", 0),
        "in_review": counts.get("in_review", 0),
        "pending_approval": counts.get("pending_approval", 0),
        "approved": counts.get("approved", 0),
        "declined": counts.get("declined", 0),
        "deferred_or_returned": counts.get("deferred", 0)
        + counts.get("returned_for_revision", 0),
    }


def assign_case(
    db: Session,
    tenant_id: int,
    case_id: int,
    actor: User,
    *,
    analyst_id: int,
    reviewer_id: Optional[int],
) -> CreditReviewCase:
    case = _case(db, tenant_id, case_id)
    if case.status in FINAL_STATUSES:
        raise ReviewConflict("A finalized case cannot be reassigned; reopen it first.")
    analyst = _member(db, tenant_id, analyst_id)
    reviewer = _member(db, tenant_id, reviewer_id) if reviewer_id is not None else None
    if reviewer is not None and analyst.id == reviewer.id:
        raise ReviewConflict("The analyst and reviewer must be different users.")
    if not has_permission(db, analyst, "credit_reviews.assess"):
        raise ReviewError("The assigned analyst must have assessment permission.")
    if reviewer is not None and not has_permission(db, reviewer, "credit_reviews.decide"):
        raise ReviewError("The assigned reviewer must have decision permission.")
    previous = {"analyst_id": case.analyst_id, "reviewer_id": case.reviewer_id}
    current = {"analyst_id": analyst.id, "reviewer_id": reviewer.id if reviewer else None}
    updated_at = _now()
    result = db.execute(
        update(CreditReviewCase)
        .where(
            CreditReviewCase.id == case.id,
            CreditReviewCase.tenant_id == case.tenant_id,
            CreditReviewCase.status == case.status,
            CreditReviewCase.revision == case.revision,
        )
        .values(
            analyst_id=analyst.id,
            reviewer_id=reviewer.id if reviewer else None,
            revision=case.revision + 1,
            updated_at=updated_at,
        )
    )
    if result.rowcount != 1:
        db.rollback()
        raise ReviewConflict("The case changed concurrently; reload and retry.")
    attributes.set_committed_value(case, "analyst_id", analyst.id)
    attributes.set_committed_value(case, "reviewer_id", reviewer.id if reviewer else None)
    attributes.set_committed_value(case, "revision", case.revision + 1)
    attributes.set_committed_value(case, "updated_at", updated_at)
    _audit(
        db,
        case,
        actor,
        "assignment",
        previous=previous,
        current={"analyst_id": analyst.id, "reviewer_id": reviewer.id if reviewer else None},
    )
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(case)
    return case


def _validated_evidence(
    db: Session,
    case: CreditReviewCase,
    financial_ids: list[int],
    document_ids: list[int],
) -> dict[str, list[int]]:
    rows = _approved_financial_rows(db, case.tenant_id, case.company_id)
    available_financials = {
        record.id: document.id for record, document in rows if record.id in (case.financial_record_ids or [])
    }
    if set(financial_ids) - set(available_financials):
        raise ReviewNotFound("One or more financial evidence records are unavailable.")
    available_documents = {
        document.id
        for record, document in rows
        if record.id in (case.financial_record_ids or [])
    }
    if set(document_ids) - available_documents:
        raise ReviewNotFound("One or more document evidence records are unavailable.")
    selected_financials = financial_ids or list(available_financials)
    selected_documents = document_ids or sorted(
        {available_financials[item] for item in selected_financials if item in available_financials}
    )
    return {
        "financial_ids": sorted(set(selected_financials)),
        "document_ids": sorted(set(selected_documents)),
    }


def save_assessment(
    db: Session,
    tenant_id: int,
    case_id: int,
    actor: User,
    payload: dict[str, Any],
) -> CreditReviewAssessment:
    case = _case(db, tenant_id, case_id)
    if case.status not in {"draft", "in_review", "returned_for_revision"}:
        raise ReviewConflict("Assessments cannot be changed in the current case status.")
    if case.analyst_id != actor.id:
        raise ReviewForbidden("Only the assigned analyst can author this assessment.")
    if payload.get("submit"):
        if not payload.get("summary", "").strip():
            raise ReviewError("An assessment summary is required before submission.")
        if not payload.get("recommendation_rationale", "").strip():
            raise ReviewError("A recommendation rationale is required before submission.")
        if payload.get("recommendation") not in RECOMMENDATIONS:
            raise ReviewError("Select a valid recommendation before submission.")
    evidence = _validated_evidence(
        db,
        case,
        payload.get("evidence_refs", {}).get("financial_ids", []),
        payload.get("evidence_refs", {}).get("document_ids", []),
    )
    latest = _latest_assessment(db, case.id)
    assessment = CreditReviewAssessment(
        case_id=case.id,
        version=(latest.version + 1) if latest else 1,
        summary=payload.get("summary", "").strip(),
        strengths=payload.get("strengths", []),
        weaknesses=payload.get("weaknesses", []),
        risk_indicators=payload.get("risk_indicators", []),
        data_quality_concerns=payload.get("data_quality_concerns", []),
        mitigations=payload.get("mitigations", []),
        outstanding_questions=payload.get("outstanding_questions", []),
        evidence_refs=evidence,
        recommendation=payload.get("recommendation", "request_information"),
        recommendation_rationale=payload.get("recommendation_rationale", "").strip(),
        author_id=actor.id,
        submitted_at=_now() if payload.get("submit") else None,
    )
    db.add(assessment)
    try:
        db.flush()
        if payload.get("submit") and case.status != "in_review":
            _transition(
                db,
                case,
                "in_review",
                actor,
                reason="Assessment and recommendation submitted by analyst",
            )
        case.revision += 1
        case.updated_at = _now()
        _audit(
            db,
            case,
            actor,
            "assessment_submitted" if payload.get("submit") else "assessment_drafted",
            current={"assessment_id": assessment.id, "version": assessment.version},
        )
        db.commit()
        db.refresh(assessment)
        return assessment
    except IntegrityError as exc:
        db.rollback()
        raise ReviewConflict("The assessment changed concurrently; reload and retry.") from exc
    except Exception:
        db.rollback()
        raise


def submit_for_approval(
    db: Session, tenant_id: int, case_id: int, actor: User
) -> CreditReviewCase:
    case = _case(db, tenant_id, case_id)
    if case.analyst_id != actor.id:
        raise ReviewForbidden("Only the assigned analyst can submit this case for approval.")
    assessment = _latest_assessment(db, case.id)
    if assessment is None or assessment.submitted_at is None:
        raise ReviewError("Submit a complete assessment before requesting approval.")
    _transition(
        db, case, "pending_approval", actor, reason="Submitted to the approval queue"
    )
    try:
        db.commit()
        db.refresh(case)
        return case
    except Exception:
        db.rollback()
        raise


def decide(
    db: Session,
    tenant_id: int,
    case_id: int,
    actor: User,
    *,
    outcome: str,
    rationale: str,
    conditions: list[dict[str, Any]],
) -> CreditReviewDecision:
    case = _case(db, tenant_id, case_id)
    if case.status != "pending_approval":
        raise ReviewConflict("Only cases pending approval can receive a decision.")
    if case.analyst_id == actor.id:
        raise ReviewForbidden("An analyst cannot make the final decision on their own case.")
    if case.reviewer_id is not None and case.reviewer_id != actor.id:
        raise ReviewForbidden("Only the assigned reviewer can make the final decision.")
    if not rationale.strip():
        raise ReviewError("A decision rationale is required.")
    if outcome == "approved_with_conditions" and not conditions:
        raise ReviewError("At least one condition is required for conditional approval.")
    if outcome != "approved_with_conditions" and conditions:
        raise ReviewError("Conditions are only valid for conditional approval.")

    assessment = _latest_assessment(db, case.id)
    if assessment is None or assessment.submitted_at is None:
        raise ReviewError("A submitted assessment is required before a final decision.")
    latest = _latest_decision(db, case.id)
    target = {
        "approved": "approved",
        "approved_with_conditions": "approved",
        "declined": "declined",
        "deferred": "deferred",
        "returned_for_revision": "returned_for_revision",
    }.get(outcome)
    if target is None:
        raise ReviewError("Unknown decision outcome.")

    decision = CreditReviewDecision(
        case_id=case.id,
        assessment_id=assessment.id,
        previous_decision_id=latest.id if latest else None,
        outcome=outcome,
        cycle_number=case.cycle_number,
        rationale=rationale.strip(),
        conditions_snapshot=[dict(item) for item in conditions],
        evidence_refs=assessment.evidence_refs,
        reporting_periods=case.reporting_periods,
        policy_version=None,
        actor_id=actor.id,
        created_at=_now(),
    )
    db.add(decision)
    try:
        db.flush()
        for item in conditions:
            if item.get("responsible_user_id") is not None:
                _member(db, tenant_id, item["responsible_user_id"])
            condition = CreditReviewCondition(
                case_id=case.id,
                decision_id=decision.id,
                description=item["description"].strip(),
                responsible_user_id=item.get("responsible_user_id"),
                due_date=item.get("due_date"),
                status="open",
                created_by=actor.id,
            )
            db.add(condition)
            db.flush()
            db.add(
                CreditReviewConditionEvent(
                    condition_id=condition.id,
                    actor_id=actor.id,
                    action="created",
                    previous_value=None,
                    new_value={"status": "open", "description": condition.description},
                    created_at=_now(),
                )
            )
        _transition(db, case, target, actor, reason=f"Decision: {outcome}. {rationale.strip()}")
        _audit(
            db,
            case,
            actor,
            "decision",
            current={
                "decision_id": decision.id,
                "outcome": outcome,
                "assessment_id": assessment.id,
                "status": target,
            },
            reason=rationale.strip(),
        )
        db.commit()
        db.refresh(decision)
        return decision
    except IntegrityError as exc:
        db.rollback()
        raise ReviewConflict("A concurrent decision was recorded; reload the case.") from exc
    except Exception:
        db.rollback()
        raise


def resume_case(
    db: Session,
    tenant_id: int,
    case_id: int,
    actor: User,
    *,
    reason: str,
) -> CreditReviewCase:
    case = _case(db, tenant_id, case_id)
    if case.status not in {"deferred", "returned_for_revision"}:
        raise ReviewConflict("Only deferred or returned cases can resume.")
    if case.analyst_id != actor.id:
        raise ReviewForbidden("Only the assigned analyst can resume this case.")
    _transition(db, case, "in_review", actor, reason=reason.strip())
    db.commit()
    db.refresh(case)
    return case


def reopen_case(
    db: Session,
    tenant_id: int,
    case_id: int,
    actor: User,
    *,
    reason: str,
) -> CreditReviewCase:
    case = _case(db, tenant_id, case_id)
    if case.status not in FINAL_STATUSES:
        raise ReviewConflict("Only a finalized case can be reopened.")
    previous_decision = _latest_decision(db, case.id)
    _transition(
        db,
        case,
        "in_review",
        actor,
        reason=f"Reopened: {reason.strip()}",
        increment_cycle=True,
    )
    _audit(
        db,
        case,
        actor,
        "reopened",
        previous={"decision_id": previous_decision.id if previous_decision else None},
        current={"status": "in_review", "cycle_number": case.cycle_number},
        reason=reason.strip(),
    )
    db.commit()
    db.refresh(case)
    return case


def update_condition(
    db: Session,
    tenant_id: int,
    case_id: int,
    condition_id: int,
    actor: User,
    *,
    status: str,
    notes: str,
) -> CreditReviewCondition:
    case = _case(db, tenant_id, case_id)
    condition = (
        db.query(CreditReviewCondition)
        .filter(
            CreditReviewCondition.id == condition_id,
            CreditReviewCondition.case_id == case.id,
        )
        .first()
    )
    if condition is None:
        raise ReviewNotFound("Condition not found.")
    if condition.status != "open":
        raise ReviewConflict("A completed or waived condition cannot be changed.")
    if status not in {"completed", "waived"}:
        raise ReviewError("Condition status must be completed or waived.")
    if not notes.strip():
        raise ReviewError("Completion evidence or a waiver reason is required.")
    previous = {"status": condition.status, "completion_notes": condition.completion_notes}
    updated_at = _now()
    result = db.execute(
        update(CreditReviewCondition)
        .where(
            CreditReviewCondition.id == condition.id,
            CreditReviewCondition.case_id == case.id,
            CreditReviewCondition.status == "open",
        )
        .values(status=status, completion_notes=notes.strip(), updated_at=updated_at)
    )
    if result.rowcount != 1:
        db.rollback()
        raise ReviewConflict("The condition changed concurrently; reload and retry.")
    attributes.set_committed_value(condition, "status", status)
    attributes.set_committed_value(condition, "completion_notes", notes.strip())
    attributes.set_committed_value(condition, "updated_at", updated_at)
    db.add(
        CreditReviewConditionEvent(
            condition_id=condition.id,
            actor_id=actor.id,
            action=status,
            previous_value=previous,
            new_value={"status": status, "completion_notes": condition.completion_notes},
            reason=notes.strip() if status == "waived" else None,
            created_at=_now(),
        )
    )
    _audit(
        db,
        case,
        actor,
        f"condition_{status}",
        previous={"condition_id": condition.id, **previous},
        current={
            "condition_id": condition.id,
            "status": status,
            "completion_notes": condition.completion_notes,
        },
        reason=notes.strip(),
    )
    db.commit()
    db.refresh(condition)
    return condition


def _serialize_assessment(row: CreditReviewAssessment) -> dict[str, Any]:
    return {
        "id": row.id,
        "version": row.version,
        "summary": row.summary,
        "strengths": row.strengths,
        "weaknesses": row.weaknesses,
        "risk_indicators": row.risk_indicators,
        "data_quality_concerns": row.data_quality_concerns,
        "mitigations": row.mitigations,
        "outstanding_questions": row.outstanding_questions,
        "evidence_refs": row.evidence_refs,
        "recommendation": row.recommendation,
        "recommendation_rationale": row.recommendation_rationale,
        "author_id": row.author_id,
        "submitted_at": row.submitted_at.isoformat() if row.submitted_at else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def _serialize_decision(row: CreditReviewDecision) -> dict[str, Any]:
    return {
        "id": row.id,
        "assessment_id": row.assessment_id,
        "previous_decision_id": row.previous_decision_id,
        "outcome": row.outcome,
        "cycle_number": row.cycle_number,
        "rationale": row.rationale,
        "conditions": row.conditions_snapshot,
        "evidence_refs": row.evidence_refs,
        "reporting_periods": row.reporting_periods,
        "policy_version": row.policy_version,
        "actor_id": row.actor_id,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def case_detail(db: Session, tenant_id: int, case_id: int) -> dict[str, Any]:
    case = _case(db, tenant_id, case_id)
    company = _company(db, tenant_id, case.company_id)
    approved_rows = _approved_financial_rows(db, tenant_id, company.id)
    included = set(case.financial_record_ids or [])
    financial_rows = [
        (financial, document)
        for financial, document in approved_rows
        if financial.id in included
    ]
    assessments = (
        db.query(CreditReviewAssessment)
        .filter(CreditReviewAssessment.case_id == case.id)
        .order_by(CreditReviewAssessment.version.asc())
        .all()
    )
    decisions = (
        db.query(CreditReviewDecision)
        .filter(CreditReviewDecision.case_id == case.id)
        .order_by(CreditReviewDecision.created_at.asc(), CreditReviewDecision.id.asc())
        .all()
    )
    conditions = (
        db.query(CreditReviewCondition)
        .filter(CreditReviewCondition.case_id == case.id)
        .order_by(CreditReviewCondition.created_at.asc(), CreditReviewCondition.id.asc())
        .all()
    )
    condition_events = (
        db.query(CreditReviewConditionEvent)
        .join(CreditReviewCondition, CreditReviewCondition.id == CreditReviewConditionEvent.condition_id)
        .filter(CreditReviewCondition.case_id == case.id)
        .order_by(CreditReviewConditionEvent.created_at.asc(), CreditReviewConditionEvent.id.asc())
        .all()
    )
    audit_rows = (
        db.query(AuditLog)
        .filter(
            AuditLog.entity_type == "credit_review_case",
            AuditLog.entity_id == case.id,
            AuditLog.action.like("credit_review.%"),
        )
        .order_by(AuditLog.timestamp.asc(), AuditLog.id.asc())
        .all()
    )
    profile = db.query(CreditProfile).filter(
        CreditProfile.tenant_id == tenant_id, CreditProfile.company_id == company.id
    ).first()
    exposure = db.query(PortfolioExposure).filter(
        PortfolioExposure.tenant_id == tenant_id, PortfolioExposure.company_id == company.id
    ).first()
    warnings = []
    if not financial_rows:
        warnings.append("No approved financial statements are linked to this review.")
    if len(financial_rows) < len(included):
        warnings.append("Some linked financial sources are no longer available as approved evidence.")

    return {
        "id": case.id,
        "reference": case.reference,
        "tenant_id": case.tenant_id,
        "company_name": company.name,
        "company": {
            "id": company.id,
            "name": company.name,
            "industry": company.industry,
            "sector": company.sector,
            "country": company.country,
            "currency": company.currency,
            "is_demo": company.is_demo,
            "data_source": company.data_source,
        },
        "review_type": case.review_type,
        "title": case.title,
        "purpose": case.purpose,
        "status": case.status,
        "cycle_number": case.cycle_number,
        "analyst_id": case.analyst_id,
        "reviewer_id": case.reviewer_id,
        "created_by": case.created_by,
        "due_date": case.due_date.isoformat() if case.due_date else None,
        "reporting_periods": case.reporting_periods,
        "revision": case.revision,
        "created_at": case.created_at.isoformat() if case.created_at else None,
        "updated_at": case.updated_at.isoformat() if case.updated_at else None,
        "financials": [
            {
                "id": financial.id,
                "fiscal_year": financial.fiscal_year,
                "currency": financial.currency,
                "unit": financial.unit,
                "revenue": financial.revenue,
                "ebitda": financial.ebitda,
                "ebit": financial.ebit,
                "net_income": financial.net_income,
                "total_assets": financial.total_assets,
                "total_liabilities": financial.total_liabilities,
                "equity": financial.equity,
                "current_assets": financial.current_assets,
                "current_liabilities": financial.current_liabilities,
                "cash": financial.cash,
                "debt": financial.debt,
                "operating_cash_flow": financial.operating_cash_flow,
                "free_cash_flow": financial.free_cash_flow,
                "approved": True,
                "source_document_id": document.id,
                "source_document_name": document.original_filename,
            }
            for financial, document in financial_rows
        ],
        "risk_profile": (
            {
                "credit_score": profile.credit_score,
                "risk_grade": profile.risk_grade,
                "current_ratio": profile.current_ratio,
                "quick_ratio": profile.quick_ratio,
                "debt_to_equity": profile.debt_to_equity,
                "interest_coverage": profile.interest_coverage,
            }
            if profile
            else None
        ),
        "exposure": (
            {
                "exposure": exposure.exposure,
                "outstanding_amount": exposure.outstanding_amount,
                "utilization": exposure.utilization,
                "delinquency_days": exposure.delinquency_days,
            }
            if exposure
            else None
        ),
        "missing_data_warnings": warnings,
        "assessments": [_serialize_assessment(row) for row in assessments],
        "decisions": [_serialize_decision(row) for row in decisions],
        "conditions": [
            {
                "id": row.id,
                "decision_id": row.decision_id,
                "description": row.description,
                "responsible_user_id": row.responsible_user_id,
                "due_date": row.due_date.isoformat() if row.due_date else None,
                "status": row.status,
                "completion_notes": row.completion_notes,
                "created_by": row.created_by,
                "created_at": row.created_at.isoformat() if row.created_at else None,
                "updated_at": row.updated_at.isoformat() if row.updated_at else None,
            }
            for row in conditions
        ],
        "condition_history": [
            {
                "condition_id": row.condition_id,
                "actor_id": row.actor_id,
                "action": row.action,
                "previous_value": row.previous_value,
                "new_value": row.new_value,
                "reason": row.reason,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
            for row in condition_events
        ],
        "history": [
            {
                "action": row.action,
                "actor_id": row.user_id,
                "actor_email": row.user_email,
                "previous_value": row.previous_value,
                "new_value": row.new_value,
                "reason": row.reason,
                "timestamp": row.timestamp.isoformat() if row.timestamp else None,
            }
            for row in audit_rows
        ],
    }
