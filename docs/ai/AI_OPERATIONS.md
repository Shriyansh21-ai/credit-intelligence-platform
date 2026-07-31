# AI Operations (M14 + running the platform)

## Monitoring (M14)

`services/ai_platform/ai_monitoring.py` measures platform health from the
artifacts the platform already produces (M5 evaluations, M1 RAG queries, M11
feedback) — no separate instrumentation needed.

**Metrics:** hallucination, retrieval_quality, accuracy, latency, cost,
feedback_score, drift (change in accuracy between older/newer evaluation halves).

**`run_monitoring`** snapshots metrics into `aip_ai_metrics` and opens
`aip_ai_incidents` on threshold breach (deduplicating open incidents per metric):

| Metric | Breach | Severity |
|--------|--------|----------|
| hallucination | > 0.30 | high |
| retrieval_quality | < 0.40 | medium |
| latency (ms) | > 3000 | medium |
| cost (USD) | > 0.08 | low |
| accuracy | < 0.60 | high |
| feedback_score | < 0.50 | high |
| drift | > 0.25 | medium |

**`dashboard`** rolls up current metrics, open incidents and a health verdict
(healthy / degraded / critical). `resolve_incident` closes an incident.

## Configuration reference

| Variable | Purpose | Default |
|----------|---------|---------|
| `AIP_LLM_PROVIDER` | AI-platform LLM | local |
| `AIP_EMBEDDING_PROVIDER` | embeddings | hashing |
| `AIP_VECTOR_STORE` | vector store | sql |
| `ANTHROPIC_API_KEY` | enable Claude | unset |

## Running & testing

- Migrations: `alembic upgrade head` (head `f3a4b5c6d7e8`). Reversible.
- Backend tests: `.venv/Scripts/python.exe -m pytest backend/tests`
  (full suite ~8–10 min; develop against `test_ai_platform_*.py`).
- Frontend: `npx tsc --noEmit` then `npm run build` (build regenerates the
  TanStack route tree).

## Production scaling notes

- Switch `AIP_VECTOR_STORE=pgvector` and provision Postgres + the `vector`
  extension for indexed ANN search; the SQL default is fine for dev.
- Switch `AIP_LLM_PROVIDER=claude` with a key for higher-quality phrasing.
- All AI endpoints are additive under `/api/aip/*`; scale them independently.

## Endpoints

`POST /api/aip/monitoring/run`, `POST /metric`, `GET /dashboard`,
`GET /incidents`, `POST /incidents/{id}/resolve`.
RBAC: `aip.monitoring.view` / `aip.monitoring.manage`.
