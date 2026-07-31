# AI Intelligence Platform — Architecture

## Layering

The AI platform is a **layer**, not an application. It sits on top of the
deterministic Phase 1–3 engines, the Phase 4/6 ML layers, the Phase 5 decision
platform, the Phase 7 connectors, the Phase 8 SaaS platform, the Phase 9
autonomous intelligence and the Phase 10 Banking OS. It reads from them (via
`services/autonomous/data_access.py` and the RAG index) and never mutates them.

```
        ┌───────────────────────── /api/aip/* routers ─────────────────────────┐
        │ rag · agents · memory · prompts · eval · investigate · reports ·      │
        │ workflows · chat · research · learning · governance · explain · monitor│
        └───────────────────────────────────────────────────────────────────────┘
                                     │ services
   ┌─────────────────────────────────────────────────────────────────────────────┐
   │ Milestone services (rag, agents, memory, prompts, evaluation, investigation,  │
   │ reports, workflows, chat, research, learning, governance, explainability,     │
   │ ai_monitoring)                                                                │
   └─────────────────────────────────────────────────────────────────────────────┘
                                     │ foundation
   ┌───────────────┬───────────────┬───────────────┬───────────────────────────────┐
   │ common        │ embeddings    │ vectorstore   │ llm (grounding-first, gated)   │
   │ (pure helpers)│ (Embedder ABC)│ (VectorStore  │                                │
   │               │               │  ABC)         │                                │
   └───────────────┴───────────────┴───────────────┴───────────────────────────────┘
                                     │ reads (never writes)
   ┌───────────────────────────────────────────────────────────────────────────────┐
   │ Phases 1–11: enterprise assessments, financial analysis, ML, connectors, SaaS, │
   │ autonomous intelligence, Banking OS                                            │
   └───────────────────────────────────────────────────────────────────────────────┘
```

## Foundation modules (`services/ai_platform/`)

- **common.py** — pure, deterministic helpers: tokenization, stop-words,
  sentence-aware overlapping chunking, token estimation, vector math (dot/cosine/
  L2), lexical similarity (Jaccard, single-doc BM25-lite), min-max scaling,
  content hashing. No DB/network. Safe to import anywhere.
- **embeddings.py** — `Embedder` ABC + `HashingEmbedder` (deterministic offline
  signed feature-hashing into a fixed 256-dim, L2-normalised vector). Resolved by
  `get_embedder()` from `AIP_EMBEDDING_PROVIDER`; unknown/unavailable → hashing.
- **vectorstore.py** — `VectorStore` ABC (`upsert`/`query`/`delete`/`count` keyed
  by namespace + ref_type/ref_id + metadata filters + tenant). `SqlVectorStore`
  persists vectors as JSON in `aip_vectors` and ranks with Python cosine (works on
  SQLite and Postgres). `PgVectorStore` is a gated native adapter. Roadmap:
  Pinecone/Weaviate/Milvus/Qdrant — implement the same four methods.
- **llm.py** — `LLMClient` ABC with an instrumented `generate()` returning text +
  usage (tokens, latency, estimated cost, grounded flag). `LocalDeterministicLLM`
  composes grounding into prose offline; `ClaudeLLM` is gated behind `anthropic`
  + `ANTHROPIC_API_KEY` and still only phrases grounding.

## Persistence

31 additive `aip_*` tables in `models/ai_platform.py`, created by migration
`f3a4b5c6d7e8` (down_revision `e2f3a4b5c6d7`). Notable design choices:

- A single unified `aip_vectors` table backs both RAG chunks and memory, keyed by
  `(tenant_id, namespace, ref_type, ref_id)`.
- Every table carries a nullable `tenant_id` so legacy single-tenant flows keep
  working; multi-tenant isolation is enforced in every query.
- Domain objects are referenced by stable strings (`company_ref`, `target_ref`,
  `asset_ref`) rather than hard FKs into prior-phase tables — loose coupling.
- The migration builds tables from the ORM metadata (filtered to `aip_*`) so it
  can never drift from the models, and `downgrade()` drops only those tables.

## Request lifecycle (grounding-first)

1. Router resolves tenant (`_tenant`) and actor (`_uref`) and checks RBAC
   (`require_permission("aip.*")`).
2. Service assembles **deterministic grounding** from real data
   (`data_access.profile`, RAG hits, portfolio, memory).
3. The LLM client phrases the grounding (local by default). Numbers only ever come
   from grounding.
4. The result + its citations/evidence/confidence is persisted for traceability.

## Cross-milestone composition

- Agents (M2), investigation (M6), reports (M7), chat (M9) and research (M10) all
  call the RAG (M1) and the shared read layer.
- Investigation (M6) produces a report (M7).
- Workflows (M8) orchestrate agent/RAG/memory/report nodes.
- Evaluation (M5) scores RAG/agent/report artifacts; monitoring (M14) aggregates
  evaluations + feedback; governance (M12) tracks the assets those produce.
