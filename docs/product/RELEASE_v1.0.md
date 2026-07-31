# Release v1.0.0 — Commercial GA

The AI Credit Intelligence Platform reaches **commercial general availability**.
This release note summarises what v1.0.0 contains and the state of the platform.

## What's in v1.0.0

An end-to-end Enterprise Banking Intelligence Platform:

- **Enterprise Assessment Engine** (Phases 1–5) — credit applications, approvals,
  covenants, risk scoring, RBAC and audit.
- **ML Platform** (Phase 6), **Banking Connectors** (Phase 7), **Multi-Tenant
  SaaS** (Phase 8), **Autonomous Intelligence** (Phase 9), **Banking OS**
  (Phase 10), **Production Engineering / CI-CD** (Phase 11).
- **Enterprise AI Intelligence Platform** (Track 2, `/api/aip/*`) — RAG,
  multi-agent, memory, prompts, evaluation, investigation, reports, workflows,
  chat, research, learning, governance, explainability, monitoring.
- **Advanced Financial Intelligence Platform** (Track 3, `/api/fin/*`) —
  treasury, portfolio, Basel III/IFRS 9, economic scenarios, ESG, market, alt
  data, forecasting, quant risk, benchmarking, executive, optimization, digital
  twin, strategic intelligence.
- **Enterprise Productization Layer** (Track 4, `/api/ent/*`) — UX/command
  palette, workspaces, developer platform, plugin marketplace, integration
  studio, data management, operations center, security center, customer success,
  deployment, monitoring, business intelligence, launch readiness.

## Platform metrics at 1.0.0

- **RBAC**: 175 permissions across all categories.
- **Migrations**: single linear head `b2c3d4e5f6a7`; every migration reversible.
- **API**: hundreds of routes across 9 namespaces, all RBAC-gated and OpenAPI-documented.
- **Frontend**: feature modules + route pages per track, unified design system,
  global ⌘K command palette.
- **Tests**: full backend suite green; zero regressions across tracks.
- **Build**: frontend `tsc --noEmit` clean + production build clean.

## Compatibility

Fully backward compatible. No API, database table, migration, authentication or
RBAC grant was removed or changed across Tracks 2–4. Existing integrations
continue to work unchanged.

## Upgrade

```bash
alembic upgrade head          # → b2c3d4e5f6a7
# frontend rebuilds regenerate the route tree automatically
```

## Known limitations (by design)

- Market data, alternative data and webhook delivery are simulated behind a
  `source`/status field, ready for gated live-provider integration.
- LLM defaults to a deterministic-local provider (offline, reproducible); the
  gated Claude provider is enabled via configuration.

## Verification

Run the full backend suite and the frontend build; verify the migration
round-trip and the launch-readiness score (`GET /api/ent/launch/readiness`).

See `COMMERCIAL_READINESS_REPORT.md` for the readiness assessment and
`CHANGELOG.md` for the full change log.
