# RAG Architecture (M1)

## Pipeline

```
register_source → ingest_document → [chunk → embed → index] → search (hybrid) → answer (cited)
```

### Knowledge sources
`aip_knowledge_sources` registers a source with a `source_type` from the taxonomy
(credit_policy, rbi_circular, basel_guideline, financial_statement, annual_report,
loan_agreement, committee_note, audit_report, ocr_document, customer_interaction,
email, external_manual, other). New source kinds need no schema change.

### Ingestion (`ingest_document`)
- Content is chunked by `common.chunk_text` (sentence-aware, ~900 chars,
  150-char overlap) so retrieval never loses cross-boundary context.
- Each chunk is embedded (`HashingEmbedder` by default) and upserted into
  `aip_vectors` under namespace `rag`, ref_type `chunk`, with rich metadata
  (document_id, source_id, source_type, doc_type, title, ordinal).
- **Versioning + lineage:** re-ingesting the same `external_id` supersedes the
  prior current document (`is_current=False`), bumps the version, records lineage
  (`supersedes_document_id`, `previous_version`, `previous_checksum`) and removes
  the old vectors so retrieval only sees the current version. Identical content
  (same checksum) is an idempotent no-op.

### Hybrid retrieval (`search`)
1. Dense candidate recall: cosine over `aip_vectors` (tenant + metadata filtered).
2. Lexical scoring: `common.bm25_lite` over the candidate chunks.
3. Fusion: min-max normalise both, `fused = w·semantic + (1-w)·lexical`
   (`semantic_weight` default 0.6), then rerank.
4. Metadata filtering (`source_types`, `doc_type`, arbitrary `metadata_filter`)
   and tenant isolation are applied throughout.

### Citation engine + confidence (`answer`)
- `build_citations` turns hits into indexed citations (label, document_id,
  chunk_id, source_type, score, snippet).
- `_confidence` blends top similarity, mean-of-top-3 and coverage.
- Grounding (headline/narrative/facts/citations) is composed by the grounding-
  first LLM. Every answer is persisted to `aip_rag_queries` with retrieved hits,
  citations, provider, tokens and latency.

## Pluggability

- **Embeddings:** swap `AIP_EMBEDDING_PROVIDER`; the `Embedder` ABC is the seam.
- **Vector store:** `AIP_VECTOR_STORE=sql` (default, any DB) or `pgvector`
  (native `<=>` on Postgres). Pinecone/Weaviate/Milvus/Qdrant implement the same
  `upsert/query/delete/count` interface.
- **Tenant isolation:** every vector row carries `tenant_id`; queries always
  filter on it.

## Endpoints

`POST /api/aip/rag/sources`, `GET /sources`, `GET /source-types`,
`POST /documents`, `GET /documents`, `POST /search`, `POST /answer`, `GET /stats`.
RBAC: `aip.rag.view` / `aip.rag.query` / `aip.rag.manage`.
