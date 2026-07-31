# Operator Guide

Day-2 operations for the **AI Credit Intelligence Platform** running on
Kubernetes. Covers health, metrics, scaling, background processing, backups,
configuration, logs, and routine tasks.

See also: [Observability](OBSERVABILITY.md) ·
[Disaster Recovery](DISASTER_RECOVERY.md) · [Configuration](../deployment/CONFIGURATION.md) ·
[Deployment](../deployment/DEPLOYMENT.md) · [Incident Response](INCIDENT_RESPONSE.md).

## Health & probes

The backend exposes three probe endpoints (served by the probes router):

| Endpoint | Meaning | Used for |
|----------|---------|----------|
| `/livez`  | process is alive | Kubernetes liveness probe, container HEALTHCHECK |
| `/readyz` | dependencies (DB) reachable | readiness probe / load-balancer gating |
| `/healthz`| lightweight aggregate | uptime checks |

Workers and the scheduler have no HTTP surface; their container HEALTHCHECK runs
`python -m backend.app.workers.healthcheck --max-age <n>` against a heartbeat
file (`WORKER_HEARTBEAT_FILE`). A stale heartbeat marks the pod unhealthy.

```bash
kubectl -n <ns> get pods
kubectl -n <ns> exec deploy/backend -- curl -fsS localhost:8000/readyz
```

## Metrics & dashboards

Prometheus text metrics are served at `/metrics`. Bring up the monitoring
side-stack with `deploy/compose/docker-compose.monitoring.yml` or the cluster
monitoring stack. Track request rate/latency/error-rate (RED), DB pool
saturation, job queue depth, and worker heartbeat age. Dashboards, alert rules,
and SLOs are documented in [Observability](OBSERVABILITY.md).

## Scaling

- **Horizontal (HPA):** `deploy/k8s/base/hpa.yaml` autoscales the backend on
  resource utilization. Tune min/max replicas per overlay; production runs HA,
  development runs a single replica of each workload.
  ```bash
  kubectl -n <ns> get hpa
  kubectl -n <ns> scale deploy/backend --replicas=6   # manual override
  ```
- **PodDisruptionBudgets** (`pdb.yaml`) keep a minimum available during node
  drains and rollouts.
- **Vertical:** adjust requests/limits in the overlay; size the DB pool
  (`DB_POOL_SIZE`, `DB_MAX_OVERFLOW`) with replica count so total connections
  stay under the Postgres limit.

## Workers & scheduler

- **worker** (`backend.app.workers.worker`) drains the job queue. Scale
  horizontally for throughput; tune `WORKER_POLL_INTERVAL`, `WORKER_BATCH_SIZE`,
  and `WORKER_QUEUE`.
- **scheduler** (`backend.app.workers.scheduler`) enqueues periodic work; keep a
  **single** replica to avoid duplicate scheduling (`SCHEDULER_INTERVAL`).
- Neither runs migrations (`RUN_MIGRATIONS=0`); the backend/init Job owns schema.

The active job broker (`JOB_BROKER`: `in_process`/`redis`/`rabbitmq`/`kafka`/
`celery`) determines where jobs flow. Watch queue depth and heartbeat age.

## Backups

Scheduled backups run via `deploy/k8s/base/backup-cronjob.yaml`; retention and
PITR windows are set by `BACKUP_RETENTION_DAYS` (default 35) and
`PITR_WINDOW_DAYS` (default 7). Restore procedures, RTO/RPO targets, and
DR drills are in [Disaster Recovery](DISASTER_RECOVERY.md).

## Configuration management

All runtime config is env-driven and validated at startup
(`backend/app/core/settings.py`). Non-secret values live in the ConfigMap
(`configmap.yaml`); secrets in a `Secret` (`secret.example.yaml`). Changing
config:

```bash
kubectl -n <ns> edit configmap ai-credit-config     # or apply an overlay patch
kubectl -n <ns> rollout restart deploy/backend      # pods re-read at startup
```

Staging/production reject insecure secrets, SQLite, wildcard CORS, and
mis-wired backends (fatal at startup). See [Configuration](../deployment/CONFIGURATION.md).

## Log access

Logs are structured JSON in production (`LOG_FORMAT=json`) with correlation IDs
so a request can be traced across services. Tail and filter:

```bash
kubectl -n <ns> logs deploy/backend -f
kubectl -n <ns> logs deploy/worker --since=1h | grep '"correlation_id":"<id>"'
```

Ship logs to your aggregator and correlate with traces
(`OTEL_EXPORTER_OTLP_ENDPOINT`, `TRACING_ENABLED`) — see
[Observability](OBSERVABILITY.md).

## Common operational tasks

- **Roll out a new version / roll back:** [Deployment](../deployment/DEPLOYMENT.md).
- **Run an ad-hoc migration:** `kubectl create job --from=cronjob/... ` or a
  one-shot Job from the backend image running `alembic upgrade head`.
- **Drain a node:** rely on PDBs; verify replicas stay above the budget.
- **Investigate an incident:** [Incident Response](INCIDENT_RESPONSE.md).

## Capacity guidance

- Size backend replicas to keep P95 latency within SLO at peak RPS; let the HPA
  absorb bursts, keep headroom of ~30%.
- Keep DB connections `= replicas × DB_POOL_SIZE + overflow` under the server
  cap; raise `DB_POOL_RECYCLE` if the DB closes idle connections.
- Scale workers to keep queue depth near zero at steady state; alert on growing
  backlog or heartbeat age.
- Provision object storage and Redis for peak concurrent uploads/sessions.
