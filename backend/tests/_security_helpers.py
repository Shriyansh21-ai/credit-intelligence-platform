"""Shared helpers for Stage 4 Security & Compliance tests (not a test module).

Builds an in-memory SQLite session with the full schema (importing the app
registers every model) plus a TestClient wired to the Stage 4 routers with auth
+ db overridden, mirroring the -10 helper pattern.
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
    from backend.app.routes.security_compliance import ROUTERS
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


def setup_env(*roles):
    """Convenience: fresh DB + seeded RBAC + one user id per role name.

    Returns ``(Session, {role: uid})``.
    """
    engine, Session = fresh_session()
    db = Session()
    try:
        seed_rbac(db)
    finally:
        db.close()
    ids = {}
    for i, role in enumerate(roles):
        ids[role] = make_user(Session, f"{role}{i}@example.com", role)
    return Session, ids
