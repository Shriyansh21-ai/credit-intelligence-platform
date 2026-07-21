"""Audit recording.

``record`` writes one :class:`AuditLog` row and commits it. It is deliberately
forgiving: unknown actors, missing request context, and non-serialisable values
are all tolerated. ``record_safe`` additionally swallows *all* exceptions so it
can be used on hot paths (e.g. middleware) without risk.
"""

from __future__ import annotations

from typing import Any, Optional

from sqlalchemy.orm import Session

from backend.app.models.audit import AuditLog


def _jsonable(value: Any) -> Any:
    """Best-effort conversion to something the JSON column can store."""
    if value is None or isinstance(value, (str, int, float, bool, list, dict)):
        return value
    try:
        return dict(value)
    except Exception:
        return str(value)


def _client_context(request: Any) -> tuple[Optional[str], Optional[str], Optional[str], Optional[str]]:
    """Extract (ip, user_agent, method, path) from a Starlette/FastAPI request."""
    if request is None:
        return None, None, None, None
    ip = None
    try:
        # Respect a proxy header when present, else the socket peer.
        fwd = request.headers.get("x-forwarded-for")
        ip = fwd.split(",")[0].strip() if fwd else (request.client.host if request.client else None)
    except Exception:
        ip = None
    ua = None
    method = None
    path = None
    try:
        ua = request.headers.get("user-agent")
    except Exception:
        ua = None
    try:
        method = request.method
        path = request.url.path
    except Exception:
        pass
    return ip, ua, method, path


def record(
    db: Session,
    *,
    action: str,
    actor: Any = None,
    entity_type: Optional[str] = None,
    entity_id: Optional[int] = None,
    previous_value: Any = None,
    new_value: Any = None,
    reason: Optional[str] = None,
    status: str = "success",
    request: Any = None,
    ip: Optional[str] = None,
    user_agent: Optional[str] = None,
    http_method: Optional[str] = None,
    path: Optional[str] = None,
    meta: Any = None,
    user_id: Optional[int] = None,
    user_email: Optional[str] = None,
) -> AuditLog:
    """Persist a single audit record and return it."""
    ctx_ip, ctx_ua, ctx_method, ctx_path = _client_context(request)

    if actor is not None:
        user_id = user_id if user_id is not None else getattr(actor, "id", None)
        user_email = user_email if user_email is not None else getattr(actor, "email", None)

    entry = AuditLog(
        user_id=user_id,
        user_email=user_email,
        ip_address=ip or ctx_ip,
        user_agent=user_agent or ctx_ua,
        http_method=http_method or ctx_method,
        path=path or ctx_path,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        previous_value=_jsonable(previous_value),
        new_value=_jsonable(new_value),
        reason=reason,
        status=status,
        meta=_jsonable(meta),
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def record_safe(db: Session, **kwargs: Any) -> Optional[AuditLog]:
    """Like :func:`record` but never raises. Rolls back on failure."""
    try:
        return record(db, **kwargs)
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
        return None
