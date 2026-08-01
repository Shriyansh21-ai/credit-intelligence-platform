# Advanced Financial Intelligence Platform · Architecture

Track 3 evolves the platform into an **Advanced Financial Intelligence Platform**
for enterprise banking, investment banking, commercial lending, treasury,
portfolio management and regulators. It is a strictly **additive** layer on top
of Phases 1–11 and Tracks 1–2 — no existing API, migration, model, auth or RBAC
grant was removed or modified.

## Design principles

1. **Additive & backward-compatible.** Every table is prefixed `fin_`, every
   route lives under `/api/fin/*`, every permission under `fin.*`. Nothing from
   prior phases is touched. The Alembic migration creates/drops **only** `fin_*`
   tables and is derived from ORM metadata so it can never drift.
2. **Deterministic & explainable.** All analytics are pure, deterministic
   functions (stdlib only — no numpy/scipy/solver dependency). Monte-Carlo uses a
   seedable SplitMix64 RNG so every simulation is exactly reproducible. Every
   result carries a `grounding` block (facts + SHA-256 checksum) and, where
   regulatory, an `explanation` naming the formula and inputs.
3. **Grounding-first AI.** Consistent with Track 2, any narrative only *phrases*
   the deterministic grounding — it never sources numbers. Strategic reports
   attach a citation (source engine + checksum) to every section.
4. **Grounded in real platform data.** The read layer re-uses the Phase 9
   `autonomous.data_access` normaliser, turning `EnterpriseAssessment` rows into
   profile dicts. No engine fabricates exposures, PDs or financials.
5. **Multi-tenant & RBAC-protected.** Every row carries a nullable `tenant_id`;
   every route enforces a `fin.*` permission via `require_permission`.

## Module layout

```
backend/app/
  models/financial_intelligence.py        21 fin_* tables
  schemas/financial_intelligence.py        inbound Pydantic request bodies
  routes/financial_intelligence.py         14 routers, ROUTERS list, /api/fin/*
  services/financial_intelligence/
    common.py          pure financial math (TVM, stats, distributions, RNG,
                       interpolation, PD/LGD/EAD→ECL, Vasicek, checksums)
    data_access.py     read-only reuse of autonomous.data_access + exposures
    treasury.py        M1   portfolio.py    M2   regulatory.py   M3
    economic.py        M4   esg.py          M5   market.py       M6
    altdata.py         M7   forecasting.py  M8   quant.py        M9
    benchmarking.py    M10  executive.py    M11  optimization.py M12
    digital_twin.py    M13  strategic.py    M14
alembic/versions/a1b2c3d4e5f6_financial_intelligence_track3.py
frontend/src/features/financial-intelligence/{api,hooks,index}.ts
frontend/src/routes/fin-*.tsx             14 route pages
```

## Data model (21 tables)

| Milestone | Tables |
|-----------|--------|
| M1 Treasury | `fin_funding_sources`, `fin_treasury_snapshots` |
| M2 Portfolio | `fin_portfolios`, `fin_portfolio_positions`, `fin_portfolio_analyses` |
| M3 Regulatory | `fin_regulatory_calcs` |
| M4 Economic | `fin_economic_indicators`, `fin_economic_scenarios` |
| M5 ESG | `fin_esg_assessments` |
| M6 Market | `fin_market_instruments`, `fin_market_quotes`, `fin_market_news` |
| M7 Alt-Data | `fin_alt_signals` |
| M8 Forecasting | `fin_forecasts` |
| M9 Quant | `fin_risk_simulations` |
| M10 Benchmarking | `fin_benchmarks` |
| M11 Executive | `fin_exec_dashboards` |
| M12 Optimization | `fin_optimizations` |
| M13 Digital Twin | `fin_twins`, `fin_twin_simulations` |
| M14 Strategic | `fin_strategic_reports` |

Rows reference domain objects by stable string refs (`company_ref`,
`subject_ref`) and optionally an `assessment_id`, keeping the layer loosely
coupled and avoiding cross-model FK-ordering issues in targeted test schemas.

## Integration points

- **Enterprise Assessment Engine** — the source of grounded PD/LGD/EAD, ratings
  and financials for regulatory, portfolio, ESG, forecasting, benchmarking,
  optimization, executive and strategic engines.
- **Economic Scenario Engine (M4)** propagates macro shocks into every
  assessment's stressed PD/EL and feeds the digital twin and strategic reports.
- **AI Platform** conventions (grounding blocks, checksums, provider
  gating) are reused; strategic reports mirror the investigation→report pattern.
- **SaaS multi-tenancy** — `_tenant()` resolves the current tenant identically to
  Track 2.

## Migration

`a1b2c3d4e5f6` (down_revision `f3a4b5c6d7e8`) is the single head. `upgrade()`
runs `create_all(checkfirst=True)` over the `fin_*` tables in FK-safe order;
`downgrade()` drops them in reverse. Verified: 21 created on upgrade, 0 remaining
on downgrade, 21 recreated on re-upgrade.

## Security

- Every endpoint requires a `fin.*` permission (27 new permissions in the
  `Financial Intelligence Platform` RBAC category; total platform permissions
  124 → 151). View vs run/manage are split so read access is broad and
  execution/ingestion is restricted by seniority.
- No secrets, no external network calls (market/alt-data providers are stubbed
  behind a `source` field for later live integration).
- Deterministic outputs + stored checksums make every calculation auditable and
  reproducible for model-risk governance.
```
