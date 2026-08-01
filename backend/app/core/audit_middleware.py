"""API-call audit middleware.

Records one audit row per mutating (or otherwise interesting) API request so the
compliance dashboard reflects real traffic. Kept deliberately cheap and safe

* GET/HEAD/OPTIONS and infrastructure paths (docs, openapi, root, static) are
  skipped to avoid drowning the log in read noise.
* The actor is resolved from the bearer token without a DB hit (JWT decode only).
* All failures are swallowed — auditing must never break a request.

Enable via ``settings.AUDIT_LOG_API_CALLS`` (on by default in the running app
tests mount isolated apps without this middleware).
"""

from __future__ import annotations

from jose import jwt
from starlette.middleware.base import BaseHTTPMiddleware

from backend.app.core.security import ALGORITHM, SECRET_KEY
from backend.app.db.database import SessionLocal
from backend.app.services.audit.recorder import record_safe

_SKIP_PREFIXES = ("/docs", "/openapi", "/redoc", "/favicon", "/static")
_SKIP_EXACT = {"/", ""}
_LOGGED_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def _actor_email(request) -> str | None:
    auth = request.headers.get("authorization")
    if not auth or not auth.lower().startswith("bearer "):
        return None
    token = auth.split(" ", 1)[1].strip()
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload.get("sub")
    except Exception:
        return None


class AuditMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)

        try:
            path = request.url.path
            method = request.method
            if (
                method in _LOGGED_METHODS
                and path not in _SKIP_EXACT
                and not path.startswith(_SKIP_PREFIXES)
            ):
                db = SessionLocal()
                try:
                    record_safe(
                        db,
                        action="api.request",
                        user_email=_actor_email(request),
                        request=request,
                        status="success" if response.status_code < 400 else "failure",
                        meta={"status_code": response.status_code},
                    )
                finally:
                    db.close()
        except Exception:
            pass

        return response
