# Production Readiness Checklist

**Date:** 2026-08-01
**Target release:** v1.0

## Transport security

- [ ] TLS enabled and enforced at ingress.
- [ ] HSTS header configured with an appropriate max-age.
- [ ] HTTP redirected to HTTPS.
- [ ] Certificate issuance and renewal automated.

## Secrets and configuration

- [ ] All default secrets replaced with strong, externally managed values.
- [ ] No default or placeholder configuration values in the production profile.
- [ ] Signing keys and credentials sourced from a secrets manager.
- [ ] Explicit CORS origins configured (no wildcard in production).

## Data store

- [ ] PostgreSQL provisioned with connection pooling.
- [ ] Schema applied via `alembic upgrade head` (`c3d4e5f6a7b8`).
- [ ] Tenant isolation verified on scoped queries.
- [ ] No runtime `create_all` in the production path.

## Monitoring and alerting

- [ ] Metrics, logs, and traces aggregated (OpenTelemetry).
- [ ] Alerting configured on error rate, latency, and saturation.
- [ ] SOC / security monitoring integration in place.
- [ ] Dashboards published for operations.

## Backups and disaster recovery

- [ ] Scheduled backups configured with retention policy.
- [ ] Point-in-time recovery (PITR) enabled and tested.
- [ ] Restore rehearsed against a non-production environment.
- [ ] DR runbook documented and owned.

## Resilience and throughput

- [ ] Rate limiting applied at the edge.
- [ ] Multiple Uvicorn workers configured for horizontal throughput.
- [ ] Health/readiness probes gating traffic.
- [ ] Webhook retry/replay and connector timeouts confirmed.

## Supply chain and dependencies

- [ ] Backend dependencies pinned; lockfile committed.
- [ ] Frontend lockfile committed.
- [ ] CVE scan run against dependencies with no unresolved criticals.

## Incident response

- [ ] Incident response plan documented with severity levels.
- [ ] On-call rotation and escalation paths defined.
- [ ] Rollback procedure verified and accessible.
- [ ] Post-incident review process established.
