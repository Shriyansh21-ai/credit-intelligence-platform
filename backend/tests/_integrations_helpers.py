"""Shared helpers for Phase 7 integration tests (not a test module).

Builds an in-memory SQLite session with exactly the tables the integration
platform needs (plus users/applications/assessments for linkage + RBAC). A
targeted ``create_all`` avoids the FeatureVector→enterprise_assessments FK
ordering issue noted for full-metadata creates.
"""

from __future__ import annotations

import warnings

warnings.filterwarnings("ignore")

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.db.database import Base
# Register the models we need (import for table registration side effects).
import backend.app.models.user  # noqa: F401
import backend.app.models.rbac  # noqa: F401
import backend.app.models.application  # noqa: F401
import backend.app.models.enterprise_assessment  # noqa: F401
import backend.app.models.integrations  # noqa: F401

_WANTED_PREFIXES = (
    "connector_", "integration_", "aa_", "bank_", "statement_",
    "collateral_", "api_", "webhook_", "portfolio_sync", "sync_",
)
_WANTED_EXACT = {
    "users", "roles", "permissions", "role_permissions", "user_roles",
    "applications", "application_status_history", "enterprise_assessments",
}


def _tables():
    return [t for n, t in Base.metadata.tables.items()
            if n.startswith(_WANTED_PREFIXES) or n in _WANTED_EXACT]


def fresh_session():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine, tables=_tables())
    Session = sessionmaker(bind=engine)
    return engine, Session


def seed_configs(db):
    from backend.app.services.integrations.config import sync_connector_configs
    return sync_connector_configs(db)
