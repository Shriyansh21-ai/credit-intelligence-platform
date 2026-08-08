"""User -> tenant provisioning.

Bridges the JWT/user world and the SaaS tenant world, which were previously
disconnected: nothing associated an authenticated ``User`` with a ``Tenant``.

:func:`resolve_user_tenant` is the single get-or-create entry point. It returns
the tenant that owns a user's data, provisioning an organization + default
tenant + owner membership on first use. The organization is keyed by the user's
email domain, so co-workers on the same domain share one tenant (real
multi-tenant behaviour) while users on different domains are fully isolated.

Idempotent and best-effort friendly: safe to call on every login/signup and
from the ``get_current_tenant`` dependency, so even pre-existing accounts are
self-healed into the tenant model without a data migration.
"""

from __future__ import annotations

import re
from typing import Optional

from sqlalchemy.orm import Session

from backend.app.models.tenancy import Organization, Tenant, TenantMembership
from backend.app.models.user import User


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (value or "").lower()).strip("-")
    return slug or "org"


def _org_identity(user: User) -> tuple[str, str]:
    """Return (org_slug, org_name) derived from the user's email domain."""
    email = (user.email or "").strip().lower()
    domain = email.split("@", 1)[1] if "@" in email else ""
    if domain:
        slug = f"org-{_slugify(domain)}"
        name = (user.organization_name or domain.split(".")[0].title() or "Organization")
        return slug, name
    slug = f"user-{user.id}"
    return slug, (user.organization_name or "Organization")


def resolve_user_tenant(db: Session, user: User) -> Optional[Tenant]:
    """Return the user's owning tenant, provisioning it on first use.

    Never raises for the caller's convenience — returns ``None`` only if the
    tenancy schema is unavailable (e.g. DB not migrated).
    """
    try:
        # 1) Existing membership wins (prefer the default one).
        memberships = (
            db.query(TenantMembership)
            .filter(TenantMembership.user_id == user.id,
                    TenantMembership.status == "active")
            .all()
        )
        if memberships:
            memberships.sort(key=lambda m: (not m.is_default, m.id))
            tenant = db.query(Tenant).get(memberships[0].tenant_id)
            if tenant is not None:
                return tenant

        # 2) Provision org (by email domain) + default tenant.
        org_slug, org_name = _org_identity(user)
        org = db.query(Organization).filter(Organization.slug == org_slug).first()
        if org is None:
            org = Organization(slug=org_slug, name=org_name, org_type="enterprise")
            db.add(org)
            db.flush()
        tenant = (
            db.query(Tenant)
            .filter(Tenant.organization_id == org.id, Tenant.is_default.is_(True))
            .first()
        )
        if tenant is None:
            tenant = Tenant(
                organization_id=org.id, slug="default", name=org_name, is_default=True
            )
            db.add(tenant)
            db.flush()

        # 3) Ensure owner membership.
        membership = (
            db.query(TenantMembership)
            .filter(TenantMembership.tenant_id == tenant.id,
                    TenantMembership.user_id == user.id)
            .first()
        )
        if membership is None:
            membership = TenantMembership(
                tenant_id=tenant.id, user_id=user.id, org_role="owner",
                status="active", is_default=True,
            )
            db.add(membership)
        db.commit()
        return tenant
    except Exception:
        db.rollback()
        return None
