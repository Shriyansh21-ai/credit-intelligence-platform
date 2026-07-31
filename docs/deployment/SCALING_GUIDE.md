# Scaling Guide (v1.0.0)

## Horizontal scale

The API is stateless FastAPI; additive services are pure/deterministic, so
instances scale horizontally behind a load balancer with no shared in-process
state. Session/auth state lives in the DB, not in memory.

## Multi-tenancy

Every additive table carries a nullable `tenant_id`; `_tenant()` resolves the
current tenant uniformly. Tenant isolation is enforced at the query layer, so a
single deployment serves many tenants. Tenant health is visible in the operations
dashboard.

## Capacity planning

`GET /api/ent/monitoring/capacity` projects volume from current inventory at a
configurable growth rate and horizon, and recommends capacity (with a 1.3×
headroom) and whether scale-out is needed.

## Cost management

`GET /api/ent/monitoring/cost` rolls up AI, ML and infra cost from platform
inventory so cost scales predictably with usage. AI cost is bounded by the
pluggable provider (deterministic-local default incurs zero external cost).

## Database scale

- JSON result columns keep the schema stable as features grow.
- Indexes on `tenant_id`, natural keys and lookup columns for hot paths.
- Read-heavy roll-ups use coarse counts, not full scans.
- Analytics results persist as snapshots so repeat views avoid recomputation.
- Postgres in production (SQLite for dev/test); migrations are engine-agnostic.

## Performance

- Deterministic, stdlib-only compute (no numpy/scipy/solver load cost).
- Monte-Carlo iteration counts are request-parameterised for latency control.
- p50/p95/p99 latency and SLA are tracked in the monitoring platform.

## Load testing & readiness

The `scaling` and `performance` launch-readiness checklists gate: horizontal
scaling verified, capacity planning in place, load test to 3× peak, multi-tenant
isolation verified, p99 within budget, hot queries indexed. Generate with
`POST /api/ent/launch/generate {checklist_type: "scaling"}`.
