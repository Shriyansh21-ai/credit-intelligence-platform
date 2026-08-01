"""Shared helpers for SaaS-platform tests (not a test module).

Builds an in-memory SQLite session with the tables plus the users/RBAC
tables needed for auth. Uses a targeted ``create_all`` (like the helper)
to avoid unrelated cross-model FK ordering issues.
"""

from __future__ import annotations

import warnings

warnings.filterwarnings("ignore")

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.core.dependencies import get_current_user
from backend.app.db.database import Base, get_db
from backend.app.models.user import User

# Register model metadata via import side effects.
import backend.app.models.rbac  # noqa: F401
import backend.app.models.tenancy  # noqa: F401
import backend.app.models.billing  # noqa: F401
import backend.app.models.feature_flags  # noqa: F401
import backend.app.models.platform_ops  # noqa: F401
import backend.app.models.saas_security  # noqa: F401

_WANTED_PREFIXES = (
    "organization", "tenant", "business_units", "department", "team",
    "workspace", "project", "custom_domains", "billing_", "subscription",
    "usage_", "invoice", "feature_flag", "background_jobs", "job_schedules",
    "storage_", "activity_", "presence_", "trace_", "security_",
    "ip_allow_", "secret_", "identity_provider_",
)
_WANTED_EXACT = {
    "users", "roles", "permissions", "role_permissions", "user_roles",
}


def _tables():
    return [t for n, t in Base.metadata.tables.items()
            if n.startswith(_WANTED_PREFIXES) or n in _WANTED_EXACT]


def fresh_session():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False},
                           poolclass=StaticPool)
    Base.metadata.create_all(engine, tables=_tables())
    Session = sessionmaker(bind=engine)
    return engine, Session


def seed_all(db):
    """Sync RBAC + seed the SaaS platform (plans, flags, default tenant)."""
    from backend.app.services.rbac import sync_rbac
    from backend.app.services.saas.seeding import seed_saas
    sync_rbac(db)
    return seed_saas(db)


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
    """A TestClient wired to the SaaS routers with auth + db overridden."""
    from backend.app.routes.saas import ROUTERS
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
