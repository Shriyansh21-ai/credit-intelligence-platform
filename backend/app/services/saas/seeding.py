"""Startup seeding for the SaaS platform (Phase 8).

Idempotent bootstrap run on app startup (and in tests). It:

* syncs the billing plan catalog into ``billing_plans``,
* syncs the feature-flag registry into ``feature_flags``,
* ensures a **default organization + tenant** exists so single-tenant / legacy
  deployments have a home tenant without any manual setup — every pre-Phase-8
  code path keeps working, now under an implicit default tenant.

Best-effort: a missing schema (DB not yet migrated) must not stop the app.
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from backend.app.models.tenancy import Organization, Tenant

DEFAULT_ORG_SLUG = "platform"
DEFAULT_TENANT_SLUG = "default"


def ensure_default_tenant(db: Session) -> Optional[Tenant]:
    """Create the platform default org + tenant if none exists. Returns the
    default tenant (or None if unavailable)."""
    org = db.query(Organization).filter(Organization.slug == DEFAULT_ORG_SLUG).first()
    if org is None:
        org = Organization(slug=DEFAULT_ORG_SLUG, name="Platform Default",
                           org_type="enterprise")
        db.add(org)
        db.flush()
    tenant = (
        db.query(Tenant)
        .filter(Tenant.organization_id == org.id, Tenant.slug == DEFAULT_TENANT_SLUG)
        .first()
    )
    if tenant is None:
        tenant = Tenant(organization_id=org.id, slug=DEFAULT_TENANT_SLUG,
                        name="Default", is_default=True)
        db.add(tenant)
    db.commit()
    return tenant


def seed_saas(db: Session) -> dict:
    """Run all Phase 8 seeding. Returns a small summary."""
    from backend.app.services.saas.billing import service as billing_svc
    from backend.app.services.saas.flags import service as flag_svc

    summary = {"plans": 0, "flags": 0, "default_tenant": None}
    try:
        summary["plans"] = billing_svc.sync_plans(db)
    except Exception:
        db.rollback()
    try:
        summary["flags"] = flag_svc.sync_flags(db)
    except Exception:
        db.rollback()
    try:
        tenant = ensure_default_tenant(db)
        summary["default_tenant"] = tenant.id if tenant else None
    except Exception:
        db.rollback()
    return summary
