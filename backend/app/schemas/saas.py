"""Request schemas for the Phase 8 SaaS platform APIs."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# --- Tenancy / organizations ------------------------------------------------
class OrganizationCreate(BaseModel):
    slug: str
    name: str
    org_type: str = Field("bank", pattern="^(bank|nbfc|fintech|credit_union|regulator|enterprise)$")
    legal_name: Optional[str] = None
    country: str = "IN"
    timezone: str = "Asia/Kolkata"
    currency: str = "INR"
    locale: str = "en-IN"


class TenantCreate(BaseModel):
    slug: str
    name: str


class NamedCreate(BaseModel):
    name: str
    code: Optional[str] = None
    parent_id: Optional[int] = None
    business_unit_id: Optional[int] = None
    department_id: Optional[int] = None
    workspace_id: Optional[int] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class MemberAdd(BaseModel):
    user_id: int
    org_role: str = "member"


class InvitationCreate(BaseModel):
    email: str
    org_role: str = "member"
    rbac_role: Optional[str] = None
    ttl_hours: int = 168


class InvitationAccept(BaseModel):
    token: str


class CustomDomainCreate(BaseModel):
    domain: str
    is_primary: bool = False


# --- Branding ---------------------------------------------------------------
class BrandingUpdate(BaseModel):
    logo_url: Optional[str] = None
    logo_dark_url: Optional[str] = None
    favicon_url: Optional[str] = None
    theme: Optional[Dict[str, Any]] = None
    email_branding: Optional[Dict[str, Any]] = None
    login_page: Optional[Dict[str, Any]] = None
    dashboard_config: Optional[Dict[str, Any]] = None
    feature_visibility: Optional[Dict[str, Any]] = None
    navigation: Optional[List[Dict[str, Any]]] = None


# --- Billing ----------------------------------------------------------------
class SubscribeRequest(BaseModel):
    plan_code: str
    seats: int = 1
    trial_days: int = 0


class ChangePlanRequest(BaseModel):
    plan_code: str


class UsageRecordRequest(BaseModel):
    meter: str
    quantity: float
    tenant_id: Optional[int] = None


class CustomPlanCreate(BaseModel):
    code: str
    name: str
    base_price: float
    limits: Dict[str, Any] = Field(default_factory=dict)
    unit_prices: Dict[str, Any] = Field(default_factory=dict)
    features: List[str] = Field(default_factory=list)


# --- Feature flags ----------------------------------------------------------
class FlagUpsert(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    enabled: Optional[bool] = None
    rollout_percentage: Optional[float] = None
    kind: Optional[str] = None
    target_roles: Optional[List[str]] = None
    dependencies: Optional[List[str]] = None


class FlagOverrideRequest(BaseModel):
    tenant_id: int
    enabled: bool
    reason: Optional[str] = None


# --- Jobs -------------------------------------------------------------------
class JobEnqueue(BaseModel):
    job_type: str
    payload: Dict[str, Any] = Field(default_factory=dict)
    queue: str = "default"
    priority: int = 5
    max_attempts: int = 3
    idempotency_key: Optional[str] = None


class ScheduleCreate(BaseModel):
    name: str
    job_type: str
    interval_seconds: int = 3600
    queue: str = "default"
    payload: Dict[str, Any] = Field(default_factory=dict)


# --- Storage ----------------------------------------------------------------
class StoreObjectRequest(BaseModel):
    key: str
    content_base64: str
    bucket: str = "default"
    content_type: Optional[str] = None
    encrypt: bool = False
    lifecycle_policy: Optional[str] = None


# --- Security ---------------------------------------------------------------
class SecretStore(BaseModel):
    name: str
    value: str


class IpAllowCreate(BaseModel):
    cidr: str
    description: Optional[str] = None


class DeviceRegister(BaseModel):
    fingerprint: str
    name: Optional[str] = None
    platform: Optional[str] = None


class IdpConfigure(BaseModel):
    protocol: str = Field("oidc", pattern="^(oidc|saml|scim)$")
    display_name: Optional[str] = None
    config: Dict[str, Any] = Field(default_factory=dict)
    client_secret: Optional[str] = None
    enabled: bool = False
    mfa_required: bool = False


class RateLimitCheck(BaseModel):
    key: str
    limit: int = 100
    window_seconds: float = 60.0
