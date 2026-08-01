# Autonomous AI Banking Intelligence Platform

**Status:** Complete & verified — **807 backend tests green** (627 pre-existing +
180 new, zero regressions); frontend `tsc --noEmit` clean and `npm run build` clean;
Alembic chain linear (head `d0e1f2a3b4c5`) and round-trips up/down.

Phase 9 turns the platform from an AI-powered enterprise lending system into an
**Autonomous Banking Intelligence Platform** — the "AI Brain". It is **fully
additive** over Phases 1–8: nothing was rewritten, simplified or removed. Existing
APIs, tables, routes, services, ML pipelines, connectors, the SaaS platform, RBAC
and workflows all continue to work unchanged.

---

## 1. What was delivered (15 milestones)

| # | Milestone | Backend module | Primary API prefix |
|---|-----------|----------------|--------------------|
| M1 | Enterprise Knowledge Graph | `services/autonomous/graph.py` | `/api/ai/graph` |
| M2 | Real-Time Risk Monitoring | `services/autonomous/monitoring.py` (+ `alerts.py`) | `/api/ai/monitoring`, `/api/ai/alerts` |
| M3 | Early Warning Signal Engine | `services/autonomous/ews.py` | `/api/ai/ews` |
| M4 | AI Credit Copilot | `services/autonomous/copilot.py` (+ `llm.py`) | `/api/ai/copilot` |
| M5 | Scenario Simulation Engine | `services/autonomous/simulation.py` | `/api/ai/simulation` |
| M6 | Stress Testing Framework | `services/autonomous/stress.py` | `/api/ai/stress` |
| M7 | Portfolio Optimization AI | `services/autonomous/optimization.py` | `/api/ai/portfolio` |
| M8 | Relationship Manager Workspace | `services/autonomous/rm.py` | `/api/ai/rm` |
| M9 | Executive Command Center | `services/autonomous/command.py` | `/api/ai/command` |
| M10 | Natural Language Analytics | `services/autonomous/nlq.py` | `/api/ai/nlq` |
| M11 | Enterprise Recommendation Engine | `services/autonomous/recommendations.py` | `/api/ai/recommendations` |
| M12 | Autonomous Workflow Intelligence | `services/autonomous/workflow.py` | `/api/ai/workflow` |
| M13 | Model Governance Platform | `services/autonomous/governance.py` | `/api/ai/governance` |
| M14 | Enterprise Data Lake | `services/autonomous/datalake.py` | `/api/ai/datalake` |
| M15 | Production Readiness | tests + docs + verification | — |

Shared foundations: `common.py` (pure numeric/severity/rating helpers) and
`data_access.py` (the single read layer over existing tables → normalized profiles).

**65 new endpoints** live under `/api/ai/*`. No existing route path was touched.

---

## 2. Architecture

```
                         ┌─────────────────────────────────────────────┐
                         │        Phase 9  —  AUTONOMOUS "AI BRAIN"      │
                         │            (services/autonomous/*)            │
                         └─────────────────────────────────────────────┘
                                            │  reads (never mutates)
        ┌───────────────────────────────────┼───────────────────────────────────┐
        ▼                                    ▼                                    ▼
┌───────────────┐                   ┌────────────────┐                  ┌──────────────────┐
│ common.py     │  pure helpers     │ data_access.py │  read layer      │ llm.py           │
│ clamp / PD /  │◄──────────────────│ profile() /    │                  │ LLMProvider ABC  │
│ severity / …  │                   │ portfolio_…()  │                  │  ├ Local (default)│
└───────────────┘                   └───────┬────────┘                  │  └ Claude (gated)│
                                            │                            └──────────────────┘
   ┌───────────────┬───────────────┬────────┴───────┬───────────────┬───────────────┐
   ▼               ▼               ▼                ▼               ▼               ▼
 graph          monitoring        ews            copilot        simulation       stress
 (M1)             (M2)            (M3)             (M4)            (M5)            (M6)
   │               │               │                │               │               │
   │               └──► alerts.py ◄─┘ (unified IntelligenceAlert inbox: M2/M3/M11)   │
   ▼               ▼               ▼                ▼               ▼               ▼
 optimization     rm            command           nlq         recommendations   workflow
 (M7)            (M8)           (M9)              (M10)           (M11)           (M12)
                                                                    │               │
                                              governance (M13) ◄────┘         datalake (M14)
                                                     │                              │
                                          ┌──────────┴───────────┐      append-only analytical store
                                          ▼                      ▼      (mirrors live tables)
                                Phase 6 ml.registry     ml_models table
```

### Layering & principles
- **Grounded, never fabricated.** Every engine reads real data through
  `data_access.profile()`. Missing figures stay `None` (PD is the one calibrated
  fallback, mirroring the Phase 1 scorecard). The Copilot/NLQ LLM layer *phrases*
  grounding; it cannot introduce a number that isn't in the grounding dict.
- **Provider-agnostic LLM** (matches the Phase 7/8 connector pattern): a
  `LocalDeterministicProvider` default that runs fully offline, and a gated
  `ClaudeProvider` (needs `anthropic` + `ANTHROPIC_API_KEY`) that degrades to local
  automatically. Set `COPILOT_LLM_PROVIDER=claude` to switch — no call site changes.
- **Additive persistence.** 19 new tables in one migration; every row carries an
  optional `tenant_id` (nullable → legacy single-tenant flows keep working) and
  references companies by a stable `company_ref` string to stay loosely coupled.
- **Repository + service + DTO separation, small modules, type hints, Pydantic v2**
  request schemas, comprehensive docstrings.

### Data model (migration `d0e1f2a3b4c5`, down_revision `c9d0e1f2a3b4`)
`kg_entities`, `kg_relationships`, `monitoring_signals`, `intelligence_alerts`,
`ews_assessments`, `copilot_conversations`, `copilot_messages`, `simulation_runs`,
`stress_test_runs`, `portfolio_optimizations`, `rm_interactions`, `rm_opportunities`,
`nl_query_logs`, `recommendations`, `workflow_actions`, `model_governance_events`,
`model_validations`, `datalake_datasets`, `datalake_objects`.

### RBAC
13 new permissions in a new **"Autonomous Intelligence"** category (catalog now
**86 permissions / 9 roles**, up from 73): `intelligence.view/manage`, `copilot.use`,
`simulation.run`, `portfolio.optimize`, `rm.workspace`, `command.center`,
`recommendations.view/act`, `governance.view/manage`, `datalake.view/manage`.
Broadly readable by the credit-workflow roles; heavy engines (simulation,
optimization, governance) are gated by seniority. `test_rbac` count assertions
updated 73 → 86.

---

## 3. Sequence diagrams

### 3.1 Real-Time Monitoring → Alert → Escalation (M2)
```
Connector/Sync ──observations──► POST /api/ai/monitoring/run
                                        │
                                        ▼
                              monitoring.run_monitoring
                                        │ per-source detectors (financial, mca, …)
                                        ▼
                              record MonitoringSignal (priority-scored)
                                        │ severity ∈ {high, critical}?
                          ┌─────────────┴─────────────┐
                         no                           yes
                          │                            ▼
                          │                 alerts.raise_alert (dedup, IntelligenceAlert)
                          ▼                            │
                 summary {signals, escalation}◄────────┘  reassessment_recommended = true
```

### 3.2 AI Copilot answer (M4) — grounded, LLM phrases only
```
User ──question──► POST /api/ai/copilot/ask
                         │
                         ▼
                 detect_intent(question)
                         │
                         ▼
                 build_grounding ──reads──► data_access / FinancialAnalysis /
                         │                  RiskExplanation / FraudCheck / recommendations
                         ▼
                 llm.get_provider().compose(question, grounding, intent)
                         │   (Local template or Claude — grounding is authoritative)
                         ▼
                 persist CopilotMessage(role=assistant, grounding, citations)
                         ▼
                 { answer, intent, provider, grounding, citations }
```

### 3.3 Governance-gated model approval (M13)
```
Risk mgr ─► POST /governance/models/{id}/validate
                 │  checks metrics vs thresholds → ModelValidation(status)
                 ▼
           POST /governance/models/{id}/approve
                 │  require_validation && status != failed ?  ──no──► 400 "must pass validation"
                 │ yes
                 ▼
           Phase 6 ml.registry.submit_for_approval → approve
                 ▼
           record ModelGovernanceEvent(event_type=approval)
                 ▼
           POST /governance/models/{id}/promote → registry.promote + governance event
```

### 3.4 Autonomous workflow (M12)
```
POST /api/ai/workflow/run {company_ref, mode}
        │
        ▼
   workflow.plan ──uses──► alerts + ews.evaluate + recommendations.recommend
        │  derive actions (monitoring cadence, committee review, assign reviewer,
        │  request docs, create task, …) each with trigger + rationale
        ▼
   persist WorkflowAction rows
        │ mode == "execute"?
        ├─ proposed → status=pending (advisory)
        └─ execute  → safe actions run best-effort (e.g. Phase 5 create_task) → status=executed
```

---

## 4. Frontend

New feature folder `frontend/src/features/autonomous-intelligence/`
(`types.ts` / `api.ts` / `hooks.ts` / `index.ts`), reusing the shared `OpsLayout`
+ risk/operations primitives. **11 new routes** wired into a new sidebar group
**"Autonomous Intelligence"**: `knowledge-graph`, `risk-monitoring`, `early-warning`,
`copilot`, `simulation`, `stress-testing-9`, `portfolio-optimization`, `rm-workspace`,
`command-center`, `nl-analytics`, `model-governance`. Shared `lib/http.ts` gained an
additive `apiPatch` helper. `npm run build` regenerates `routeTree.gen.ts`.

---

## 5. Testing (M15)

180 new tests across 9 files (helper: `tests/_autonomous_helpers.py`):
`test_autonomous_common`, `_data_access`, `_graph`, `_monitoring_ews`, `_copilot`,
`_simulation_stress`, `_portfolio_rm`, `_command_nlq`, `_recommendations_workflow`,
`_governance_datalake`, `_api`. Same conventions as prior phases (unittest,
in-memory SQLite + StaticPool, TestClient with `get_db`/`get_current_user`
overridden, `sync_rbac` in setup). API tests assert RBAC enforcement
(e.g. viewer 403 on manage endpoints; analyst 403 on `portfolio.optimize`/`governance.manage`).

**Totals:** 627 → **807** backend tests, all green. No regressions.

---

## 6. Verification checklist

- [x] `python -m unittest discover -s backend/tests` — 807 passed
- [x] Alembic single head `d0e1f2a3b4c5`, linear, downgrade+upgrade round-trip clean
- [x] `npx tsc --noEmit` clean; `npm run build` clean (routeTree regenerated)
- [x] App boots; 65 `/api/ai/*` routes registered; no existing route modified
- [x] RBAC catalog 86 perms / 9 roles; `test_rbac` updated
- [x] LLM layer offline-safe by default; Claude adapter gated + graceful-degrading

## 7. Notes / future hooks
- The Claude adapter is wired but gated (no key in this environment) — the
  intended "wired but gated" behavior, identical to Phase 7 production connectors.
- Monitoring is pull-driven (`run_monitoring(observations)`); a Phase 5 background
  job can call it on a schedule to make it continuous in production.
- Data-lake ingestion adapters cover assessments/simulations/monitoring; more
  namespaces can register adapters without schema changes.
