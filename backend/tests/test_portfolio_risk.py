from __future__ import annotations

from datetime import date

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.core.dependencies import get_current_tenant_id, get_current_user
from backend.app.db.database import get_db
from backend.app.models.company import (
    Company,
    CompanyFinancials,
    PortfolioExposure,
    PortfolioExposureBreach,
    PortfolioExposureLimitEvent,
)
from backend.app.models.document import Document
from backend.app.models.tenancy import Organization, Tenant, TenantMembership
from backend.app.models.user import User
from backend.app.routes.portfolio_risk import router
from backend.app.services.rbac.seeding import assign_role
from backend.tests._demo_portfolio_helpers import fresh_session


@pytest.fixture
def portfolio_risk_setup():
    engine, session_factory = fresh_session()
    db = session_factory()
    org_a = Organization(slug="risk-bank-a", name="Risk Bank A")
    org_b = Organization(slug="risk-bank-b", name="Risk Bank B")
    db.add_all([org_a, org_b])
    db.flush()
    tenant_a = Tenant(organization_id=org_a.id, slug="default", name="Risk A")
    tenant_b = Tenant(organization_id=org_b.id, slug="default", name="Risk B")
    db.add_all([tenant_a, tenant_b])
    db.flush()

    def user(email: str, role: str, tenant_id: int) -> int:
        account = User(email=email, password="test-password")
        db.add(account)
        db.flush()
        db.add(
            TenantMembership(
                tenant_id=tenant_id,
                user_id=account.id,
                org_role="member",
                status="active",
                is_default=True,
            )
        )
        db.commit()
        assign_role(db, account, role, replace=True)
        return account.id

    manager_id = user("risk-manager@example.test", "risk_manager", tenant_a.id)
    viewer_id = user("risk-viewer@example.test", "viewer", tenant_a.id)
    outsider_id = user("risk-outsider@example.test", "risk_manager", tenant_b.id)
    company_a = Company(
        tenant_id=tenant_a.id,
        external_id="risk-company-a",
        name="Borrower A",
        industry="Manufacturing",
        sector="Industry",
        currency="USD",
        is_demo=False,
        data_source="test",
    )
    company_b = Company(
        tenant_id=tenant_b.id,
        external_id="risk-company-b",
        name="Borrower B",
        industry="Manufacturing",
        sector="Industry",
        currency="USD",
        is_demo=False,
        data_source="test",
    )
    db.add_all([company_a, company_b])
    db.commit()
    company_a_id, company_b_id = company_a.id, company_b.id
    tenant_a_id, tenant_b_id = tenant_a.id, tenant_b.id
    db.close()

    state = {"user_id": manager_id, "tenant_id": tenant_a_id}
    app = FastAPI()
    app.include_router(router)

    def override_db():
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    def override_user():
        session = session_factory()
        try:
            return session.query(User).filter(User.id == state["user_id"]).one()
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_user
    app.dependency_overrides[get_current_tenant_id] = lambda: state["tenant_id"]
    client = TestClient(app)
    yield {
        "client": client,
        "session_factory": session_factory,
        "state": state,
        "manager_id": manager_id,
        "viewer_id": viewer_id,
        "outsider_id": outsider_id,
        "tenant_a": tenant_a_id,
        "tenant_b": tenant_b_id,
        "company_a": company_a_id,
        "company_b": company_b_id,
    }
    client.close()
    engine.dispose()


def _add_exposure(setup, *, company_id=None, tenant_id=None, value=100, currency="USD"):
    db = setup["session_factory"]()
    try:
        row = PortfolioExposure(
            tenant_id=tenant_id or setup["tenant_a"],
            company_id=company_id or setup["company_a"],
            exposure=value,
            currency=currency,
        )
        db.add(row)
        db.commit()
        return row.id
    finally:
        db.close()


def test_exposure_limit_breach_lifecycle_is_auditable_and_idempotent(portfolio_risk_setup):
    setup = portfolio_risk_setup
    _add_exposure(setup, value=110)
    client = setup["client"]
    created = client.post(
        "/api/portfolio-risk/limits",
        json={
            "scope": "company",
            "company_id": setup["company_a"],
            "currency": "USD",
            "threshold": 100,
            "approaching_ratio": 0.8,
        },
    )
    assert created.status_code == 201, created.text
    limit_id = created.json()["id"]

    assert client.post("/api/portfolio-risk/limits/evaluate").status_code == 200
    assert client.post("/api/portfolio-risk/limits/evaluate").status_code == 200
    db = setup["session_factory"]()
    breach = db.query(PortfolioExposureBreach).one()
    breach_id = breach.id
    assert breach.status == "open"
    assert breach.supporting_company_ids == [setup["company_a"]]
    assert len(breach.supporting_exposure_ids) == 1
    assert db.query(PortfolioExposureLimitEvent).filter_by(action="detected").count() == 1
    db.close()

    acknowledged = client.post(
        f"/api/portfolio-risk/breaches/{breach_id}/acknowledge",
        json={"reason": "Reviewed by risk management."},
    )
    assert acknowledged.status_code == 200
    assert acknowledged.json()["status"] == "acknowledged"
    client.post("/api/portfolio-risk/limits/evaluate")
    db = setup["session_factory"]()
    assert db.query(PortfolioExposureBreach).one().status == "acknowledged"
    exposure = db.query(PortfolioExposure).one()
    exposure.exposure = 80
    db.commit()
    db.close()

    client.post("/api/portfolio-risk/limits/evaluate")
    db = setup["session_factory"]()
    assert db.query(PortfolioExposureBreach).one().status == "resolved"
    db.query(PortfolioExposure).one().exposure = 110
    db.commit()
    db.close()
    client.post("/api/portfolio-risk/limits/evaluate")

    db = setup["session_factory"]()
    assert db.query(PortfolioExposureBreach).one().status == "open"
    assert db.query(PortfolioExposureLimitEvent).filter_by(action="reopened").count() == 1
    db.close()
    assert client.get(f"/api/portfolio-risk/limits/{limit_id}/events").status_code == 200


def test_mixed_currency_or_missing_exposure_is_not_reported_as_zero(portfolio_risk_setup):
    setup = portfolio_risk_setup
    _add_exposure(setup, value=100, currency="EUR")
    client = setup["client"]
    created = client.post(
        "/api/portfolio-risk/limits",
        json={
            "scope": "portfolio",
            "currency": "USD",
            "threshold": 1000,
        },
    )
    assert created.status_code == 201, created.text
    row = created.json()
    assert row["calculation_status"] == "insufficient_data"
    assert row["utilization"] is None
    assert client.post("/api/portfolio-risk/limits/evaluate").json()["results"][0][
        "status"
    ] == "insufficient_data"


def test_portfolio_limit_requires_exposure_records_for_all_tenant_companies(
    portfolio_risk_setup,
):
    setup = portfolio_risk_setup
    db = setup["session_factory"]()
    db.add(
        Company(
            tenant_id=setup["tenant_a"],
            external_id="risk-company-without-exposure",
            name="Borrower without exposure",
            industry="Services",
            is_demo=False,
            data_source="test",
        )
    )
    db.commit()
    db.close()
    _add_exposure(setup, value=0, currency="USD")
    response = setup["client"].post(
        "/api/portfolio-risk/limits",
        json={"scope": "portfolio", "currency": "USD", "threshold": 100},
    )
    assert response.status_code == 201
    assert response.json()["calculation_status"] == "insufficient_data"
    assert response.json()["eligible_exposure"] is None


def test_tenant_and_permission_boundaries_for_limits(portfolio_risk_setup):
    setup = portfolio_risk_setup
    client = setup["client"]
    cross_tenant = client.post(
        "/api/portfolio-risk/limits",
        json={
            "scope": "company",
            "company_id": setup["company_b"],
            "currency": "USD",
            "threshold": 100,
        },
    )
    assert cross_tenant.status_code == 404

    setup["state"].update(user_id=setup["outsider_id"], tenant_id=setup["tenant_b"])
    assert client.get("/api/portfolio-risk/limits").json()["limits"] == []
    setup["state"].update(user_id=setup["manager_id"], tenant_id=setup["tenant_a"])
    created = client.post(
        "/api/portfolio-risk/limits",
        json={"scope": "portfolio", "currency": "USD", "threshold": 100},
    )
    assert created.status_code == 201
    deactivated = client.patch(
        f"/api/portfolio-risk/limits/{created.json()['id']}",
        json={"is_active": False, "reason": "Limit retired by risk."},
    )
    assert deactivated.status_code == 200
    assert deactivated.json()["status"] == "inactive"
    setup["state"]["user_id"] = setup["viewer_id"]
    assert client.post(
        "/api/portfolio-risk/limits/evaluate"
    ).status_code == 403
    assert client.post(
        "/api/portfolio-risk/limits",
        json={"scope": "portfolio", "currency": "USD", "threshold": 100},
    ).status_code == 403


def test_company_covenant_uses_only_approved_matching_evidence(portfolio_risk_setup):
    setup = portfolio_risk_setup
    db = setup["session_factory"]()
    doc = Document(
        tenant_id=setup["tenant_a"],
        user_id=setup["manager_id"],
        company_id=setup["company_a"],
        fiscal_year=2025,
        document_type="financial_statement",
        original_filename="approved.pdf",
        mime_type="application/pdf",
        size_bytes=1,
        storage_uri="private://approved",
        content_hash="c" * 64,
        status="approved",
    )
    db.add(doc)
    db.flush()
    financial = CompanyFinancials(
        tenant_id=setup["tenant_a"],
        company_id=setup["company_a"],
        fiscal_year=2025,
        current_assets=50,
        current_liabilities=100,
        source_document_id=doc.id,
        currency="USD",
        unit="units",
    )
    db.add(financial)
    db.commit()
    source_document_id = doc.id
    db.close()

    client = setup["client"]
    created = client.post(
        f"/api/portfolio-risk/companies/{setup['company_a']}/covenants",
        json={
            "metric_key": "current_ratio_min",
            "name": "Minimum current ratio",
            "threshold": 1,
            "effective_date": date.today().isoformat(),
            "review_frequency_months": 12,
        },
    )
    assert created.status_code == 201, created.text
    covenant_id = created.json()["covenant"]["id"]
    first = client.post(f"/api/portfolio-risk/covenants/{covenant_id}/evaluate")
    second = client.post(f"/api/portfolio-risk/covenants/{covenant_id}/evaluate")
    assert first.json()["evaluation"]["status"] == "breached"
    assert first.json()["evaluation"]["calculated_value"] == 0.5
    assert first.json()["evaluation"]["source_document_id"] == source_document_id
    assert second.json()["evaluation"]["id"] == first.json()["evaluation"]["id"]

    acknowledged = client.post(
        f"/api/portfolio-risk/covenant-evaluations/{first.json()['evaluation']['id']}/acknowledge",
        json={"reason": "Reviewed and added to the credit file."},
    )
    assert acknowledged.json()["evaluation"]["status"] == "breached"
    assert acknowledged.json()["evaluation"]["acknowledged_at"]
    updated = client.patch(
        f"/api/portfolio-risk/covenants/{covenant_id}",
        json={"threshold": 0.4, "reason": "Approved covenant amendment."},
    )
    assert updated.status_code == 200
    reassessed = client.post(f"/api/portfolio-risk/covenants/{covenant_id}/evaluate")
    assert reassessed.json()["evaluation"]["status"] == "compliant"
    assert reassessed.json()["evaluation"]["id"] != first.json()["evaluation"]["id"]
    history = client.get(
        f"/api/portfolio-risk/companies/{setup['company_a']}/covenants"
    ).json()["covenants"][0]["evaluations"]
    assert len(history) == 2


def test_covenant_rejects_cross_tenant_company_and_missing_evidence_is_not_breach(
    portfolio_risk_setup,
):
    setup = portfolio_risk_setup
    client = setup["client"]
    denied = client.post(
        f"/api/portfolio-risk/companies/{setup['company_b']}/covenants",
        json={
            "metric_key": "debt_to_equity_max",
            "name": "Debt to equity",
            "threshold": 2,
        },
    )
    assert denied.status_code == 404

    created = client.post(
        f"/api/portfolio-risk/companies/{setup['company_a']}/covenants",
        json={
            "metric_key": "debt_to_ebitda_max",
            "name": "Debt to EBITDA",
            "threshold": 4,
        },
    )
    assert created.status_code == 201, created.text
    covenant_id = created.json()["covenant"]["id"]
    evaluation = client.post(f"/api/portfolio-risk/covenants/{covenant_id}/evaluate")
    assert evaluation.json()["evaluation"]["status"] == "insufficient_data"
    assert evaluation.json()["evaluation"]["calculated_value"] is None
    assert evaluation.json()["evaluation"]["source_document_id"] is None

    setup["state"].update(user_id=setup["outsider_id"], tenant_id=setup["tenant_b"])
    assert client.get(
        f"/api/portfolio-risk/companies/{setup['company_a']}/covenants"
    ).status_code == 404
    assert client.post(
        f"/api/portfolio-risk/covenants/{covenant_id}/evaluate"
    ).status_code == 404
    assert client.post(
        f"/api/portfolio-risk/covenant-evaluations/{evaluation.json()['evaluation']['id']}/acknowledge",
        json={"reason": "Should not reveal another tenant."},
    ).status_code == 404

    setup["state"].update(user_id=setup["manager_id"], tenant_id=setup["tenant_a"])
    setup["state"].update(user_id=setup["viewer_id"])
    assert client.post(
        f"/api/portfolio-risk/companies/{setup['company_a']}/covenants",
        json={
            "metric_key": "current_ratio_min",
            "name": "Unauthorized",
            "threshold": 1,
        },
    ).status_code == 403


def test_zero_denominator_in_approved_evidence_is_insufficient_data(portfolio_risk_setup):
    setup = portfolio_risk_setup
    db = setup["session_factory"]()
    doc = Document(
        tenant_id=setup["tenant_a"],
        user_id=setup["manager_id"],
        company_id=setup["company_a"],
        fiscal_year=2025,
        document_type="financial_statement",
        original_filename="zero-denominator.pdf",
        mime_type="application/pdf",
        size_bytes=1,
        storage_uri="private://zero-denominator",
        content_hash="e" * 64,
        status="approved",
    )
    db.add(doc)
    db.flush()
    db.add(
        CompanyFinancials(
            tenant_id=setup["tenant_a"],
            company_id=setup["company_a"],
            fiscal_year=2025,
            current_assets=50,
            current_liabilities=0,
            source_document_id=doc.id,
        )
    )
    db.commit()
    db.close()
    created = setup["client"].post(
        f"/api/portfolio-risk/companies/{setup['company_a']}/covenants",
        json={
            "metric_key": "current_ratio_min",
            "name": "Positive denominator",
            "threshold": 1,
        },
    )
    evaluation = setup["client"].post(
        f"/api/portfolio-risk/covenants/{created.json()['covenant']['id']}/evaluate"
    )
    assert evaluation.json()["evaluation"]["status"] == "insufficient_data"
    assert evaluation.json()["evaluation"]["calculated_value"] is None


def test_company_financials_with_unapproved_document_do_not_create_false_breach(
    portfolio_risk_setup,
):
    setup = portfolio_risk_setup
    db = setup["session_factory"]()
    doc = Document(
        tenant_id=setup["tenant_a"],
        user_id=setup["manager_id"],
        company_id=setup["company_a"],
        fiscal_year=2025,
        document_type="financial_statement",
        original_filename="pending.pdf",
        mime_type="application/pdf",
        size_bytes=1,
        storage_uri="private://pending",
        content_hash="d" * 64,
        status="reviewed",
    )
    db.add(doc)
    db.flush()
    db.add(
        CompanyFinancials(
            tenant_id=setup["tenant_a"],
            company_id=setup["company_a"],
            fiscal_year=2025,
            debt=100,
            ebitda=10,
            source_document_id=doc.id,
        )
    )
    db.commit()
    db.close()

    created = setup["client"].post(
        f"/api/portfolio-risk/companies/{setup['company_a']}/covenants",
        json={
            "metric_key": "debt_to_ebitda_max",
            "name": "Debt to EBITDA",
            "threshold": 4,
        },
    )
    evaluation = setup["client"].post(
        f"/api/portfolio-risk/covenants/{created.json()['covenant']['id']}/evaluate"
    )
    assert evaluation.json()["evaluation"]["status"] == "insufficient_data"
    assert evaluation.json()["evaluation"]["evidence_status"] == "missing_approved_financials"
