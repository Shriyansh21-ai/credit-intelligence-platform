"""Dashboard aggregation API.

One endpoint per enterprise dashboard, each returning ready-to-render aggregates.

    GET /api/dashboards/operations Credit Operations (applications.view)
    GET /api/dashboards/admin Administrator (users.manage)
    GET /api/dashboards/analyst Analyst (self) (tasks.view)
    GET /api/dashboards/manager Manager (approvals.view)
    GET /api/dashboards/portfolio Portfolio (portfolio.view)
    GET /api/dashboards/compliance Compliance (audit.view)
    GET /api/dashboards/monitoring Monitoring (monitoring.view)
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.app.core.dependencies import get_current_user
from backend.app.db.database import get_db
from backend.app.models.user import User
from backend.app.services import dashboards
from backend.app.services.rbac import require_permission

router = APIRouter(prefix="/api/dashboards", tags=["Dashboards"])


@router.get("/operations")
def operations(
    db: Session = Depends(get_db),
    _user: User = Depends(require_permission("applications.view")),
):
    return dashboards.operations_dashboard(db)


@router.get("/admin")
def admin(
    db: Session = Depends(get_db),
    _user: User = Depends(require_permission("users.manage")),
):
    return dashboards.admin_dashboard(db)


@router.get("/analyst")
def analyst(
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("tasks.view")),
):
    return dashboards.analyst_dashboard(db, user.id)


@router.get("/manager")
def manager(
    db: Session = Depends(get_db),
    _user: User = Depends(require_permission("approvals.view")),
):
    return dashboards.manager_dashboard(db)


@router.get("/portfolio")
def portfolio(
    db: Session = Depends(get_db),
    _user: User = Depends(require_permission("portfolio.view")),
):
    return dashboards.portfolio_dashboard(db)


@router.get("/compliance")
def compliance(
    db: Session = Depends(get_db),
    _user: User = Depends(require_permission("audit.view")),
):
    return dashboards.compliance_dashboard(db)


@router.get("/monitoring")
def monitoring(
    db: Session = Depends(get_db),
    _user: User = Depends(require_permission("monitoring.view")),
):
    return dashboards.monitoring_dashboard(db)
