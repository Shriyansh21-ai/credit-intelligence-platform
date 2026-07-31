# Developer Guide

How to get the **AI Credit Intelligence Platform** running locally and how to
make changes to it. Backend is FastAPI + SQLAlchemy + Alembic on Python 3.13;
frontend is TanStack/React + Vite managed with bun.

See also: [Coding Standards](CODING_STANDARDS.md) ·
[Configuration](../deployment/CONFIGURATION.md) · [Architecture](../architecture/ARCHITECTURE.md) ·
[Contributing](../../CONTRIBUTING.md).

## Local setup

### Backend

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn backend.app.main:app --reload
```

The API serves on <http://localhost:8000> (docs at `/docs`). With no environment
set it uses zero-config defaults: SQLite plus in-process cache/broker/storage, so
it runs out of the box. Point `DATABASE_URL` at Postgres for a production-like
setup.

### Frontend

```bash
cd frontend
bun install
bun run dev            # Vite dev server on http://localhost:3000
```

Set `VITE_API_URL` to reach the backend (the compose stack proxies via nginx).

### Full stack (Docker)

```bash
docker compose up -d --build
```

Brings up api + worker + scheduler + frontend + nginx and all backing services.
See [Containers](../deployment/CONTAINERS.md) and [Deployment](../deployment/DEPLOYMENT.md).

## Project layout

```
backend/app/
  main.py        FastAPI app factory + router wiring
  core/          settings, security, telemetry, startup — cross-cutting infra
  models/        SQLAlchemy ORM models (one module per domain)
  schemas/       Pydantic request/response models
  routes/        API routers (applications, approvals, ml, rbac, ...)
  services/      business logic (credit analysis, autonomous, banking_os, ...)
  ml/            model, scorecard, explainability
  db/            engine/session, model registry
  workers/       worker, scheduler, runtime, healthcheck
backend/alembic/ migration environment + versions/
backend/tests/   pytest suite (1000+ tests)
frontend/        TanStack/React + Vite app
deploy/          Dockerfiles, compose, k8s base + overlays
infra/terraform/ cloud infrastructure
```

Config is centralized and typed in `backend/app/core/settings.py`
(pydantic-settings); access it via `get_settings()`.

## How to add …

### A route

1. Create/extend a router module in `backend/app/routes/`.
2. Define request/response models in `backend/app/schemas/`.
3. Put business logic in `backend/app/services/`, not the router.
4. Register the router in `backend/app/main.py`.
5. Add tests under `backend/tests/`.

### A model

1. Add the ORM class to a module in `backend/app/models/` (ensure it is imported
   so its table registers — see `backend/app/db/registry.py`).
2. Generate a migration (below). Never hand-edit the DB; Alembic owns schema.

### A migration

```bash
alembic revision --autogenerate -m "add covenant breach index"
alembic upgrade head
```

Review the generated script (autogenerate is a starting point, not final).
Migrations must be **additive and backward compatible** — do not drop or rename
columns that live code still reads. Keep a single head; CI fails on a branch and
runs an upgrade/downgrade/re-upgrade round-trip.

## Running tests & lint

```bash
pytest backend/tests                    # full suite, from repo root
pytest backend/tests -m "not slow"      # fast lane
pytest backend/tests -n auto            # parallel (pytest-xdist)
ruff check backend                      # correctness-core gate (repo-wide, green)
ruff format backend                     # formatter
```

CI additionally applies the strict full-rule ruff gate to changed files only
(see [ADR 0002](../architecture/adr/0002-two-tier-lint-adoption.md)). Markers (`integration`,
`ml`, `security`, `migration`, …) are defined in `pyproject.toml`.

## Conventions

Follow [Coding Standards](CODING_STANDARDS.md): typed code, services over fat
routers, additive migrations, structured logging. New code must pass the strict
ruff rule set and `ruff format --check`. Commit style and PR flow are in
[Contributing](../../CONTRIBUTING.md).

## Track 4 — Enterprise Developer Platform (`/api/ent/developer`)

An in-product developer platform for building against the API:

- **API keys** — `POST /api/ent/developer/keys` returns the plaintext secret
  **once** (`sk_test_…`/`sk_live_…`); only the SHA-256 hash + prefix are stored.
  Revoke with `POST .../keys/{id}/revoke`; test limits with `.../keys/rate-limit-test`.
- **Webhooks** — register (`POST .../webhooks {url, events[]}` → `whsec_…`
  signing secret), simulate a signed delivery (`.../webhooks/test`), replay
  (`.../webhooks/deliveries/{id}/replay`), and inspect history.
- **Sandbox** — `POST .../sandbox {method, path, body?}` records into request
  history and returns a deterministic echo; view history at `.../requests`.
- **API explorer** — `GET .../explorer` summarises the OpenAPI surface
  (`/openapi.json`, `/docs`), path groups and webhook events.

## Building an additive module (the platform convention)

Mirror this shape for new work — it is how Phases 1–11 and Tracks 1–4 are built:

1. `models/<module>.py` — additive `<prefix>_*` tables (nullable `tenant_id`,
   JSON payloads, `created_at`, `checksum` on computed results).
2. `alembic/versions/<rev>_<module>.py` — metadata-derived, reversible; append to
   the single head.
3. `services/<module>/` — `common.py` (pure helpers) + `data_access.py` + one
   module per feature; deterministic where possible.
4. `schemas/<module>.py` — inbound Pydantic bodies only.
5. `routes/<module>.py` — routers with `require_permission("<scope>")`, collected
   into a `ROUTERS` list mounted in `main.py`.
6. `services/rbac/catalog.py` — append permissions + role grants; bump the
   `test_rbac.py` count.
7. Frontend `features/<module>/` (api + hooks + index) + `routes/<prefix>-*.tsx`
   + a sidebar section.
8. `tests/test_<module>_*.py` + a helper mounting the module's `ROUTERS`.

Never remove APIs, tables, migrations or permissions — the platform is
additive-only.
