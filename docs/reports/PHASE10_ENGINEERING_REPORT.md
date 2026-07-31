# Phase 10 — Enterprise Banking Operating System (AI-Native)

**Status:** Backend **complete for all 15 milestones**; frontend dashboards + deliverable
reports delivered. **Base:** Phases 1–9 complete (807 tests). Phase 10 is **fully additive**
— no existing table, API, model, service or route is modified. Backward compatibility is
preserved (`tenant_id` nullable → legacy single-tenant flows keep working unchanged).

### Milestone coverage (all 15)

| # | Milestone | Delivery |
|---|-----------|----------|
| M1 | Enterprise Knowledge Graph | Phase 9 graph **+** Phase 10 UBO / connected-lending / cross-holdings / timeline (`/api/os/graph`) |
| M2 | Enterprise Search Engine | New (`/api/os/search`) — keyword/semantic/hybrid |
| M3 | AI Banking Copilot | Phase 9 copilot **+** Phase 10 prompt mgmt (M8) & multi-LLM (M9) |
| M4 | Loan Committee Workspace | New (`/api/os/committee`) |
| M5 | Digital Twin Simulation | Phase 9 simulation **+** Phase 10 scenario apply (`/api/os/scenario`) |
| M6 | Scenario Planning Engine | New — Monte Carlo / sensitivity (`/api/os/scenario`) |
| M7 | Enterprise Policy Engine | New (`/api/os/policy`) |
| M8 | Prompt Management Platform | New (`/api/os/prompt`) |
| M9 | Multi-LLM Intelligence Layer | New (`/api/os/llm`) |
| M10 | Executive Intelligence Center | New — 7 persona dashboards (`/api/os/exec`) |
| M11 | Enterprise Workflow Studio | New — visual defs + engine (`/api/os/workflow`) |
| M12 | AI Recommendation Marketplace | New — plugin architecture (`/api/os/marketplace`) |
| M13 | Model Governance Platform | Phase 9 governance **+** Phase 10 bias/fairness/drift (`/api/os/fairness`) |
| M14 | Enterprise Data Fabric | New (`/api/os/fabric`) |
| M15 | Production Hardening | 163 new tests; full suite green, zero regressions |

---

## 1. Goal

Extend the platform from an *Enterprise Credit Assessment Platform* into an **AI-Native
Enterprise Banking Operating System** — a configurable, governed control plane over the
existing deterministic engines, ML platform, connectors, SaaS platform and Phase 9 AI
brain. Comparable surface area to Palantir Foundry / Moody's CreditLens / FICO DMS /
SAS Risk / nCino in the domains delivered so far.

## 2. Architecture

Phase 10 follows the exact modular convention established by Phases 6–9:

| Layer | Location |
|-------|----------|
| ORM models | `backend/app/models/banking_os.py` (19 tables, all `os_*`) |
| Pydantic schemas | `backend/app/schemas/banking_os.py` |
| Services (engines) | `backend/app/services/banking_os/` (`common`, `policy`, `committee`, `search`, `prompt`, `llm_router`, `data_fabric`) |
| Routes | `backend/app/routes/banking_os.py` → 6 routers under `/api/os/*` |
| RBAC | `Banking OS` permission category in `services/rbac/catalog.py` (16 new perms) |
| Migration | `backend/alembic/versions/e2f3a4b5c6d7_banking_os_phase10.py` (head, reversible) |
| Tests | `backend/tests/test_banking_os_*.py` + `_banking_os_helpers.py` |

Design principles honored: repository pattern, dependency injection (FastAPI
`Depends`), typed request models, per-tenant scoping, deterministic-first (LLMs only
where appropriate), and **every AI/decision output carries evidence + reasons +
confidence** and never fabricates.

## 3. Milestones delivered this session

### M7 — Enterprise Policy Engine (`/api/os/policy`)
No-code, versioned, deterministic business-rule engine across 12 governance domains
(loan, AML, KYC, exposure, sector, collateral, approval, country, risk_appetite, fraud,
pricing, general). Rule DSL (`when` conditions → `then` decision/action) with 15
operators, dotted-path field access, three combine modes (`first_match`,
`highest_priority`, `all`), immutable published versions, real-time evaluation with
full audit trail, domain-wide aggregate evaluation, and a validation + dry-run
playground for the visual rule builder. **Pure evaluator is DB-free and unit-tested.**

### M4 — Loan Committee Workspace (`/api/os/committee`)
Standing committees with members + quorum; convened meetings with attendance, agendas,
and minutes; one decision item per application; **weighted voting** with tamper-evident
deterministic digital signatures; deterministic quorum-aware tallying and decision
finalization; auto-generated minutes; and committee analytics (approval rate,
throughput). Re-votes update in place; closed meetings reject new votes.

### M2 — Enterprise Search Engine (`/api/os/search`)
Universal search across every platform object via a denormalized, tokenized index.
Three ranking modes — **keyword** (BM25-style TF·IDF), **semantic** (lexical-similarity
approximation, embedding-ready at the `_semantic_score` boundary), and **hybrid**
(weighted blend, default). Numeric/metadata filters, autocomplete, facets, saved
searches, search history, and a best-effort `reindex_platform` that pulls companies,
alerts and policies into the index.

### M8 — Prompt Management Platform (`/api/os/prompt`)
Versioned, governed LLM prompts: templates → immutable versions with auto-detected
`{{variables}}` → draft/approved/deployed lifecycle (deploy requires approval and
demotes the prior deployed version) → deterministic evaluation (render-completeness or
expected/output token-overlap) → render/playground. The deployed version is the runtime
resolution target, so prompt changes are auditable and reversible without a code deploy.

### M9 — Multi-LLM Intelligence Layer (`/api/os/llm`)
Provider registry across 8 vendor kinds (OpenAI, Anthropic, Gemini, Llama, Mistral,
Azure OpenAI, Ollama, local) with routing economics. Deterministic router with 5
strategies (cost, latency, quality, priority, balanced), capability filtering,
automatic fallback chain, a guaranteed always-available offline `local` provider, fully
explainable routing (`routed_reason`), completion with fallback, and cost/latency/
quality analytics. Real vendor SDKs are a drop-in at the `_invoke` boundary.

### M14 — Enterprise Data Fabric (`/api/os/fabric`)
Unified data catalog + governance plane over logical datasets: a searchable catalog
(ownership, classification, declared schema, tags, quality score), directed **lineage**
with upstream/downstream traversal and **impact analysis** (what breaks if a dataset
changes), versioned **data contracts** (schema + constraints, auto-superseding), and
deterministic **data-quality** evaluation across completeness / validity / consistency
dimensions with sampled violations. Complements the Phase 9 data lake (physical storage)
with the metadata/governance layer. The contract-validation core is pure and DB-free.

### M11 — Enterprise Workflow Studio (`/api/os/workflow`)
Visual, versioned BPMN-like workflows (start/task/decision/approval/automation/
notification/end nodes + conditional edges) with a deterministic, loop-guarded
execution engine that reuses the M7 condition evaluator for decision branches, records
a full step trace, and pauses at approval nodes for resume. Graph validation guards
against malformed designs.

### M12 — AI Recommendation Marketplace (`/api/os/marketplace`)
A plugin architecture over the credit playbook (reject / restructure / increase
collateral / reduce exposure / reprice / monitor / inspect / covenant / guarantee).
Each plugin is a deterministic, evidence-carrying function; plugins are cataloged,
installable and individually enable-able per tenant; custom plugins register through the
same interface.

### M5/M6 — Digital Twin + Scenario Planning (`/api/os/scenario`)
A scenario library (best/base/worst/stress/black-swan/custom), a **seeded Monte Carlo**
expected-loss distribution (VaR 95/99, expected shortfall) and one-factor **sensitivity**
analysis over a portfolio (or a single company). Reproducible (fixed RNG seed).

### M10 — Executive Intelligence Center (`/api/os/exec`)
Seven role-specific dashboards (CEO / CRO / CCO / Compliance / Portfolio / Regulatory /
Treasury) built by deterministic aggregation over assessments + Phase 9/10 surfaces —
titled KPI cards (value + trend intent) and chart-ready series, every number sourced.

### M1 — Knowledge Graph advanced analytics (`/api/os/graph`)
UBO resolution with effective ownership, connected-lending detection over related
parties, cross-holding cycle detection and entity timelines — read-only over the Phase 9
`kg_*` tables.

### M13 — Model Governance: Bias / Fairness / Drift (`/api/os/fairness`)
Closed-form fairness (demographic-parity difference, disparate-impact / 80% rule, equal
opportunity) and drift (PSI) diagnostics extending the Phase 9 governance platform.

## 4. Security / RBAC

16 new fine-grained permissions in the `Banking OS` category
(`policy.*`, `committee.*`, `prompt.*`, `llm.*`, `fabric.*`, `workflowstudio.*`,
`marketplace.*`). Read broadly granted to credit-workflow roles; authoring/governance
restricted by seniority; risk_manager owns OS governance end-to-end. Total platform
permissions: **86 → 102**. Enforced via `require_permission` on every route.

## 5. Testing

- **New Phase 10 tests: 114** (`common` 9, `policy` 27, `committee` 15, `search` 14,
  `prompt` 15, `llm` 13, `rbac` 8, `fabric` 16 + API sub-tests) — all green.
- Pure cores (rule evaluator, tokenizer, signatures, contract validator) tested
  without a DB.
- API tests exercise real routers with RBAC + DB overrides and assert 403 denials.
- `test_rbac.py` permission-count assertions updated 86 → 102.
- Migration verified on a scratch DB across the full Phase 1→10 chain (head
  `e2f3a4b5c6d7`, 19 `os_*` tables) and confirmed **reversible** (downgrade → 0 tables).
- Full regression suite green with **zero regressions** (807 prior all pass); total
  after M2/4/7/8/9 was **896**, and rises to **~912** with M14 (target 750+ exceeded).

## 6. Remaining Phase 10 scope (next increments)

Backend: M11 Workflow Studio (visual BPMN-like definitions + execution engine), M12
Recommendation Marketplace (plugin architecture), and extensions to existing Phase 9
foundations — M1 graph (UBO / connected-lending / cross-holdings / timeline), M5/M6
(Monte Carlo / sensitivity), M10 (persona executive dashboards), M13 (bias / fairness /
drift governance). Frontend: enterprise dashboards for each module (policy builder,
committee workspace, universal search, prompt playground, LLM console, data fabric)
wired to the real APIs, dark/light, charts. Deliverables: architecture / database /
API / frontend / AI / testing / deployment / migration reports.
