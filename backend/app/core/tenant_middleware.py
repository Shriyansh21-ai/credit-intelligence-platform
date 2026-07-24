"""Tenant-resolution middleware (Phase 8, Milestone 1).

Establishes the ambient :class:`TenantContext` for each request so tenant-aware
repositories, caches and loggers scope automatically. Resolution order:

1. ``X-Tenant-ID`` header (integer tenant id) — the fast path used by the SPA
   and service-to-service calls behind the gateway.
2. ``X-Tenant`` + ``X-Organization`` slugs — resolved to a tenant id via the DB.
3. ``Host`` header matched against a verified custom domain.

Absent any of these the request runs with **no tenant context** — exactly the
pre-Phase-8 behaviour — so every legacy route keeps working unchanged. The
middleware never rejects a request; enforcement is the repositories' job.
"""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from backend.app.services.saas import context as tenant_context


class TenantMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        ctx = self._resolve(request)
        token = tenant_context.set_context(ctx) if ctx else None
        if ctx:
            request.state.tenant_context = ctx
        try:
            return await call_next(request)
        finally:
            if token is not None:
                tenant_context.reset_context(token)

    def _resolve(self, request: Request):
        headers = request.headers
        tenant_id = None
        org_id = None

        raw_tid = headers.get("x-tenant-id")
        if raw_tid and raw_tid.isdigit():
            tenant_id = int(raw_tid)
        raw_oid = headers.get("x-organization-id")
        if raw_oid and raw_oid.isdigit():
            org_id = int(raw_oid)

        if tenant_id is None:
            tenant_id, org_id = self._resolve_from_db(request, org_id)

        if tenant_id is None:
            return None
        return tenant_context.TenantContext(
            tenant_id=tenant_id, organization_id=org_id,
            is_superadmin=headers.get("x-platform-admin") == "1",
        )

    def _resolve_from_db(self, request: Request, org_id):
        """Slow path: resolve tenant/org slugs or a custom domain via the DB."""
        headers = request.headers
        org_slug = headers.get("x-organization")
        tenant_slug = headers.get("x-tenant")
        host = headers.get("host", "").split(":")[0]
        if not (org_slug and tenant_slug) and not host:
            return None, org_id

        from backend.app.db.database import SessionLocal
        from backend.app.services.saas import tenancy as tenancy_svc

        db = SessionLocal()
        try:
            tenant = None
            if org_slug and tenant_slug:
                tenant = tenancy_svc.get_tenant_by_slug(db, org_slug, tenant_slug)
            if tenant is None and host:
                tenant = tenancy_svc.resolve_tenant_by_domain(db, host)
            if tenant is None:
                return None, org_id
            return tenant.id, tenant.organization_id
        except Exception:
            return None, org_id
        finally:
            db.close()
