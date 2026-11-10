"""Helpers for service tests that need real tenant membership records."""

from backend.app.models.tenancy import Organization, Tenant, TenantMembership
from backend.app.models.user import User


def ensure_test_membership(db, user_id: int, email: str, tenant_id: int | None = None) -> int:
    membership_query = db.query(TenantMembership).filter(
        TenantMembership.user_id == user_id,
        TenantMembership.status == "active",
    )
    if tenant_id is not None:
        membership_query = membership_query.filter(TenantMembership.tenant_id == tenant_id)
    membership = membership_query.order_by(
        TenantMembership.is_default.desc(), TenantMembership.id
    ).first()
    if membership is not None:
        return membership.tenant_id

    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        user = User(id=user_id, email=email, password="test")
        db.add(user)
        db.flush()

    if tenant_id is None:
        organization = Organization(
            slug=f"test-user-{user_id}",
            name="Test organization",
            org_type="enterprise",
        )
        db.add(organization)
        db.flush()
        tenant = Tenant(
            organization_id=organization.id,
            slug="default",
            name="Test tenant",
            is_default=True,
        )
        db.add(tenant)
        db.flush()
        tenant_id = tenant.id

    db.add(
        TenantMembership(
            tenant_id=tenant_id,
            user_id=user_id,
            org_role="member",
            status="active",
            is_default=True,
        )
    )
    db.commit()
    return tenant_id
