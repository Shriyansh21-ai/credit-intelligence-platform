# Phase 10 — Architecture Report

## Position in the platform
Phase 10 is the **AI-native operating-system layer** sitting on top of the Phases 1–9
stack (deterministic engines → ML platform → connectors → SaaS platform → Phase 9 AI
brain). It is a single cohesive module, `banking_os`, added without modifying any prior
layer — the same additive pattern used by Phases 6–9.

```
Routes  (routes/banking_os.py, 12 routers, /api/os/*)
  │  FastAPI + Depends DI + require_permission RBAC + typed Pydantic bodies
Services (services/banking_os/*)         ← business logic, repository pattern
  │  policy · committee · search · prompt · llm_router · data_fabric
  │  workflow_studio · marketplace · scenario · fairness · graph_advanced · exec_center
  │  common (pure helpers: tokenize, signature, bm25_idf, evidence, clamp)
Models  (models/banking_os.py, 25 os_* tables)   ← SQLAlchemy ORM
  │  Alembic migration e2f3a4b5c6d7 (single source of truth for schema)
DB      (SQLite dev / Postgres prod)
```

## Design principles
- **Additive & backward compatible.** No Phase 1–9 file's behavior changed. New tables,
  new routes, new permissions only. All 807 prior tests still pass unchanged.
- **Deterministic-first.** Policy evaluation, committee tallying, search ranking, workflow
  execution, scenario Monte Carlo (seeded), fairness metrics and marketplace plugins are
  all closed-form and reproducible. LLMs are used only where generative (copilot/prompt),
  behind the M9 router boundary.
- **Pure cores, DB-free.** The rule evaluator (`policy.evaluate_rules`), tokenizer,
  signatures, contract validator (`data_fabric.evaluate_records`), workflow engine
  (`execute_graph`), Monte Carlo and fairness math are pure functions — trivially unit
  tested and reused across the persistence and playground paths.
- **Repository pattern + DI.** Services expose repository functions; routes inject the
  session via `Depends(get_db)` and the user via `require_permission(...)`.
- **Reuse over duplication.** M11 decision branches reuse the M7 condition evaluator;
  Phase 10 `common` re-exports the Phase 9 numeric helpers; M1/M10/M13 read Phase 9 tables
  read-only; the frontend reuses the shared `OpsLayout` / primitives.
- **Multi-tenant & observable.** Nullable `tenant_id` throughout; requests flow through the
  existing audit / tenant / observability middleware unchanged.

## Module boundaries
Each service is a focused engine with a narrow public surface (repository + orchestration +
`*_dict` serializers). Cross-service coupling is limited to: `policy.eval_condition` reused
by `workflow_studio`; `common` shared helpers; read-only reads of Phase 9 `kg_*`,
`intelligence_alerts` and Phase 1 `enterprise_assessment`.

## Extensibility
- Real LLM vendors: drop-in at `llm_router._invoke`.
- Real vector search: swap `search._semantic_score` for an ANN backend (interface-ready).
- Custom marketplace plugins: `marketplace.register_custom_plugin(key, fn)`.
- New workflow node behaviors and policy operators are data-driven additions.
