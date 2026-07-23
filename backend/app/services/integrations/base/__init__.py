"""Universal connector framework (Phase 7, Milestone 1).

The public surface every integration is built on:

* :class:`~.types.ProviderMode` — mock / sandbox / production.
* :class:`~.types.ConnectorRequest` / :class:`~.types.ConnectorResponse` —
  the neutral envelope that flows through every connector.
* :class:`~.connector.BaseConnector` — the abstract base that wraps a provider's
  ``_execute`` with auth, retries, rate limiting, timeout, circuit breaking,
  caching, audit logging, metrics and health checks.
* :class:`~.registry.ConnectorRegistry` — config-driven provider selection.
* :class:`~.resilience` — the resilience primitives (retry, circuit breaker,
  rate limiter) as standalone, independently testable pieces.
"""

from backend.app.services.integrations.base.connector import BaseConnector
from backend.app.services.integrations.base.exceptions import (
    AuthenticationError,
    CircuitOpenError,
    ConnectorError,
    ProviderError,
    RateLimitError,
    TimeoutError,
)
from backend.app.services.integrations.base.observability import MetricsCollector, metrics
from backend.app.services.integrations.base.registry import ConnectorRegistry, registry
from backend.app.services.integrations.base.resilience import (
    CircuitBreaker,
    CircuitState,
    RateLimiter,
    RetryPolicy,
)
from backend.app.services.integrations.base.types import (
    ConnectorCategory,
    ConnectorRequest,
    ConnectorResponse,
    HealthReport,
    HealthStatus,
    ProviderMode,
)

__all__ = [
    "BaseConnector",
    "ConnectorRegistry",
    "registry",
    "MetricsCollector",
    "metrics",
    "CircuitBreaker",
    "CircuitState",
    "RateLimiter",
    "RetryPolicy",
    "ProviderMode",
    "ConnectorCategory",
    "ConnectorRequest",
    "ConnectorResponse",
    "HealthReport",
    "HealthStatus",
    "ConnectorError",
    "ProviderError",
    "AuthenticationError",
    "RateLimitError",
    "TimeoutError",
    "CircuitOpenError",
]
