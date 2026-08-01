"""Neutral data types shared across every connector.

These are plain dataclasses / enums with no ORM or framework dependencies so
they can be imported anywhere (providers, services, tests, migrations-adjacent
code) without side effects.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Any, Dict, Optional


class ProviderMode(str, enum.Enum):
    """Which implementation of a connector is active.

    ``MOCK`` is deterministic and offline (default everywhere). ``SANDBOX``
    targets a provider's test environment. ``PRODUCTION`` targets the live
    system and requires real credentials.
    """

    MOCK = "mock"
    SANDBOX = "sandbox"
    PRODUCTION = "production"


class ConnectorCategory(str, enum.Enum):
    """Coarse grouping of external systems."""

    GOVERNMENT = "government"
    BANKING = "banking"
    ERP = "erp"
    ACCOUNTING = "accounting"
    CREDIT_BUREAU = "credit_bureau"
    PAYMENT = "payment"
    TAX = "tax"
    IDENTITY = "identity"
    ACCOUNT_AGGREGATOR = "account_aggregator"


class HealthStatus(str, enum.Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"
    UNKNOWN = "unknown"


@dataclass
class ConnectorRequest:
    """A neutral request envelope handed to a connector operation.

    ``operation`` names the logical action (e.g. ``"get_profile"``); ``params``
    carries operation-specific inputs. ``idempotency_key`` (when set) makes the
    call safe to retry and drives cache keys.
    """

    operation: str
    params: Dict[str, Any] = field(default_factory=dict)
    idempotency_key: Optional[str] = None
    cacheable: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ConnectorResponse:
    """A neutral response envelope returned by every connector call."""

    provider: str
    operation: str
    mode: ProviderMode
    data: Any = None
    success: bool = True
    error: Optional[str] = None
    from_cache: bool = False
    latency_ms: float = 0.0
    attempts: int = 1
    raw: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "provider": self.provider,
            "operation": self.operation,
            "mode": self.mode.value if isinstance(self.mode, ProviderMode) else self.mode,
            "data": self.data,
            "success": self.success,
            "error": self.error,
            "from_cache": self.from_cache,
            "latency_ms": round(self.latency_ms, 3),
            "attempts": self.attempts,
        }


@dataclass
class HealthReport:
    """Outcome of a connector health check."""

    provider: str
    category: str
    mode: ProviderMode
    status: HealthStatus
    detail: str = ""
    circuit_state: str = "closed"
    latency_ms: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "provider": self.provider,
            "category": self.category,
            "mode": self.mode.value if isinstance(self.mode, ProviderMode) else self.mode,
            "status": self.status.value if isinstance(self.status, HealthStatus) else self.status,
            "detail": self.detail,
            "circuit_state": self.circuit_state,
            "latency_ms": self.latency_ms,
        }
