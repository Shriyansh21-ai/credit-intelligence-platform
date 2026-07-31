# Phase 10 — Deployment Report

## Readiness summary
- **Backend:** all 15 milestones implemented; full suite **961 passed / 0 failed**; zero
  regressions on the 807-test baseline.
- **Frontend:** production build clean (exit 0, TypeScript typechecked); 12 new routes
  code-split and registered.
- **Schema:** additive, reversible migration `e2f3a4b5c6d7` verified up and down.
- **Security:** 16 new fine-grained RBAC permissions; every route permission-gated.

## Deploy steps (unchanged shape from prior phases)
1. `pip install -r requirements.txt` (adds `pytest`, `httpx` for the test lane only).
2. `alembic upgrade head` → applies `e2f3a4b5c6d7`.
3. Start the API (`uvicorn backend.app.main:app`). Startup `sync_rbac` reconciles the
   Banking OS permissions/grants idempotently.
4. Build & serve the frontend (`npm run build` in `frontend/`).
5. (Optional, per tenant) `POST /api/os/marketplace/seed` to install the built-in
   recommendation plugins; `POST /api/os/search/reindex` to populate the universal index.

## Configuration
- `DATABASE_URL` honored (SQLite dev default, Postgres in prod) — no new required env vars.
- LLM vendor credentials are **not** required to run: the M9 router ships a deterministic
  offline `local` provider and only calls hosted vendors when configured at the `_invoke`
  boundary.

## Observability
Phase 10 routes flow through the existing audit, tenant-resolution and observability
middleware (correlation ids + latency metrics). LLM invocations are logged to
`os_llm_invocations` for cost/latency/quality dashboards; policy evaluations, workflow runs,
committee votes and quality runs are all persisted with timestamps for audit.

## Recommended pre-GA hardening (M15 follow-on)
- Load tests on `/api/os/search`, `/api/os/scenario/run` (Monte Carlo) and
  `/api/os/exec/dashboard/*` (aggregation) under representative portfolio sizes.
- API contract tests (OpenAPI schema snapshot) in CI.
- Playwright E2E across the 12 new pages.
- OpenTelemetry exporter wiring (the middleware is OTel-ready) and dashboards for LLM cost.
- Index review on Postgres for the largest tenants (search + evaluations tables).

## Risk assessment
Low. The layer is additive and isolated; rollback is a single `alembic downgrade` with no
impact on Phase 1–9 data or behavior. No breaking changes to existing APIs, models or RBAC.
