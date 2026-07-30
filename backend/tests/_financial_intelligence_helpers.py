"""Shared helpers for Track 3 Financial Intelligence tests (not a test module).

Builds an in-memory SQLite session with the full schema (importing the app
registers every model) plus TestClients wired to the Track 3 routers with auth +
db overridden, mirroring the Track 2 helper pattern.
"""

from __future__ import annotations

import warnings

warnings.filterwarnings("ignore")

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Importing main registers every ORM model + builds the app (side effects only).
import backend.app.main  # noqa: F401
from backend.app.core.dependencies import get_current_user
from backend.app.db.database import Base, get_db
from backend.app.models.enterprise_assessment import EnterpriseAssessment
from backend.app.models.user import User


def fresh_session():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False},
                           poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return engine, sessionmaker(bind=engine)


def seed_rbac(db):
    from backend.app.services.rbac import sync_rbac
    sync_rbac(db)


def make_user(Session, email, role):
    from backend.app.services.rbac.seeding import assign_role
    db = Session()
    try:
        u = User(email=email, password="x")
        db.add(u)
        db.commit()
        db.refresh(u)
        assign_role(db, u, role)
        return u.id
    finally:
        db.close()


def client_for(Session, uid):
    from backend.app.routes.financial_intelligence import ROUTERS
    app = FastAPI()
    for r in ROUTERS:
        app.include_router(r)

    def override_db():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    def override_user():
        db = Session()
        try:
            return db.query(User).filter(User.id == uid).first()
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_user
    return TestClient(app)


def admin_client():
    """Convenience: fresh session + admin client + the Session factory."""
    engine, Session = fresh_session()
    db = Session()
    seed_rbac(db)
    db.close()
    uid = make_user(Session, "fin-admin@x.com", "administrator")
    return Session, client_for(Session, uid)


def seed_company(db, *, company_name="Acme Corp", industry="manufacturing", score=650,
                 pd=0.05, lgd=0.45, exposure=5_000_000.0, rating="BBB", **overrides):
    base = dict(user_id=1, company_name=company_name, industry=industry, business_type="pvt",
                years_in_business=12, employee_count=200, country="IN",
                enterprise_credit_score=score, probability_of_default=pd,
                loss_given_default=lgd, expected_loss=exposure * pd * lgd, risk_rating=rating,
                recommended_loan_amount=exposure, loan_recommendation="approve",
                interest_rate_recommendation="10%", loan_tenure_recommendation="36m",
                collateral_recommendation="property", ai_analysis="ok",
                engine_input={"revenue": 500, "net_margin": 0.1, "current_ratio": 1.4,
                              "debt_to_equity": 1.5, "operating_cash_flow": 60,
                              "revenue_growth": 0.09})
    base.update(overrides)
    a = EnterpriseAssessment(**base)
    db.add(a)
    db.commit()
    db.refresh(a)
    return a


def seed_portfolio_companies(db, n=6):
    industries = ["manufacturing", "technology", "retail", "manufacturing", "services", "energy"]
    out = []
    for i in range(n):
        out.append(seed_company(db, company_name=f"Company {i}", industry=industries[i % len(industries)],
                                score=600 + i * 20, pd=0.03 + i * 0.01, exposure=1_000_000.0 * (i + 1)))
    return out
