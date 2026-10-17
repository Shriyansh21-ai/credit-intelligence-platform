"""User -> tenant provisioning.

Bridges the JWT/user world and the SaaS tenant world, which were previously
disconnected: nothing associated an authenticated ``User`` with a ``Tenant``.

:func:`resolve_user_tenant` is the single get-or-create entry point. It returns
the tenant that owns a user's data, provisioning an organization + default
tenant + owner membership on first use. New users receive an isolated
organization; an email domain is not proof of authorization to join another
customer's tenant. Additional users join only through an explicit membership.

Idempotent and best-effort friendly: safe to call on every login/signup and
from the ``get_current_tenant`` dependency, so even pre-existing accounts are
self-healed into the tenant model without a data migration.
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from backend.app.models.tenancy import Organization, Tenant, TenantMembership
from backend.app.models.user import User


def _org_identity(user: User) -> tuple[str, str]:
    """Return an isolated identity; organization labels are not authorization."""
    return f"user-{user.id}", (user.organization_name or "Organization")


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

        # 2) Provision a per-user org + default tenant. Shared access requires
        # an explicit membership rather than control of an email domain.
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
