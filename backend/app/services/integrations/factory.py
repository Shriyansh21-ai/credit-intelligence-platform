"""Connector factory + domain registration (Milestone 1).

Importing this module registers every domain's mock/sandbox/production providers
with the process-wide :data:`registry`. :func:`get_connector` builds a connector
for a key using the provider mode from :class:`ConnectorConfig` (or a default),
wiring per-connector resilience settings from config. This is the single entry
point services use, so nothing else needs to know which provider is active.
"""

from __future__ import annotations

from typing import Any, Optional

from sqlalchemy.orm import Session

from backend.app.services.integrations import config as cfg_svc
from backend.app.services.integrations.base.connector import BaseConnector
from backend.app.services.integrations.base.providers import register_domain
from backend.app.services.integrations.base.registry import registry
from backend.app.services.integrations.base.resilience import RateLimiter, RetryPolicy
from backend.app.services.integrations.base.types import ConnectorCategory

_REGISTERED = False


def register_all() -> None:
    """Register every domain's providers exactly once (idempotent)."""
    global _REGISTERED
    if _REGISTERED:
        return

    from backend.app.services.integrations.gst.connector import (
        MockGSTConnector, ProductionGSTConnector, SandboxGSTConnector,
    )
    from backend.app.services.integrations.mca.connector import (
        MockMCAConnector, ProductionMCAConnector, SandboxMCAConnector,
    )
    from backend.app.services.integrations.aa.connector import (
        MockAAConnector, ProductionAAConnector, SandboxAAConnector,
    )
    from backend.app.services.integrations.bureau.connector import (
        MockBureauConnector, ProductionBureauConnector, SandboxBureauConnector,
    )
    from backend.app.services.integrations.erp.connector import (
        MockERPConnector, ProductionERPConnector, SandboxERPConnector,
    )
    from backend.app.services.integrations.payments.connector import (
        MockPaymentsConnector, ProductionPaymentsConnector, SandboxPaymentsConnector,
    )

    register_domain(registry, "gst", ConnectorCategory.GOVERNMENT,
                    MockGSTConnector, SandboxGSTConnector, ProductionGSTConnector)
    register_domain(registry, "mca", ConnectorCategory.GOVERNMENT,
                    MockMCAConnector, SandboxMCAConnector, ProductionMCAConnector)
    register_domain(registry, "account_aggregator", ConnectorCategory.ACCOUNT_AGGREGATOR,
                    MockAAConnector, SandboxAAConnector, ProductionAAConnector)
    register_domain(registry, "bureau", ConnectorCategory.CREDIT_BUREAU,
                    MockBureauConnector, SandboxBureauConnector, ProductionBureauConnector)
    register_domain(registry, "erp", ConnectorCategory.ERP,
                    MockERPConnector, SandboxERPConnector, ProductionERPConnector)
    register_domain(registry, "payments", ConnectorCategory.PAYMENT,
                    MockPaymentsConnector, SandboxPaymentsConnector, ProductionPaymentsConnector)

    _REGISTERED = True


def get_connector(
    db: Optional[Session],
    connector_key: str,
    *,
    mode: Optional[str] = None,
    **overrides: Any,
) -> BaseConnector:
    """Build a connector for ``connector_key`` using the configured provider mode."""
    register_all()
    resolved_mode = mode or cfg_svc.resolve_mode(db, connector_key)

    kwargs: dict = {"mode": resolved_mode}
    # Apply per-connector resilience settings from config, if present.
    if db is not None:
        cfg = cfg_svc.get_config(db, connector_key)
        if cfg is not None:
            if cfg.rate_limit_per_sec:
                kwargs["limiter"] = RateLimiter(rate=cfg.rate_limit_per_sec, capacity=cfg.rate_limit_per_sec)
            if cfg.timeout_seconds:
                kwargs["timeout_seconds"] = cfg.timeout_seconds
            if cfg.config:
                kwargs["config"] = dict(cfg.config)
    kwargs.update(overrides)
    return registry.create(connector_key, **kwargs)
