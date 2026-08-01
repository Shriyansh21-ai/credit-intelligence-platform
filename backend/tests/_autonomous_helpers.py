"""Shared helpers for Autonomous Intelligence tests (not a test module).

Builds an in-memory SQLite session with the full schema (importing the app
registers every model) plus TestClients wired to the routers with auth +
db overridden, mirroring the /7/8 helper pattern.
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
    from backend.app.routes.autonomous import ROUTERS
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


_COMPANIES = [
    dict(company_name="TextileCo", industry="textile", enterprise_credit_score=520,
         probability_of_default=0.14, loss_given_default=0.5, expected_loss=700000,
         risk_rating="B", recommended_loan_amount=10000000, liquidity_health=35,
         debt_health=30, working_capital_health=40, business_stability=55,
         recommended_interest_rate=12.0),
    dict(company_name="PharmaInc", industry="pharma", enterprise_credit_score=780,
         probability_of_default=0.02, loss_given_default=0.4, expected_loss=80000,
         risk_rating="AA", recommended_loan_amount=50000000, liquidity_health=80,
         debt_health=75, working_capital_health=70, business_stability=85,
         recommended_interest_rate=9.0),
    dict(company_name="SteelWorks", industry="steel", enterprise_credit_score=640,
         probability_of_default=0.06, loss_given_default=0.45, expected_loss=250000,
         risk_rating="BBB", recommended_loan_amount=20000000, liquidity_health=55,
         debt_health=50, working_capital_health=58, business_stability=60,
         recommended_interest_rate=10.5),
]


def seed_assessment(db, *, user_id=1, **overrides):
    base = dict(user_id=user_id, industry="general", business_type="pvt", years_in_business=10,
                employee_count=150, country="IN",
                enterprise_credit_score=650, probability_of_default=0.05,
                loss_given_default=0.45, expected_loss=100000, risk_rating="BBB",
                loan_recommendation="review",
                interest_rate_recommendation="x", loan_tenure_recommendation="x",
                collateral_recommendation="x", ai_analysis="x",
                engine_input={"revenue": 100, "net_margin": 0.1, "current_ratio": 1.2,
                              "debt_to_equity": 1.5, "operating_cash_flow": 20})
    base.update(overrides)
    a = EnterpriseAssessment(**base)
    db.add(a)
    db.commit()
    db.refresh(a)
    return a


def seed_portfolio(db, user_id=1):
    out = []
    for c in _COMPANIES:
        out.append(seed_assessment(db, user_id=user_id, **c))
    return out
