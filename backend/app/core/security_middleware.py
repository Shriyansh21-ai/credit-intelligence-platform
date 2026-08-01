"""Security headers middleware.

Adds OWASP-recommended response headers (HSTS, CSP, anti-clickjacking, MIME
sniffing protection, referrer + permissions policy). Configurable via settings
and additive — it only sets headers that are not already present, so routes that
need a bespoke policy (e.g. an embeddable widget) can override per-response.
"""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from backend.app.core.settings import get_settings


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        settings = get_settings()
        if not settings.security_headers_enabled:
            return response

        headers = response.headers

        def _default(name: str, value: str) -> None:
            if name not in headers:
                headers[name] = value

        # HSTS only makes sense over TLS; emit unless plainly on http in dev.
        if request.url.scheme == "https" or settings.is_production_like:
            hsts = f"max-age={settings.hsts_max_age}; includeSubDomains"
            if settings.hsts_preload:
                hsts += "; preload"
            _default("Strict-Transport-Security", hsts)

        _default("Content-Security-Policy", settings.content_security_policy)
        _default("X-Content-Type-Options", "nosniff")
        _default("X-Frame-Options", "DENY")
        _default("Referrer-Policy", "strict-origin-when-cross-origin")
        _default("Permissions-Policy", settings.permissions_policy)
        _default("Cross-Origin-Opener-Policy", "same-origin")
        _default("Cross-Origin-Resource-Policy", "same-origin")
        _default("X-Permitted-Cross-Domain-Policies", "none")
        # Do not leak the server implementation.
        headers["X-Powered-By"] = "ai-credit-platform"
        return response
