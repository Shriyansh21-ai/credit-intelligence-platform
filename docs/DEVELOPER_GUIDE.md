# Developer Guide

How to get the **AI Credit Intelligence Platform** running locally and how to
make changes to it. Backend is FastAPI + SQLAlchemy + Alembic on Python 3.13;
frontend is TanStack/React + Vite managed with bun.

See also: [Coding Standards](CODING_STANDARDS.md) ·
[Configuration](CONFIGURATION.md) · [Architecture](ARCHITECTURE.md) ·
[Contributing](CONTRIBUTING.md).

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
See [Containers](CONTAINERS.md) and [Deployment](DEPLOYMENT.md).

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
(see [ADR 0002](adr/0002-two-tier-lint-adoption.md)). Markers (`integration`,
`ml`, `security`, `migration`, …) are defined in `pyproject.toml`.

## Conventions

Follow [Coding Standards](CODING_STANDARDS.md): typed code, services over fat
routers, additive migrations, structured logging. New code must pass the strict
ruff rule set and `ruff format --check`. Commit style and PR flow are in
[Contributing](CONTRIBUTING.md).
