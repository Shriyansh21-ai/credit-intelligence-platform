"""SaaS analytics platform.

Cross-cutting, read-only aggregations for executive dashboards: tenant growth
revenue (MRR / ARR), usage per meter, feature adoption and per-tenant activity.
Everything is computed from the durable tables so no separate ETL is
required for the platform to report on itself.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.app.models.billing import (
    BillingPlan, Invoice, Subscription, UsageRecord,
)
from backend.app.models.platform_ops import ActivityEvent, BackgroundJob, StorageObject
from backend.app.models.tenancy import Organization, Tenant, TenantMembership
from backend.app.services.saas import storage as storage_svc
from backend.app.services.saas.billing import service as billing_svc


def platform_overview(db: Session) -> Dict[str, Any]:
    org_count = db.query(func.count(Organization.id)).scalar() or 0
    tenant_count = db.query(func.count(Tenant.id)).scalar() or 0
    active_subs = (
        db.query(func.count(Subscription.id))
        .filter(Subscription.status.in_(["trialing", "active", "past_due"]))
        .scalar() or 0
    )
    member_count = db.query(func.count(func.distinct(TenantMembership.user_id))).scalar() or 0
    return {
        "organizations": org_count,
        "tenants": tenant_count,
        "active_subscriptions": active_subs,
        "distinct_users": member_count,
        "mrr": revenue_analytics(db)["mrr"],
    }


def revenue_analytics(db: Session) -> Dict[str, Any]:
    subs = (
        db.query(Subscription)
        .filter(Subscription.status.in_(["trialing", "active", "past_due"]))
        .all()
    )
    by_plan: Dict[str, Dict[str, Any]] = defaultdict(lambda: {"count": 0, "mrr": 0.0})
    mrr = 0.0
    for sub in subs:
        plan = db.query(BillingPlan).get(sub.plan_id)
        if plan is None:
            continue
        monthly = plan.base_price if plan.billing_interval == "monthly" else plan.base_price / 12.0
        mrr += monthly
        by_plan[plan.code]["count"] += 1
        by_plan[plan.code]["mrr"] += monthly
    paid_total = (
        db.query(func.coalesce(func.sum(Invoice.total), 0.0))
        .filter(Invoice.status == "paid")
        .scalar() or 0.0
    )
    return {
        "mrr": round(mrr, 2),
        "arr": round(mrr * 12, 2),
        "by_plan": {k: {"count": v["count"], "mrr": round(v["mrr"], 2)}
                    for k, v in by_plan.items()},
        "lifetime_paid": round(float(paid_total), 2),
    }


def usage_analytics(db: Session, *, period: Optional[str] = None) -> Dict[str, Any]:
    period = period or billing_svc.current_period()
    rows = (
        db.query(UsageRecord.meter, func.sum(UsageRecord.quantity))
        .filter(UsageRecord.period == period)
        .group_by(UsageRecord.meter)
        .all()
    )
    return {"period": period, "totals": {meter: float(total) for meter, total in rows}}


def growth_metrics(db: Session) -> Dict[str, Any]:
    by_month: Dict[str, int] = defaultdict(int)
    for (created,) in db.query(Organization.created_at).all():
        if created:
            by_month[created.strftime("%Y-%m")] += 1
    months = sorted(by_month)
    cumulative, running = {}, 0
    for m in months:
        running += by_month[m]
        cumulative[m] = running
    return {"new_orgs_by_month": dict(sorted(by_month.items())), "cumulative_orgs": cumulative}


def tenant_analytics(db: Session, tenant_id: int) -> Dict[str, Any]:
    members = db.query(func.count(TenantMembership.id)).filter(
        TenantMembership.tenant_id == tenant_id).scalar() or 0
    activity = db.query(func.count(ActivityEvent.id)).filter(
        ActivityEvent.tenant_id == tenant_id).scalar() or 0
    jobs = db.query(func.count(BackgroundJob.id)).filter(
        BackgroundJob.tenant_id == tenant_id).scalar() or 0
    objects = db.query(func.count(StorageObject.id)).filter(
        StorageObject.tenant_id == tenant_id).scalar() or 0
    return {
        "tenant_id": tenant_id,
        "members": members,
        "activity_events": activity,
        "background_jobs": jobs,
        "storage_objects": objects,
        "storage_gb": storage_svc.storage_usage_gb(db, tenant_id),
    }


def feature_adoption(db: Session) -> Dict[str, Any]:
    """Adoption = share of tenants for which each flag evaluates ON."""
    from backend.app.services.saas.flags import service as flag_svc
    tenants = db.query(Tenant.id).all()
    total = len(tenants) or 1
    counts: Dict[str, int] = defaultdict(int)
    for (tid,) in tenants:
        for key, on in flag_svc.evaluate_all(db, tenant_id=tid).items():
            if on:
                counts[key] += 1
    return {k: {"tenants": v, "adoption_rate": round(v / total, 4)}
            for k, v in counts.items()}


def executive_dashboard(db: Session) -> Dict[str, Any]:
    return {
        "generated_at": datetime.utcnow().isoformat(),
        "overview": platform_overview(db),
        "revenue": revenue_analytics(db),
        "usage": usage_analytics(db),
        "growth": growth_metrics(db),
        "feature_adoption": feature_adoption(db),
    }
