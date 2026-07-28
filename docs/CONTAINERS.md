# Container Images

> Phase 11, Milestone 2 — Containerization

Five production images, all multi-stage, non-root, with health checks and
layer-cached dependency installs.

| Image | Dockerfile | Base | Runs as | Ports | Purpose |
|-------|-----------|------|---------|-------|---------|
| Backend API | `Dockerfile` (target `backend`, default) | `python:3.13-slim` | `appuser` (10001) | 8000 | FastAPI / uvicorn |
| Worker | `Dockerfile` (target `worker`) | `python:3.13-slim` | `appuser` (10001) | — | Drains the job queue |
| Scheduler | `Dockerfile` (target `scheduler`) | `python:3.13-slim` | `appuser` (10001) | — | Ticks schedules + due tasks |
| Frontend | `frontend/Dockerfile` | build `oven/bun`, run `node:22-slim` | `appuser` (10001) | 3000 | TanStack Start SSR |
| Nginx edge | `deploy/docker/Dockerfile.nginx` | `nginxinc/nginx-unprivileged` | uid 101 | 8080 web / 8081 API | Reverse proxy |

## Python app image (backend / worker / scheduler)

One multi-stage source (`Dockerfile`) produces three role images that share a
single dependency layer. Build tools live only in the `builder` stage; runtime
stages copy a self-contained virtualenv (`/opt/venv`), so no compilers ship in
the final image.

```bash
docker build -t ai-credit-backend .                       # default target
docker build --target worker    -t ai-credit-worker    .
docker build --target scheduler -t ai-credit-scheduler .
```

- **Backend** runs migrations (`RUN_MIGRATIONS=1`) via `deploy/entrypoint.sh`,
  then `uvicorn`. Health: `GET /livez`.
- **Worker** (`python -m backend.app.workers.worker`) drains the background job
  queue via `services.saas.jobs.run_pending`. `RUN_MIGRATIONS=0`.
- **Scheduler** (`python -m backend.app.workers.scheduler`) ticks recurring
  schedules and notifies due tasks. Run exactly one replica.
- Worker/scheduler are HTTP-less; their liveness is a heartbeat file checked by
  `python -m backend.app.workers.healthcheck`.

Runtime OS libs: `libgomp1` (xgboost/lightgbm) and `tesseract-ocr` (OCR).

## Frontend image

The TanStack Start build emits a Web-standard SSR fetch handler
(`dist/server/server.js`) plus hashed client assets (`dist/client/assets`). The
dependency-free adapter `frontend/server/node-server.mjs` serves both on Node:
static assets directly (immutable caching), everything else through SSR, with a
`/healthz` probe and graceful shutdown.

```bash
docker build -f frontend/Dockerfile -t ai-credit-frontend ./frontend
```

Set `VITE_API_URL` at build time to point the browser at the production API
edge; it defaults to `http://127.0.0.1:8000` for local development.

## Nginx edge

Two independent edges so backend routes never collide with SPA routes:

- `:8080` **web edge** → frontend SSR (`FRONTEND_UPSTREAM`, default `frontend:3000`)
- `:8081` **API gateway** → backend (`BACKEND_UPSTREAM`, default `api:8000`)

Upstream hosts are injected at start via the nginx image's `envsubst` template
mechanism. Both listen on ports > 1024 so the container runs fully unprivileged.
Health: `GET /nginx-health`.

```bash
docker build -f deploy/docker/Dockerfile.nginx -t ai-credit-nginx .
```

## Build-context hygiene

`.dockerignore` (root) and `frontend/.dockerignore` keep contexts small —
excluding `.venv`, `node_modules`, `*.db`, caches, tests, and docs — for fast,
reproducible builds.
