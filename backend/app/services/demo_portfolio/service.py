"""Tenant-scoped demo-portfolio persistence + read models."""

from __future__ import annotations

from collections import Counter
from typing import Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.app.models.company import (
    Company,
    CompanyFinancials,
    CreditProfile,
    PortfolioExposure,
)
from backend.app.services.providers import DataProvider, get_data_provider

DEFAULT_COMPANY_COUNT = 50
MAX_COMPANY_COUNT = 150


# ===========================================================================
# Write path
# ===========================================================================
def load_demo_portfolio(
    db: Session,
    tenant_id: int,
    *,
    count: int = DEFAULT_COMPANY_COUNT,
    years: int = 3,
    provider: Optional[DataProvider] = None,
) -> Dict[str, object]:
    """Idempotently load a demo portfolio into ``tenant_id``.

    Companies are keyed by ``(tenant_id, external_id)``; a company that already
    exists for the tenant is skipped (never duplicated), so the operation is
    safe to run repeatedly. Returns the real persisted counts.
    """
    if tenant_id is None:
        raise ValueError("tenant_id is required")
    count = max(1, min(int(count), MAX_COMPANY_COUNT))
    provider = provider or get_data_provider()

    existing_ext = {
        row[0]
        for row in db.query(Company.external_id)
        .filter(Company.tenant_id == tenant_id)
        .all()
    }

    companies_loaded = 0
    financial_records_loaded = 0
    credit_profiles_loaded = 0
    portfolio_records_loaded = 0
    skipped_existing = 0

    for record in provider.generate(count, years=years):
        ext = record.profile.external_id
        if ext in existing_ext:
            skipped_existing += 1
            continue

        p = record.profile
        company = Company(
            tenant_id=tenant_id,
            external_id=ext,
            name=p.name,
            legal_name=p.legal_name,
            industry=p.industry,
            sector=p.sector,
            country=p.country,
            region=p.region,
            incorporation_year=p.incorporation_year,
            employee_count=p.employee_count,
            annual_revenue=p.annual_revenue,
            business_status=p.business_status,
            gstin=p.gstin,
            pan=p.pan,
            cin=p.cin,
            is_demo=provider.is_synthetic,
            data_source=provider.name,
        )
        db.add(company)
        db.flush()  # assign company.id
        companies_loaded += 1

        for f in record.financials:
            db.add(
                CompanyFinancials(
                    tenant_id=tenant_id,
                    company_id=company.id,
                    fiscal_year=f.fiscal_year,
                    revenue=f.revenue,
                    ebitda=f.ebitda,
                    ebit=f.ebit,
                    net_income=f.net_income,
                    operating_margin=f.operating_margin,
                    net_margin=f.net_margin,
                    total_assets=f.total_assets,
                    total_liabilities=f.total_liabilities,
                    equity=f.equity,
                    current_assets=f.current_assets,
                    current_liabilities=f.current_liabilities,
                    cash=f.cash,
                    debt=f.debt,
                    working_capital=f.working_capital,
                    operating_cash_flow=f.operating_cash_flow,
                    free_cash_flow=f.free_cash_flow,
                )
            )
            financial_records_loaded += 1

        if record.credit is not None:
            c = record.credit
            db.add(
                CreditProfile(
                    tenant_id=tenant_id,
                    company_id=company.id,
                    credit_score=c.credit_score,
                    probability_of_default=c.probability_of_default,
                    risk_grade=c.risk_grade,
                    expected_loss=c.expected_loss,
                    debt_to_equity=c.debt_to_equity,
                    current_ratio=c.current_ratio,
                    quick_ratio=c.quick_ratio,
                    interest_coverage=c.interest_coverage,
                    dscr=c.dscr,
                    leverage=c.leverage,
                    liquidity_score=c.liquidity_score,
                    requested_loan_amount=c.requested_loan_amount,
                    recommended_loan_amount=c.recommended_loan_amount,
                    interest_rate=c.interest_rate,
                    collateral_value=c.collateral_value,
                    loan_tenure_months=c.loan_tenure_months,
                    repayment_history=c.repayment_history,
                    approval_status=c.approval_status,
                )
            )
            credit_profiles_loaded += 1

        if record.portfolio is not None:
            pf = record.portfolio
            db.add(
                PortfolioExposure(
                    tenant_id=tenant_id,
                    company_id=company.id,
                    exposure=pf.exposure,
                    outstanding_amount=pf.outstanding_amount,
                    utilization=pf.utilization,
                    repayment_performance=pf.repayment_performance,
                    delinquency_days=pf.delinquency_days,
                    is_delinquent=pf.is_delinquent,
                    sector_classification=pf.sector_classification,
                )
            )
            portfolio_records_loaded += 1

        existing_ext.add(ext)

    db.commit()

    already = skipped_existing > 0 and companies_loaded == 0
    return {
        "status": "success",
        "tenant_id": tenant_id,
        "data_source": provider.name,
        "is_demo": provider.is_synthetic,
        "already_loaded": already,
        "companies_loaded": companies_loaded,
        "financial_records_loaded": financial_records_loaded,
        "credit_profiles_loaded": credit_profiles_loaded,
        "portfolio_records_loaded": portfolio_records_loaded,
        "skipped_existing": skipped_existing,
    }


def reset_demo_portfolio(db: Session, tenant_id: int) -> Dict[str, object]:
    """Delete the tenant's demo portfolio (companies + dependent rows)."""
    if tenant_id is None:
        raise ValueError("tenant_id is required")
    company_ids = [
        row[0]
        for row in db.query(Company.id).filter(Company.tenant_id == tenant_id).all()
    ]
    if company_ids:
        # Delete children explicitly (SQLite ignores ON DELETE CASCADE by default).
        for model in (PortfolioExposure, CreditProfile, CompanyFinancials):
            db.query(model).filter(model.company_id.in_(company_ids)).delete(
                synchronize_session=False
            )
        db.query(Company).filter(Company.id.in_(company_ids)).delete(
            synchronize_session=False
        )
        db.commit()
    return {"status": "success", "companies_removed": len(company_ids)}


# ===========================================================================
# Read path (all tenant-scoped)
# ===========================================================================
def portfolio_status(db: Session, tenant_id: int) -> Dict[str, object]:
    total = (
        db.query(func.count(Company.id))
        .filter(Company.tenant_id == tenant_id)
        .scalar()
        or 0
    )
    return {"loaded": total > 0, "companies": int(total)}


def portfolio_summary(db: Session, tenant_id: int) -> Dict[str, object]:
    """Aggregate the tenant's book for dashboard consumption."""
    companies = db.query(Company).filter(Company.tenant_id == tenant_id).all()
    total_companies = len(companies)

    empty = {
        "loaded": False,
        "is_demo": True,
        "total_companies": 0,
        "total_exposure": 0.0,
        "total_outstanding": 0.0,
        "approval_rate": 0.0,
        "approved_count": 0,
        "high_risk_accounts": 0,
        "delinquent_accounts": 0,
        "active_borrowers": 0,
        "average_credit_score": 0,
        "average_pd": 0.0,
        "expected_loss": 0.0,
        "risk_distribution": {},
        "sector_distribution": {},
        "industry_distribution": {},
        "financial_trend": [],
    }
    if total_companies == 0:
        return empty

    credits = (
        db.query(CreditProfile).filter(CreditProfile.tenant_id == tenant_id).all()
    )
    exposures = (
        db.query(PortfolioExposure)
        .filter(PortfolioExposure.tenant_id == tenant_id)
        .all()
    )

    total_exposure = sum(e.exposure or 0.0 for e in exposures)
    total_outstanding = sum(e.outstanding_amount or 0.0 for e in exposures)
    delinquent = sum(1 for e in exposures if e.is_delinquent)

    approved = sum(1 for c in credits if c.approval_status == "approved")
    approval_rate = round(approved * 100 / len(credits), 2) if credits else 0.0
    high_risk = sum(
        1
        for c in credits
        if (c.probability_of_default or 0) >= 0.20
        or c.risk_grade in {"B", "CCC", "D"}
    )
    avg_score = round(sum(c.credit_score or 0 for c in credits) / len(credits)) if credits else 0
    avg_pd = round(sum(c.probability_of_default or 0 for c in credits) / len(credits), 4) if credits else 0.0
    expected_loss = round(sum(c.expected_loss or 0.0 for c in credits), 2)

    risk_distribution = dict(Counter(c.risk_grade for c in credits if c.risk_grade))
    sector_distribution = dict(Counter(c.sector for c in companies if c.sector))
    industry_distribution = dict(Counter(c.industry for c in companies if c.industry))

    # Financial trend: total revenue + net income per fiscal year across the book.
    trend_rows = (
        db.query(
            CompanyFinancials.fiscal_year,
            func.sum(CompanyFinancials.revenue),
            func.sum(CompanyFinancials.net_income),
            func.sum(CompanyFinancials.ebitda),
        )
        .filter(CompanyFinancials.tenant_id == tenant_id)
        .group_by(CompanyFinancials.fiscal_year)
        .order_by(CompanyFinancials.fiscal_year)
        .all()
    )
    financial_trend = [
        {
            "fiscal_year": int(fy),
            "revenue": round(rev or 0.0, 2),
            "net_income": round(ni or 0.0, 2),
            "ebitda": round(eb or 0.0, 2),
        }
        for fy, rev, ni, eb in trend_rows
    ]

    return {
        "loaded": True,
        "is_demo": any(c.is_demo for c in companies),
        "data_source": companies[0].data_source if companies else "demo",
        "total_companies": total_companies,
        "total_exposure": round(total_exposure, 2),
        "total_outstanding": round(total_outstanding, 2),
        "approval_rate": approval_rate,
        "approved_count": approved,
        "high_risk_accounts": high_risk,
        "delinquent_accounts": delinquent,
        "active_borrowers": sum(1 for e in exposures if (e.outstanding_amount or 0) > 0),
        "average_credit_score": avg_score,
        "average_pd": avg_pd,
        "expected_loss": expected_loss,
        "risk_distribution": risk_distribution,
        "sector_distribution": sector_distribution,
        "industry_distribution": industry_distribution,
        "financial_trend": financial_trend,
    }


def list_companies(
    db: Session, tenant_id: int, *, limit: int = 50, offset: int = 0
) -> Dict[str, object]:
    limit = max(1, min(int(limit), 200))
    offset = max(0, int(offset))
    total = (
        db.query(func.count(Company.id))
        .filter(Company.tenant_id == tenant_id)
        .scalar()
        or 0
    )
    rows = (
        db.query(Company)
        .filter(Company.tenant_id == tenant_id)
        .order_by(Company.id)
        .offset(offset)
        .limit(limit)
        .all()
    )
    items: List[Dict[str, object]] = []
    for company in rows:
        credit = company.credit_profile
        exposure = company.exposure
        items.append(
            {
                "id": company.id,
                "external_id": company.external_id,
                "name": company.name,
                "industry": company.industry,
                "sector": company.sector,
                "region": company.region,
                "annual_revenue": company.annual_revenue,
                "employee_count": company.employee_count,
                "is_demo": company.is_demo,
                "credit_score": credit.credit_score if credit else None,
                "risk_grade": credit.risk_grade if credit else None,
                "probability_of_default": credit.probability_of_default if credit else None,
                "approval_status": credit.approval_status if credit else None,
                "exposure": exposure.exposure if exposure else None,
                "outstanding_amount": exposure.outstanding_amount if exposure else None,
                "is_delinquent": exposure.is_delinquent if exposure else None,
            }
        )
    return {"total": int(total), "limit": limit, "offset": offset, "items": items}
