"""Super-admin console service (Phase 8, Milestone 12).

Cross-tenant, platform-operator views. These functions deliberately bypass the
tenant scope (the operator is a platform super-admin) and aggregate the state an
operator needs: tenants, subscriptions, usage, jobs, audit and system health.
Route-level authorization restricts this surface to the ``platform.admin``
permission.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.app.models.billing import Subscription, UsageRecord
from backend.app.models.platform_ops import BackgroundJob
from backend.app.models.tenancy import Organization, Tenant, TenantMembership
from backend.app.services.saas import analytics, observability
from backend.app.services.saas.billing import service as billing_svc


def list_all_organizations(db: Session) -> List[Dict[str, Any]]:
    out = []
    for org in db.query(Organization).order_by(Organization.id).all():
        sub = billing_svc.active_subscription(db, org.id)
        tenants = db.query(func.count(Tenant.id)).filter(
            Tenant.organization_id == org.id).scalar() or 0
        out.append({
            "id": org.id, "slug": org.slug, "name": org.name,
            "org_type": org.org_type, "status": org.status,
            "tenants": tenants,
            "plan": _plan_code(db, sub),
            "subscription_status": sub.status if sub else None,
        })
    return out


def _plan_code(db, sub: Optional[Subscription]) -> Optional[str]:
    if sub is None:
        return None
    from backend.app.models.billing import BillingPlan
    plan = db.query(BillingPlan).get(sub.plan_id)
    return plan.code if plan else None


def organization_detail(db: Session, org_id: int) -> Dict[str, Any]:
    org = db.query(Organization).get(org_id)
    if org is None:
        raise ValueError("organization not found")
    tenants = db.query(Tenant).filter(Tenant.organization_id == org_id).all()
    return {
        "organization": {"id": org.id, "slug": org.slug, "name": org.name,
                         "status": org.status, "org_type": org.org_type},
        "tenants": [{"id": t.id, "slug": t.slug, "name": t.name,
                     "status": t.status, "is_default": t.is_default} for t in tenants],
        "billing": billing_svc.billing_analytics(db, org_id),
        "subscription_history": [
            {"event": e.event_type, "from": e.from_plan, "to": e.to_plan,
             "at": e.created_at.isoformat() if e.created_at else None}
            for e in billing_svc.subscription_history(db, org_id)
        ],
    }


def suspend_organization(db: Session, org_id: int, *, suspend: bool = True) -> Organization:
    org = db.query(Organization).get(org_id)
    if org is None:
        raise ValueError("organization not found")
    org.status = "suspended" if suspend else "active"
    # Cascade to tenants.
    for t in db.query(Tenant).filter(Tenant.organization_id == org_id).all():
        t.status = org.status
    db.commit()
    db.refresh(org)
    return org


def usage_console(db: Session, *, period: Optional[str] = None) -> Dict[str, Any]:
    """Per-organization usage breakdown across all meters (ML/OCR/API/etc.)."""
    period = period or billing_svc.current_period()
    rows = (
        db.query(UsageRecord.organization_id, UsageRecord.meter,
                 func.sum(UsageRecord.quantity))
        .filter(UsageRecord.period == period)
        .group_by(UsageRecord.organization_id, UsageRecord.meter)
        .all()
    )
    out: Dict[int, Dict[str, float]] = {}
    for org_id, meter, total in rows:
        out.setdefault(org_id, {})[meter] = float(total)
    return {"period": period, "by_organization": out}


def jobs_console(db: Session) -> Dict[str, Any]:
    rows = (
        db.query(BackgroundJob.status, func.count(BackgroundJob.id))
        .group_by(BackgroundJob.status)
        .all()
    )
    return {"by_status": {status: count for status, count in rows}}


def system_health(db: Session) -> Dict[str, Any]:
    return {
        "health": observability.health_report(db),
        "service_map": observability.service_map(),
        "errors": observability.error_analytics(),
        "slow_queries": observability.slow_queries(limit=10),
        "generated_at": datetime.utcnow().isoformat(),
    }


def platform_summary(db: Session) -> Dict[str, Any]:
    return {
        "overview": analytics.platform_overview(db),
        "jobs": jobs_console(db),
        "health_status": observability.health_report(db)["status"],
    }
