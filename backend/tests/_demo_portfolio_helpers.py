"""Shared helpers for demo-portfolio tests (not a test module).

Builds an in-memory SQLite database with every ORM table registered (via the
model registry), seeds RBAC + the default SaaS tenant, and wires a TestClient to
the real auth + demo-portfolio routers with the DB overridden. Auth flows
through the genuine ``/signup`` endpoint (which provisions each user's tenant),
so tenant isolation is exercised end-to-end, not mocked.
"""

from __future__ import annotations

import warnings

warnings.filterwarnings("ignore")

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import backend.app.db.registry  # noqa: F401  (register every ORM mapper/table)
from backend.app.db.database import Base, get_db


def fresh_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    # Seed RBAC catalog + default tenant so signup can grant a role.
    db = Session()
    try:
        from backend.app.services.rbac import sync_rbac
        from backend.app.services.saas.seeding import seed_saas

        sync_rbac(db)
        seed_saas(db)
    finally:
        db.close()
    return engine, Session


def make_app(Session):
    """A TestClient with /signup, /login and /api/demo-portfolio, DB overridden."""
    from backend.app.routes import auth as auth_routes
    from backend.app.routes import demo_portfolio as dp_routes

    app = FastAPI()
    app.include_router(auth_routes.router)
    app.include_router(dp_routes.router)

    def override_db():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_db
    return TestClient(app)


def signup(client: TestClient, email: str, password: str = "Demo@12345") -> str:
    resp = client.post("/signup", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body.get("success"), body
    return body["access_token"]


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}
