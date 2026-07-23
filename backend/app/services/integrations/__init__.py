"""Banking Ecosystem Integration Platform (Phase 7).

A connector-based integration layer that lets the Credit Decision Platform
consume external financial information (GST, MCA, Account Aggregator, credit
bureaus, ERPs, payment rails), validate and enrich enterprise profiles, and
synchronise portfolios with real-world banking systems.

Design principles:

* **Connector-based** — every external system implements one common interface
  (:class:`~backend.app.services.integrations.base.connector.BaseConnector`).
* **Provider-agnostic** — each domain ships ``mock``, ``sandbox`` and
  ``production`` providers; the active one is chosen by configuration, never by
  hard-coding. Swapping a mock for a real provider is a config change.
* **Resilient by default** — the base connector wires authentication, retries,
  rate limiting, timeouts, a circuit breaker, caching, audit logging, metrics
  and health checks around every call, so individual providers stay thin.
* **Additive** — nothing from Phases 1–6 is modified. All new persistence is
  created by a dedicated Alembic migration.
"""
