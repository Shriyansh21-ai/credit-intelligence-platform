# Deploying to Render — AI Credit Intelligence Platform

This guide covers a production deployment on [Render](https://render.com):

- **Backend** — FastAPI, deployed as a Render **Web Service** (native Python).
- **Database** — Render **PostgreSQL** (managed).
- **Frontend** — TanStack Start app. See [Frontend hosting](#5-frontend-hosting) —
  it is an **edge/SSR** app, not a plain static site; read that section before
  choosing a target.

SQLite remains the zero-config default for **local development only**. In
`staging`/`production` the app **refuses to start on a SQLite URL** (it will not
silently fall back), so a PostgreSQL `DATABASE_URL` is mandatory in production.

---

## 1. Backend — Render Web Service

| Setting | Value |
| --- | --- |
| Runtime | Python 3 |
| Build Command | `pip install -r requirements.txt` |
| Pre-Deploy Command | `alembic upgrade head` |
| Start Command | `uvicorn backend.app.main:app --host 0.0.0.0 --port $PORT` |
| Health Check Path | `/health` |

Notes:

- The import path is **`backend.app.main:app`** (verified against the repo
  layout — `backend/app/main.py` defines `app`). `alembic.ini` lives at the repo
  root and its `env.py` overrides `sqlalchemy.url` from `DATABASE_URL`, so
  `alembic upgrade head` works from the repo root with no extra flags.
- **Migrations are Alembic-owned.** `Base.metadata.create_all()` is **not** used
  as the production schema mechanism. Run migrations in the **Pre-Deploy
  Command** and set `RUN_MIGRATIONS=0` so the app does not also try to migrate on
  boot. (If you prefer boot-time migration instead of a pre-deploy step, drop the
  pre-deploy command and set `RUN_MIGRATIONS=1`; only do one or the other.)
- Docker is **not required** — the repo has a working `Dockerfile`, but Render
  can build and run the app natively. Use Docker only if you specifically want
  it (set the service's runtime to Docker; the default `backend` target already
  runs `uvicorn ... :8000` and applies migrations via `deploy/entrypoint.sh`).

## 2. Database — Render PostgreSQL

Create a managed PostgreSQL instance and link it to the backend service. Render
exposes its connection string as `DATABASE_URL` in the form
`postgresql://user:pass@host:5432/db` (no explicit driver).

The application **normalizes the driver automatically** at startup:

```
postgres://…       ->  postgresql+psycopg://…
postgresql://…     ->  postgresql+psycopg://…
postgresql+psycopg://…  (left unchanged)
sqlite:///…             (left unchanged)
```

This is required because only **psycopg v3** (`psycopg[binary]`) is installed —
without normalization SQLAlchemy would default `postgresql://` to psycopg2 and
crash at boot with `ModuleNotFoundError: psycopg2`.

- **SSL**: Render's internal connection string does not require an explicit
  `sslmode`. If you connect over the **external** hostname, append
  `?sslmode=require` to `DATABASE_URL`.
- **Pooling**: configured via `DB_POOL_SIZE` / `DB_MAX_OVERFLOW` /
  `DB_POOL_TIMEOUT` / `DB_POOL_RECYCLE`, with `pool_pre_ping` on (dead
  connections are dropped transparently). Pooling is applied only for real DB
  servers, never for SQLite.

## 3. Environment variables

Required in production:

| Variable | Purpose |
| --- | --- |
| `APP_ENV=production` | Enables strict startup validation (fails fast on SQLite, insecure secrets, wildcard CORS). |
| `DATABASE_URL` | Managed Postgres DSN (auto-normalized to psycopg v3). |
| `SECRET_KEY` | App signing/encryption master secret. Use `openssl rand -hex 32`. |
| `JWT_SECRET_KEY` | JWT signing key (falls back to `SECRET_KEY` if unset). |
| `CONNECTOR_MASTER_KEY` | Encrypts connector credentials at rest. `openssl rand -hex 32`. |
| `CORS_ORIGINS` | Comma-separated allowed browser origins, e.g. `https://your-frontend.example.com`. |
| `DATA_PROVIDER=demo` | Source for the seed / Load Demo Portfolio feature (`demo` \| `public` \| `production`). |
| `RUN_MIGRATIONS=0` | When migrations run in the Pre-Deploy Command (recommended). |

Recommended: `LOG_FORMAT=json`, `DEBUG=false`. All external API keys
(`ANTHROPIC_API_KEY`, `STRIPE_API_KEY`, …) are read from the environment only —
never hardcoded. See `.env.example` for the full catalogue.

The app **fails to start in production** if `SECRET_KEY` / `CONNECTOR_MASTER_KEY`
are missing or use a well-known default, if `DATABASE_URL` is SQLite, or if CORS
is a credentialed wildcard — see `backend/app/core/settings.py::validate_runtime`.

## 4. Commands reference

```bash
# Build
pip install -r requirements.txt

# Migrate (Pre-Deploy)
alembic upgrade head

# Start
uvicorn backend.app.main:app --host 0.0.0.0 --port $PORT

# Seed a demo portfolio into the platform default tenant (idempotent)
python -m backend.app.seed --companies 50
python -m backend.app.seed --companies 100
python -m backend.app.seed --reset --companies 50   # wipe then reseed
```

Seeding is **idempotent**: companies are keyed by `(tenant_id, external_id)`, so
re-running never creates duplicates. End users don't need the CLI — they click
**Load Demo Portfolio** in the dashboard, which calls
`POST /api/demo-portfolio/load` and persists to PostgreSQL under their own
JWT-derived tenant.

## 5. Frontend hosting

> **Important:** the frontend is a **TanStack Start** app built with Nitro,
> targeting the **Cloudflare edge runtime** (`@lovable.dev/vite-tanstack-config`
> pins this). `vite build` emits `dist/client/assets` (with **no static
> `index.html`**) and `dist/server/server.js` (an edge `fetch(request, env, ctx)`
> handler). It is therefore **not** a plain static site and **not** a plain Node
> server out of the box.

Options, in order of least change:

1. **Frontend on Cloudflare Workers/Pages, backend on Render (recommended).**
   The build already targets Cloudflare — no architecture/build change. Set
   `VITE_API_URL=https://<your-backend>.onrender.com` at build time and add the
   Cloudflare URL to the backend's `CORS_ORIGINS`.

2. **Frontend as a Render Static Site.** Requires switching TanStack Start to
   SPA/prerender output (a **build-config change** in the shared Vite config,
   which the config comments warn against editing). Feasible — the app has no
   essential server-side functions (only an unused example `createServerFn`) —
   but it is a deviation from the current architecture and must be validated.
   If pursued: Publish Directory would be `frontend/dist/client` **once an
   `index.html` shell is produced**.

3. **Frontend as a Render Node Web Service.** Requires changing the Nitro preset
   to `node-server` in the shared Vite config so the build emits a Node listener
   (`.output/server/index.mjs`). `NITRO_PRESET=node-server` alone is **not**
   honored by the current config (verified), so this needs a config edit.

Whichever target you choose, the browser API base URL is controlled by
**`VITE_API_URL`** (baked in at build time; the realtime WebSocket URL is derived
from it, http→ws / https→wss). Set it to the Render backend origin.

## 6. Verification performed

Against a real PostgreSQL 18 instance (`postgresql+psycopg://`), end-to-end:

- All 24 Alembic migrations apply to a fresh Postgres DB; single head
  `e3f4a5b6c7d8`; downgrade/upgrade round-trip is reversible on Postgres.
- Signup → JWT → login → tenant provisioning → authenticated API → dashboard.
- Two-tenant isolation (Priya @ Alpha Bank vs Rahul @ Beta Finance): names and
  organizations render correctly; neither can read the other's book;
  `X-Tenant-ID` header is ignored (tenant comes from the JWT); tampered JWT → 401.
- Load Demo Portfolio persists 50 companies + 150 financials + 50 credit
  profiles + 50 exposures; **data survives a backend restart** (verified in a
  separate process); re-load is idempotent (0 new, 50 skipped); reset removes
  all; re-load restores. Confirmed with direct `psql` row counts — PostgreSQL is
  the source of truth, not browser storage.
- Seed CLI idempotent for `--companies 50` and `--companies 100`.
- `GET /health` returns `{"status":"healthy","database":"connected","dialect":"postgresql"}`.
