"""Multi-tenant SaaS core persistence (Phase 8, Milestones 1-3).

All tables are **additive** — nothing from Phases 1-7 is modified. Schema is
created by the Alembic migration ``c9d0e1f2a3b4_saas_platform_phase8`` (never
``create_all`` in the app).

Tenancy hierarchy (top to bottom)::

    Organization              legal / billing entity (the SaaS customer, e.g. a bank)
      └── Tenant              isolation boundary — the primary scoping key
            ├── BusinessUnit  optional org sub-structure
            │     └── Department
            │           └── Team
            └── Workspace
                  └── Project

Every Phase 8 domain row carries a ``tenant_id``. ``Tenant`` is the single
isolation key enforced by the tenant-aware middleware, repositories and cache.
Users are linked to tenants through :class:`TenantMembership` (a user may belong
to several tenants); the legacy single-tenant ``users`` table is untouched.

White-label branding (M3) lives here too: :class:`TenantBranding` and
:class:`CustomDomain`.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean, Column, DateTime, ForeignKey, Integer, JSON, String, Text,
    UniqueConstraint,
)

from backend.app.db.database import Base


class Organization(Base):
    """Top-level legal / billing entity. One bank/NBFC/fintech = one org."""

    __tablename__ = "organizations"

    id = Column(Integer, primary_key=True, index=True)
    slug = Column(String, nullable=False, unique=True, index=True)
    name = Column(String, nullable=False)
    legal_name = Column(String, nullable=True)
    org_type = Column(String, nullable=False, default="bank")  # bank|nbfc|fintech|credit_union|regulator|enterprise
    status = Column(String, nullable=False, default="active", index=True)  # active|suspended|closed
    # Regional / locale defaults (inherited by tenants unless overridden).
    country = Column(String, nullable=True, default="IN")
    timezone = Column(String, nullable=True, default="Asia/Kolkata")
    currency = Column(String, nullable=True, default="INR")
    locale = Column(String, nullable=True, default="en-IN")
    settings = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Tenant(Base):
    """The isolation boundary. Every scoped entity references ``tenant_id``."""

    __tablename__ = "tenants"
    __table_args__ = (UniqueConstraint("organization_id", "slug", name="uq_tenant_org_slug"),)

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    slug = Column(String, nullable=False, index=True)
    name = Column(String, nullable=False)
    status = Column(String, nullable=False, default="active", index=True)  # active|suspended|closed
    is_default = Column(Boolean, nullable=False, default=False)
    # Optional per-tenant overrides of the org locale defaults.
    timezone = Column(String, nullable=True)
    currency = Column(String, nullable=True)
    locale = Column(String, nullable=True)
    # Per-tenant data-encryption key reference (see services/saas/security).
    encryption_key_ref = Column(String, nullable=True)
    settings = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class BusinessUnit(Base):
    __tablename__ = "business_units"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    name = Column(String, nullable=False)
    code = Column(String, nullable=True)
    parent_id = Column(Integer, ForeignKey("business_units.id"), nullable=True)
    # Branch office metadata (address, region, cost centre) — free-form.
    metadata_json = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)


class Department(Base):
    __tablename__ = "departments"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    business_unit_id = Column(Integer, ForeignKey("business_units.id"), nullable=True, index=True)
    name = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class Team(Base):
    __tablename__ = "teams"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=True, index=True)
    name = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class Workspace(Base):
    __tablename__ = "workspaces"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    name = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id"), nullable=True, index=True)
    name = Column(String, nullable=False)
    status = Column(String, nullable=False, default="active")
    created_at = Column(DateTime, default=datetime.utcnow)


class TenantMembership(Base):
    """Links a legacy :class:`~backend.app.models.user.User` to a tenant.

    ``org_role`` is a coarse tenant-level role (owner|admin|member|billing|
    viewer) distinct from the fine-grained RBAC roles in Phase 5 — it governs
    *organization* actions (invite users, manage billing) rather than credit
    workflow permissions.
    """

    __tablename__ = "tenant_memberships"
    __table_args__ = (UniqueConstraint("tenant_id", "user_id", name="uq_membership_tenant_user"),)

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    org_role = Column(String, nullable=False, default="member")  # owner|admin|member|billing|viewer
    status = Column(String, nullable=False, default="active")  # active|invited|suspended
    business_unit_id = Column(Integer, ForeignKey("business_units.id"), nullable=True)
    team_id = Column(Integer, ForeignKey("teams.id"), nullable=True)
    is_default = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class TenantInvitation(Base):
    __tablename__ = "tenant_invitations"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    email = Column(String, nullable=False, index=True)
    org_role = Column(String, nullable=False, default="member")
    rbac_role = Column(String, nullable=True)  # Phase 5 role to grant on acceptance
    token = Column(String, nullable=False, unique=True, index=True)
    status = Column(String, nullable=False, default="pending", index=True)  # pending|accepted|revoked|expired
    invited_by = Column(String, nullable=True)
    expires_at = Column(DateTime, nullable=True)
    accepted_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


# ===========================================================================
# M3 — White-label branding
# ===========================================================================
class TenantBranding(Base):
    """Per-tenant white-label configuration (one row per tenant)."""

    __tablename__ = "tenant_branding"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, unique=True, index=True)
    logo_url = Column(String, nullable=True)
    logo_dark_url = Column(String, nullable=True)
    favicon_url = Column(String, nullable=True)
    # Theme tokens: primary/secondary/accent colours, typography, radius, etc.
    theme = Column(JSON, nullable=False, default=dict)
    # Email branding (from-name, footer, header image, template overrides).
    email_branding = Column(JSON, nullable=False, default=dict)
    # Login-page customisation (hero image, tagline, background).
    login_page = Column(JSON, nullable=False, default=dict)
    # Dashboard layout preferences + custom report headers.
    dashboard_config = Column(JSON, nullable=False, default=dict)
    # Feature visibility toggles + tenant-specific navigation ordering.
    feature_visibility = Column(JSON, nullable=False, default=dict)
    navigation = Column(JSON, nullable=False, default=list)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class CustomDomain(Base):
    __tablename__ = "custom_domains"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    domain = Column(String, nullable=False, unique=True, index=True)
    status = Column(String, nullable=False, default="pending")  # pending|verifying|active|failed
    verification_token = Column(String, nullable=True)
    is_primary = Column(Boolean, nullable=False, default=False)
    ssl_status = Column(String, nullable=False, default="none")  # none|provisioning|active
    verified_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
