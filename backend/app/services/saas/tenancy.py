"""Tenancy + organization-management service (Phase 8, M1 & M2).

Pure service functions over the tenancy models. Organization creation always
provisions a default tenant so the hierarchy is never empty. The org-structure
helpers (business units / departments / teams / workspaces / projects) and the
membership + invitation flows all go through the tenant scope.
"""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from backend.app.models.tenancy import (
    BusinessUnit, CustomDomain, Department, Organization, Project, Team,
    Tenant, TenantInvitation, TenantMembership, Workspace,
)
from backend.app.models.user import User

_ORG_TYPES = {"bank", "nbfc", "fintech", "credit_union", "regulator", "enterprise"}
_ORG_ROLES = {"owner", "admin", "member", "billing", "viewer"}


# ===========================================================================
# Organizations + tenants
# ===========================================================================
def create_organization(
    db: Session,
    *,
    slug: str,
    name: str,
    org_type: str = "bank",
    legal_name: Optional[str] = None,
    country: str = "IN",
    timezone: str = "Asia/Kolkata",
    currency: str = "INR",
    locale: str = "en-IN",
    tenant_slug: str = "default",
    settings: Optional[Dict[str, Any]] = None,
) -> Organization:
    if org_type not in _ORG_TYPES:
        raise ValueError(f"invalid org_type: {org_type}")
    if db.query(Organization).filter(Organization.slug == slug).first():
        raise ValueError(f"organization slug already exists: {slug}")
    org = Organization(
        slug=slug, name=name, org_type=org_type, legal_name=legal_name,
        country=country, timezone=timezone, currency=currency, locale=locale,
        settings=settings or {},
    )
    db.add(org)
    db.flush()
    # Every org gets a default tenant.
    create_tenant(db, org.id, slug=tenant_slug, name=name, is_default=True)
    db.commit()
    db.refresh(org)
    return org


def create_tenant(
    db: Session,
    organization_id: int,
    *,
    slug: str,
    name: str,
    is_default: bool = False,
) -> Tenant:
    org = db.query(Organization).get(organization_id)
    if org is None:
        raise ValueError("organization not found")
    if db.query(Tenant).filter(Tenant.organization_id == organization_id,
                               Tenant.slug == slug).first():
        raise ValueError(f"tenant slug already exists in org: {slug}")
    tenant = Tenant(
        organization_id=organization_id, slug=slug, name=name,
        is_default=is_default,
    )
    db.add(tenant)
    db.flush()
    return tenant


def get_organization(db: Session, org_id: int) -> Optional[Organization]:
    return db.query(Organization).get(org_id)


def list_organizations(db: Session) -> List[Organization]:
    return db.query(Organization).order_by(Organization.id).all()


def get_tenant(db: Session, tenant_id: int) -> Optional[Tenant]:
    return db.query(Tenant).get(tenant_id)


def get_tenant_by_slug(db: Session, org_slug: str, tenant_slug: str) -> Optional[Tenant]:
    return (
        db.query(Tenant)
        .join(Organization, Tenant.organization_id == Organization.id)
        .filter(Organization.slug == org_slug, Tenant.slug == tenant_slug)
        .first()
    )


def list_tenants(db: Session, organization_id: int) -> List[Tenant]:
    return db.query(Tenant).filter(Tenant.organization_id == organization_id).all()


def default_tenant(db: Session, organization_id: int) -> Optional[Tenant]:
    return (
        db.query(Tenant)
        .filter(Tenant.organization_id == organization_id, Tenant.is_default.is_(True))
        .first()
    )


def set_tenant_status(db: Session, tenant_id: int, status: str) -> Tenant:
    tenant = db.query(Tenant).get(tenant_id)
    if tenant is None:
        raise ValueError("tenant not found")
    tenant.status = status
    db.commit()
    db.refresh(tenant)
    return tenant


# ===========================================================================
# Organization structure (tenant-scoped)
# ===========================================================================
def create_business_unit(db: Session, tenant_id: int, name: str, *,
                          code: Optional[str] = None, parent_id: Optional[int] = None,
                          metadata: Optional[Dict[str, Any]] = None) -> BusinessUnit:
    bu = BusinessUnit(tenant_id=tenant_id, name=name, code=code,
                      parent_id=parent_id, metadata_json=metadata or {})
    db.add(bu)
    db.commit()
    db.refresh(bu)
    return bu


def create_department(db: Session, tenant_id: int, name: str, *,
                      business_unit_id: Optional[int] = None) -> Department:
    dept = Department(tenant_id=tenant_id, name=name, business_unit_id=business_unit_id)
    db.add(dept)
    db.commit()
    db.refresh(dept)
    return dept


def create_team(db: Session, tenant_id: int, name: str, *,
                department_id: Optional[int] = None) -> Team:
    team = Team(tenant_id=tenant_id, name=name, department_id=department_id)
    db.add(team)
    db.commit()
    db.refresh(team)
    return team


def create_workspace(db: Session, tenant_id: int, name: str) -> Workspace:
    ws = Workspace(tenant_id=tenant_id, name=name)
    db.add(ws)
    db.commit()
    db.refresh(ws)
    return ws


def create_project(db: Session, tenant_id: int, name: str, *,
                   workspace_id: Optional[int] = None) -> Project:
    proj = Project(tenant_id=tenant_id, name=name, workspace_id=workspace_id)
    db.add(proj)
    db.commit()
    db.refresh(proj)
    return proj


def get_hierarchy(db: Session, tenant_id: int) -> Dict[str, Any]:
    """A nested snapshot of a tenant's org structure for the UI."""
    bus = db.query(BusinessUnit).filter(BusinessUnit.tenant_id == tenant_id).all()
    depts = db.query(Department).filter(Department.tenant_id == tenant_id).all()
    teams = db.query(Team).filter(Team.tenant_id == tenant_id).all()
    workspaces = db.query(Workspace).filter(Workspace.tenant_id == tenant_id).all()
    projects = db.query(Project).filter(Project.tenant_id == tenant_id).all()

    def team_dict(t: Team):
        return {"id": t.id, "name": t.name}

    def dept_dict(d: Department):
        return {"id": d.id, "name": d.name,
                "teams": [team_dict(t) for t in teams if t.department_id == d.id]}

    def bu_dict(b: BusinessUnit):
        return {"id": b.id, "name": b.name, "code": b.code,
                "departments": [dept_dict(d) for d in depts if d.business_unit_id == b.id]}

    return {
        "tenant_id": tenant_id,
        "business_units": [bu_dict(b) for b in bus],
        "unassigned_departments": [dept_dict(d) for d in depts if d.business_unit_id is None],
        "workspaces": [
            {"id": w.id, "name": w.name,
             "projects": [{"id": p.id, "name": p.name} for p in projects if p.workspace_id == w.id]}
            for w in workspaces
        ],
    }


# ===========================================================================
# Membership + invitations (M2)
# ===========================================================================
def add_member(db: Session, tenant_id: int, user_id: int, *,
               org_role: str = "member", is_default: bool = False) -> TenantMembership:
    if org_role not in _ORG_ROLES:
        raise ValueError(f"invalid org_role: {org_role}")
    existing = (
        db.query(TenantMembership)
        .filter(TenantMembership.tenant_id == tenant_id,
                TenantMembership.user_id == user_id)
        .first()
    )
    if existing:
        existing.org_role = org_role
        existing.status = "active"
        db.commit()
        db.refresh(existing)
        return existing
    m = TenantMembership(tenant_id=tenant_id, user_id=user_id,
                         org_role=org_role, status="active", is_default=is_default)
    db.add(m)
    db.commit()
    db.refresh(m)
    return m


def list_members(db: Session, tenant_id: int) -> List[TenantMembership]:
    return db.query(TenantMembership).filter(
        TenantMembership.tenant_id == tenant_id).all()


def user_tenants(db: Session, user_id: int) -> List[TenantMembership]:
    return db.query(TenantMembership).filter(
        TenantMembership.user_id == user_id,
        TenantMembership.status == "active").all()


def is_member(db: Session, tenant_id: int, user_id: int) -> bool:
    return (
        db.query(TenantMembership)
        .filter(TenantMembership.tenant_id == tenant_id,
                TenantMembership.user_id == user_id,
                TenantMembership.status == "active")
        .first()
        is not None
    )


def create_invitation(db: Session, tenant_id: int, email: str, *,
                      org_role: str = "member", rbac_role: Optional[str] = None,
                      invited_by: Optional[str] = None, ttl_hours: int = 168) -> TenantInvitation:
    if org_role not in _ORG_ROLES:
        raise ValueError(f"invalid org_role: {org_role}")
    inv = TenantInvitation(
        tenant_id=tenant_id, email=email.lower().strip(), org_role=org_role,
        rbac_role=rbac_role, invited_by=invited_by,
        token=secrets.token_urlsafe(24),
        expires_at=datetime.utcnow() + timedelta(hours=ttl_hours),
    )
    db.add(inv)
    db.commit()
    db.refresh(inv)
    return inv


def list_invitations(db: Session, tenant_id: int) -> List[TenantInvitation]:
    return db.query(TenantInvitation).filter(
        TenantInvitation.tenant_id == tenant_id).all()


def accept_invitation(db: Session, token: str, user: User) -> TenantMembership:
    inv = db.query(TenantInvitation).filter(TenantInvitation.token == token).first()
    if inv is None:
        raise ValueError("invitation not found")
    if inv.status != "pending":
        raise ValueError(f"invitation is {inv.status}")
    if inv.expires_at and inv.expires_at < datetime.utcnow():
        inv.status = "expired"
        db.commit()
        raise ValueError("invitation expired")
    membership = add_member(db, inv.tenant_id, user.id, org_role=inv.org_role)
    # Grant the mapped Phase-5 RBAC role, if any (idempotent).
    if inv.rbac_role:
        try:
            from backend.app.services.rbac.seeding import assign_role
            assign_role(db, user, inv.rbac_role)
        except Exception:
            db.rollback()
    inv.status = "accepted"
    inv.accepted_at = datetime.utcnow()
    db.commit()
    db.refresh(membership)
    return membership


def revoke_invitation(db: Session, tenant_id: int, invitation_id: int) -> TenantInvitation:
    inv = (
        db.query(TenantInvitation)
        .filter(TenantInvitation.id == invitation_id,
                TenantInvitation.tenant_id == tenant_id)
        .first()
    )
    if inv is None:
        raise ValueError("invitation not found")
    inv.status = "revoked"
    db.commit()
    db.refresh(inv)
    return inv


# ===========================================================================
# Custom domains (M3 helper — branding module owns the theme surface)
# ===========================================================================
def add_custom_domain(db: Session, tenant_id: int, domain: str, *,
                      is_primary: bool = False) -> CustomDomain:
    cd = CustomDomain(
        tenant_id=tenant_id, domain=domain.lower().strip(),
        verification_token=secrets.token_hex(16), is_primary=is_primary,
    )
    db.add(cd)
    db.commit()
    db.refresh(cd)
    return cd


def verify_custom_domain(db: Session, tenant_id: int, domain_id: int) -> CustomDomain:
    cd = (
        db.query(CustomDomain)
        .filter(CustomDomain.id == domain_id, CustomDomain.tenant_id == tenant_id)
        .first()
    )
    if cd is None:
        raise ValueError("domain not found")
    cd.status = "active"
    cd.ssl_status = "active"
    cd.verified_at = datetime.utcnow()
    db.commit()
    db.refresh(cd)
    return cd


def resolve_tenant_by_domain(db: Session, domain: str) -> Optional[Tenant]:
    cd = (
        db.query(CustomDomain)
        .filter(CustomDomain.domain == domain.lower().strip(),
                CustomDomain.status == "active")
        .first()
    )
    return db.query(Tenant).get(cd.tenant_id) if cd else None
