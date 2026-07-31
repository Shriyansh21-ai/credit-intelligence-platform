# Deployment Checklist

_AI Credit Intelligence Platform — Phase 11. Use per environment (dev/staging/prod)._

See [DEPLOYMENT.md](DEPLOYMENT.md) for procedures and [CICD.md](CICD.md) for the
pipeline.

## Pre-deploy

- [ ] Target branch green: `CI / CI success` passed.
- [ ] Version tagged (`vX.Y.Z`) and release images published to GHCR (prod).
- [ ] `alembic heads` shows exactly **one** head.
- [ ] Migration reviewed: additive + reversible (`upgrade`/`downgrade` tested).
- [ ] Changelog / release notes updated.
- [ ] Rollback plan confirmed (previous immutable image tag known).

## Infrastructure

- [ ] Terraform applied for the environment (`infra/terraform/environments/<env>`).
- [ ] Managed Postgres / Redis / object storage provisioned and reachable.
- [ ] Remote state backend configured (no secrets in VCS).
- [ ] DNS + TLS certificate (ACM/Cert-Manager) valid for the environment host.

## Configuration & secrets

- [ ] `APP_ENV` set correctly (`staging`/`production`).
- [ ] Strong `SECRET_KEY`, `JWT_SECRET_KEY`, `ENCRYPTION_KEY`, `CONNECTOR_MASTER_KEY`
      set from the secret manager (startup validation will fail otherwise).
- [ ] `DATABASE_URL` points at PostgreSQL (not SQLite).
- [ ] `CORS_ORIGINS` set to real frontend origins (no wildcard with credentials).
- [ ] `CACHE_BACKEND`/`JOB_BROKER`/`STORAGE_BACKEND` set with matching URLs/buckets.
- [ ] `LOG_FORMAT=json`; `METRICS_ENABLED=1`; `TRACING_ENABLED` + `OTEL_EXPORTER_OTLP_ENDPOINT` if tracing.

## Kubernetes

- [ ] Correct overlay selected (`deploy/k8s/overlays/<env>`).
- [ ] Image tags pinned to the immutable release version (not `latest`) for prod.
- [ ] Secrets created (not the `secret.example.yaml` placeholder).
- [ ] Resource requests/limits, HPA, PDB reviewed for the environment.
- [ ] NetworkPolicies applied.

## Deploy

- [ ] Run migrations (Job / `RUN_MIGRATIONS=1` entrypoint) — completes successfully.
- [ ] `kubectl apply -k` (or trigger the Deploy workflow; prod requires approval).
- [ ] Rollout status healthy for backend/worker/scheduler/frontend/nginx.

## Post-deploy verification

- [ ] `GET /livez`, `/readyz`, `/healthz` → 200.
- [ ] `GET /metrics` scraped by Prometheus; targets up.
- [ ] Grafana dashboards populating; no firing SLO alerts.
- [ ] Structured logs flowing to Loki with correlation IDs.
- [ ] Smoke test of a core flow (create/assess an application) passes.
- [ ] Security headers present on responses.

## Rollback (if needed)

- [ ] `kubectl rollout undo deploy/<name>` (Deploy workflow auto-rolls-back on failure).
- [ ] Redeploy previous immutable image tag.
- [ ] If schema changed: apply the migration `downgrade` (only if safe/reversible).
- [ ] Post-incident note recorded (see [INCIDENT_RESPONSE.md](../operations/INCIDENT_RESPONSE.md)).
