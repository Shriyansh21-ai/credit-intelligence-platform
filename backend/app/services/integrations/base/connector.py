"""The universal connector base class.

Every external system — GST, MCA, Account Aggregator, bureau, ERP, payment rail
— is reached through a subclass of :class:`BaseConnector`. Subclasses implement
only the thin, provider-specific bits

* :meth:`_authenticate` — validate/obtain credentials (mock providers no-op).
* :meth:`_execute` — perform one operation and return raw data (or raise a
  :class:`ConnectorError`).
* :attr:`category` — the :class:`ConnectorCategory` this provider serves.

Everything cross-cutting is handled here, once, for all connectors
authentication, **retries**, **rate limiting**, **timeouts**, a **circuit
breaker**, **caching**, **audit logging**, **metrics** and **health checks**.
The result is that adding a real provider is a small, focused amount of code.
"""

from __future__ import annotations

import hashlib
import json
import time as _time
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, Optional, Union

from backend.app.core.cache import TTLCache
from backend.app.services.integrations.base.exceptions import (
    AuthenticationError,
    CircuitOpenError,
    ConnectorError,
    ProviderError,
    TimeoutError as ConnectorTimeoutError,
)
from backend.app.services.integrations.base.observability import MetricsCollector, metrics as _default_metrics
from backend.app.services.integrations.base.resilience import (
    CircuitBreaker,
    RateLimiter,
    RetryPolicy,
)
from backend.app.services.integrations.base.security import SecretResolver, default_secret_resolver
from backend.app.services.integrations.base.types import (
    ConnectorCategory,
    ConnectorRequest,
    ConnectorResponse,
    HealthReport,
    HealthStatus,
    ProviderMode,
)


class BaseConnector(ABC):
    # Overridden by each concrete connector.
    category: ConnectorCategory = ConnectorCategory.BANKING

    def __init__(
        self,
        provider: str,
        mode: Union[ProviderMode, str] = ProviderMode.MOCK,
        *,
        config: Optional[Dict[str, Any]] = None,
        retry: Optional[RetryPolicy] = None,
        breaker: Optional[CircuitBreaker] = None,
        limiter: Optional[RateLimiter] = None,
        cache: Optional[TTLCache] = None,
        cache_ttl: float = 300.0,
        timeout_seconds: float = 15.0,
        metrics_collector: Optional[MetricsCollector] = None,
        secret_resolver: Optional[SecretResolver] = None,
        clock: Callable[[], float] = _time.monotonic,
    ):
        self.provider = provider
        self.mode = ProviderMode(mode) if not isinstance(mode, ProviderMode) else mode
        self.config = dict(config or {})
        self.timeout_seconds = timeout_seconds
        self._retry = retry or RetryPolicy()
        self._breaker = breaker or CircuitBreaker()
        self._limiter = limiter or RateLimiter(rate=100.0, capacity=100.0)
        self._cache = cache if cache is not None else TTLCache(ttl_seconds=cache_ttl)
        self._metrics = metrics_collector or _default_metrics
        self._secrets = secret_resolver or default_secret_resolver
        self._clock = clock
        self._authenticated = False

    # ------------------------------------------------------------------
    # Provider contract (subclasses implement these)
    # ------------------------------------------------------------------
    @abstractmethod
    def _execute(self, request: ConnectorRequest) -> Any:
        """Perform a single operation and return raw data, or raise ConnectorError."""

    def _authenticate(self) -> None:
        """Validate/obtain credentials. Default: no-op (mock providers)."""
        return None

    def operations(self) -> List[str]:
        """Advertised operation names (best-effort, for discovery/docs)."""
        return []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def call(
        self,
        request: Union[ConnectorRequest, str],
        params: Optional[Dict[str, Any]] = None,
        *,
        db: Any = None,
    ) -> ConnectorResponse:
        """Execute an operation with the full resilience/observability stack."""
        req = self._normalize(request, params)
        started = _time.perf_counter()
        cache_key = self._cache_key(req)

        # 1) Cache -----------------------------------------------------
        if req.cacheable and cache_key is not None:
            cached = self._cache.get(cache_key)
            if cached is not None:
                latency = (_time.perf_counter() - started) * 1000.0
                self._metrics.record(
                    self.category.value, self.provider,
                    success=True, latency_ms=latency, cache_hit=True,
                )
                resp = ConnectorResponse(
                    provider=self.provider, operation=req.operation, mode=self.mode,
                    data=cached, success=True, from_cache=True, latency_ms=latency,
                )
                self._log(db, req, resp, circuit_state=self._breaker.state)
                return resp

        # 2) Authenticate once (auth failures are terminal) ------------
        try:
            if not self._authenticated:
                self._authenticate()
                self._authenticated = True
        except ConnectorError as exc:
            return self._fail(db, req, exc, started, attempts=1)

        # 3) Execute under rate-limit + breaker + retry ----------------
        attempts_made = {"n": 0}

        def _attempt() -> Any:
            attempts_made["n"] += 1
            self._limiter.enforce()
            return self._breaker.call(lambda: self._run_with_timeout(req))

        try:
            data = self._retry.run(_attempt)
        except ConnectorError as exc:
            return self._fail(db, req, exc, started, attempts=attempts_made["n"] or 1)
        except Exception as exc:  # noqa: BLE001 - normalise unexpected errors
            wrapped = ProviderError(str(exc) or exc.__class__.__name__,
                                    provider=self.provider, operation=req.operation)
            return self._fail(db, req, wrapped, started, attempts=attempts_made["n"] or 1)

        latency = (_time.perf_counter() - started) * 1000.0
        if req.cacheable and cache_key is not None:
            self._cache.set(cache_key, data)
        self._metrics.record(
            self.category.value, self.provider,
            success=True, latency_ms=latency, attempts=attempts_made["n"] or 1,
        )
        resp = ConnectorResponse(
            provider=self.provider, operation=req.operation, mode=self.mode,
            data=data, success=True, latency_ms=latency, attempts=attempts_made["n"] or 1,
        )
        self._log(db, req, resp, circuit_state=self._breaker.state)
        return resp

    def health_check(self, db: Any = None) -> HealthReport:
        """Probe the provider via its ``health`` operation (or auth), never raising."""
        started = _time.perf_counter()
        state = self._breaker.state
        try:
            if not self._authenticated:
                self._authenticate()
                self._authenticated = True
            detail = self._health_probe()
            latency = (_time.perf_counter() - started) * 1000.0
            status = HealthStatus.HEALTHY if state == "closed" else HealthStatus.DEGRADED
            return HealthReport(
                provider=self.provider, category=self.category.value, mode=self.mode,
                status=status, detail=detail, circuit_state=state, latency_ms=round(latency, 3),
            )
        except ConnectorError as exc:
            return HealthReport(
                provider=self.provider, category=self.category.value, mode=self.mode,
                status=HealthStatus.UNAVAILABLE, detail=str(exc), circuit_state=self._breaker.state,
            )

    # ------------------------------------------------------------------
    # Introspection / control
    # ------------------------------------------------------------------
    @property
    def circuit_state(self) -> str:
        return self._breaker.state

    def clear_cache(self) -> None:
        self._cache.clear()

    def secret(self, name: str) -> str:
        """Resolve a named secret (used by production/sandbox providers)."""
        return self._secrets.resolve(name)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _health_probe(self) -> str:
        """Default health probe. Subclasses may override with a cheap ping."""
        return f"{self.provider} ({self.mode.value}) reachable"

    def _run_with_timeout(self, req: ConnectorRequest) -> Any:
        """Execute the provider call, enforcing a soft timeout budget.

        Real network providers pass ``timeout_seconds`` to their HTTP client
        here we additionally measure wall time and raise if a (mock-simulated)
        call blew the budget, so timeout handling is exercised end-to-end.
        """
        t0 = _time.perf_counter()
        data = self._execute(req)
        elapsed = _time.perf_counter() - t0
        if elapsed > self.timeout_seconds:
            raise ConnectorTimeoutError(
                f"operation '{req.operation}' exceeded {self.timeout_seconds}s",
                provider=self.provider, operation=req.operation,
            )
        return data

    def _fail(
        self, db: Any, req: ConnectorRequest, exc: ConnectorError, started: float, attempts: int,
    ) -> ConnectorResponse:
        latency = (_time.perf_counter() - started) * 1000.0
        circuit_rejected = isinstance(exc, CircuitOpenError)
        self._metrics.record(
            self.category.value, self.provider,
            success=False, latency_ms=latency, attempts=attempts,
            circuit_rejected=circuit_rejected,
        )
        resp = ConnectorResponse(
            provider=self.provider, operation=req.operation, mode=self.mode,
            data=None, success=False, error=str(exc), latency_ms=latency, attempts=attempts,
        )
        self._log(db, req, resp, circuit_state=self._breaker.state, error=exc)
        return resp

    @staticmethod
    def _normalize(request: Union[ConnectorRequest, str], params: Optional[Dict[str, Any]]) -> ConnectorRequest:
        if isinstance(request, ConnectorRequest):
            return request
        return ConnectorRequest(operation=str(request), params=params or {})

    def _cache_key(self, req: ConnectorRequest) -> Optional[str]:
        if not req.cacheable:
            return None
        basis = req.idempotency_key or json.dumps(req.params, sort_keys=True, default=str)
        digest = hashlib.sha256(basis.encode("utf-8")).hexdigest()[:16]
        return f"{self.category.value}:{self.provider}:{req.operation}:{digest}"

    def _log(
        self, db: Any, req: ConnectorRequest, resp: ConnectorResponse,
        *, circuit_state: str, error: Optional[ConnectorError] = None,
    ) -> None:
        """Best-effort durable call log. Never raises (mirrors audit.record_safe)."""
        if db is None:
            return
        try:
            from backend.app.services.integrations.logging import record_call
            record_call(db, connector=self, request=req, response=resp,
                        circuit_state=circuit_state, error=error)
        except Exception:  # noqa: BLE001 - logging must never break a call
            try:
                db.rollback()
            except Exception:  # noqa: BLE001
                pass
