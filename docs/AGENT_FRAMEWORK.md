# Multi-Agent Framework (M2)

## Overview

A grounding-first multi-agent system that behaves like a credit committee:
a **planner** decomposes a goal into specialist workers, a **coordinator**
executes them (with retry + reflection), and their contributions are fused by
**confidence-weighted consensus** with explicit **conflict resolution** and an
**executive synthesis**. Every run + step persists to `aip_agent_runs` /
`aip_agent_steps`.

## The 12 specialist agents

Credit Analyst · Risk Analyst · Fraud Investigator · Compliance Officer ·
Portfolio Manager · Relationship Manager · Financial-Statement Expert ·
Banking-Policy Expert · Regulatory Expert · Underwriter · Document Specialist ·
Executive Advisor (synthesis).

Each worker `gather()`s deterministic grounding from its domain (profile via
`data_access`, ratios from `engine_input`, portfolio stats, or the RAG index for
policy/regulatory/document experts), emits a `Contribution` (summary, facts,
signal ∈ {positive, caution, negative, neutral}, confidence, recommendation,
citations), and self-critiques (`_critique`).

## Planner

`plan(goal, roles?)` either honours explicit `roles` or scores each agent by
keyword overlap with the goal, always includes the core credit + risk analysts,
and pads to a meaningful committee. Returns an ordered plan with rationale.

## Coordinator

`run(...)`:
1. Resolves the borrower profile once and shares it in the context.
2. Executes workers sequentially or in parallel (`ThreadPoolExecutor`,
   `parallel=True`).
3. Retries a failing worker (`retries`) before marking it `failed` (excluded from
   consensus).
4. Computes consensus, runs the executive synthesis, persists everything.

## Consensus, voting & conflict resolution

- Each signal maps to a vote weight (`positive +1`, `caution −0.35`,
  `negative −1`, `neutral 0`), weighted by the agent's confidence.
- `vote_score = Σ(weight·confidence) / Σ(confidence)`. Decision:
  `≥ 0.4 → APPROVE`, `≤ −0.4 → DECLINE`, else `REVIEW`.
- **Conflict:** if strong positive and strong negative contributions coexist, a
  `signal_conflict` is recorded, resolution is deferred to the executive synthesis
  and overall confidence is reduced (×0.7).
- Agreement = share of the modal signal; confidence blends `|vote_score|` with a
  conflict penalty.

## Traceability

`GET /api/aip/agents/runs/{id}` returns the plan, consensus, every contribution
and every persisted step (role, status, critique, score). RBAC: `aip.agents.run`.

## Endpoints

`GET /roster`, `POST /plan`, `POST /run`, `GET /runs`, `GET /runs/{id}`.
