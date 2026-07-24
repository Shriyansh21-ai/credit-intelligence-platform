"""Multi-Tenant Enterprise SaaS Platform APIs (Phase 8).

A set of focused, additive routers exposing the whole SaaS surface under
``/api/saas/*`` (plus unauthenticated k8s probes at the root). Every router is
new; no existing route is modified.

    /api/saas/tenancy         organizations, tenants, hierarchy, members, invites
    /api/saas/branding        white-label theming + custom domains
    /api/saas/billing         plans, subscriptions, usage, invoices, analytics
    /api/saas/flags           feature flags + overrides + evaluation
    /api/saas/jobs            background job platform + schedules + DLQ
    /api/saas/storage         cloud object storage + signed URLs
    /api/saas/realtime        activity stream, presence, live WebSocket
    /api/saas/observability   tracing, metrics, health, errors
    /api/saas/cache           tenant-aware cache admin
    /api/saas/security        secrets, sessions, devices, IP allow-list, IdPs
    /api/saas/analytics       SaaS executive analytics
    /api/saas/admin           super-admin console (cross-tenant)
    /healthz /livez /readyz   deployment probes (M11)
"""

from __future__ import annotations

import base64
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from backend.app.core.dependencies import get_current_user
from backend.app.db.database import get_db
from backend.app.models.user import User
from backend.app.schemas.saas import (
    BrandingUpdate, ChangePlanRequest, CustomDomainCreate, CustomPlanCreate,
    DeviceRegister, FlagOverrideRequest, FlagUpsert, IdpConfigure, InvitationAccept,
    InvitationCreate, IpAllowCreate, JobEnqueue, MemberAdd, NamedCreate,
    OrganizationCreate, RateLimitCheck, ScheduleCreate, SecretStore,
    StoreObjectRequest, SubscribeRequest, TenantCreate, UsageRecordRequest,
)
from backend.app.services import audit
from backend.app.services.rbac import require_permission, user_role_names
from backend.app.services.saas import admin as admin_svc
from backend.app.services.saas import analytics as analytics_svc
from backend.app.services.saas import branding as branding_svc
from backend.app.services.saas import context as tenant_ctx
from backend.app.services.saas import jobs as jobs_svc
from backend.app.services.saas import observability as obs_svc
from backend.app.services.saas import realtime as realtime_svc
from backend.app.services.saas import security as security_svc
from backend.app.services.saas import storage as storage_svc
from backend.app.services.saas import tenancy as tenancy_svc
from backend.app.services.saas.billing import service as billing_svc
from backend.app.services.saas.cache import platform_cache
from backend.app.services.saas.flags import service as flags_svc


def _tenant_scope(explicit: Optional[int]) -> int:
    tid = explicit if explicit is not None else tenant_ctx.current_tenant_id()
    if tid is None:
        raise HTTPException(status_code=400, detail="tenant scope required (X-Tenant-ID header or tenant_id)")
    return tid


def _bad_request(exc: Exception):
    raise HTTPException(status_code=400, detail=str(exc))


# ===========================================================================
# Tenancy + organization management (M1, M2)
# ===========================================================================
tenancy_router = APIRouter(prefix="/api/saas/tenancy", tags=["SaaS: Tenancy"])


@tenancy_router.get("/organizations")
def list_orgs(db: Session = Depends(get_db), _u=Depends(require_permission("tenancy.view"))):
    return [{"id": o.id, "slug": o.slug, "name": o.name, "org_type": o.org_type,
             "status": o.status} for o in tenancy_svc.list_organizations(db)]


@tenancy_router.post("/organizations")
def create_org(body: OrganizationCreate, db: Session = Depends(get_db),
               actor: User = Depends(require_permission("tenancy.manage"))):
    try:
        org = tenancy_svc.create_organization(
            db, slug=body.slug, name=body.name, org_type=body.org_type,
            legal_name=body.legal_name, country=body.country, timezone=body.timezone,
            currency=body.currency, locale=body.locale)
    except ValueError as e:
        _bad_request(e)
    audit.record_safe(db, action="saas.org.create", actor=actor,
                      entity_type="organization", entity_id=org.id)
    return {"id": org.id, "slug": org.slug, "name": org.name}


@tenancy_router.get("/organizations/{org_id}/tenants")
def list_tenants(org_id: int, db: Session = Depends(get_db),
                 _u=Depends(require_permission("tenancy.view"))):
    return [{"id": t.id, "slug": t.slug, "name": t.name, "status": t.status,
             "is_default": t.is_default} for t in tenancy_svc.list_tenants(db, org_id)]


@tenancy_router.post("/organizations/{org_id}/tenants")
def create_tenant(org_id: int, body: TenantCreate, db: Session = Depends(get_db),
                  actor: User = Depends(require_permission("tenancy.manage"))):
    try:
        t = tenancy_svc.create_tenant(db, org_id, slug=body.slug, name=body.name)
        db.commit()
    except ValueError as e:
        _bad_request(e)
    return {"id": t.id, "slug": t.slug, "name": t.name}


@tenancy_router.get("/tenants/{tenant_id}/hierarchy")
def hierarchy(tenant_id: int, db: Session = Depends(get_db),
              _u=Depends(require_permission("tenancy.view"))):
    return tenancy_svc.get_hierarchy(db, tenant_id)


@tenancy_router.post("/tenants/{tenant_id}/business-units")
def add_bu(tenant_id: int, body: NamedCreate, db: Session = Depends(get_db),
           _u=Depends(require_permission("tenancy.manage"))):
    bu = tenancy_svc.create_business_unit(db, tenant_id, body.name, code=body.code,
                                          parent_id=body.parent_id, metadata=body.metadata)
    return {"id": bu.id, "name": bu.name}


@tenancy_router.post("/tenants/{tenant_id}/departments")
def add_dept(tenant_id: int, body: NamedCreate, db: Session = Depends(get_db),
             _u=Depends(require_permission("tenancy.manage"))):
    d = tenancy_svc.create_department(db, tenant_id, body.name,
                                      business_unit_id=body.business_unit_id)
    return {"id": d.id, "name": d.name}


@tenancy_router.post("/tenants/{tenant_id}/teams")
def add_team(tenant_id: int, body: NamedCreate, db: Session = Depends(get_db),
             _u=Depends(require_permission("tenancy.manage"))):
    t = tenancy_svc.create_team(db, tenant_id, body.name, department_id=body.department_id)
    return {"id": t.id, "name": t.name}


@tenancy_router.post("/tenants/{tenant_id}/workspaces")
def add_ws(tenant_id: int, body: NamedCreate, db: Session = Depends(get_db),
           _u=Depends(require_permission("tenancy.manage"))):
    w = tenancy_svc.create_workspace(db, tenant_id, body.name)
    return {"id": w.id, "name": w.name}


@tenancy_router.post("/tenants/{tenant_id}/projects")
def add_project(tenant_id: int, body: NamedCreate, db: Session = Depends(get_db),
                _u=Depends(require_permission("tenancy.manage"))):
    p = tenancy_svc.create_project(db, tenant_id, body.name, workspace_id=body.workspace_id)
    return {"id": p.id, "name": p.name}


@tenancy_router.get("/tenants/{tenant_id}/members")
def list_members(tenant_id: int, db: Session = Depends(get_db),
                 _u=Depends(require_permission("tenancy.view"))):
    return [{"id": m.id, "user_id": m.user_id, "org_role": m.org_role,
             "status": m.status} for m in tenancy_svc.list_members(db, tenant_id)]


@tenancy_router.post("/tenants/{tenant_id}/members")
def add_member(tenant_id: int, body: MemberAdd, db: Session = Depends(get_db),
               _u=Depends(require_permission("tenancy.manage"))):
    try:
        m = tenancy_svc.add_member(db, tenant_id, body.user_id, org_role=body.org_role)
    except ValueError as e:
        _bad_request(e)
    return {"id": m.id, "user_id": m.user_id, "org_role": m.org_role}


@tenancy_router.get("/tenants/{tenant_id}/invitations")
def list_invites(tenant_id: int, db: Session = Depends(get_db),
                 _u=Depends(require_permission("tenancy.view"))):
    return [{"id": i.id, "email": i.email, "org_role": i.org_role,
             "status": i.status} for i in tenancy_svc.list_invitations(db, tenant_id)]


@tenancy_router.post("/tenants/{tenant_id}/invitations")
def invite(tenant_id: int, body: InvitationCreate, db: Session = Depends(get_db),
           actor: User = Depends(require_permission("tenancy.manage"))):
    try:
        inv = tenancy_svc.create_invitation(
            db, tenant_id, body.email, org_role=body.org_role,
            rbac_role=body.rbac_role, invited_by=getattr(actor, "email", None),
            ttl_hours=body.ttl_hours)
    except ValueError as e:
        _bad_request(e)
    return {"id": inv.id, "email": inv.email, "token": inv.token, "status": inv.status}


@tenancy_router.post("/invitations/accept")
def accept_invite(body: InvitationAccept, db: Session = Depends(get_db),
                  user: User = Depends(get_current_user)):
    try:
        m = tenancy_svc.accept_invitation(db, body.token, user)
    except ValueError as e:
        _bad_request(e)
    return {"tenant_id": m.tenant_id, "org_role": m.org_role, "status": m.status}


# ===========================================================================
# White-label branding (M3)
# ===========================================================================
branding_router = APIRouter(prefix="/api/saas/branding", tags=["SaaS: Branding"])


@branding_router.get("/tenants/{tenant_id}")
def get_branding(tenant_id: int, db: Session = Depends(get_db),
                 _u=Depends(require_permission("branding.view"))):
    return branding_svc.get_branding(db, tenant_id)


@branding_router.put("/tenants/{tenant_id}")
def update_branding(tenant_id: int, body: BrandingUpdate, db: Session = Depends(get_db),
                    _u=Depends(require_permission("branding.manage"))):
    return branding_svc.update_branding(db, tenant_id, body.model_dump(exclude_none=True))


@branding_router.post("/tenants/{tenant_id}/domains")
def add_domain(tenant_id: int, body: CustomDomainCreate, db: Session = Depends(get_db),
               _u=Depends(require_permission("branding.manage"))):
    cd = tenancy_svc.add_custom_domain(db, tenant_id, body.domain, is_primary=body.is_primary)
    return {"id": cd.id, "domain": cd.domain, "status": cd.status,
            "verification_token": cd.verification_token}


@branding_router.post("/tenants/{tenant_id}/domains/{domain_id}/verify")
def verify_domain(tenant_id: int, domain_id: int, db: Session = Depends(get_db),
                  _u=Depends(require_permission("branding.manage"))):
    try:
        cd = tenancy_svc.verify_custom_domain(db, tenant_id, domain_id)
    except ValueError as e:
        _bad_request(e)
    return {"id": cd.id, "domain": cd.domain, "status": cd.status, "ssl_status": cd.ssl_status}


# ===========================================================================
# Billing (M4)
# ===========================================================================
billing_router = APIRouter(prefix="/api/saas/billing", tags=["SaaS: Billing"])


@billing_router.get("/plans")
def list_plans(org_id: Optional[int] = None, db: Session = Depends(get_db),
               _u=Depends(require_permission("billing.view"))):
    return [{"code": p.code, "name": p.name, "tier": p.tier, "base_price": p.base_price,
             "limits": p.limits, "features": p.features}
            for p in billing_svc.list_plans(db, org_id)]


@billing_router.post("/orgs/{org_id}/subscribe")
def subscribe(org_id: int, body: SubscribeRequest, db: Session = Depends(get_db),
              actor: User = Depends(require_permission("billing.manage"))):
    try:
        sub = billing_svc.subscribe(db, org_id, body.plan_code, seats=body.seats,
                                    trial_days=body.trial_days,
                                    actor=getattr(actor, "email", None))
    except ValueError as e:
        _bad_request(e)
    return {"id": sub.id, "plan_id": sub.plan_id, "status": sub.status, "seats": sub.seats}


@billing_router.post("/orgs/{org_id}/change-plan")
def change_plan(org_id: int, body: ChangePlanRequest, db: Session = Depends(get_db),
                actor: User = Depends(require_permission("billing.manage"))):
    try:
        sub = billing_svc.change_plan(db, org_id, body.plan_code,
                                      actor=getattr(actor, "email", None))
    except ValueError as e:
        _bad_request(e)
    return {"id": sub.id, "plan_id": sub.plan_id, "status": sub.status}


@billing_router.post("/orgs/{org_id}/cancel")
def cancel(org_id: int, db: Session = Depends(get_db),
           actor: User = Depends(require_permission("billing.manage"))):
    try:
        sub = billing_svc.cancel_subscription(db, org_id, actor=getattr(actor, "email", None))
    except ValueError as e:
        _bad_request(e)
    return {"id": sub.id, "status": sub.status, "cancel_at_period_end": sub.cancel_at_period_end}


@billing_router.post("/orgs/{org_id}/custom-plan")
def custom_plan(org_id: int, body: CustomPlanCreate, db: Session = Depends(get_db),
                _u=Depends(require_permission("billing.manage"))):
    p = billing_svc.create_custom_plan(db, org_id, code=body.code, name=body.name,
                                       base_price=body.base_price, limits=body.limits,
                                       unit_prices=body.unit_prices, features=body.features)
    return {"code": p.code, "tier": p.tier}


@billing_router.post("/orgs/{org_id}/usage")
def record_usage(org_id: int, body: UsageRecordRequest, db: Session = Depends(get_db),
                 _u=Depends(require_permission("billing.manage"))):
    rec = billing_svc.record_usage(db, org_id, body.meter, body.quantity,
                                   tenant_id=body.tenant_id)
    return {"id": rec.id, "meter": rec.meter, "quantity": rec.quantity, "period": rec.period}


@billing_router.get("/orgs/{org_id}/usage")
def usage_summary(org_id: int, db: Session = Depends(get_db),
                  _u=Depends(require_permission("billing.view"))):
    return billing_svc.usage_summary(db, org_id)


@billing_router.get("/orgs/{org_id}/quota/{meter}")
def check_quota(org_id: int, meter: str, additional: float = 0.0,
                db: Session = Depends(get_db), _u=Depends(require_permission("billing.view"))):
    return billing_svc.check_quota(db, org_id, meter, additional=additional)


@billing_router.post("/orgs/{org_id}/invoices")
def generate_invoice(org_id: int, period: Optional[str] = None, db: Session = Depends(get_db),
                     _u=Depends(require_permission("billing.manage"))):
    try:
        inv = billing_svc.generate_invoice(db, org_id, period=period)
    except ValueError as e:
        _bad_request(e)
    return {"id": inv.id, "number": inv.number, "total": inv.total, "status": inv.status,
            "lines": [{"description": l.description, "amount": l.amount, "kind": l.kind}
                      for l in billing_svc.invoice_lines(db, inv.id)]}


@billing_router.post("/invoices/{invoice_id}/pay")
def pay_invoice(invoice_id: int, db: Session = Depends(get_db),
                _u=Depends(require_permission("billing.manage"))):
    try:
        inv = billing_svc.pay_invoice(db, invoice_id)
    except ValueError as e:
        _bad_request(e)
    return {"id": inv.id, "status": inv.status, "provider_ref": inv.provider_ref}


@billing_router.get("/orgs/{org_id}/invoices")
def list_invoices(org_id: int, db: Session = Depends(get_db),
                  _u=Depends(require_permission("billing.view"))):
    return [{"id": i.id, "number": i.number, "total": i.total, "status": i.status,
             "period": i.period} for i in billing_svc.list_invoices(db, org_id)]


@billing_router.get("/orgs/{org_id}/analytics")
def billing_analytics(org_id: int, db: Session = Depends(get_db),
                      _u=Depends(require_permission("billing.view"))):
    return billing_svc.billing_analytics(db, org_id)


# ===========================================================================
# Feature flags (M5)
# ===========================================================================
flags_router = APIRouter(prefix="/api/saas/flags", tags=["SaaS: Feature Flags"])


@flags_router.get("")
def list_flags(db: Session = Depends(get_db), _u=Depends(require_permission("flags.view"))):
    return [{"key": f.key, "name": f.name, "enabled": f.enabled,
             "rollout_percentage": f.rollout_percentage, "kind": f.kind,
             "dependencies": f.dependencies} for f in flags_svc.list_flags(db)]


@flags_router.get("/evaluate")
def evaluate(tenant_id: Optional[int] = None, db: Session = Depends(get_db),
             user: User = Depends(get_current_user)):
    roles = user_role_names(user)
    return flags_svc.evaluate_all(db, tenant_id=tenant_id, roles=roles)


@flags_router.get("/{key}")
def get_flag(key: str, tenant_id: Optional[int] = None, db: Session = Depends(get_db),
             user: User = Depends(get_current_user)):
    roles = user_role_names(user)
    return {"key": key, "enabled": flags_svc.is_enabled(db, key, tenant_id=tenant_id, roles=roles)}


@flags_router.put("/{key}")
def upsert_flag(key: str, body: FlagUpsert, db: Session = Depends(get_db),
                _u=Depends(require_permission("flags.manage"))):
    f = flags_svc.upsert_flag(db, key, **body.model_dump(exclude_none=True))
    return {"key": f.key, "enabled": f.enabled, "rollout_percentage": f.rollout_percentage}


@flags_router.post("/{key}/override")
def set_override(key: str, body: FlagOverrideRequest, db: Session = Depends(get_db),
                 _u=Depends(require_permission("flags.manage"))):
    ov = flags_svc.set_override(db, key, body.tenant_id, body.enabled, reason=body.reason)
    return {"flag_key": ov.flag_key, "tenant_id": ov.tenant_id, "enabled": ov.enabled}


@flags_router.delete("/{key}/override/{tenant_id}")
def clear_override(key: str, tenant_id: int, db: Session = Depends(get_db),
                   _u=Depends(require_permission("flags.manage"))):
    flags_svc.clear_override(db, key, tenant_id)
    return {"cleared": True}


# ===========================================================================
# Background jobs (M6)
# ===========================================================================
jobs_router = APIRouter(prefix="/api/saas/jobs", tags=["SaaS: Background Jobs"])


@jobs_router.get("")
def list_jobs(tenant_id: Optional[int] = None, status: Optional[str] = None,
              queue: Optional[str] = None, db: Session = Depends(get_db),
              _u=Depends(require_permission("bgjobs.view"))):
    return [{"id": j.id, "job_type": j.job_type, "status": j.status, "queue": j.queue,
             "attempts": j.attempts, "progress": j.progress}
            for j in jobs_svc.list_jobs(db, tenant_id=tenant_id, status=status, queue=queue)]


@jobs_router.get("/types")
def job_types(_u=Depends(require_permission("bgjobs.view"))):
    return {"types": jobs_svc.registered_types()}


@jobs_router.post("")
def enqueue(body: JobEnqueue, tenant_id: Optional[int] = None, db: Session = Depends(get_db),
            _u=Depends(require_permission("bgjobs.manage"))):
    job = jobs_svc.enqueue(db, body.job_type, body.payload, tenant_id=tenant_id,
                           queue=body.queue, priority=body.priority,
                           max_attempts=body.max_attempts,
                           idempotency_key=body.idempotency_key)
    return {"id": job.id, "status": job.status, "job_type": job.job_type}


@jobs_router.get("/{job_id}")
def get_job(job_id: int, db: Session = Depends(get_db),
            _u=Depends(require_permission("bgjobs.view"))):
    j = jobs_svc.get_job(db, job_id)
    if j is None:
        raise HTTPException(status_code=404, detail="job not found")
    return {"id": j.id, "job_type": j.job_type, "status": j.status, "progress": j.progress,
            "attempts": j.attempts, "result": j.result, "error": j.error}


@jobs_router.post("/{job_id}/cancel")
def cancel_job(job_id: int, db: Session = Depends(get_db),
               _u=Depends(require_permission("bgjobs.manage"))):
    try:
        j = jobs_svc.cancel_job(db, job_id)
    except ValueError as e:
        _bad_request(e)
    return {"id": j.id, "status": j.status}


@jobs_router.post("/run")
def run_pending(queue: Optional[str] = None, db: Session = Depends(get_db),
                _u=Depends(require_permission("bgjobs.manage"))):
    processed = jobs_svc.run_pending(db, queue=queue)
    return {"processed": [{"id": j.id, "status": j.status} for j in processed]}


@jobs_router.get("/dlq/list")
def dead_letters(tenant_id: Optional[int] = None, db: Session = Depends(get_db),
                 _u=Depends(require_permission("bgjobs.view"))):
    return [{"id": j.id, "job_type": j.job_type, "error": j.error}
            for j in jobs_svc.dead_letters(db, tenant_id=tenant_id)]


@jobs_router.post("/dlq/{job_id}/requeue")
def requeue(job_id: int, db: Session = Depends(get_db),
            _u=Depends(require_permission("bgjobs.manage"))):
    try:
        j = jobs_svc.requeue_dead(db, job_id)
    except ValueError as e:
        _bad_request(e)
    return {"id": j.id, "status": j.status}


@jobs_router.post("/schedules")
def create_schedule(body: ScheduleCreate, tenant_id: Optional[int] = None,
                    db: Session = Depends(get_db),
                    _u=Depends(require_permission("bgjobs.manage"))):
    s = jobs_svc.create_schedule(db, body.name, body.job_type, body.interval_seconds,
                                 tenant_id=tenant_id, queue=body.queue, payload=body.payload)
    return {"id": s.id, "name": s.name, "next_run_at": s.next_run_at.isoformat() if s.next_run_at else None}


@jobs_router.post("/schedules/tick")
def tick(db: Session = Depends(get_db), _u=Depends(require_permission("bgjobs.manage"))):
    enq = jobs_svc.tick_schedules(db)
    return {"enqueued": [j.id for j in enq]}


# ===========================================================================
# Cloud storage (M7)
# ===========================================================================
storage_router = APIRouter(prefix="/api/saas/storage", tags=["SaaS: Storage"])


@storage_router.post("/tenants/{tenant_id}/objects")
def put_object(tenant_id: int, body: StoreObjectRequest, db: Session = Depends(get_db),
               _u=Depends(require_permission("storage.manage"))):
    try:
        data = base64.b64decode(body.content_base64)
    except Exception:
        raise HTTPException(status_code=400, detail="content_base64 is not valid base64")
    obj = storage_svc.put_object(db, tenant_id, body.key, data, bucket=body.bucket,
                                 content_type=body.content_type, encrypt=body.encrypt,
                                 lifecycle_policy=body.lifecycle_policy)
    return {"id": obj.id, "key": obj.key, "version": obj.current_version,
            "size_bytes": obj.size_bytes, "encrypted": obj.encrypted}


@storage_router.get("/tenants/{tenant_id}/objects")
def list_objects(tenant_id: int, bucket: Optional[str] = None, prefix: Optional[str] = None,
                 db: Session = Depends(get_db), _u=Depends(require_permission("storage.view"))):
    return [{"id": o.id, "key": o.key, "bucket": o.bucket, "version": o.current_version,
             "size_bytes": o.size_bytes} for o in storage_svc.list_objects(db, tenant_id, bucket=bucket, prefix=prefix)]


@storage_router.get("/tenants/{tenant_id}/objects/{bucket}/{key:path}")
def get_object(tenant_id: int, bucket: str, key: str, version: Optional[int] = None,
               db: Session = Depends(get_db), _u=Depends(require_permission("storage.view"))):
    try:
        data = storage_svc.get_object(db, tenant_id, key, bucket=bucket, version=version)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="object not found")
    return {"key": key, "content_base64": base64.b64encode(data).decode()}


@storage_router.post("/tenants/{tenant_id}/objects/{bucket}/{key:path}/sign")
def sign_url(tenant_id: int, bucket: str, key: str, expires_in: int = 3600,
             _u=Depends(require_permission("storage.view"))):
    return storage_svc.sign_url(tenant_id, bucket, key, expires_in=expires_in)


@storage_router.delete("/tenants/{tenant_id}/objects/{bucket}/{key:path}")
def delete_object(tenant_id: int, bucket: str, key: str, db: Session = Depends(get_db),
                  _u=Depends(require_permission("storage.manage"))):
    storage_svc.delete_object(db, tenant_id, key, bucket=bucket)
    return {"deleted": True}


# ===========================================================================
# Real-time (M8)
# ===========================================================================
realtime_router = APIRouter(prefix="/api/saas/realtime", tags=["SaaS: Real-time"])


@realtime_router.get("/activity")
def activity(tenant_id: Optional[int] = None, channel: Optional[str] = None, limit: int = 50,
             db: Session = Depends(get_db), _u=Depends(require_permission("realtime.view"))):
    return [{"id": e.id, "channel": e.channel, "event_type": e.event_type,
             "actor": e.actor, "subject": e.subject, "payload": e.payload,
             "created_at": e.created_at.isoformat() if e.created_at else None}
            for e in realtime_svc.recent_activity(db, tenant_id=tenant_id, channel=channel, limit=limit)]


@realtime_router.post("/presence")
def presence(status: str = "online", tenant_id: Optional[int] = None,
             db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    rec = realtime_svc.mark_presence(db, tenant_id, user.id, status=status)
    return {"user_id": rec.user_id, "status": rec.status}


@realtime_router.get("/presence")
def online(tenant_id: Optional[int] = None, db: Session = Depends(get_db),
           _u=Depends(require_permission("realtime.view"))):
    return [{"user_id": p.user_id, "status": p.status} for p in realtime_svc.online_users(db, tenant_id)]


@realtime_router.websocket("/ws")
async def realtime_ws(websocket: WebSocket, tenant_id: Optional[int] = Query(None),
                      channel: str = Query("global")):
    await websocket.accept()
    conn = realtime_svc.hub.connect(tenant_id=tenant_id, channels={channel})
    # Replay recent buffer on connect.
    for event in realtime_svc.hub.recent(tenant_id, channel):
        await websocket.send_json(event)
    try:
        async for event in realtime_svc.hub.stream(conn):
            await websocket.send_json(event)
    except WebSocketDisconnect:
        pass
    finally:
        realtime_svc.hub.disconnect(conn.id)


# ===========================================================================
# Observability (M9)
# ===========================================================================
observability_router = APIRouter(prefix="/api/saas/observability", tags=["SaaS: Observability"])


@observability_router.get("/metrics")
def get_metrics(_u=Depends(require_permission("observability.view"))):
    return obs_svc.metrics.snapshot()


@observability_router.get("/health")
def obs_health(db: Session = Depends(get_db), _u=Depends(require_permission("observability.view"))):
    return obs_svc.health_report(db)


@observability_router.get("/service-map")
def service_map(_u=Depends(require_permission("observability.view"))):
    return obs_svc.service_map()


@observability_router.get("/errors")
def errors(_u=Depends(require_permission("observability.view"))):
    return obs_svc.error_analytics()


@observability_router.get("/slow-queries")
def slow_queries(_u=Depends(require_permission("observability.view"))):
    return {"slow_queries": obs_svc.slow_queries()}


@observability_router.get("/traces/{correlation_id}")
def trace(correlation_id: str, db: Session = Depends(get_db),
          _u=Depends(require_permission("observability.view"))):
    return [{"name": s.name, "kind": s.kind, "duration_ms": s.duration_ms,
             "status": s.status} for s in obs_svc.trace_timeline(db, correlation_id)]


# ===========================================================================
# Cache platform (M10)
# ===========================================================================
cache_router = APIRouter(prefix="/api/saas/cache", tags=["SaaS: Cache"])


@cache_router.get("/stats")
def cache_stats(_u=Depends(require_permission("cache.manage"))):
    return platform_cache.stats()


@cache_router.post("/invalidate")
def cache_invalidate(key: Optional[str] = None, prefix: Optional[str] = None,
                     tenant_id: Optional[int] = None,
                     _u=Depends(require_permission("cache.manage"))):
    if tenant_id is not None and key is None and prefix is None:
        count = platform_cache.invalidate_tenant(tenant_id)
        return {"invalidated": count}
    if prefix:
        return {"invalidated": platform_cache.invalidate_prefix(prefix, tenant_id=tenant_id)}
    if key:
        platform_cache.invalidate(key, tenant_id=tenant_id)
        return {"invalidated": 1}
    raise HTTPException(status_code=400, detail="provide key, prefix or tenant_id")


# ===========================================================================
# Security (M14)
# ===========================================================================
security_router = APIRouter(prefix="/api/saas/security", tags=["SaaS: Security"])


@security_router.post("/tenants/{tenant_id}/secrets")
def store_secret(tenant_id: int, body: SecretStore, db: Session = Depends(get_db),
                 _u=Depends(require_permission("security.manage"))):
    ref = security_svc.store_secret(db, body.name, body.value, tenant_id=tenant_id)
    return {"name": ref.name, "version": ref.version, "manager": ref.manager}


@security_router.post("/tenants/{tenant_id}/secrets/{name}/rotate")
def rotate_secret(tenant_id: int, name: str, body: SecretStore, db: Session = Depends(get_db),
                  _u=Depends(require_permission("security.manage"))):
    ref = security_svc.rotate_secret(db, name, body.value, tenant_id=tenant_id)
    return {"name": ref.name, "version": ref.version}


@security_router.post("/tenants/{tenant_id}/ip-allow")
def add_ip(tenant_id: int, body: IpAllowCreate, db: Session = Depends(get_db),
           _u=Depends(require_permission("security.manage"))):
    try:
        e = security_svc.add_ip_allow(db, tenant_id, body.cidr, description=body.description)
    except ValueError as ex:
        _bad_request(ex)
    return {"id": e.id, "cidr": e.cidr}


@security_router.get("/tenants/{tenant_id}/ip-allow/check")
def check_ip(tenant_id: int, ip: str, db: Session = Depends(get_db),
             _u=Depends(require_permission("security.view"))):
    return {"ip": ip, "allowed": security_svc.ip_allowed(db, tenant_id, ip)}


@security_router.post("/rate-limit/check")
def rate_limit(body: RateLimitCheck, _u=Depends(require_permission("security.view"))):
    return security_svc.rate_limiter.check(body.key, limit=body.limit, window_seconds=body.window_seconds)


@security_router.get("/sessions/{user_id}")
def sessions(user_id: int, db: Session = Depends(get_db),
             _u=Depends(require_permission("security.view"))):
    return [{"id": s.id, "status": s.status, "ip": s.ip_address, "mfa": s.mfa_verified}
            for s in security_svc.list_sessions(db, user_id)]


@security_router.post("/sessions/{session_id}/revoke")
def revoke_session(session_id: int, db: Session = Depends(get_db),
                   _u=Depends(require_permission("security.manage"))):
    try:
        s = security_svc.revoke_session(db, session_id)
    except ValueError as e:
        _bad_request(e)
    return {"id": s.id, "status": s.status}


@security_router.post("/tenants/{tenant_id}/devices")
def register_device(tenant_id: int, body: DeviceRegister, db: Session = Depends(get_db),
                    user: User = Depends(get_current_user)):
    dev = security_svc.register_device(db, user.id, body.fingerprint, tenant_id=tenant_id,
                                       name=body.name, platform=body.platform)
    return {"id": dev.id, "trusted": dev.trusted}


@security_router.post("/tenants/{tenant_id}/idp")
def configure_idp(tenant_id: int, body: IdpConfigure, db: Session = Depends(get_db),
                  _u=Depends(require_permission("security.manage"))):
    try:
        row = security_svc.configure_idp(db, tenant_id, body.protocol,
                                         display_name=body.display_name, config=body.config,
                                         client_secret=body.client_secret, enabled=body.enabled,
                                         mfa_required=body.mfa_required)
    except ValueError as e:
        _bad_request(e)
    return {"id": row.id, "protocol": row.protocol, "enabled": row.enabled}


@security_router.get("/tenants/{tenant_id}/idp")
def list_idp(tenant_id: int, db: Session = Depends(get_db),
             _u=Depends(require_permission("security.view"))):
    return [{"id": i.id, "protocol": i.protocol, "enabled": i.enabled,
             "mfa_required": i.mfa_required} for i in security_svc.list_idps(db, tenant_id)]


# ===========================================================================
# Analytics (M13)
# ===========================================================================
analytics_router = APIRouter(prefix="/api/saas/analytics", tags=["SaaS: Analytics"])


@analytics_router.get("/overview")
def overview(db: Session = Depends(get_db), _u=Depends(require_permission("analytics.view"))):
    return analytics_svc.platform_overview(db)


@analytics_router.get("/revenue")
def revenue(db: Session = Depends(get_db), _u=Depends(require_permission("analytics.view"))):
    return analytics_svc.revenue_analytics(db)


@analytics_router.get("/usage")
def usage(period: Optional[str] = None, db: Session = Depends(get_db),
          _u=Depends(require_permission("analytics.view"))):
    return analytics_svc.usage_analytics(db, period=period)


@analytics_router.get("/growth")
def growth(db: Session = Depends(get_db), _u=Depends(require_permission("analytics.view"))):
    return analytics_svc.growth_metrics(db)


@analytics_router.get("/adoption")
def adoption(db: Session = Depends(get_db), _u=Depends(require_permission("analytics.view"))):
    return analytics_svc.feature_adoption(db)


@analytics_router.get("/tenants/{tenant_id}")
def tenant_analytics(tenant_id: int, db: Session = Depends(get_db),
                     _u=Depends(require_permission("analytics.view"))):
    return analytics_svc.tenant_analytics(db, tenant_id)


@analytics_router.get("/executive")
def executive(db: Session = Depends(get_db), _u=Depends(require_permission("analytics.view"))):
    return analytics_svc.executive_dashboard(db)


# ===========================================================================
# Super-admin console (M12)
# ===========================================================================
admin_router = APIRouter(prefix="/api/saas/admin", tags=["SaaS: Admin Console"])


@admin_router.get("/organizations")
def admin_orgs(db: Session = Depends(get_db), _u=Depends(require_permission("platform.admin"))):
    return admin_svc.list_all_organizations(db)


@admin_router.get("/organizations/{org_id}")
def admin_org_detail(org_id: int, db: Session = Depends(get_db),
                     _u=Depends(require_permission("platform.admin"))):
    try:
        return admin_svc.organization_detail(db, org_id)
    except ValueError as e:
        _bad_request(e)


@admin_router.post("/organizations/{org_id}/suspend")
def admin_suspend(org_id: int, suspend: bool = True, db: Session = Depends(get_db),
                  actor: User = Depends(require_permission("platform.admin"))):
    try:
        org = admin_svc.suspend_organization(db, org_id, suspend=suspend)
    except ValueError as e:
        _bad_request(e)
    audit.record_safe(db, action="saas.org.suspend", actor=actor,
                      entity_type="organization", entity_id=org_id, meta={"suspend": suspend})
    return {"id": org.id, "status": org.status}


@admin_router.get("/usage")
def admin_usage(period: Optional[str] = None, db: Session = Depends(get_db),
                _u=Depends(require_permission("platform.admin"))):
    return admin_svc.usage_console(db, period=period)


@admin_router.get("/jobs")
def admin_jobs(db: Session = Depends(get_db), _u=Depends(require_permission("platform.admin"))):
    return admin_svc.jobs_console(db)


@admin_router.get("/health")
def admin_health(db: Session = Depends(get_db), _u=Depends(require_permission("platform.admin"))):
    return admin_svc.system_health(db)


@admin_router.get("/summary")
def admin_summary(db: Session = Depends(get_db), _u=Depends(require_permission("platform.admin"))):
    return admin_svc.platform_summary(db)


# ===========================================================================
# Deployment probes (M11) — unauthenticated, no tenant scope
# ===========================================================================
probes_router = APIRouter(tags=["Probes"])


@probes_router.get("/healthz")
def healthz():
    return {"status": "ok"}


@probes_router.get("/livez")
def livez():
    return {"status": "alive"}


@probes_router.get("/readyz")
def readyz(db: Session = Depends(get_db)):
    report = obs_svc.health_report(db)
    return {"status": report["status"], "checks": report["checks"]}


ROUTERS = [
    tenancy_router, branding_router, billing_router, flags_router, jobs_router,
    storage_router, realtime_router, observability_router, cache_router,
    security_router, analytics_router, admin_router, probes_router,
]
