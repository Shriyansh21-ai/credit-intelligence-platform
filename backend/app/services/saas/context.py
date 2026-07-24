"""Tenant context — the ambient isolation scope for a request (Phase 8, M1).

A :class:`TenantContext` identifies the organization + tenant a unit of work
runs under. The active context is held in a :class:`contextvars.ContextVar` so
tenant-aware repositories, caches and loggers can read it without threading it
through every call. The tenant-aware middleware sets it per request; background
jobs and tests set it explicitly via :func:`use_tenant`.

Isolation rule: code that touches a tenant-scoped table MUST go through a
:class:`~backend.app.services.saas.repository.TenantRepository`, which reads the
active context and refuses cross-tenant access.
"""

from __future__ import annotations

import contextvars
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Dict, Iterator, Optional


@dataclass(frozen=True)
class TenantContext:
    tenant_id: Optional[int] = None
    organization_id: Optional[int] = None
    user_id: Optional[int] = None
    org_role: Optional[str] = None
    # True for platform super-admins who may operate across tenants.
    is_superadmin: bool = False
    attributes: Dict[str, Any] = field(default_factory=dict)

    def require_tenant(self) -> int:
        if self.tenant_id is None:
            raise TenantContextError("No active tenant in context")
        return self.tenant_id


class TenantContextError(RuntimeError):
    """Raised on missing context or an attempted cross-tenant access."""


_current: "contextvars.ContextVar[Optional[TenantContext]]" = contextvars.ContextVar(
    "saas_tenant_context", default=None
)


def set_context(ctx: Optional[TenantContext]) -> "contextvars.Token":
    return _current.set(ctx)


def reset_context(token: "contextvars.Token") -> None:
    _current.reset(token)


def current_context() -> Optional[TenantContext]:
    return _current.get()


def current_tenant_id() -> Optional[int]:
    ctx = _current.get()
    return ctx.tenant_id if ctx else None


def require_tenant_id() -> int:
    ctx = _current.get()
    if ctx is None:
        raise TenantContextError("No active tenant context")
    return ctx.require_tenant()


@contextmanager
def use_tenant(
    tenant_id: Optional[int],
    *,
    organization_id: Optional[int] = None,
    user_id: Optional[int] = None,
    org_role: Optional[str] = None,
    is_superadmin: bool = False,
) -> Iterator[TenantContext]:
    """Bind a tenant context for the duration of a ``with`` block.

    Used by background jobs, tests and any non-HTTP entrypoint that still needs
    tenant scoping.
    """
    ctx = TenantContext(
        tenant_id=tenant_id,
        organization_id=organization_id,
        user_id=user_id,
        org_role=org_role,
        is_superadmin=is_superadmin,
    )
    token = set_context(ctx)
    try:
        yield ctx
    finally:
        reset_context(token)
