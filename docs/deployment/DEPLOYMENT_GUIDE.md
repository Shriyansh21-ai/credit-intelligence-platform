# Deployment Guide (v1.0.0)

## Environments

Four standard environments — **development, testing, staging, production** —
modelled in the deployment platform (`/api/ent/deployment`). Seed them with
`POST /api/ent/deployment/environments/seed`.

## Deployment strategies

| Strategy | When to use | Steps (auto-planned) |
|----------|-------------|----------------------|
| `rolling` | default, low-risk changes | batched rolling update + health check |
| `blue_green` | zero-downtime major releases | provision green → deploy → smoke test → switch → decommission blue |
| `canary` | risk-managed rollout | route N% → observe → promote to 100% |
| `recreate` | stateful/breaking changes | stop old → deploy → start new |

Deploy: `POST /api/ent/deployment/deploy {environment_id, version, strategy,
canary_percent?, release_notes?}`. Each deployment records an auditable step plan
and updates the environment's live version.

## Rollback

`POST /api/ent/deployment/rollback {environment_id, to_version?}` reverts to the
prior successful version (or an explicit `to_version`) and records a
`rolled_back` deployment. The version dashboard
(`GET /api/ent/deployment/versions`) shows the live version and health per
environment plus deployment success rate.

## Container & CI/CD

The repo ships a `Dockerfile`, `docker-compose.yml`, Kustomize overlays under
`deploy/`, and GitHub Actions (`ci.yml`, `security.yml`, `deploy.yml`,
`release.yml`). Production images are semver-tagged and published by
`release.yml`.

## Pre-deploy checklist

Generate the deployment + production readiness checklists:
`POST /api/ent/launch/generate` with `checklist_type: "deployment"` (and
`"production"`), then review `GET /api/ent/launch/readiness`. Aim for ≥85%
overall readiness before promoting to production.

## Migrations

Run `alembic upgrade head` (current head `b2c3d4e5f6a7`). Every migration is
reversible; `alembic downgrade -1` is safe. Verify with a round-trip in staging.

## Rollout runbook

1. Merge to main → CI green (lint, tests, migration round-trip, image build).
2. Deploy to staging (`blue_green`), run smoke tests.
3. Canary to production at 10%, observe latency/SLA/error-rate in the monitoring
   dashboard.
4. Promote to 100% or roll back.
