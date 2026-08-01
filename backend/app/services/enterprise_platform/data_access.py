"""Read-only platform reads for (Enterprise Productization).

's operations, monitoring, security and BI surfaces roll up *real* signals
from across the platform (assessments, tenants, AI/ML usage). This module is the
single defensive read layer. Every helper tolerates a missing table / empty DB so
targeted unit tests and fresh installs keep working.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session


def _safe(fn, default):
    try:
        return fn()
    except Exception:
        return default


def count_assessments(db: Session) -> int:
    def q():
        from backend.app.models.enterprise_assessment import EnterpriseAssessment
        return db.query(EnterpriseAssessment).count()
    return _safe(q, 0)


def count_tenants(db: Session) -> int:
    def q():
        from backend.app.models.tenancy import Tenant
        return db.query(Tenant).count()
    return _safe(q, 0)


def count_users(db: Session) -> int:
    def q():
        from backend.app.models.user import User
        return db.query(User).count()
    return _safe(q, 0)


def count_rows(db: Session, model_path: str, class_name: str) -> int:
    def q():
        import importlib
        mod = importlib.import_module(model_path)
        cls = getattr(mod, class_name)
        return db.query(cls).count()
    return _safe(q, 0)


def platform_counts(db: Session) -> Dict[str, int]:
    """Coarse platform inventory used by ops/BI/monitoring roll-ups."""
    return {
        "assessments": count_assessments(db),
        "tenants": count_tenants(db),
        "users": count_users(db),
        "portfolios": count_rows(db, "backend.app.models.financial_intelligence", "FinPortfolio"),
        "ai_reports": count_rows(db, "backend.app.models.ai_platform", "AIPReport")
        if _has(db, "backend.app.models.ai_platform", "AIPReport") else 0,
    }


def _has(db: Session, model_path: str, class_name: str) -> bool:
    def q():
        import importlib
        mod = importlib.import_module(model_path)
        return hasattr(mod, class_name)
    return _safe(q, False)
