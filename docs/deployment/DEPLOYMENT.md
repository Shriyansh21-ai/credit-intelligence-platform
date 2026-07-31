# Deployment Guide

How to build, ship, and roll out the **AI Credit Intelligence Platform**. The
platform is a FastAPI backend, a TanStack/React frontend, and background
worker/scheduler processes, packaged as containers and deployed to Kubernetes
via Kustomize.

See also: [CI/CD](CICD.md) · [Containers](CONTAINERS.md) ·
[Disaster Recovery](../operations/DISASTER_RECOVERY.md) · [Configuration](CONFIGURATION.md).

## Prerequisites

- Docker with BuildKit (`docker buildx`) — the `Dockerfile` uses
  `# syntax=docker/dockerfile:1.7`.
- `kubectl` and `kustomize` (or `kubectl apply -k`).
- Cluster access via a kubeconfig (CI injects it from the `KUBE_CONFIG_B64`
  per-environment secret).
- A container registry. CI publishes to `ghcr.io/<owner>/<service>`.
- A managed PostgreSQL 16 instance for staging/production (SQLite is rejected at
  startup outside development — see [Configuration](CONFIGURATION.md)).

## Environments

| Environment | Overlay | DB | Replicas | Promotion |
|-------------|---------|----|----------|-----------|
| development | `deploy/k8s/overlays/development` | Postgres | 1 each | auto-deploy on green CI of `develop` |
| staging     | `deploy/k8s/overlays/staging`     | Postgres (HA) | scaled | manual dispatch |
| production  | `deploy/k8s/overlays/production`  | Postgres (HA) | HA + HPA | manual dispatch, required reviewers |

GitHub Environment protection rules (reviewers, wait timers, allowed branches)
gate production — see [Branch Protection](../development/BRANCH_PROTECTION.md).

## Docker build — three targets

One multi-stage `Dockerfile` produces three role images sharing a dependency
layer. `backend` is the default (last) stage:

```bash
docker build --target backend   -t ai-credit-backend   .   # API server (uvicorn, :8000)
docker build --target worker    -t ai-credit-worker    .   # background jobs
docker build --target scheduler -t ai-credit-scheduler .   # periodic tasks
```

The `nginx` edge image builds from `deploy/docker/Dockerfile.nginx`. All runtime
stages run as unprivileged UID 10001 and carry no compilers.

## docker-compose (local / single-host)

- Root `docker-compose.yml` — full **development** stack: api + worker +
  scheduler, frontend, nginx edge, and backing services (Postgres, Redis, Kafka,
  RabbitMQ, MinIO) plus dev tooling (Mailhog, Adminer, PgAdmin).
  ```bash
  docker compose up -d --build
  ```
- `deploy/compose/docker-compose.prod.yml` — production-shaped single-host stack.
- `deploy/compose/docker-compose.monitoring.yml` — observability side-stack
  (see [Observability](../operations/OBSERVABILITY.md)).

## Kubernetes via Kustomize

The frozen base lives in `deploy/k8s/base` (Deployments, Services, HPA, PDB,
Ingress, NetworkPolicy, RBAC, ConfigMap, migrations Job, backup CronJob).
Overlays under `deploy/k8s/overlays/{development,staging,production}` patch only
environment-specific concerns (namespace, replica counts, image tags) — the base
is never edited.

```bash
kubectl apply -k deploy/k8s/overlays/production
```

At deploy time CI pins immutable image tags per service with
`kustomize edit set image ai-credit/<svc>=<registry>/<svc>:<tag>`.

## Database migrations (Alembic)

Alembic is the single source of truth for schema. Migrations are idempotent and
safe to re-run.

- **Container entrypoint** (`deploy/entrypoint.sh`) runs `alembic upgrade head`
  when `RUN_MIGRATIONS=1` (default for the `backend` image; `0` for
  worker/scheduler, which do not own schema).
- **Kubernetes** runs migrations once as a one-shot `Job` before rollout
  (`deploy/k8s/base/migrations-job.yaml`); the deploy workflow creates
  `db-migrate` from the target image and waits for completion.
- **Manual**:
  ```bash
  DATABASE_URL=postgresql+psycopg://... alembic upgrade head
  ```

CI proves the chain with an upgrade → downgrade-to-base → re-upgrade round-trip
against a real Postgres and asserts a single migration head.

## Required secrets & variables

Minimum for staging/production (startup validation is fatal if missing/insecure):

- `DATABASE_URL` — PostgreSQL DSN (`postgresql+psycopg://...`).
- `SECRET_KEY` — strong random value (`openssl rand -hex 32`).
- `CONNECTOR_MASTER_KEY` — connector-credential encryption key.
- `REDIS_URL` when `CACHE_BACKEND=redis` or `JOB_BROKER=redis`.
- Broker/storage/mail/billing credentials matching the selected backends.

In Kubernetes these come from a `Secret` (see
`deploy/k8s/base/secret.example.yaml`) and non-secret values from the ConfigMap.
In CI, `KUBE_CONFIG_B64`, `vars.K8S_NAMESPACE`, and `vars.APP_URL` drive the
rollout. Full catalog: [Configuration](CONFIGURATION.md).

## Rollout & rollback

Rollout is driven by `.github/workflows/deploy.yml` (manual dispatch with
`environment` + `image_tag`, or auto-deploy of `develop` to development):

1. Resolve the immutable image tag.
2. Run the migrations Job (idempotent `alembic upgrade head`).
3. `kustomize edit set image` then `kubectl apply -k <overlay>`.
4. `kubectl rollout status` each workload; on failure `kubectl rollout undo` all
   workloads and re-check status.

Manual rollback of a single workload:

```bash
kubectl -n <ns> rollout undo deploy/backend
kubectl -n <ns> rollout status deploy/backend --timeout=300s
```

## Smoke tests

After rollout the workflow curls the public URL:

```bash
curl -fsS "$APP_URL/livez"   # process is up
curl -fsS "$APP_URL/readyz"  # dependencies (DB) reachable
```

Probes are served by the app: `/livez`, `/readyz`, `/healthz`, plus `/metrics`.
For backup/restore and RTO/RPO during a failed deploy, see
[Disaster Recovery](../operations/DISASTER_RECOVERY.md).
