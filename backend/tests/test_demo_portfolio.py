"""Demo-portfolio: seeding, idempotency, reset, tenant isolation, auth.

Covers the end-to-end flow required by the production-readiness upgrade:
authenticated load, duplicate prevention, correct DB record counts, reset, and
strict organization isolation (User A cannot see User B's book).
"""

from __future__ import annotations

import warnings

warnings.filterwarnings("ignore")

from backend.app.services import demo_portfolio
from backend.tests._demo_portfolio_helpers import (
    auth_headers,
    fresh_session,
    make_app,
    signup,
)


# ---------------------------------------------------------------- service layer
def test_service_load_persists_and_is_idempotent():
    engine, Session = fresh_session()
    db = Session()
    try:
        # Use the platform default tenant (id 1) seeded by seed_saas.
        from backend.app.models.tenancy import Tenant

        tenant_id = db.query(Tenant).first().id

        first = demo_portfolio.load_demo_portfolio(db, tenant_id, count=20)
        assert first["companies_loaded"] == 20
        assert first["financial_records_loaded"] == 60  # 3 years each
        assert first["credit_profiles_loaded"] == 20
        assert first["portfolio_records_loaded"] == 20
        assert first["skipped_existing"] == 0

        # Second run: nothing duplicated.
        second = demo_portfolio.load_demo_portfolio(db, tenant_id, count=20)
        assert second["companies_loaded"] == 0
        assert second["skipped_existing"] == 20
        assert second["already_loaded"] is True

        summary = demo_portfolio.portfolio_summary(db, tenant_id)
        assert summary["loaded"] is True
        assert summary["total_companies"] == 20
        assert summary["is_demo"] is True
        assert summary["total_exposure"] > 0
        assert 0 <= summary["approval_rate"] <= 100
        assert len(summary["financial_trend"]) == 3

        # Reset removes the book.
        removed = demo_portfolio.reset_demo_portfolio(db, tenant_id)
        assert removed["companies_removed"] == 20
        assert demo_portfolio.portfolio_summary(db, tenant_id)["total_companies"] == 0
    finally:
        db.close()


# ----------------------------------------------------------------- API + auth
def test_load_requires_authentication():
    engine, Session = fresh_session()
    client = make_app(Session)
    assert client.get("/api/demo-portfolio/summary").status_code in (401, 403)
    assert client.post("/api/demo-portfolio/load", json={"count": 10}).status_code in (401, 403)


def test_api_load_summary_and_counts():
    engine, Session = fresh_session()
    client = make_app(Session)
    token = signup(client, "alice@bank-alpha.com")
    h = auth_headers(token)

    loaded = client.post("/api/demo-portfolio/load", json={"count": 25}, headers=h).json()
    assert loaded["status"] == "success"
    assert loaded["companies_loaded"] == 25
    assert loaded["is_demo"] is True

    summary = client.get("/api/demo-portfolio/summary", headers=h).json()
    assert summary["total_companies"] == 25
    assert summary["loaded"] is True

    companies = client.get("/api/demo-portfolio/companies?limit=5", headers=h).json()
    assert companies["total"] == 25
    assert len(companies["items"]) == 5
    assert companies["items"][0]["is_demo"] is True


def test_api_idempotent_load():
    engine, Session = fresh_session()
    client = make_app(Session)
    h = auth_headers(signup(client, "carol@bank-gamma.com"))

    client.post("/api/demo-portfolio/load", json={"count": 15}, headers=h)
    again = client.post("/api/demo-portfolio/load", json={"count": 15}, headers=h).json()
    assert again["companies_loaded"] == 0
    assert again["skipped_existing"] == 15
    assert again["already_loaded"] is True


def test_tenant_isolation_between_organizations():
    engine, Session = fresh_session()
    client = make_app(Session)

    a = auth_headers(signup(client, "user-a@bank-a.com"))
    b = auth_headers(signup(client, "user-b@bank-b.com"))

    # A loads 30; B's book is still empty (isolation).
    client.post("/api/demo-portfolio/load", json={"count": 30}, headers=a)
    assert client.get("/api/demo-portfolio/summary", headers=b).json()["total_companies"] == 0

    # B loads 40; A remains 30 (no cross-contamination).
    client.post("/api/demo-portfolio/load", json={"count": 40}, headers=b)
    assert client.get("/api/demo-portfolio/summary", headers=a).json()["total_companies"] == 30
    assert client.get("/api/demo-portfolio/summary", headers=b).json()["total_companies"] == 40

    # A resets; B is unaffected.
    client.delete("/api/demo-portfolio/reset", headers=a)
    assert client.get("/api/demo-portfolio/summary", headers=a).json()["total_companies"] == 0
    assert client.get("/api/demo-portfolio/summary", headers=b).json()["total_companies"] == 40


def test_same_domain_users_share_tenant():
    # Co-workers on the same email domain share one organization/tenant.
    engine, Session = fresh_session()
    client = make_app(Session)
    a = auth_headers(signup(client, "first@shared-bank.com"))
    b = auth_headers(signup(client, "second@shared-bank.com"))

    client.post("/api/demo-portfolio/load", json={"count": 20}, headers=a)
    # The second user sees the same book (same tenant).
    assert client.get("/api/demo-portfolio/summary", headers=b).json()["total_companies"] == 20
