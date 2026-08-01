"""Reusable provider mixins.

Each integration domain ships three providers behind one interface

* **Mock** — deterministic, offline, always available (the default).
* **Sandbox** — points at a provider's test environment. Here it reuses the mock
  data (so switching mock → sandbox is exercisable end-to-end) but authenticates
  against a sandbox token and tags responses ``mode=sandbox``.
* **Production** — wired for the real system but *fails loudly* until credentials
  are configured, so a misconfigured production connector never silently returns
  fake data. Supplying the secret + implementing the HTTP calls is all that's
  left to go live.

These mixins capture the shared sandbox/production behaviour so each domain only
writes it once.
"""

from __future__ import annotations

from typing import Any

from backend.app.services.integrations.base.connector import BaseConnector
from backend.app.services.integrations.base.exceptions import ProviderError
from backend.app.services.integrations.base.types import ConnectorRequest, ProviderMode

# A built-in sandbox token so sandbox providers work out of the box in tests/demos.
_DEFAULT_SANDBOX_TOKEN = "sandbox-token"


class SandboxProviderMixin:
    """Authenticates against a sandbox token; otherwise behaves like the mock."""

    # Secret name checked for a sandbox token (falls back to a default).
    sandbox_secret: str = "sandbox.token"

    def _authenticate(self) -> None:  # type: ignore[override]
        resolver = getattr(self, "_secrets", None)
        token = None
        if resolver is not None:
            token = resolver.try_resolve(self.sandbox_secret)  # type: ignore[attr-defined]
        # Sandbox always has a usable default token — the point is to exercise the
        # auth path and mode switch, not to gate access.
        self._sandbox_token = token or _DEFAULT_SANDBOX_TOKEN  # type: ignore[attr-defined]


class ProductionProviderMixin:
    """Production wiring that requires real credentials.

    ``_authenticate`` resolves the required secret (raising ``ConfigurationError``
    when unset — the "configure credentials" path). Even with a secret present
    ``_execute`` raises a clear ``ProviderError`` because real HTTP wiring is
    intentionally not shipped in this build; a real deployment implements it here.
    """

    # Secret that must be configured to use the live provider.
    production_secret: str = "api_key"

    def _authenticate(self) -> None:  # type: ignore[override]
        # Raises ConfigurationError("secret '...' is not configured") when unset.
        self._api_key = self.secret(self.production_secret)  # type: ignore[attr-defined]

    def _execute(self, request: ConnectorRequest) -> Any:  # type: ignore[override]
        raise ProviderError(
            "production HTTP transport is not implemented in this build — "
            "implement the live API calls for this provider to go to production",
            provider=getattr(self, "provider", "production"),
            operation=request.operation,
        )


def register_domain(registry, key, category, mock_cls, sandbox_cls, production_cls) -> None:
    """Register all three providers for a domain under one connector key."""
    registry.register(key, ProviderMode.MOCK, mock_cls, category=category)
    registry.register(key, ProviderMode.SANDBOX, sandbox_cls, category=category)
    registry.register(key, ProviderMode.PRODUCTION, production_cls, category=category)
