# Production Hardening Reference

*The production-readiness controls that ship with the platform, and where each
is wired — verified for Stage 3.*

This is an operator-facing map of the security, observability, deployment and
reliability controls already implemented across the codebase. Every item below
was verified against the running application and the deployment manifests.

## Observability & health (M2)

| Control | Where | Status |
|---------|-------|--------|
| Liveness probe | `GET /healthz`, `GET /livez` (`routes/saas.py`) | `200 {"status":"ok"/"alive"}` |
| Readiness probe (with dependency checks) | `GET /readyz` — checks the database | `200 {"status":"healthy","checks":[…]}` |
| Prometheus metrics | `GET /metrics` (`core/telemetry.py`) | Prometheus exposition format |
| Structured logging | `LOG_FORMAT=json`; `ObservabilityMiddleware` | Wired in `main.py` |
| Distributed tracing | OpenTelemetry (`OTEL_EXPORTER_OTLP_ENDPOINT`, `TRACING_ENABLED`) | Init on startup |
| Monitoring stack | `deploy/monitoring/` (Prometheus, Grafana, Loki, Tempo, Alertmanager) | Present |

Probes are unauthenticated and wired into Kubernetes:
`deploy/k8s/base/backend.yaml` sets `livenessProbe → /healthz` and
`readinessProbe → /readyz`. On shutdown, readiness flips so Kubernetes drains
traffic before termination.

## Security hardening (M3)

| Control | Where | Status |
|---------|-------|--------|
| Security response headers (HSTS/CSP/XFO/…) | `SecurityHeadersMiddleware` | Enabled by default |
| Secret management + insecure-default rejection | `core/settings.py` (`INSECURE_SECRETS`, `SECRETS_PROVIDER`) | Fails fast in prod |
| Field encryption + key rotation | `core/crypto.py` (AES-256-GCM, crypto-shred) | |
| Auth hardening (JWT/refresh rotation, MFA, lockout) | `core/authn.py` | |
| Rate limiting | `services/saas/security.py` | |
| Non-root container | `Dockerfile` (`useradd -u 10001 appuser`, `USER appuser`) | |
| K8s `runAsNonRoot` / dropped capabilities | `deploy/k8s/base/*.yaml` `securityContext` | |
| Explicit CORS (no wildcard in prod) | `settings.validate_runtime()` | Rejected in prod |
| Pipeline scanning (SAST, deps, secrets, IaC) | `.github/workflows/security.yml` | |

## Container & deployment hardening (M4)

| Control | Where | Status |
|---------|-------|--------|
| Multi-stage image, non-root, `HEALTHCHECK` | `Dockerfile` (app/worker/scheduler targets) | |
| Compose full stack | `docker-compose.yml` | |
| K8s base + environment overlays (Kustomize) | `deploy/k8s/{base,overlays}` | |
| Resource requests/limits | `deploy/k8s/base/backend.yaml` `resources` | |
| Multi-cloud IaC | `infra/terraform/` (AWS/Azure/GCP) | |
| Environment profiles | `deploy/env/*.env.example` (Stage 3 · M1) | Validated |
| Blue-green / canary / rollback | Enterprise Deployment module + `deploy.yml` | |

## Reliability & operations (M5)

| Control | Where | Status |
|---------|-------|--------|
| Fail-fast configuration validation | `core/startup.py` | Refuses to boot on fatal misconfig |
| Backups + retention | `deploy/k8s/base/backup-cronjob.yaml`; `BACKUP_RETENTION_DAYS` | |
| Point-in-time recovery window | `PITR_WINDOW_DAYS` | |
| Graceful draining on shutdown | readiness probe + Kubernetes `SIGTERM`/preStop | |
| Migration gating in prod | `RUN_MIGRATIONS=0` in prod profile → run as a deploy step | |
| Runbooks / DR / incident response | `docs/operations/` | |

## Pre-rollout verification

```bash
# 1. Validate the target profile (fails fast on any fatal issue).
APP_ENV=production python -c \
  "from backend.app.core.startup import validate_configuration as v; v()"

# 2. Probe the running service.
curl -fsS localhost:8000/healthz && curl -fsS localhost:8000/readyz

# 3. Confirm metrics are scrapeable.
curl -fsS localhost:8000/metrics | head
```

---

← Back to [Deployment Documentation](index.md) ·
See also [Environment Profiles](ENVIRONMENT_PROFILES.md) ·
[Production Readiness Report](../reports/PRODUCTION_READINESS_REPORT.md)
