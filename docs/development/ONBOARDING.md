# Onboarding

Welcome to the **AI Credit Intelligence Platform**. This gets a new engineer
from zero to a merged first PR in about a week. Read alongside the
[Developer Guide](DEVELOPER_GUIDE.md) and [Architecture](../architecture/ARCHITECTURE.md).

## Day 1 — accounts & access

- [ ] GitHub org access and repo access; join your Code Owner team(s) in
      `.github/CODEOWNERS`.
- [ ] SSO / VPN, cloud console (read at minimum), and `kubectl` context for the
      development cluster.
- [ ] Container registry (`ghcr.io`) pull access.
- [ ] Secrets manager access for the values you need (never commit secrets).
- [ ] Local toolchain: Python 3.13, `pip`/venv, Docker + BuildKit, `bun`,
      `kubectl` + `kustomize`.

## Day 1 — clone & run locally

```bash
git clone <repo> && cd ai_credit_system
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn backend.app.main:app --reload      # API on :8000, docs at /docs
```

Frontend:

```bash
cd frontend && bun install && bun run dev  # :3000
```

Or the whole stack: `docker compose up -d --build`. With no env set the backend
uses SQLite + in-process backends, so it just works. Full detail:
[Developer Guide](DEVELOPER_GUIDE.md), [Containers](../deployment/CONTAINERS.md).

## Week 1 — orientation

- [ ] Read [Architecture](../architecture/ARCHITECTURE.md) for the module map and request flow.
- [ ] Skim `backend/app/`: `core` (settings/security/telemetry), `models`,
      `routes`, `services`, `ml`, `db`, `workers`.
- [ ] Run the suite: `pytest backend/tests`; run `ruff check backend`.
- [ ] Read [Coding Standards](CODING_STANDARDS.md) and
      [Contributing](../../CONTRIBUTING.md).
- [ ] Trace one real endpoint (e.g. `routes/applications.py` →
      `services/…` → `models/…`) end to end.
- [ ] Bring up the monitoring stack and find the dashboards
      ([Observability](../operations/OBSERVABILITY.md)).

## Key docs index

| Topic | Doc |
|-------|-----|
| System design & module map | [Architecture](../architecture/ARCHITECTURE.md) |
| Local dev & how-to | [Developer Guide](DEVELOPER_GUIDE.md) |
| Contributing / PRs | [Contributing](../../CONTRIBUTING.md) |
| Coding standards | [Coding Standards](CODING_STANDARDS.md) |
| Config & env vars | [Configuration](../deployment/CONFIGURATION.md) |
| Build & release | [CI/CD](../deployment/CICD.md), [Containers](../deployment/CONTAINERS.md) |
| Deploy & rollback | [Deployment](../deployment/DEPLOYMENT.md) |
| Run in prod | [Operator Guide](../operations/OPERATOR_GUIDE.md), [Runbook](../operations/RUNBOOK.md) |
| When it breaks | [Incident Response](../operations/INCIDENT_RESPONSE.md), [Disaster Recovery](../operations/DISASTER_RECOVERY.md) |
| Security & compliance | [Security](../security/SECURITY_ARCHITECTURE.md), [Compliance](../security/COMPLIANCE.md) |
| API & performance | [API Platform](../api/API_PLATFORM.md), [Performance](../operations/PERFORMANCE.md) |
| Decisions | [ADRs](adr/) |

## First PR walkthrough

1. Pick a `good first issue`; branch off `develop`
   (`feat/<scope>-<summary>`).
2. Make the change **service-first** (logic in `services/`, thin routers) and
   add tests under `backend/tests/`.
3. Need schema? `alembic revision --autogenerate -m "..."`, review it, keep it
   additive and reversible.
4. `pytest backend/tests` + `ruff check backend` + `ruff format` locally.
5. Commit with sign-off and a Conventional-Commit message
   (`git commit -s -m "feat(...): ..."`).
6. Open the PR, fill the template, get Code Owner approval, land it green.

Full rules: [Contributing](../../CONTRIBUTING.md).

## Who owns what

Ownership is codified in `.github/CODEOWNERS` and enforced by branch protection:
backend app → backend team; `core/`/security surfaces → platform + security;
`models/`/`alembic/` → backend + DBA; `ml/` → ML; `frontend/` → frontend;
`deploy/`/`infra/`/`.github/` → platform + SRE; `docs/` → docs. Your PR will
auto-request the right reviewers.

## Glossary

- **Credit application** — a borrower's request for credit; the core object that
  moves through intake, analysis, decision, and approval.
- **Covenant** — a contractual condition on a facility (financial or
  behavioral); the platform monitors and flags breaches.
- **Portfolio** — a collection of exposures/facilities managed and monitored
  together for risk.
- **Scorecard** — a model that turns applicant features into a risk score/PD;
  the default ML model (`ML_DEFAULT_MODEL=scorecard`).
- **RBAC** — role-based access control; permissions gate every sensitive action.
- **Tenant** — an isolated customer org in the multi-tenant SaaS; data is
  partitioned per tenant.
- **Connector** — a pluggable integration to an external system (bureau, GST,
  bank, ERP), with encrypted credentials keyed by `CONNECTOR_MASTER_KEY`.
