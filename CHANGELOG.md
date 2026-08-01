
# Changelog

All notable changes to the **AI Credit Intelligence Platform** are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and
the project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
Per-release notes are generated automatically by `.github/workflows/release.yml`
from the commit history and published to GitHub Releases.

> The platform was built as a sequence of **strictly additive** milestones
> (Phases 1–10, Tracks 1–4). No release removed an API, table, migration, auth
> flow, or RBAC grant. Per-milestone engineering detail lives in the
> [engineering reports](docs/reports/index.md).

## [Unreleased]

### Added
- **Phase 11, M5 — CI/CD.** GitHub Actions pipeline: `ci.yml` (lint, matrix
  tests, migration round-trip, Docker build), `security.yml` (SAST, dependency
  audit, secret scan, IaC scan, CodeQL), `deploy.yml` (environment-gated k8s
  rollout with rollback), `release.yml` (semver image publish + release).
  Added `CODEOWNERS`, Dependabot, PR template, Kustomize environment overlays,
  `pyproject.toml` tooling config, and CI/CD + branch-protection docs.
- **Documentation & repository presentation.** Consolidated all documentation
  into a single `docs/` hub with sectioned indexes; one root `README.md`; added
  `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `SECURITY.md`, and `LICENSE`.

## [1.0.0] — Commercial GA — 2026-07-31

The platform reaches commercial general availability. Tracks 2–4 add the
Enterprise AI Intelligence, Advanced Financial Intelligence and Enterprise
Productization layers on top of Phases 1–10 / Track 1. Every addition is
strictly additive — no API, table, migration, auth or RBAC grant was removed.

### Added — Track 4: Enterprise Productization & Commercial Readiness
- **Enterprise Platform module** (`/api/ent/*`, `ent_*` tables): Enterprise UX
(global K command palette, personalization, saved layouts), Workspaces,
  Developer Platform (API keys/webhooks/sandbox), Plugin Marketplace, Integration
  Studio, Data Management (MDM), Operations Center, Security Center (zero-trust),
  Customer Success, Deployment Platform (blue-green/canary/rollback), Monitoring
  (tracing/SLA/cost), Business Intelligence and Launch Readiness.
- 29 `ent_*` tables (migration head `b2c3d4e5f6a7`), 104 routes, 24 `ent.*` RBAC
  permissions, 13 frontend pages + a global command palette, 17 final reports.

### Added — Track 3: Advanced Financial Intelligence Platform
- **Financial Intelligence module** (`/api/fin/*`, `fin_*` tables): Treasury,
  Portfolio, Basel III/IFRS 9, Economic Scenarios, ESG/Climate, Market
  Intelligence, Alternative Data, Forecasting, Quantitative Risk, Benchmarking,
  Executive Center, Decision Optimization, Financial Digital Twin and Strategic
  Intelligence. 21 `fin_*` tables (migration head `a1b2c3d4e5f6`), 109 routes,
  27 `fin.*` permissions, 14 frontend pages.

### Added — Track 2: Enterprise AI Intelligence Platform
- **AI Platform module** (`/api/aip/*`, `aip_*` tables): RAG, multi-agent,
  long-term memory, prompt engineering, evaluation, investigation, reports,
  workflows, conversational AI, research, continuous learning, governance,
  explainability and monitoring. Migration head `f3a4b5c6d7e8`, 22 `aip.*`
  permissions, 14 frontend pages.

### Platform totals at 1.0.0
- RBAC: **175 permissions** across all categories.
- Migrations: single linear head `b2c3d4e5f6a7`, every migration reversible.
- Tests: full backend suite green; zero regressions across tracks.

## [0.10.0] — Phase 10: AI-native Enterprise Banking OS
- **Banking OS module** (`/api/os/*`, `banking_os` package): 12 routers spanning
  the banking operating-system surface. 25 tables (migration head
  `e2f3a4b5c6d7`), 102 RBAC permissions, 12 frontend pages. Full suite green.
  See the [Phase 10 reports](docs/reports/index.md).

## [0.9.0] — Phase 9: Autonomous Intelligence ("AI Brain")
- **Autonomous Intelligence** (`/api/ai/*`): Enterprise Knowledge Graph,
  real-time risk monitoring & Early Warning Signals, AI Credit Copilot & natural
  language analytics, scenario simulation, stress testing, portfolio
  optimization, RM workspace, executive command center, recommendation engine,
  autonomous workflow intelligence, model governance and an enterprise data lake.
  Migration head `d0e1f2a3b4c5`, 86 RBAC permissions. Grounded in deterministic
  platform data — the optional LLM only phrases facts.

## [0.8.0] — Phase 8: Multi-Tenant SaaS Platform
- **SaaS module** (`/api/saas/*`): tenancy, billing, feature flags, background
  jobs, storage, realtime, observability, cache, security and admin/analytics.
  Cloud-native, multi-tenant foundation. Migration head `c9d0e1f2a3b4`.

## [0.7.0] — Phase 7: Banking Ecosystem & Connectors
- **Connector-based integration platform**: GST, MCA, Account Aggregator, credit
  bureau, ERP, payments, collateral, Customer 360, sync and open-API connectors.
  Migration head `b8c9d0e1f2a3`.

## [0.6.0] — Phase 6: Enterprise MLOps & Explainable AI
- **ML Platform** (`/api/ml/*`): model registry, versioning, drift detection,
  monitoring and explainability. Migration head `a7b8c9d0e1f2`.

## [0.5.0] — Phase 5: Credit Decision Platform
- **Platform foundation**: RBAC, audit, lifecycle and approvals subsystems.
  Migration head `f2b3c4d5e6a7`.

## [0.4.0] — Phase 4: Enterprise AI Risk Intelligence (ML layer)
- Introduced the enterprise ML risk-intelligence layer (risk models,
  explainability foundations).

## [0.1.0] — Phase 1 / Track 1: Core Credit & Fraud Platform
- Initial platform: AI credit scoring, Isolation-Forest fraud detection, risk &
  fraud history, portfolio analytics, executive dashboard, JWT authentication,
  React SPA frontend and FastAPI backend.

---

_Milestones 0.1.0–0.10.0 predate semantic-version tagging; versions are assigned
retrospectively to present a coherent history. See the per-phase engineering
reports under [`docs/reports/`](docs/reports/index.md) for full detail._
