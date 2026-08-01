# Deployment Checklist

**Date:** 2026-08-01
**Target release:** v1.0

## Environment configuration

- [ ] Select the correct environment profile (production).
- [ ] Set all required application settings via environment variables.
- [ ] Set explicit CORS origins for production clients.
- [ ] Confirm no default or placeholder configuration values remain.

## Secrets

- [ ] Provision real secrets from an external secrets manager.
- [ ] Rotate/replace all default credentials and signing keys.
- [ ] Confirm no secrets are present in tracked files or images.
- [ ] Restrict secret access to the deploying service identity.

## Database migration

- [ ] Provision PostgreSQL with connection pooling.
- [ ] Back up any existing data before migrating.
- [ ] Run `alembic upgrade head` and confirm head is `c3d4e5f6a7b8`.
- [ ] Verify 22 migrations applied and schema matches expectations.
- [ ] Confirm no runtime `create_all`; schema is migration-managed only.

## Container / Kubernetes

- [ ] Apply Kubernetes manifests (or compose stack) for the target environment.
- [ ] Confirm image tags/digests match the signed-off release artifacts.
- [ ] Configure multiple Uvicorn workers for horizontal throughput.
- [ ] Set resource requests/limits and replica counts.
- [ ] Configure TLS termination and HSTS at ingress.

## Health and readiness probes

- [ ] Configure liveness probes on the application health endpoint.
- [ ] Configure readiness probes gating traffic on dependency availability.
- [ ] Verify probes report healthy after rollout.
- [ ] Confirm stateless compute paths remain available during datastore issues.

## Rollback plan

- [ ] Record the previous known-good image tag and migration head.
- [ ] Confirm database downgrade path (`alembic downgrade`) is verified.
- [ ] Define rollback trigger criteria and owner.
- [ ] Rehearse rollback in a staging environment before promotion.
- [ ] Confirm backups and PITR are in place prior to cutover.
