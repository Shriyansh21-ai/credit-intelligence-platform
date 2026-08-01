# AI Intelligence Platform — Roadmap

## Delivered

RAG, multi-agent system, long-term memory, prompt engineering, evaluation,
autonomous investigation, report generation, workflow builder, conversational AI,
research assistant, continuous learning, governance, explainability, monitoring —
all additive, backward-compatible, offline by default, 1277 backend tests green,
frontend clean.

## Near-term extensions (no schema change required)

- **Real embeddings & vector DB.** Implement `Embedder` for a hosted model and
  wire a `pgvector` native column; the ABCs are the only seam. Add Pinecone /
  Weaviate / Milvus / Qdrant adapters (`upsert/query/delete/count`).
- **Real Claude phrasing.** Turn on `AIP_LLM_PROVIDER=claude` with a key; grounding
  stays deterministic, so only phrasing quality changes. Prefer Opus 4.8 / Sonnet 5.
- **Streaming chat** for the M9 assistant.
- **Reranker model** to replace the BM25-lite lexical fusion in M1.

## Medium-term

- **External research feeds** (economic indicators, ESG, news) behind connector
  nodes, so M10 research grounds on live external data (with citations) rather
  than only internal + indexed knowledge.
- **Visual workflow canvas** (drag-drop) over the M8 graph engine; the backend
  already validates and executes arbitrary node/edge graphs.
- **Automated retraining execution** wired from M11 training events into the
  Phase 6 ML training pipeline.
- **Human-in-the-loop approval UI** for M8 approval-gate nodes and M4 prompt
  approvals.

## Longer-term

- **Agent tool-use** (letting agents call connectors/APIs directly under policy).
- **Fine-tuned domain models** governed through M12 with full lineage.
- **Multi-modal ingestion** (charts/tables in annual reports) into the RAG index.
- **Continuous evaluation gates** in CI that fail a deploy if scorecards regress.

## Non-goals (by design)

- Replacing or rewriting any prior-phase engine — the AI layer stays additive.
- Trusting an LLM for numbers — grounding-first is permanent.
