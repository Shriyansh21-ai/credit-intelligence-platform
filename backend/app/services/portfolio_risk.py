"""Tenant-scoped exposure limits and company covenant calculations."""

from __future__ import annotations

from datetime import UTC, date, datetime
import hashlib
import json
import math
from typing import Any

from sqlalchemy.orm import Session

from backend.app.models.audit import AuditLog
from backend.app.models.company import (
    Company,
    CompanyFinancials,
    PortfolioExposure,
    PortfolioExposureBreach,
    PortfolioExposureLimit,
    PortfolioExposureLimitEvent,
)
from backend.app.models.covenant import CompanyCovenant, CompanyCovenantEvaluation
from backend.app.models.document import Document


class PortfolioRiskError(ValueError):
    """Invalid portfolio risk configuration or operation."""


class PortfolioRiskNotFound(PortfolioRiskError):
    """A requested record is not visible in the active tenant."""


_COVENANT_METRICS = {
    "current_ratio_min": ("min", "ratio", "Current ratio"),
    "debt_to_equity_max": ("max", "ratio", "Debt to equity"),
    "debt_to_ebitda_max": ("max", "ratio", "Debt to EBITDA"),
}


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _scope_key(
    db: Session,
    tenant_id: int,
    scope: str,
    company_id: int | None,
    sector: str | None,
) -> str:
    if scope == "portfolio":
        if company_id is not None or sector is not None:
            raise PortfolioRiskError("Portfolio limits cannot specify a company or sector.")
        return "*"
    if scope == "company":
        if company_id is None or sector is not None:
            raise PortfolioRiskError("Company limits require only a company_id.")
        company = (
            db.query(Company.id)
            .filter(Company.id == company_id, Company.tenant_id == tenant_id)
            .first()
        )
        if company is None:
            raise PortfolioRiskNotFound("Company not found.")
        return str(company_id)
    if company_id is not None or not sector or sector.strip() != sector:
        raise PortfolioRiskError("Sector limits require a trimmed sector name only.")
    known = (
        db.query(Company.id)
        .filter(Company.tenant_id == tenant_id, Company.sector == sector)
        .first()
    )
    if known is None:
        raise PortfolioRiskNotFound("Sector not found.")
    return sector


def _limit_rows(db: Session, tenant_id: int, limit: PortfolioExposureLimit):
    query = (
        db.query(Company, PortfolioExposure)
        .outerjoin(
            PortfolioExposure,
            (PortfolioExposure.company_id == Company.id)
            & (PortfolioExposure.tenant_id == tenant_id),
        )
        .filter(Company.tenant_id == tenant_id)
    )
    if limit.scope == "company":
        query = query.filter(Company.id == int(limit.scope_key))
    elif limit.scope == "sector":
        query = query.filter(Company.sector == limit.scope_key)
    return [
        (exposure, company)
        for company, exposure in query.order_by(Company.id).all()
    ]


def portfolio_overview(db: Session, tenant_id: int) -> dict[str, Any]:
    rows = (
        db.query(Company, PortfolioExposure)
        .outerjoin(
            PortfolioExposure,
            (PortfolioExposure.company_id == Company.id)
            & (PortfolioExposure.tenant_id == tenant_id),
        )
        .filter(Company.tenant_id == tenant_id)
        .order_by(Company.id)
        .all()
    )
    grouped: dict[str, float] = {}
    unpriced = 0
    no_exposure = 0
    companies_with_exposure = set()
    for company, exposure in rows:
        if (
            exposure is None
            or exposure.exposure is None
            or not math.isfinite(float(exposure.exposure))
            or exposure.exposure < 0
        ):
            no_exposure += 1
            continue
        if not exposure.currency:
            unpriced += 1
            continue
        grouped[exposure.currency] = grouped.get(exposure.currency, 0.0) + float(exposure.exposure)
        if exposure.exposure > 0:
            companies_with_exposure.add(company.id)
    return {
        "tenant_id": tenant_id,
        "company_count": len(rows),
        "companies_with_exposure": len(companies_with_exposure),
        "exposure_by_currency": [
            {"currency": currency, "total_exposure": round(amount, 2)}
            for currency, amount in sorted(grouped.items())
        ],
        "data_quality": {
            "missing_or_invalid_exposure_records": no_exposure,
            "exposure_records_without_currency": unpriced,
        },
    }


def list_companies(db: Session, tenant_id: int, *, limit: int = 100, offset: int = 0):
    rows = (
        db.query(Company)
        .filter(Company.tenant_id == tenant_id)
        .order_by(Company.name, Company.id)
        .offset(max(0, offset))
        .limit(max(1, min(limit, 200)))
        .all()
    )
    return [
        {
            "id": company.id,
            "name": company.name,
            "sector": company.sector,
            "currency": company.currency,
            "is_demo": company.is_demo,
        }
        for company in rows
    ]


def limit_utilization(db: Session, tenant_id: int, limit: PortfolioExposureLimit) -> dict[str, Any]:
    rows = _limit_rows(db, tenant_id, limit)
    if not rows:
        return {
            "calculation_status": "insufficient_data",
            "reason": "No exposure records are available for this limit scope.",
            "eligible_exposure": None,
            "utilization": None,
            "remaining_headroom": None,
            "status": "insufficient_data",
            "company_count": 0,
        }

    invalid_count = sum(
        1
        for exposure, _company in rows
        if exposure is None
        or exposure.exposure is None
        or not math.isfinite(float(exposure.exposure))
        or exposure.exposure < 0
        or exposure.currency != limit.currency
    )
    if invalid_count:
        return {
            "calculation_status": "insufficient_data",
            "reason": (
                f"{invalid_count} exposure record(s) have a missing/negative amount "
                "or currency incompatible with the limit."
            ),
            "eligible_exposure": None,
            "utilization": None,
            "remaining_headroom": None,
            "status": "insufficient_data",
            "company_count": len(rows),
        }

    eligible = sum(float(exposure.exposure) for exposure, _company in rows)
    utilization = eligible / limit.threshold
    if eligible > limit.threshold:
        status = "breached"
    elif limit.approaching_ratio is not None and utilization >= limit.approaching_ratio:
        status = "approaching"
    else:
        status = "within_limit"
    return {
        "calculation_status": "calculated",
        "reason": None,
        "eligible_exposure": round(eligible, 2),
        "utilization": round(utilization, 6),
        "remaining_headroom": round(limit.threshold - eligible, 2),
        "status": status,
        "company_count": len(rows),
        "supporting_exposure_ids": [exposure.id for exposure, _company in rows],
        "supporting_company_ids": [company.id for _exposure, company in rows],
    }


def serialize_limit(
    db: Session, tenant_id: int, limit: PortfolioExposureLimit
) -> dict[str, Any]:
    calculation = limit_utilization(db, tenant_id, limit)
    if not limit.is_active:
        calculation["status"] = "inactive"
    result = {
        "id": limit.id,
        "scope": limit.scope,
        "scope_key": limit.scope_key,
        "currency": limit.currency,
        "threshold": limit.threshold,
        "approaching_ratio": limit.approaching_ratio,
        "is_active": limit.is_active,
        "created_at": limit.created_at.isoformat() if limit.created_at else None,
        **calculation,
    }
    breach = (
        db.query(PortfolioExposureBreach)
        .filter(PortfolioExposureBreach.limit_id == limit.id)
        .first()
    )
    result["breach"] = serialize_breach(breach) if breach else None
    return result


def serialize_breach(breach: PortfolioExposureBreach) -> dict[str, Any]:
    return {
        "id": breach.id,
        "limit_id": breach.limit_id,
        "observed_exposure": breach.observed_exposure,
        "supporting_exposure_ids": breach.supporting_exposure_ids,
        "supporting_company_ids": breach.supporting_company_ids,
        "status": breach.status,
        "first_detected_at": breach.first_detected_at.isoformat(),
        "last_observed_at": breach.last_observed_at.isoformat(),
        "acknowledged_by": breach.acknowledged_by,
        "acknowledged_at": (
            breach.acknowledged_at.isoformat() if breach.acknowledged_at else None
        ),
        "acknowledgement_reason": breach.acknowledgement_reason,
        "resolved_at": breach.resolved_at.isoformat() if breach.resolved_at else None,
    }


def create_limit(
    db: Session,
    tenant_id: int,
    actor_id: int,
    *,
    scope: str,
    company_id: int | None,
    sector: str | None,
    currency: str,
    threshold: float,
    approaching_ratio: float | None,
) -> PortfolioExposureLimit:
    key = _scope_key(db, tenant_id, scope, company_id, sector)
    limit = PortfolioExposureLimit(
        tenant_id=tenant_id,
        scope=scope,
        scope_key=key,
        currency=currency,
        threshold=threshold,
        approaching_ratio=approaching_ratio,
        created_by=actor_id,
    )
    db.add(limit)
    try:
        db.flush()
        db.add(
            PortfolioExposureLimitEvent(
                limit_id=limit.id,
                actor_id=actor_id,
                action="created",
                new_value=(
                    f"scope={scope};scope_key={key};currency={currency};threshold={threshold}"
                ),
            )
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(limit)
    return limit


def update_limit(
    db: Session,
    tenant_id: int,
    actor_id: int,
    limit_id: int,
    *,
    threshold: float | None,
    approaching_ratio: float | None,
    clear_approaching_ratio: bool,
    is_active: bool | None,
    reason: str,
) -> PortfolioExposureLimit:
    limit = (
        db.query(PortfolioExposureLimit)
        .filter(
            PortfolioExposureLimit.id == limit_id,
            PortfolioExposureLimit.tenant_id == tenant_id,
        )
        .first()
    )
    if limit is None:
        raise PortfolioRiskNotFound("Exposure limit not found.")
    previous = (
        f"threshold={limit.threshold};approaching_ratio={limit.approaching_ratio};"
        f"is_active={limit.is_active}"
    )
    changed = False
    if threshold is not None:
        limit.threshold = threshold
        changed = True
    if approaching_ratio is not None:
        limit.approaching_ratio = approaching_ratio
        changed = True
    elif clear_approaching_ratio:
        limit.approaching_ratio = None
        changed = True
    if is_active is not None:
        limit.is_active = is_active
        changed = True
    if not changed:
        raise PortfolioRiskError("At least one limit setting must be updated.")
    new_value = (
        f"threshold={limit.threshold};approaching_ratio={limit.approaching_ratio};"
        f"is_active={limit.is_active}"
    )
    db.add(
        PortfolioExposureLimitEvent(
            limit_id=limit.id,
            actor_id=actor_id,
            action="updated",
            reason=reason,
            previous_value=previous,
            new_value=new_value,
        )
    )
    db.commit()
    db.refresh(limit)
    return limit


def _event(
    db: Session,
    limit_id: int,
    breach_id: int | None,
    actor_id: int | None,
    action: str,
    *,
    reason: str | None = None,
    previous: str | None = None,
    current: str | None = None,
) -> None:
    db.add(
        PortfolioExposureLimitEvent(
            limit_id=limit_id,
            breach_id=breach_id,
            actor_id=actor_id,
            action=action,
            reason=reason,
            previous_value=previous,
            new_value=current,
        )
    )


def evaluate_limits(db: Session, tenant_id: int, actor_id: int) -> list[dict[str, Any]]:
    limits = (
        db.query(PortfolioExposureLimit)
        .filter(
            PortfolioExposureLimit.tenant_id == tenant_id,
            PortfolioExposureLimit.is_active.is_(True),
        )
        .order_by(PortfolioExposureLimit.id)
        .all()
    )
    now = _now()
    results = []
    try:
        for limit in limits:
            calculation = limit_utilization(db, tenant_id, limit)
            if calculation["calculation_status"] != "calculated":
                results.append({"limit_id": limit.id, **calculation})
                continue
            current = (
                db.query(PortfolioExposureBreach)
                .filter(PortfolioExposureBreach.limit_id == limit.id)
                .first()
            )
            over = calculation["status"] == "breached"
            if over:
                if current is None:
                    current = PortfolioExposureBreach(
                        limit_id=limit.id,
                        observed_exposure=calculation["eligible_exposure"],
                        supporting_exposure_ids=calculation["supporting_exposure_ids"],
                        supporting_company_ids=calculation["supporting_company_ids"],
                        status="open",
                        first_detected_at=now,
                        last_observed_at=now,
                    )
                    db.add(current)
                    db.flush()
                    _event(
                        db, limit.id, current.id, actor_id, "detected",
                        current=str(calculation["eligible_exposure"]),
                    )
                else:
                    current.observed_exposure = calculation["eligible_exposure"]
                    current.supporting_exposure_ids = calculation["supporting_exposure_ids"]
                    current.supporting_company_ids = calculation["supporting_company_ids"]
                    current.last_observed_at = now
                    if current.status == "resolved":
                        previous = current.status
                        current.status = "open"
                        current.first_detected_at = now
                        current.acknowledged_by = None
                        current.acknowledged_at = None
                        current.acknowledgement_reason = None
                        current.resolved_at = None
                        _event(
                            db,
                            limit.id,
                            current.id,
                            actor_id,
                            "reopened",
                            previous=previous,
                            current="open",
                        )
            elif current is not None and current.status != "resolved":
                previous = current.status
                current.status = "resolved"
                current.resolved_at = now
                current.last_observed_at = now
                current.observed_exposure = calculation["eligible_exposure"]
                _event(
                    db,
                    limit.id,
                    current.id,
                    actor_id,
                    "resolved",
                    previous=previous,
                    current=str(calculation["eligible_exposure"]),
                )
            results.append(
                {
                    "limit_id": limit.id,
                    **calculation,
                    "breach": serialize_breach(current) if current else None,
                }
            )
        db.commit()
    except Exception:
        db.rollback()
        raise
    return results


def acknowledge_breach(
    db: Session,
    tenant_id: int,
    breach_id: int,
    actor_id: int,
    reason: str,
) -> PortfolioExposureBreach:
    row = (
        db.query(PortfolioExposureBreach)
        .join(PortfolioExposureLimit, PortfolioExposureLimit.id == PortfolioExposureBreach.limit_id)
        .filter(
            PortfolioExposureBreach.id == breach_id,
            PortfolioExposureLimit.tenant_id == tenant_id,
        )
        .first()
    )
    if row is None:
        raise PortfolioRiskNotFound("Exposure breach not found.")
    if row.status == "resolved":
        raise PortfolioRiskError("Resolved breaches cannot be acknowledged.")
    now = _now()
    previous = row.status
    row.status = "acknowledged"
    row.acknowledged_by = actor_id
    row.acknowledged_at = now
    row.acknowledgement_reason = reason
    _event(
        db,
        row.limit_id,
        row.id,
        actor_id,
        "acknowledged",
        reason=reason,
        previous=previous,
        current="acknowledged",
    )
    db.commit()
    db.refresh(row)
    return row


def limit_events(db: Session, tenant_id: int, limit_id: int, limit: int = 100):
    visible = (
        db.query(PortfolioExposureLimit.id)
        .filter(
            PortfolioExposureLimit.id == limit_id,
            PortfolioExposureLimit.tenant_id == tenant_id,
        )
        .first()
    )
    if visible is None:
        raise PortfolioRiskNotFound("Exposure limit not found.")
    return (
        db.query(PortfolioExposureLimitEvent)
        .filter(PortfolioExposureLimitEvent.limit_id == limit_id)
        .order_by(
            PortfolioExposureLimitEvent.created_at.desc(),
            PortfolioExposureLimitEvent.id.desc(),
        )
        .limit(max(1, min(limit, 200)))
        .all()
    )


def _financial_value(metric_key: str, financial: CompanyFinancials | None) -> float | None:
    if financial is None:
        return None
    if metric_key == "current_ratio_min":
        numerator, denominator = financial.current_assets, financial.current_liabilities
    elif metric_key == "debt_to_equity_max":
        numerator, denominator = financial.debt, financial.equity
    else:
        numerator, denominator = financial.debt, financial.ebitda
    if (
        numerator is None
        or denominator is None
        or not math.isfinite(float(numerator))
        or not math.isfinite(float(denominator))
        or numerator < 0
        or denominator <= 0
    ):
        return None
    return round(float(numerator) / float(denominator), 8)


def create_company_covenant(
    db: Session,
    tenant_id: int,
    company_id: int,
    actor_id: int,
    *,
    metric_key: str,
    name: str,
    threshold: float,
    effective_date: date | None,
    review_frequency_months: int | None,
) -> CompanyCovenant:
    company = (
        db.query(Company.id)
        .filter(Company.id == company_id, Company.tenant_id == tenant_id)
        .first()
    )
    if company is None:
        raise PortfolioRiskNotFound("Company not found.")
    operator, unit, _label = _COVENANT_METRICS[metric_key]
    covenant = CompanyCovenant(
        tenant_id=tenant_id,
        company_id=company_id,
        metric_key=metric_key,
        name=name,
        operator=operator,
        threshold=threshold,
        unit=unit,
        effective_date=effective_date,
        review_frequency_months=review_frequency_months,
        created_by=actor_id,
    )
    db.add(covenant)
    db.flush()
    db.add(
        AuditLog(
            user_id=actor_id,
            timestamp=_now(),
            action="portfolio_risk.covenant_created",
            entity_type="company_covenant",
            entity_id=covenant.id,
            new_value={
                "tenant_id": tenant_id,
                "company_id": company_id,
                "metric_key": metric_key,
                "threshold": threshold,
            },
            status="success",
        )
    )
    db.commit()
    db.refresh(covenant)
    return covenant


def update_company_covenant(
    db: Session,
    tenant_id: int,
    covenant_id: int,
    actor_id: int,
    *,
    threshold: float | None,
    is_active: str | None,
    reason: str,
) -> CompanyCovenant:
    covenant = (
        db.query(CompanyCovenant)
        .filter(
            CompanyCovenant.id == covenant_id,
            CompanyCovenant.tenant_id == tenant_id,
        )
        .first()
    )
    if covenant is None:
        raise PortfolioRiskNotFound("Covenant not found.")
    previous = {"threshold": covenant.threshold, "is_active": covenant.is_active}
    if threshold is not None:
        covenant.threshold = threshold
    if is_active is not None:
        covenant.is_active = is_active
    if previous == {"threshold": covenant.threshold, "is_active": covenant.is_active}:
        raise PortfolioRiskError("At least one covenant setting must be updated.")
    db.add(
        AuditLog(
            user_id=actor_id,
            timestamp=_now(),
            action="portfolio_risk.covenant_updated",
            entity_type="company_covenant",
            entity_id=covenant.id,
            previous_value=previous,
            new_value={"threshold": covenant.threshold, "is_active": covenant.is_active},
            reason=reason,
            status="success",
        )
    )
    db.commit()
    db.refresh(covenant)
    return covenant


def evaluate_company_covenant(
    db: Session, tenant_id: int, covenant_id: int
) -> CompanyCovenantEvaluation:
    covenant = (
        db.query(CompanyCovenant)
        .filter(
            CompanyCovenant.id == covenant_id,
            CompanyCovenant.tenant_id == tenant_id,
        )
        .first()
    )
    if covenant is None:
        raise PortfolioRiskNotFound("Covenant not found.")

    evidence_fields = {"evidence_status": "unavailable"}
    if covenant.is_active != "active":
        evidence_key = f"inactive:threshold:{covenant.threshold}"
        value = None
        financial = None
        document = None
        result_status = "inactive"
        evidence_status = "inactive"
        evidence_fields = {"evidence_status": evidence_status}
    elif covenant.effective_date and covenant.effective_date > date.today():
        evidence_key = (
            f"not-due:{covenant.effective_date.isoformat()}:threshold:{covenant.threshold}"
        )
        value = None
        financial = None
        document = None
        result_status = "not_yet_due"
        evidence_status = "not_yet_due"
        evidence_fields = {"evidence_status": evidence_status}
    else:
        row = (
            db.query(CompanyFinancials, Document)
            .join(Document, Document.id == CompanyFinancials.source_document_id)
            .filter(
                CompanyFinancials.tenant_id == tenant_id,
                CompanyFinancials.company_id == covenant.company_id,
                Document.tenant_id == tenant_id,
                Document.company_id == covenant.company_id,
                Document.status == "approved",
            )
            .order_by(CompanyFinancials.fiscal_year.desc(), CompanyFinancials.id.desc())
            .first()
        )
        if row is None:
            evidence_key = f"missing:threshold:{covenant.threshold}"
            value = None
            financial = None
            document = None
            result_status = "insufficient_data"
            evidence_status = "missing_approved_financials"
            evidence_fields = {"evidence_status": evidence_status}
        else:
            financial, document = row
            evidence_fields = {
                "financial_record_id": financial.id,
                "source_document_id": document.id,
                "source_document_extraction_id": financial.source_document_extraction_id,
                "fiscal_year": financial.fiscal_year,
                "metric_key": covenant.metric_key,
                "threshold": covenant.threshold,
                "currency": financial.currency,
                "unit": financial.unit,
                "current_assets": financial.current_assets,
                "current_liabilities": financial.current_liabilities,
                "debt": financial.debt,
                "equity": financial.equity,
                "ebitda": financial.ebitda,
            }
            evidence_key = hashlib.sha256(
                json.dumps(evidence_fields, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest()
            value = _financial_value(covenant.metric_key, financial)
            evidence_status = "approved"
            result_status = (
                "insufficient_data"
                if value is None
                else (
                    "breached"
                    if (
                        (covenant.operator == "min" and value < covenant.threshold)
                        or (covenant.operator == "max" and value > covenant.threshold)
                    )
                    else "compliant"
                )
            )

    existing = (
        db.query(CompanyCovenantEvaluation)
        .filter(
            CompanyCovenantEvaluation.covenant_id == covenant.id,
            CompanyCovenantEvaluation.evidence_key == evidence_key,
        )
        .first()
    )
    if existing is not None:
        return existing

    evaluation = CompanyCovenantEvaluation(
        covenant_id=covenant.id,
        evidence_key=evidence_key,
        financial_record_id=financial.id if financial else None,
        source_document_id=document.id if document else None,
        source_document_extraction_id=(
            financial.source_document_extraction_id if financial else None
        ),
        evidence_snapshot=evidence_fields,
        fiscal_year=financial.fiscal_year if financial else None,
        calculated_value=value,
        threshold=covenant.threshold,
        status=result_status,
        evidence_status=evidence_status,
    )
    db.add(evaluation)
    db.commit()
    db.refresh(evaluation)
    return evaluation


def acknowledge_company_covenant_evaluation(
    db: Session,
    tenant_id: int,
    evaluation_id: int,
    actor_id: int,
    reason: str,
) -> CompanyCovenantEvaluation:
    evaluation = (
        db.query(CompanyCovenantEvaluation)
        .join(CompanyCovenant, CompanyCovenant.id == CompanyCovenantEvaluation.covenant_id)
        .filter(
            CompanyCovenantEvaluation.id == evaluation_id,
            CompanyCovenant.tenant_id == tenant_id,
        )
        .first()
    )
    if evaluation is None:
        raise PortfolioRiskNotFound("Covenant evaluation not found.")
    if evaluation.status != "breached":
        raise PortfolioRiskError("Only breached covenant evaluations can be acknowledged.")
    if evaluation.acknowledged_at is not None:
        raise PortfolioRiskError("Covenant evaluation has already been acknowledged.")
    evaluation.acknowledged_by = actor_id
    evaluation.acknowledged_at = _now()
    evaluation.acknowledgement_reason = reason
    db.add(
        AuditLog(
            user_id=actor_id,
            timestamp=_now(),
            action="portfolio_risk.covenant_evaluation_acknowledged",
            entity_type="company_covenant_evaluation",
            entity_id=evaluation.id,
            new_value={"status": evaluation.status, "reason": reason},
            meta={"tenant_id": tenant_id, "covenant_id": evaluation.covenant_id},
            status="success",
        )
    )
    db.commit()
    db.refresh(evaluation)
    return evaluation


def serialize_company_covenant(
    covenant: CompanyCovenant, evaluations: list[CompanyCovenantEvaluation]
) -> dict[str, Any]:
    return {
        "id": covenant.id,
        "tenant_id": covenant.tenant_id,
        "company_id": covenant.company_id,
        "metric_key": covenant.metric_key,
        "name": covenant.name,
        "operator": covenant.operator,
        "threshold": covenant.threshold,
        "unit": covenant.unit,
        "effective_date": covenant.effective_date.isoformat() if covenant.effective_date else None,
        "review_frequency_months": covenant.review_frequency_months,
        "is_active": covenant.is_active,
        "evaluations": [
            {
                "id": item.id,
                "financial_record_id": item.financial_record_id,
                "source_document_id": item.source_document_id,
                "source_document_extraction_id": item.source_document_extraction_id,
                "evidence_snapshot": item.evidence_snapshot,
                "fiscal_year": item.fiscal_year,
                "calculated_value": item.calculated_value,
                "threshold": item.threshold,
                "status": item.status,
                "evidence_status": item.evidence_status,
                "acknowledged_by": item.acknowledged_by,
                "acknowledged_at": (
                    item.acknowledged_at.isoformat() if item.acknowledged_at else None
                ),
                "acknowledgement_reason": item.acknowledgement_reason,
                "created_at": item.created_at.isoformat(),
            }
            for item in evaluations
        ],
    }


def list_company_covenants(db: Session, tenant_id: int, company_id: int):
    company = (
        db.query(Company.id)
        .filter(Company.id == company_id, Company.tenant_id == tenant_id)
        .first()
    )
    if company is None:
        raise PortfolioRiskNotFound("Company not found.")
    rows = (
        db.query(CompanyCovenant)
        .filter(
            CompanyCovenant.tenant_id == tenant_id,
            CompanyCovenant.company_id == company_id,
        )
        .order_by(CompanyCovenant.id)
        .all()
    )
    return [
        serialize_company_covenant(
            row,
            db.query(CompanyCovenantEvaluation)
            .filter(CompanyCovenantEvaluation.covenant_id == row.id)
            .order_by(
                CompanyCovenantEvaluation.created_at.desc(),
                CompanyCovenantEvaluation.id.desc(),
            )
            .limit(50)
            .all(),
        )
        for row in rows
    ]


def company_review_evidence(db: Session, tenant_id: int, company_id: int) -> dict[str, Any]:
    company = (
        db.query(Company)
        .filter(Company.id == company_id, Company.tenant_id == tenant_id)
        .first()
    )
    if company is None:
        raise PortfolioRiskNotFound("Company not found.")
    limits = (
        db.query(PortfolioExposureLimit)
        .filter(
            PortfolioExposureLimit.tenant_id == tenant_id,
            PortfolioExposureLimit.is_active.is_(True),
        )
        .order_by(PortfolioExposureLimit.id)
        .limit(200)
        .all()
    )
    relevant_limits = [
        limit
        for limit in limits
        if limit.scope == "portfolio"
        or (limit.scope == "company" and limit.scope_key == str(company_id))
        or (limit.scope == "sector" and limit.scope_key == company.sector)
    ]
    covenant_rows = (
        db.query(CompanyCovenant)
        .filter(
            CompanyCovenant.tenant_id == tenant_id,
            CompanyCovenant.company_id == company_id,
            CompanyCovenant.is_active == "active",
        )
        .order_by(CompanyCovenant.id)
        .all()
    )
    return {
        "limits": [
            serialize_limit(db, tenant_id, limit) for limit in relevant_limits
        ],
        "covenants": list_company_covenants(db, tenant_id, company_id),
        "active_covenant_count": len(covenant_rows),
    }
