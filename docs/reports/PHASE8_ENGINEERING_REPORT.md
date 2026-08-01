# Multi-Tenant Enterprise SaaS Cloud Platform

**Engineering Report**

Phase 8 transforms the AI Credit Intelligence Platform (Phases 1–7) into a
production-grade, cloud-native, multi-tenant SaaS platform capable of serving
banks, NBFCs, fintechs, credit unions, lenders, regulators and enterprises from
a single deployment.

Everything in this phase is **fully additive**. No existing business logic was
rewritten, no working API replaced, no database table removed, and no prior
phase broken. Backward compatibility is total: legacy single-tenant flows run
unchanged under an implicitly-provisioned default tenant.

---

## Status at a glance

| Metric | Before | After |
| --- | --- | --- |
| Backend tests | 483 | **627 (all green)** |
| Alembic head | `b8c9d0e1f2a3` | **`c9d0e1f2a3b4`** (one additive migration) |
| New tables | — | **31** (all tenant/org scoped) |
| RBAC permissions | 54 | **73** (+19 platform permissions) |
| RBAC roles | 8 | **9** (+`platform_admin`) |
| API surface | `/api/*` | **+ `/api/saas/*` + k8s probes** |
| Regressions | — | **0** |

Target of 600+ backend tests met (627). No existing test was deleted; only the
RBAC catalog-size assertions were updated to reflect the enlarged catalog.

---

## Design principles

1. **Additive-only.** New tables, new routers (`/api/saas/*`), new services under
   `app/services/saas/`. Middleware and startup seeding are best-effort and never
   reject a request or block boot.
2. **Tenant is the isolation key.** Every Phase 8 row carries `tenant_id`;
   isolation is enforced structurally by a single `TenantRepository` choke-point,
   not by remembering `WHERE` clauses.
3. **Abstractions over vendors.** Payments, storage backends, job brokers, cache
   backends, secret managers and identity providers are all interfaces with a
   working built-in default and vendor stubs — wiring a real vendor never changes
   the schema or call sites.
4. **Configurable without code changes.** Plans, feature flags, branding, quotas
   and IdP config are data-driven and seeded idempotently on startup.

---

## 1. Multi-Tenant Architecture (M1)

**Hierarchy** (`models/tenancy.py`):

```
Organization  → Tenant  → BusinessUnit → Department → Team
                        → Workspace    → Project
Users ── TenantMembership ──► Tenant        (a user may belong to many tenants)
```

- `Organization` is the legal/billing entity (the customer). `Tenant` is the
  isolation boundary. Creating an org always provisions a default tenant.
- **Tenant context** (`services/saas/context.py`): a `contextvars`-backed
  `TenantContext` carrying tenant/org/user/superadmin. Set per-request by
  middleware, or explicitly via `use_tenant(...)` for jobs and tests.
- **Tenant-aware middleware** (`core/tenant_middleware.py`): resolves the tenant
  from `X-Tenant-ID`, org/tenant slugs, or a verified custom domain — best-effort,
  never rejects; absent headers ⇒ legacy no-tenant behaviour.
- **Tenant-aware repository** (`services/saas/repository.py`): auto-filters every
  query by the active tenant, stamps `tenant_id` on insert, and raises
  `CrossTenantAccessError` on any cross-tenant fetch/delete. This is the single
  point that makes cross-tenant leakage structurally hard.
- **Tenant-aware cache**: keys namespaced `t{tenant}:...` (see M10).

## 2. Organization Management (M2)

`services/saas/tenancy.py` provides organization creation, multi-tenant support,
the full BU/Dept/Team/Workspace/Project hierarchy, coarse org-roles
(owner/admin/member/billing/viewer), member management, and a token-based
**invitation** flow that (on accept) creates the membership and grants the mapped
Phase-5 RBAC role. Regional settings (country/timezone/currency/locale) live on
the org and are overridable per tenant. Branch offices are modelled as business
units with address metadata.

APIs: `/api/saas/tenancy/*` (orgs, tenants, hierarchy, members, invitations,
`/invitations/accept`).

## 3. White-Label Platform (M3)

`services/saas/branding.py` + `TenantBranding`/`CustomDomain`:

- Logos (light/dark/favicon), a full **theme** (colors, typography, shape),
  email branding, login-page customisation, dashboard config, per-feature
  **visibility toggles**, and tenant-specific **navigation**.
- A code-defined `DEFAULT_THEME` is **deep-merged** with stored overrides so the
  frontend always receives a complete, ready-to-apply theme; partial updates only
  touch the keys sent.
- **Custom domains** with a verification token + SSL status; `resolve_tenant_by_domain`
  lets the middleware map an incoming `Host` header to a tenant.

APIs: `/api/saas/branding/tenants/{id}` (+ domains + verify).

## 4. Subscription & Billing (M4)

`services/saas/billing/`:

- **Plan catalog** (`catalog.py`, pure data): Free / Professional / Enterprise,
  each with hard `limits` and per-meter `unit_prices`. Custom per-org plans are
  supported. Seeded into `billing_plans` on startup.
- **Metering** across all requested dimensions: seats, storage_gb, api_calls,
  ml_predictions, ocr_pages, connector_calls (usage-based, seat, storage, API, ML,
  OCR and connector billing).
- **Quota enforcement** (`check_quota`) returns allowance detail (unlimited when a
  limit key is absent — Enterprise) so callers choose hard-block vs soft-meter.
- **Invoicing**: rolls a period's usage into base + seat + usage/overage lines,
  applies tax, and charges through the **`PaymentGateway`** abstraction. The
  built-in `InternalGateway` settles locally; `StripeGateway`/`RazorpayGateway`
  are ready stubs — no schema change to switch.
- **Subscription history** (append-only events) and **billing analytics** (MRR,
  billed/paid/outstanding, current-period usage).

APIs: `/api/saas/billing/*`.

## 5. Feature Flag System (M5)

`services/saas/flags/` — evaluation order: missing→off, expired→off, unmet
dependency→off, explicit tenant override wins, role targeting, global enabled,
then deterministic **percentage/canary rollout** (stable hash of `key:tenant`).
Supports global/tenant/role flags, experimental & canary kinds, expiration, and
prerequisite **dependency** chains (cycle-guarded). A code registry seeds defaults;
re-sync preserves ops-changed enabled/rollout values.

APIs: `/api/saas/flags/*` (list, evaluate, per-flag, upsert, override).

## 6. Background Job Platform (M6)

`services/saas/jobs.py` — durable, tenant-scoped jobs (`background_jobs`) with
queues, **priorities**, **retries with exponential backoff**, a **dead-letter
queue** + manual replay, **scheduling/recurring** jobs (`job_schedules`),
**cancellation**, **progress tracking**, and event **notifications** (via the
real-time hub). Execution is broker-agnostic: the built-in `InProcessBroker`
uses the table as the queue and `run_pending` as the worker loop;
`RedisBroker` (and future Celery/RabbitMQ/Kafka) implement the same `JobBroker`
interface. Handlers register by `job_type`.

APIs: `/api/saas/jobs/*` (enqueue, run, cancel, DLQ, schedules).

## 7. Cloud Storage Platform (M7)

`services/saas/storage.py` — tenant-scoped object store with a pluggable
`StorageBackend` (`LocalBackend` default, `MemoryBackend` for tests, and
S3/Azure/GCS/MinIO stubs). Features: **versioning** (`storage_object_versions`),
at-rest **encryption** (per-tenant keystream envelope), **lifecycle policies**
with computed expiry + a sweep job, HMAC **signed URLs** with expiry, and
**multipart/large-file** upload assembly. Metadata is backend-independent, so
switching backend never changes application code.

APIs: `/api/saas/storage/*`.

## 8. Real-Time Platform (M8)

`services/saas/realtime.py` — an in-process pub/sub `RealtimeHub` backing a
WebSocket endpoint (`/api/saas/realtime/ws`), a durable **activity stream**
(`activity_events`), and **presence** tracking. `publish()` is synchronous and
safe off the event loop: it persists the event and fans it out to matching live
connections (tenant + channel scoped), enabling live notifications, dashboards,
approvals, monitoring, collaboration and streaming updates. The transport is
swappable (Redis pub/sub, a bus) without changing producers.

APIs: `/api/saas/realtime/*` + WebSocket.

## 9. Observability Platform (M9)

`services/saas/observability.py` + `core/observability_middleware.py`:

- **Correlation IDs** (contextvars) propagated via `X-Correlation-ID`.
- **Distributed tracing** spans (`trace_spans`, OpenTelemetry-shaped:
  trace/span/parent ids) with a `trace()` context manager.
- In-memory **metrics** registry (counters/gauges/histograms with p50/p95/p99).
- **Slow-query detection**, **error analytics**, **health report**, and a
  **service/dependency map**.
- Sinks are OTLP-swappable; the middleware records latency + 5xx best-effort.

APIs: `/api/saas/observability/*`.

## 10. Cache Platform (M10)

`services/saas/cache.py` — `CachePlatform` over a pluggable `CacheBackend`
(`MemoryCacheBackend` default, `RedisCacheBackend` stub). TTLs, `get_or_set`,
key/prefix/**tenant-namespace** invalidation, cache **warming**, and hit/miss
**statistics**. **Tenant-aware** by construction: keys are `t{tenant}:...`, so one
tenant can neither read nor flush another's entries.

APIs: `/api/saas/cache/*`.

## 11. DevOps & Deployment (M11)

- **Dockerfile** (multi-stage, non-root, healthcheck) + `deploy/entrypoint.sh`
  (idempotent `alembic upgrade head` then serve).
- **docker-compose.yml**: API (2 replicas) + Postgres + Redis + MinIO, with
  commented env to switch the abstractions onto real backends.
- **Kubernetes manifests** (`deploy/k8s/`): Deployment with liveness/readiness/
  **startup probes**, resource requests/limits, rolling updates, a Service, and an
  **HPA** (3→20 on CPU). ConfigMap + Secret for the environment profile.
- **Probes** served by the app: `/healthz` (startup), `/livez` (liveness),
  `/readyz` (readiness, checks the DB).
- **Environment profiles** (`.env.example`) and an env-overridable `DATABASE_URL`
  (SQLite default preserved) — the app is stateless and horizontally scalable.
- **Secrets abstraction** — see M14.

## 12. Enterprise Admin Console (M13→ super-admin) (M12)

`services/saas/admin.py` — cross-tenant, platform-operator views gated by
`platform.admin`: list/inspect organizations, subscription + billing detail,
**suspend** (cascades to tenants), a **usage console** (per-org ML/OCR/API/
connector/storage meters), a **jobs console** (by status), and **system health**
(health + service map + errors + slow queries). A dedicated `platform_admin` RBAC
role holds the platform permissions with separation of duties from credit-workflow
permissions.

APIs: `/api/saas/admin/*`.

## 13. Analytics Platform (M13)

`services/saas/analytics.py` — SaaS self-analytics computed from the durable
tables (no separate ETL): platform overview, **revenue** (MRR/ARR, by-plan,
lifetime paid), **usage** per meter, **growth** (new & cumulative orgs by month),
**feature adoption** (share of tenants a flag evaluates on for), per-tenant
analytics, and a composed **executive dashboard**.

APIs: `/api/saas/analytics/*`.

## 14. Enterprise Security (M14)

`services/saas/security.py`:

- **Secrets management** by reference with **rotation** (`SecretRef.version`);
  built-in local envelope, `SecretManager` interface for Vault/KMS/etc.
- **Per-tenant encryption** helpers (tenant-keyed envelope, cross-tenant decrypt
  rejected).
- **Rate limiting** (in-memory sliding window, Redis-swappable).
- **IP allow-lists** (CIDR, open when unconfigured).
- **Session** and **device** management (register/trust, revoke).
- **MFA/SSO/SAML/OIDC/SCIM-ready**: `IdentityProviderConfig` captures the config
  surface; client secrets are stored by reference.

APIs: `/api/saas/security/*`.

---

## Data model (31 new tables)

`organizations, tenants, business_units, departments, teams, workspaces,
projects, tenant_memberships, tenant_invitations, tenant_branding, custom_domains,
billing_plans, subscriptions, subscription_events, usage_records, invoices,
invoice_line_items, feature_flags, feature_flag_overrides, job_schedules,
background_jobs, storage_objects, storage_object_versions, activity_events,
presence_records, trace_spans, security_devices, security_sessions,
ip_allow_entries, secret_refs, identity_provider_configs`

All created by the single additive migration `c9d0e1f2a3b4` (down-revision
`b8c9d0e1f2a3`), FK-ordered, fully reversible via `downgrade()`.

## Integration points

- `main.py`: registers `SAAS_ROUTERS`, adds `TenantMiddleware` +
  `ObservabilityMiddleware` (outermost), and calls `seed_saas` in the existing
  startup hook (plans, flags, default tenant).
- RBAC catalog: +19 permissions in a new "SaaS Platform" category, +`platform_admin`
  role, with read-only platform visibility granted to oversight roles.

## Testing (M15)

144 new tests across 9 modules (tenancy, isolation, billing, flags+branding,
jobs, storage, realtime+observability+cache, security, admin+analytics, and an
HTTP+RBAC+probes suite), bringing the suite to **627 passing** with zero
regressions. Tests use in-memory SQLite with a targeted `create_all`, mirroring
the Phase 7 harness.

## Architectural resemblance

The result mirrors the layering of enterprise SaaS platforms: tenant isolation
(Salesforce/ServiceNow), metered subscription billing (Stripe), feature flags
(LaunchDarkly-style), background jobs, cloud storage, real-time streaming,
observability (Datadog-style), and a super-admin control plane — modular,
cloud-native, horizontally scalable, tenant-isolated, observable, secure,
extensible and Kubernetes-ready.
