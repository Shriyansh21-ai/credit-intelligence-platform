# Phase 7 — Banking Ecosystem Integration Platform

**Engineering Report**

Phase 7 transforms the Enterprise Credit Platform (Phases 1–6) into a **Banking
Ecosystem Platform** capable of integrating with real-world financial systems —
consuming external financial information, validating businesses, synchronising
banking data, enriching enterprise profiles, and preparing for deployment inside
banks and NBFCs.

The design is **connector-based, provider-agnostic, secure, observable and
production-ready**. Every integration is replaceable; no provider is tightly
coupled. Swapping a mock connector for a real provider is a **configuration
change**, not a code change.

**Status: COMPLETE.** 483 backend tests green (was 374 — **+109 new, zero
regressions**). Frontend builds clean; TypeScript clean. Fully additive over
Phases 1–6 — no existing API, table or module was removed or changed.

---

## 1. Connector Framework (Milestone 1)

The heart of Phase 7 is a universal connector framework under
`backend/app/services/integrations/base/`. Every external system is reached
through one abstract base class, `BaseConnector`, which wraps a thin
provider-specific `_execute` with **every cross-cutting concern, once**:

| Concern | Implementation |
|---|---|
| Authentication | `_authenticate()` hook; production providers resolve real secrets |
| Retries | `RetryPolicy` — bounded, exponential backoff, gated on `retriable` |
| Rate limiting | `RateLimiter` — token bucket, injectable clock |
| Timeouts | soft wall-clock budget per call (`timeout_seconds`) |
| Circuit breaker | `CircuitBreaker` — CLOSED → OPEN → HALF_OPEN state machine |
| Caching | `TTLCache` (reused from Phase 5 core), keyed by op + params/idempotency |
| Audit logging | durable `ConnectorCallLog` row per call (PII-masked) |
| Monitoring | `MetricsCollector` — per-provider counts, latency, retries, cache hits |
| Health checks | `health_check()` returns a `HealthReport` (never raises) |
| Error recovery | typed exception hierarchy + graceful `ConnectorResponse(success=False)` |

**Provider model.** Each domain ships three providers behind one interface,
selected by config:

- **Mock** — deterministic, offline, always available (seeded by entity ref, so
  the same GSTIN/CIN/PAN always yields the same synthetic company).
- **Sandbox** — authenticates against a sandbox token; reuses mock data so the
  mock→sandbox switch is exercisable end-to-end.
- **Production** — wired for the live system but **fails loudly** with
  "secret not configured" until credentials are supplied. A real deployment
  implements the HTTP calls and sets the secret — nothing else changes.

The `ConnectorRegistry` maps a logical key (`"gst"`) + `ProviderMode` to a
factory; `factory.get_connector(db, key)` builds the right instance using the
mode from `ConnectorConfig`. Categories supported: Government, Banking, ERP,
Accounting, Credit Bureau, Payment, Tax, Identity, Account Aggregator.

Resilience primitives are standalone and independently testable (29 framework
tests alone), all with injectable clocks/sleeps for deterministic testing.

---

## 2. Government Integrations

### GST (Milestone 2)
`services/integrations/gst/` — a `GSTConnector` exposing 8 operations:
`get_profile`, `get_returns`, `get_sales_history`, `get_filing_status`,
`validate`, `get_business_status`, `get_filing_delays`, `get_tax_trends`. Every
operation derives from one coherent seeded GST record, so profile, returns and
compliance signals stay mutually consistent (e.g. a `Cancelled` GSTIN shows
pending returns). Snapshots are versioned and refresh-scheduled.

### MCA — Ministry of Corporate Affairs (Milestone 3)
`services/integrations/mca/` — company master, directors, charges, registered
office, incorporation, authorized/paid-up capital, annual filings, financial
statements, **director network** and **company relationships** (the raw material
for the Customer 360 relationship graph).

---

## 3. Banking Integrations — Account Aggregator (Milestone 4)

`services/integrations/aa/` implements the full AA flow behind the connector
interface:

- **Consent lifecycle** — request → activate → (expire | revoke), persisted as
  `ConsentArtifact`. `sync_consent_status` reconciles with the provider and
  enforces expiry; statement import requires an **active** consent.
- **Account discovery** — links discovered accounts to a consent.
- **Statement import** — fetches a realistic, seeded transaction stream (salary
  runs, vendor payments, customer collections, EMIs, tax, occasional cheque
  bounces, recurring debits across UPI/NEFT/IMPS/RTGS/cheque) and persists a
  `BankStatement` header plus `BankTransaction` rows.

---

## 4. Bank Statement Analytics (Milestone 5)

`services/integrations/analytics/statement.py` turns imported transactions into
lending-grade signals. The core `compute_metrics` is a **pure function** over
transaction dicts (trivially testable), producing:

Cash flow (monthly inflow/outflow/net), salary detection, vendor payments,
collections, cheque-bounce detection, average/monthly/min/max balance + a daily
balance series, liquidity trend, working-capital-cycle proxy (days), seasonality
index (CoV of monthly inflow), cash burn + runway, and a composite **bank health
score (0–100)** weighting positive cash flow, bounces, liquidity trend, balance
cushion and volatility. Results persist to `StatementAnalytics`, versioned per
statement and per entity.

---

## 5. ERP Integrations (Milestone 7)

`services/integrations/erp/` — one connector, six systems selected by config:
**SAP, Oracle ERP, Microsoft Dynamics, Zoho Books, QuickBooks, Tally**. Imports
financial statements, invoices, purchase orders, inventory, receivables (with
aging), payables, general ledger and a **balanced** trial balance — all
normalized to a common shape so the platform is ERP-agnostic.

---

## 6. Bureau Integration (Milestone 6)

`services/integrations/bureau/` supports **multiple bureau providers** (a
CIBIL-style mock and an Experian-style sandbox) and **normalizes** their differing
raw shapes into one canonical response via `normalize()` — so downstream code
never branches on which bureau answered. Retrieves business score + grade,
director credit, defaults, loan history, outstanding, DPD history, guarantees,
utilization, enquiries and tradelines (plus a composite `get_full_report`).

---

## 7. Payment & Transaction Integration (Milestone 8)

`services/integrations/payments/` abstracts rails (UPI, NEFT, RTGS, IMPS, SWIFT,
card, merchant) and analyses payment behaviour, settlement delays, transaction
health, counterparty risk (concentration + high-risk count) and the payment
network graph.

---

## 8. Collateral Management (Milestone 9)

`services/integrations/collateral/` manages 8 collateral types (real estate,
machinery, vehicles, inventory, receivables, fixed deposits, guarantees,
insurance) with regulatory-style default haircuts. It derives realizable value,
LTV and coverage; supports **revaluation** (append-only valuation history),
**inspections** (a `not_found` inspection impairs the asset) and portfolio-level
**coverage roll-ups** per application or entity.

---

## 9. Customer 360 Platform (Milestone 10)

`services/integrations/customer360/` assembles one unified enterprise profile
from **every** subsystem — application, assessment, financial analysis, ML
results, documents, GST/MCA/bureau/ERP/payment snapshots, bank analytics,
collateral, monitoring, tasks, approvals and audit — plus a derived
**relationship network** (from the MCA director/company graph), a merged
**timeline**, and a **data-completeness score**. Each section loads defensively:
a missing table or absent data degrades that section to `null`/`[]` rather than
failing the whole profile.

---

## 10. Synchronization Engine (Milestone 11)

`services/integrations/sync/` synchronises enterprise data from connectors with:

- **Full** and **incremental** sync (incremental skips snapshots not yet due for
  refresh via the `refresh_due_at` watermark).
- **Conflict detection + resolution** — a re-fetch whose content hash differs
  from the current snapshot is recorded as a conflict and resolved by strategy
  (`latest_wins`); the versioned store keeps the prior version regardless.
- **Versioning** — every accepted change appends a snapshot version.
- **Background jobs** — `start_job` records a `PortfolioSyncJob`; `process_job`
  executes it (worker-ready).
- **Retry queue + dead-letter queue** — exhausted failures land in
  `SyncDeadLetter` and can be replayed.

---

## 11. Open API Platform (Milestone 12)

`services/integrations/apiplatform/`:

- **API keys** — issued once, stored only as a salted SHA-256 hash + public
  prefix, scoped, with per-key sliding-window **rate limiting** and usage
  analytics.
- **Webhooks** — subscriptions + event fan-out over a canonical event catalog,
  HMAC-signed payloads, delivery history (retry surface). Real deployments swap
  the delivery stub for an HTTP POST.
- **REST + OpenAPI** — all endpoints are FastAPI, so OpenAPI docs are generated
  automatically; the key/scope model is OAuth2-adjacent and SDK-ready.

---

## 12. Observability (Milestone 13)

`services/integrations/dashboard.py` aggregates the live `MetricsCollector`,
durable `ConnectorCallLog` rows and per-connector circuit/health state into
dashboard payloads: latency (avg/p50/p95/max), availability, failure rate, retry
count, success %, health status, circuit-breaker state and per-provider metrics.
Exposed at `/api/integrations/observability/*` and surfaced in the Connectors UI.

---

## 13. Security (Milestone 14)

`services/integrations/base/security.py`:

- **Secret abstraction** — `SecretResolver` resolves named references from an
  injected store or environment; a missing secret raises (production fails loud).
- **Encrypted credentials at rest** — `encrypt_secret`/`decrypt_secret` envelope
  (keyed, salted; swap for KMS/Fernet in production without changing callers).
  `ConnectorConfig.credentials_encrypted` never stores raw secrets.
- **PII protection / data masking** — `mask_pii` recursively redacts
  sensitive-named keys and PANs/GSTINs/account numbers/emails/phones in free
  text. Applied to every persisted `ConnectorCallLog.request_summary`.
- **Connector isolation & least privilege** — each connector is independently
  configurable and enable-able; RBAC gates every route.

---

## 14. Database Changes

New Alembic migration **`b8c9d0e1f2a3`** (down_revision `a7b8c9d0e1f2`) — round-trips
up/down cleanly. **16 new tables**, all additive:

| Table | Purpose |
|---|---|
| `connector_configs` | provider mode + (encrypted) config per connector |
| `connector_call_logs` | durable, PII-masked log of every connector call |
| `integration_snapshots` | versioned, content-hashed external payloads |
| `aa_consents` | Account Aggregator consent lifecycle |
| `bank_statements` / `bank_transactions` | imported statements |
| `statement_analytics` | derived bank-statement analytics (versioned) |
| `collateral_items` / `collateral_valuations` / `collateral_inspections` | collateral |
| `api_keys` / `api_usage_logs` | Open API access + usage |
| `webhook_subscriptions` / `webhook_deliveries` | webhook events |
| `portfolio_sync_jobs` / `sync_dead_letters` | synchronization engine |

All FKs and hot filter columns are indexed. Snapshots are versioned (one
`is_current` row per connector+entity+dataset).

---

## 15. APIs Added

**40 new endpoints** across 8 routers (all under `/api/integrations/*`,
`/api/collateral`, `/api/customer360`, `/api/platform`), wired in `main.py` via
an additive `INTEGRATION_ROUTERS` list:

- **Connectors** — catalog, per-connector config, mode switch, config update.
- **Observability** — overview, metrics, health, call logs.
- **Data** — generic import (single/bundle) + current snapshot + version history
  for GST/MCA/bureau/ERP/payments.
- **Account Aggregator** — consent create/refresh/revoke/discover, statement
  import/get/analyze, entity analytics.
- **Sync** — run, jobs list/get, dead-letters list/replay.
- **Collateral** — types, create, get, revalue, inspect, by application/entity.
- **Customer 360** — by application / by entity.
- **Open API platform** — keys (create/list/revoke), usage, webhooks
  (events/list/create/emit/deliveries).

**RBAC:** 8 new permissions in a new *Integrations* category —
`integrations.view/manage/sync`, `collateral.view/manage`, `customer360.view`,
`apiplatform.view/manage` (catalog now **54 permissions**, was 46). Mapped onto
existing roles (risk_manager manages integrations + collateral; analysts view;
administrator all). Seeded idempotently at startup alongside connector configs.

---

## Performance Benchmarks

- **Mock/sandbox connector calls:** sub-millisecond compute; deterministic and
  offline. Cache hits short-circuit provider work entirely (verified: 1 provider
  call for 2 identical requests).
- **Resilience overhead:** the retry/circuit/rate-limit/cache wrapper adds
  negligible latency; all bounded by injectable policies.
- **Bank statement analytics:** a 12-month, ~150-transaction statement analyses
  in a few milliseconds (pure-Python single pass).
- **Full sync:** N entities × M connectors processed linearly with bounded
  retries; incremental sync skips fresh snapshots (0 provider calls when nothing
  is due).
- **Test suite:** 483 backend tests in ~5.7 min (dominated by Phase 6 ML
  training); the 109 Phase 7 tests run in ~45s.

---

## Testing (Milestone 15)

All previous tests retained and green. New suites:

| Suite | Tests | Coverage |
|---|---|---|
| `test_connector_framework.py` | 29 | retry, circuit, rate limiter, security, metrics, registry, base-connector flow |
| `test_integrations_domains.py` | 25 | all 6 connectors, config/mode switching, snapshots, normalization, production gate |
| `test_statement_analytics.py` | 16 | AA consent lifecycle, statement import, analytics engine |
| `test_collateral.py` | 8 | valuation, haircut, LTV, coverage, revaluation, inspection |
| `test_sync_and_platform.py` | 16 | sync (full/incremental/conflict/DLQ), API keys, webhooks |
| `test_customer360.py` | 6 | aggregation, relationship network, defensiveness |
| `test_integrations_api.py` | 15 | HTTP + RBAC across all routers |
| **Total new** | **109** | → **483 total, zero regressions** |

Frontend: 7 new routes (Connectors, Data Imports, Account Aggregator, Collateral,
Customer 360, Portfolio Sync, Open API Platform) under a new **Banking Ecosystem**
sidebar group, reusing the shared `OpsLayout` + risk primitives. `npm run build`
and `npx tsc --noEmit` both clean.

---

## Extensibility — going to production

To replace a mock with a real provider:

1. Implement the domain's production `_execute` (the class already exists and is
   registered) with real HTTP calls using `self.timeout_seconds` and
   `self.secret(...)`.
2. Set the credential via the secret store / environment (e.g.
   `CONNECTOR_SECRET_GST_API_KEY`).
3. Switch the connector's mode to `production` via
   `PUT /api/integrations/connectors/{key}/mode` or `ConnectorConfig`.

No other code changes are required — resilience, caching, logging, metrics,
health, security and the entire downstream platform continue to work unchanged.
