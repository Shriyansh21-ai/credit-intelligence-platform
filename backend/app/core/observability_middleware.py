"""Observability middleware (Phase 8, Milestone 9).

Assigns / propagates a correlation id per request, times the request, records a
root trace span + latency metrics, and echoes the correlation id back on the
``X-Correlation-ID`` response header. Self-contained and best-effort — recording
failures never affect the response.
"""

from __future__ import annotations

import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from backend.app.services.saas import observability


class ObservabilityMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        incoming = request.headers.get("x-correlation-id")
        cid = observability.start_context(incoming)
        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            self._record(request, 500, start)
            raise
        self._record(request, response.status_code, start)
        try:
            response.headers["X-Correlation-ID"] = cid
        except Exception:
            pass
        return response

    @staticmethod
    def _record(request: Request, status_code: int, start: float) -> None:
        elapsed = (time.perf_counter() - start) * 1000.0
        try:
            observability.metrics.incr("http.requests", method=request.method)
            observability.metrics.observe("http.latency_ms", elapsed, path=request.url.path)
            if status_code >= 500:
                observability.record_error("http_5xx", f"{request.url.path} -> {status_code}",
                                           path=request.url.path)
        except Exception:
            pass
