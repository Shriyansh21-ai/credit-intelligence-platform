"""Connector framework exception hierarchy.

All errors raised by the framework or a provider derive from
:class:`ConnectorError`, so callers can catch the whole family with one clause.
Each carries a ``retriable`` flag the retry policy consults.
"""

from __future__ import annotations

from typing import Optional


class ConnectorError(Exception):
    """Base class for every connector-related failure."""

    #: Whether a retry could plausibly succeed. Overridden per subclass.
    retriable: bool = False

    def __init__(self, message: str, *, provider: Optional[str] = None, operation: Optional[str] = None):
        super().__init__(message)
        self.message = message
        self.provider = provider
        self.operation = operation

    def __str__(self) -> str:  # pragma: no cover - trivial
        ctx = []
        if self.provider:
            ctx.append(f"provider={self.provider}")
        if self.operation:
            ctx.append(f"operation={self.operation}")
        suffix = f" ({', '.join(ctx)})" if ctx else ""
        return f"{self.message}{suffix}"


class ProviderError(ConnectorError):
    """The upstream provider returned an error. Transient by default."""

    retriable = True


class AuthenticationError(ConnectorError):
    """Credentials are missing, invalid or expired. Never retriable."""

    retriable = False


class RateLimitError(ConnectorError):
    """The local rate limiter (or the provider) rejected the call for volume."""

    retriable = True


class TimeoutError(ConnectorError):
    """The call exceeded its configured timeout budget."""

    retriable = True


class CircuitOpenError(ConnectorError):
    """The circuit breaker is open; the call was short-circuited."""

    retriable = False


class ConfigurationError(ConnectorError):
    """A provider is misconfigured (e.g. production without credentials)."""

    retriable = False


class NotFoundError(ConnectorError):
    """The requested entity does not exist upstream. Never retriable."""

    retriable = False
