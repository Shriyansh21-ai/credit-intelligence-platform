"""M2 — Enterprise Search Engine.

Universal search across every platform object (companies, applications,
documents, reports, alerts, tasks, policies, models, transactions, …). One
denormalized :class:`SearchDocument` per object carries a cached, tokenized term
list so ranking runs in-memory over the tenant's index.

Ranking blends three signals (all deterministic, no external service required):

* **keyword**  — BM25-style TF·IDF over the tokenized index.
* **semantic** — a lexical-similarity approximation (token Jaccard + prefix/
  substring overlap) that stands in for a vector model; the interface is
  embedding-ready (swap :func:`_semantic_score` for a real ANN backend).
* **hybrid**   — a weighted blend of the two (the default).

Plus field/numeric filters, autocomplete, facets, saved searches and history.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from backend.app.models.banking_os import SavedSearch, SearchDocument, SearchHistory
from .common import bm25_idf, dedupe_preserve_order, term_frequencies, tokenize

# Canonical searchable object types (drives facets + the frontend filter chips).
DOC_TYPES = [
    "company", "application", "document", "report", "alert", "task", "policy",
    "model", "transaction", "prediction", "approval", "notification", "connector",
    "committee", "prompt",
]


# ---------------------------------------------------------------------------
# Indexing
# ---------------------------------------------------------------------------
def index_document(db: Session, *, doc_type: str, ref: str, title: str,
                   body: Optional[str] = None, keywords: Optional[list] = None,
                   metadata: Optional[dict] = None, url: Optional[str] = None,
                   numeric_fields: Optional[dict] = None,
                   tenant_id: Optional[int] = None) -> SearchDocument:
    keywords = keywords or []
    terms = dedupe_preserve_order(
        tokenize(title) + tokenize(body) + [k.lower() for k in keywords])
    row = (db.query(SearchDocument)
           .filter(SearchDocument.tenant_id == tenant_id,
                   SearchDocument.doc_type == doc_type, SearchDocument.ref == ref).first())
    if row is None:
        row = SearchDocument(tenant_id=tenant_id, doc_type=doc_type, ref=ref, title=title,
                             body=body, keywords=keywords, doc_metadata=metadata or {}, url=url,
                             terms=terms, numeric_fields=numeric_fields or {})
        db.add(row)
    else:
        row.title, row.body, row.keywords = title, body, keywords
        row.doc_metadata = metadata or {}
        row.url = url
        row.terms = terms
        row.numeric_fields = numeric_fields or {}
    db.commit()
    db.refresh(row)
    return row


def reindex_platform(db: Session, *, tenant_id: Optional[int] = None) -> Dict[str, int]:
    """(Re)index the core platform objects into the universal search index.

    Best-effort per source: a missing table/model never aborts the whole reindex,
    so this stays robust across partially-migrated environments.
    """
    counts: Dict[str, int] = defaultdict(int)

    # Companies / assessments
    try:
        from backend.app.models.enterprise_assessment import EnterpriseAssessment
        for a in db.query(EnterpriseAssessment).limit(2000).all():
            index_document(
                db, doc_type="company", ref=a.company_name, title=a.company_name,
                body=f"{a.industry or ''} {a.risk_rating or ''} {a.loan_recommendation or ''}",
                keywords=[a.industry, a.risk_rating], metadata={"industry": a.industry,
                    "rating": a.risk_rating, "assessment_id": a.id},
                numeric_fields={"score": a.enterprise_credit_score or 0,
                                "pd": a.probability_of_default or 0,
                                "amount": a.recommended_loan_amount or 0},
                tenant_id=tenant_id)
            counts["company"] += 1
    except Exception:
        pass

    # Intelligence alerts (Phase 9)
    try:
        from backend.app.models.autonomous import IntelligenceAlert
        for al in db.query(IntelligenceAlert).filter(IntelligenceAlert.tenant_id == tenant_id).limit(2000).all():
            index_document(db, doc_type="alert", ref=str(al.id), title=al.title,
                           body=al.recommended_action or al.business_impact,
                           keywords=[al.category, al.severity],
                           metadata={"severity": al.severity, "status": al.status,
                                     "company_ref": al.company_ref},
                           numeric_fields={"priority": al.priority_score or 0}, tenant_id=tenant_id)
            counts["alert"] += 1
    except Exception:
        pass

    # Policies (Phase 10)
    try:
        from backend.app.models.banking_os import Policy
        for p in db.query(Policy).filter(Policy.tenant_id == tenant_id).limit(2000).all():
            index_document(db, doc_type="policy", ref=p.key, title=p.name,
                           body=p.description, keywords=[p.domain, p.status],
                           metadata={"domain": p.domain, "status": p.status}, tenant_id=tenant_id)
            counts["policy"] += 1
    except Exception:
        pass

    return dict(counts)


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------
def _keyword_scores(query_terms: List[str], docs: List[SearchDocument]) -> Dict[int, float]:
    n = len(docs)
    doc_freq: Dict[str, int] = defaultdict(int)
    for d in docs:
        for t in set(d.terms or []):
            doc_freq[t] += 1
    idf = {t: bm25_idf(n, doc_freq.get(t, 0)) for t in set(query_terms)}
    scores: Dict[int, float] = {}
    for d in docs:
        tf = term_frequencies(d.terms or [])
        dl = max(1, len(d.terms or []))
        s = 0.0
        for t in query_terms:
            if t in tf:
                # BM25 term saturation (k1=1.5)
                freq = tf[t]
                s += idf.get(t, 0.0) * (freq * 2.5) / (freq + 1.5)
        # Title exact-match boost
        if any(t in tokenize(d.title) for t in query_terms):
            s *= 1.5
        if s > 0:
            scores[d.id] = round(s / (1 + 0.001 * dl), 4)
    return scores


def _semantic_score(query_terms: List[str], doc: SearchDocument) -> float:
    """Deterministic lexical-similarity stand-in for a vector model.

    Token Jaccard plus prefix/substring overlap — no external embeddings needed;
    replaceable by a real ANN backend without touching callers.
    """
    dt = set(doc.terms or [])
    qt = set(query_terms)
    if not qt or not dt:
        return 0.0
    jaccard = len(qt & dt) / len(qt | dt)
    partial = 0.0
    for q in qt:
        for t in dt:
            if q != t and (t.startswith(q) or q.startswith(t) or q in t):
                partial += 0.25
                break
    return round(min(1.0, jaccard + partial / max(1, len(qt))), 4)


def _passes_filters(doc: SearchDocument, filters: Dict[str, Any]) -> bool:
    for key, cond in (filters or {}).items():
        nf = (doc.numeric_fields or {})
        md = (doc.doc_metadata or {})
        if key in nf:
            val = nf[key]
            if isinstance(cond, dict):
                if "gte" in cond and not (val is not None and val >= cond["gte"]):
                    return False
                if "lte" in cond and not (val is not None and val <= cond["lte"]):
                    return False
            elif val != cond:
                return False
        elif key in md:
            if md[key] != cond:
                return False
        else:
            return False
    return True


def search(db: Session, *, query: str = "", doc_types: Optional[List[str]] = None,
           filters: Optional[dict] = None, mode: str = "hybrid", limit: int = 20,
           tenant_id: Optional[int] = None, user_id: Optional[int] = None,
           persist: bool = True) -> Dict[str, Any]:
    q = db.query(SearchDocument).filter(SearchDocument.tenant_id == tenant_id)
    if doc_types:
        q = q.filter(SearchDocument.doc_type.in_(doc_types))
    docs = q.all()
    docs = [d for d in docs if _passes_filters(d, filters or {})]

    query_terms = tokenize(query)
    results: List[Dict[str, Any]] = []
    if not query_terms:
        # Empty query → recency-ordered browse of the filtered set.
        for d in sorted(docs, key=lambda x: x.updated_at or x.created_at, reverse=True)[:limit]:
            results.append(_hit(d, 0.0, {"keyword": 0.0, "semantic": 0.0}))
    else:
        kw = _keyword_scores(query_terms, docs) if mode in ("keyword", "hybrid") else {}
        max_kw = max(kw.values()) if kw else 1.0
        scored = []
        for d in docs:
            k = kw.get(d.id, 0.0)
            k_norm = (k / max_kw) if max_kw else 0.0
            sem = _semantic_score(query_terms, d) if mode in ("semantic", "hybrid") else 0.0
            if mode == "keyword":
                final = k_norm
            elif mode == "semantic":
                final = sem
            else:
                final = round(0.6 * k_norm + 0.4 * sem, 4)
            if final > 0:
                scored.append((final, {"keyword": round(k_norm, 4), "semantic": sem}, d))
        scored.sort(key=lambda x: -x[0])
        for final, parts, d in scored[:limit]:
            results.append(_hit(d, round(final, 4), parts))

    if persist and query:
        db.add(SearchHistory(tenant_id=tenant_id, user_id=user_id, query=query,
                             filters=filters or {}, result_count=len(results)))
        db.commit()
    return {"query": query, "mode": mode, "count": len(results), "results": results}


def _hit(d: SearchDocument, score: float, parts: Dict[str, float]) -> Dict[str, Any]:
    return {"doc_type": d.doc_type, "ref": d.ref, "title": d.title,
            "snippet": (d.body or "")[:200], "url": d.url, "metadata": d.doc_metadata,
            "score": score, "signals": parts}


# ---------------------------------------------------------------------------
# Autocomplete + facets
# ---------------------------------------------------------------------------
def autocomplete(db: Session, prefix: str, *, limit: int = 10,
                 tenant_id: Optional[int] = None) -> List[Dict[str, Any]]:
    p = (prefix or "").strip().lower()
    if not p:
        return []
    docs = db.query(SearchDocument).filter(SearchDocument.tenant_id == tenant_id).all()
    out = []
    for d in docs:
        title_l = d.title.lower()
        if title_l.startswith(p) or any(t.startswith(p) for t in tokenize(d.title)):
            out.append({"title": d.title, "doc_type": d.doc_type, "ref": d.ref,
                        "exact": title_l.startswith(p)})
    out.sort(key=lambda x: (not x["exact"], x["title"]))
    return out[:limit]


def facets(db: Session, *, tenant_id: Optional[int] = None) -> Dict[str, Any]:
    docs = db.query(SearchDocument).filter(SearchDocument.tenant_id == tenant_id).all()
    by_type: Dict[str, int] = defaultdict(int)
    for d in docs:
        by_type[d.doc_type] += 1
    return {"total": len(docs), "by_doc_type": dict(by_type), "doc_types": DOC_TYPES}


# ---------------------------------------------------------------------------
# Saved searches + history
# ---------------------------------------------------------------------------
def save_search(db: Session, *, name: str, query: str, filters: Optional[dict] = None,
                user_id: Optional[int] = None, tenant_id: Optional[int] = None) -> SavedSearch:
    s = SavedSearch(tenant_id=tenant_id, user_id=user_id, name=name, query=query,
                    filters=filters or {})
    db.add(s)
    db.commit()
    db.refresh(s)
    return s


def list_saved(db: Session, *, user_id: Optional[int] = None,
               tenant_id: Optional[int] = None) -> List[Dict[str, Any]]:
    q = db.query(SavedSearch).filter(SavedSearch.tenant_id == tenant_id)
    if user_id is not None:
        q = q.filter(SavedSearch.user_id == user_id)
    return [{"id": s.id, "name": s.name, "query": s.query, "filters": s.filters}
            for s in q.order_by(SavedSearch.created_at.desc()).all()]


def history(db: Session, *, user_id: Optional[int] = None, tenant_id: Optional[int] = None,
            limit: int = 50) -> List[Dict[str, Any]]:
    q = db.query(SearchHistory).filter(SearchHistory.tenant_id == tenant_id)
    if user_id is not None:
        q = q.filter(SearchHistory.user_id == user_id)
    return [{"id": h.id, "query": h.query, "filters": h.filters, "result_count": h.result_count,
             "created_at": h.created_at.isoformat() if h.created_at else None}
            for h in q.order_by(SearchHistory.created_at.desc()).limit(limit).all()]
