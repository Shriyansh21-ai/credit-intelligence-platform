"""Shared helpers for Phase 10 Banking OS tests (not a test module).

Builds an in-memory SQLite session with the full schema (importing the app
registers every model) plus a TestClient wired to the Phase 10 routers with auth
+ db overridden, mirroring the Phase 6/7/8/9 helper pattern.
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
    from backend.app.routes.banking_os import ROUTERS
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
