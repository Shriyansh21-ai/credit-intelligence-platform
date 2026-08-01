"""M1 — Enterprise Retrieval Augmented Generation platform.

A complete, production-shaped RAG pipeline built on the pluggable embedding +
vector-store seam

    register_source → ingest_document (chunk → embed → index, versioned + lineage)
      → search (hybrid semantic + lexical, reranked, metadata-filtered, tenant-isolated)
      → answer (grounded composition with a citation engine + confidence scoring)

Knowledge sources cover internal credit policies, RBI circulars, Basel guidelines
financial statements, annual reports, loan agreements, committee notes, audit
reports, OCR documents, customer interactions, emails and external manuals — all
distinguished by ``source_type`` and free-form metadata rather than bespoke
tables, so new source kinds need no schema change.

Everything is deterministic and offline by default; swapping in real embeddings
(``AIP_EMBEDDING_PROVIDER``), a real LLM (``AIP_LLM_PROVIDER``) or a real vector
DB (``AIP_VECTOR_STORE``) changes quality, not behaviour.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from backend.app.models.ai_platform import (
    AIPChunk, AIPDocument, AIPKnowledgeSource, AIPRagQuery,
)
from backend.app.services.ai_platform import common, embeddings, llm as llm_mod, vectorstore

NAMESPACE = "rag"

# Recognised knowledge-source taxonomy (advisory — arbitrary types are allowed).
SOURCE_TYPES = [
    "credit_policy", "rbi_circular", "basel_guideline", "financial_statement",
    "annual_report", "loan_agreement", "committee_note", "audit_report",
    "ocr_document", "customer_interaction", "email", "external_manual", "other",
]


# ---------------------------------------------------------------------------
# Source registry
# ---------------------------------------------------------------------------
def register_source(db: Session, *, key: str, name: str, source_type: str,
                    description: Optional[str] = None,
                    config: Optional[Dict[str, Any]] = None,
                    tenant_id: Optional[int] = None,
                    created_by: Optional[str] = None) -> AIPKnowledgeSource:
    existing = (db.query(AIPKnowledgeSource)
                .filter(AIPKnowledgeSource.tenant_id == tenant_id,
                        AIPKnowledgeSource.key == key).first())
    if existing:
        existing.name = name
        existing.source_type = source_type
        existing.description = description
        existing.config = config or existing.config
        db.commit()
        db.refresh(existing)
        return existing
    src = AIPKnowledgeSource(
        tenant_id=tenant_id, key=key, name=name, source_type=source_type,
        description=description, config=config or {}, created_by=created_by,
        created_at=common.utcnow(), updated_at=common.utcnow(),
    )
    db.add(src)
    db.commit()
    db.refresh(src)
    return src


def list_sources(db: Session, *, tenant_id: Optional[int] = None) -> List[AIPKnowledgeSource]:
    return (db.query(AIPKnowledgeSource)
            .filter(AIPKnowledgeSource.tenant_id == tenant_id)
            .order_by(AIPKnowledgeSource.id.desc()).all())


def _resolve_source(db: Session, *, source_key: Optional[str], source_id: Optional[int],
                    tenant_id: Optional[int]) -> AIPKnowledgeSource:
    q = db.query(AIPKnowledgeSource).filter(AIPKnowledgeSource.tenant_id == tenant_id)
    src = None
    if source_id is not None:
        src = q.filter(AIPKnowledgeSource.id == source_id).first()
    elif source_key is not None:
        src = q.filter(AIPKnowledgeSource.key == source_key).first()
    if src is None:
        raise ValueError("knowledge source not found")
    return src


# ---------------------------------------------------------------------------
# Ingestion pipeline (chunk → embed → index) with versioning + lineage
# ---------------------------------------------------------------------------
def ingest_document(db: Session, *, title: str, text: str,
                    source_key: Optional[str] = None, source_id: Optional[int] = None,
                    doc_type: Optional[str] = None, external_id: Optional[str] = None,
                    uri: Optional[str] = None, language: str = "en",
                    metadata: Optional[Dict[str, Any]] = None,
                    tenant_id: Optional[int] = None,
                    created_by: Optional[str] = None,
                    chunk_size: int = 900, overlap: int = 150) -> AIPDocument:
    """Ingest one document into a knowledge source.

    Re-ingesting the same ``external_id`` supersedes the previous version (the old
    document is marked ``is_current=False`` and its vectors are removed), giving
    versioned knowledge with a lineage trail. Content-addressed by checksum.
    """
    src = _resolve_source(db, source_key=source_key, source_id=source_id, tenant_id=tenant_id)
    text = (text or "").strip()
    if not text:
        raise ValueError("document text is empty")
    checksum = common.content_hash(title, text)
    store = vectorstore.get_vector_store()
    embedder = embeddings.get_embedder()

    # Version handling: supersede a prior current doc with the same external_id.
    prior = None
    version = 1
    lineage: Dict[str, Any] = {"ingested_at": common.iso(common.utcnow())}
    if external_id:
        prior = (db.query(AIPDocument)
                 .filter(AIPDocument.tenant_id == tenant_id,
                         AIPDocument.source_id == src.id,
                         AIPDocument.external_id == external_id,
                         AIPDocument.is_current.is_(True)).first())
    if prior is not None:
        if prior.checksum == checksum:
            return prior  # identical content — idempotent no-op
        prior.is_current = False
        version = prior.version + 1
        lineage["supersedes_document_id"] = prior.id
        lineage["previous_version"] = prior.version
        lineage["previous_checksum"] = prior.checksum
        # Remove old vectors so retrieval only sees the current version.
        _delete_doc_vectors(db, store, tenant_id, prior.id)

    doc = AIPDocument(
        tenant_id=tenant_id, source_id=src.id, external_id=external_id, title=title,
        uri=uri, doc_type=doc_type or src.source_type, language=language,
        checksum=checksum, version=version, is_current=True,
        supersedes_id=(prior.id if prior else None),
        lineage=lineage, meta=metadata or {}, status="indexed", created_by=created_by,
        created_at=common.utcnow(),
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    chunks = common.chunk_text(text, chunk_size=chunk_size, overlap=overlap)
    for ordinal, chunk_text in chunks:
        ch = AIPChunk(
            tenant_id=tenant_id, document_id=doc.id, source_id=src.id, ordinal=ordinal,
            text=chunk_text, token_count=common.token_count(chunk_text),
            meta={"title": title, "doc_type": doc.doc_type,
                  "source_type": src.source_type, "source_id": src.id,
                  "document_id": doc.id, "version": version},
            created_at=common.utcnow(),
        )
        db.add(ch)
        db.commit()
        db.refresh(ch)
        vec = embedder.embed(chunk_text)
        store.upsert(db, namespace=NAMESPACE, ref_type="chunk", ref_id=str(ch.id),
                     vector=vec, text=chunk_text, tenant_id=tenant_id,
                     model=embedder.model,
                     metadata={"chunk_id": ch.id, "document_id": doc.id,
                               "source_id": src.id, "source_type": src.source_type,
                               "doc_type": doc.doc_type, "title": title,
                               "ordinal": ordinal})

    doc.chunk_count = len(chunks)
    src.document_count = (db.query(AIPDocument)
                          .filter(AIPDocument.source_id == src.id,
                                  AIPDocument.is_current.is_(True)).count())
    db.commit()
    db.refresh(doc)
    return doc


def _delete_doc_vectors(db, store, tenant_id, document_id) -> None:
    chunk_ids = [c.id for c in db.query(AIPChunk.id)
                 .filter(AIPChunk.document_id == document_id).all()]
    for cid in chunk_ids:
        store.delete(db, namespace=NAMESPACE, ref_type="chunk", ref_id=str(cid),
                     tenant_id=tenant_id)


def list_documents(db: Session, *, source_id: Optional[int] = None,
                   tenant_id: Optional[int] = None, current_only: bool = True) -> List[AIPDocument]:
    q = db.query(AIPDocument).filter(AIPDocument.tenant_id == tenant_id)
    if source_id is not None:
        q = q.filter(AIPDocument.source_id == source_id)
    if current_only:
        q = q.filter(AIPDocument.is_current.is_(True))
    return q.order_by(AIPDocument.id.desc()).all()


# ---------------------------------------------------------------------------
# Hybrid retrieval (semantic + lexical) with reranking + metadata filtering
# ---------------------------------------------------------------------------
def search(db: Session, *, query: str, top_k: int = 5,
           tenant_id: Optional[int] = None,
           source_types: Optional[List[str]] = None,
           doc_type: Optional[str] = None,
           metadata_filter: Optional[Dict[str, Any]] = None,
           semantic_weight: float = 0.6,
           candidate_pool: int = 200) -> List[Dict[str, Any]]:
    """Hybrid retrieval: dense cosine + lexical BM25-lite, min-max fused & reranked.

    Metadata filters and ``source_types`` narrow the pool; ``tenant_id`` enforces
    isolation. Returns citation-ready hit dicts sorted by fused score.
    """
    embedder = embeddings.get_embedder()
    store = vectorstore.get_vector_store()
    qv = embedder.embed(query)
    flt: Dict[str, Any] = dict(metadata_filter or {})
    if source_types:
        flt["source_type"] = list(source_types)
    if doc_type:
        flt["doc_type"] = doc_type
    candidates = store.query(db, namespace=NAMESPACE, vector=qv,
                             top_k=candidate_pool, tenant_id=tenant_id,
                             metadata_filter=flt, ref_type="chunk")
    if not candidates:
        return []
    q_tokens = common.keywords(query)
    sem_scores = [max(0.0, h.score) for h in candidates]
    lex_scores = [common.bm25_lite(q_tokens, common.keywords(h.text)) for h in candidates]
    sem_n = common.minmax_scale(sem_scores)
    lex_n = common.minmax_scale(lex_scores)
    lw = 1.0 - semantic_weight
    ranked = []
    for h, s, sn, ln, lex in zip(candidates, sem_scores, sem_n, lex_n, lex_scores):
        fused = semantic_weight * sn + lw * ln
        meta = h.metadata or {}
        ranked.append({
            "chunk_id": meta.get("chunk_id"),
            "document_id": meta.get("document_id"),
            "source_id": meta.get("source_id"),
            "source_type": meta.get("source_type"),
            "doc_type": meta.get("doc_type"),
            "title": meta.get("title"),
            "ordinal": meta.get("ordinal"),
            "snippet": common.truncate(h.text, 500),
            "semantic_score": common.round_opt(s, 6),
            "lexical_score": common.round_opt(lex, 6),
            "score": common.round_opt(fused, 6),
        })
    ranked.sort(key=lambda r: r["score"], reverse=True)
    return ranked[: max(1, top_k)]


def _confidence(hits: List[Dict[str, Any]]) -> float:
    if not hits:
        return 0.0
    sem = [h.get("semantic_score") or 0.0 for h in hits]
    top = sem[0]
    mean_top3 = sum(sem[:3]) / min(3, len(sem))
    coverage = min(1.0, len(hits) / 3.0)
    return common.round_opt(common.clamp(0.55 * top + 0.30 * mean_top3 + 0.15 * coverage), 4)


def build_citations(hits: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    cites = []
    for i, h in enumerate(hits, 1):
        cites.append({
            "index": i,
            "label": f"{h.get('title') or 'source'} (§{h.get('ordinal', 0)})",
            "document_id": h.get("document_id"),
            "chunk_id": h.get("chunk_id"),
            "source_type": h.get("source_type"),
            "score": h.get("score"),
            "snippet": h.get("snippet"),
        })
    return cites


# ---------------------------------------------------------------------------
# Grounded answering with citation engine + confidence
# ---------------------------------------------------------------------------
def answer(db: Session, *, question: str, top_k: int = 5,
           tenant_id: Optional[int] = None,
           source_types: Optional[List[str]] = None,
           doc_type: Optional[str] = None,
           metadata_filter: Optional[Dict[str, Any]] = None,
           provider: Optional[str] = None,
           created_by: Optional[str] = None,
           persist: bool = True) -> Dict[str, Any]:
    hits = search(db, query=question, top_k=top_k, tenant_id=tenant_id,
                  source_types=source_types, doc_type=doc_type,
                  metadata_filter=metadata_filter)
    citations = build_citations(hits)
    confidence = _confidence(hits)
    grounding = {
        "headline": f"Answer to: {common.truncate(question, 160)}",
        "narrative": (hits[0]["snippet"] if hits else
                      "No indexed knowledge matched this question."),
        "facts": [{"label": c["label"], "value": c["snippet"]} for c in citations],
        "citations": citations,
    }
    client = llm_mod.get_llm(provider)
    result = client.generate(prompt=f"Answer the banking question: {question}",
                             grounding=grounding if hits else None)
    payload = {
        "question": question,
        "answer": result.text,
        "confidence": confidence,
        "retrieved": hits,
        "citations": citations,
        "provider": result.provider,
        "usage": result.as_dict(),
        "grounded": bool(hits),
    }
    if persist:
        row = AIPRagQuery(
            tenant_id=tenant_id, question=question, answer=result.text,
            confidence=confidence, retrieved=hits, citations=citations,
            filters={"source_types": source_types, "doc_type": doc_type,
                     "metadata_filter": metadata_filter},
            provider=result.provider, total_tokens=result.total_tokens,
            latency_ms=result.latency_ms, created_by=created_by,
            created_at=common.utcnow(),
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        payload["query_id"] = row.id
    return payload


def stats(db: Session, *, tenant_id: Optional[int] = None) -> Dict[str, Any]:
    store = vectorstore.get_vector_store()
    return {
        "sources": db.query(AIPKnowledgeSource)
        .filter(AIPKnowledgeSource.tenant_id == tenant_id).count(),
        "documents": db.query(AIPDocument)
        .filter(AIPDocument.tenant_id == tenant_id,
                AIPDocument.is_current.is_(True)).count(),
        "chunks": db.query(AIPChunk).filter(AIPChunk.tenant_id == tenant_id).count(),
        "vectors": store.count(db, namespace=NAMESPACE, tenant_id=tenant_id),
        "queries": db.query(AIPRagQuery)
        .filter(AIPRagQuery.tenant_id == tenant_id).count(),
        "embedder": embeddings.embedder_status(),
        "vector_store": vectorstore.vector_store_status(),
        "llm": llm_mod.llm_status(),
    }
