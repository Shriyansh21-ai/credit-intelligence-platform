"""M3 — Enterprise long-term memory.

Unifies three storage modalities behind one API

* **SQL memory** — the durable ``aip_memories`` table (typed, scoped, audited).
* **Vector memory**— every memory is embedded and indexed for semantic recall.
* **Graph memory** — memories can reference related memories (``related_ids``)
  giving a lightweight associative graph traversable from any node.

Memory types (``semantic``, ``episodic``, ``procedural``, ``organization``
``tenant``, ``user``, ``conversation``, ``project``, ``banking_case``
``committee``, ``customer``) and scopes are advisory strings, so new kinds need
no schema change.

Retrieval is scored by a blend of semantic similarity, curated importance
recency and reinforcement (access count). Summaries compress a scope; a decay-
based forgetting strategy prunes stale, low-value memories — all deterministic.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from backend.app.models.ai_platform import AIPMemory, AIPMemorySummary
from backend.app.services.ai_platform import common, embeddings, vectorstore

MEMORY_TYPES = [
    "semantic", "episodic", "procedural", "organization", "tenant", "user",
    "conversation", "project", "banking_case", "committee", "customer",
]


def _ns(scope: str) -> str:
    return f"mem:{scope}"


# ---------------------------------------------------------------------------
# Write
# ---------------------------------------------------------------------------
def write(db: Session, *, content: str, memory_type: str = "semantic",
          scope: str = "organization", scope_ref: Optional[str] = None,
          key: Optional[str] = None, importance: float = 0.5,
          decay: float = 0.02, source: Optional[str] = None,
          related_ids: Optional[List[int]] = None,
          meta: Optional[Dict[str, Any]] = None,
          tenant_id: Optional[int] = None) -> AIPMemory:
    """Persist a memory (SQL) and index it (vector). Idempotent on (scope, key)."""
    content = (content or "").strip()
    if not content:
        raise ValueError("memory content is empty")
    meta = dict(meta or {})
    if related_ids:
        meta["related_ids"] = list(related_ids)
    row = None
    if key:
        row = (db.query(AIPMemory)
               .filter(AIPMemory.tenant_id == tenant_id, AIPMemory.scope == scope,
                       AIPMemory.key == key, AIPMemory.superseded.is_(False)).first())
    if row is not None:
        row.content = content
        row.importance = importance
        row.memory_type = memory_type
        row.meta = meta
    else:
        row = AIPMemory(
            tenant_id=tenant_id, memory_type=memory_type, scope=scope,
            scope_ref=scope_ref, key=key, content=content,
            importance=common.clamp(importance), decay=decay, source=source,
            meta=meta, created_at=common.utcnow())
        db.add(row)
    db.commit()
    db.refresh(row)
    vec = embeddings.get_embedder().embed(content)
    vectorstore.get_vector_store().upsert(
        db, namespace=_ns(scope), ref_type="memory", ref_id=str(row.id),
        vector=vec, text=content, tenant_id=tenant_id,
        metadata={"memory_id": row.id, "memory_type": memory_type,
                  "scope": scope, "scope_ref": scope_ref, "importance": row.importance})
    return row


# ---------------------------------------------------------------------------
# Recall (semantic + importance + recency + reinforcement)
# ---------------------------------------------------------------------------
def _recency_score(created_at, half_life_days: float = 30.0) -> float:
    if not created_at:
        return 0.5
    age_days = max(0.0, (common.utcnow() - created_at).total_seconds() / 86400.0)
    return math.exp(-math.log(2) * age_days / half_life_days)


def recall(db: Session, *, query: str, scope: str = "organization",
           scope_ref: Optional[str] = None, memory_type: Optional[str] = None,
           top_k: int = 5, tenant_id: Optional[int] = None,
           reinforce: bool = True) -> List[Dict[str, Any]]:
    embedder = embeddings.get_embedder()
    store = vectorstore.get_vector_store()
    qv = embedder.embed(query)
    flt: Dict[str, Any] = {}
    if scope_ref is not None:
        flt["scope_ref"] = scope_ref
    if memory_type is not None:
        flt["memory_type"] = memory_type
    hits = store.query(db, namespace=_ns(scope), vector=qv, top_k=max(top_k * 4, 20),
                       tenant_id=tenant_id, metadata_filter=flt or None, ref_type="memory")
    out: List[Dict[str, Any]] = []
    for h in hits:
        mid = (h.metadata or {}).get("memory_id")
        row = db.query(AIPMemory).filter(AIPMemory.id == mid).first() if mid else None
        if row is None or row.superseded:
            continue
        sim = max(0.0, h.score)
        rec = _recency_score(row.created_at)
        reinforcement = min(1.0, math.log1p(row.access_count) / 3.0)
        score = (0.6 * sim + 0.2 * row.importance + 0.15 * rec + 0.05 * reinforcement)
        out.append({"memory_id": row.id, "content": row.content,
                    "memory_type": row.memory_type, "scope": row.scope,
                    "scope_ref": row.scope_ref, "importance": row.importance,
                    "similarity": common.round_opt(sim, 4),
                    "recency": common.round_opt(rec, 4),
                    "score": common.round_opt(score, 4),
                    "related_ids": (row.meta or {}).get("related_ids", [])})
    out.sort(key=lambda r: r["score"], reverse=True)
    out = out[: max(1, top_k)]
    if reinforce:
        for r in out:
            row = db.query(AIPMemory).filter(AIPMemory.id == r["memory_id"]).first()
            if row:
                row.access_count += 1
                row.last_accessed = common.utcnow()
        db.commit()
    return out


# ---------------------------------------------------------------------------
# Graph memory
# ---------------------------------------------------------------------------
def link(db: Session, *, memory_id: int, related_id: int) -> None:
    for a, b in ((memory_id, related_id), (related_id, memory_id)):
        row = db.query(AIPMemory).filter(AIPMemory.id == a).first()
        if row:
            meta = dict(row.meta or {})
            rel = set(meta.get("related_ids", []))
            rel.add(b)
            meta["related_ids"] = sorted(rel)
            row.meta = meta
    db.commit()


def neighbors(db: Session, *, memory_id: int, depth: int = 1) -> List[Dict[str, Any]]:
    """Traverse the associative memory graph up to ``depth`` hops."""
    seen = {memory_id}
    frontier = [memory_id]
    result: List[Dict[str, Any]] = []
    for _ in range(max(1, depth)):
        nxt = []
        for mid in frontier:
            row = db.query(AIPMemory).filter(AIPMemory.id == mid).first()
            if not row:
                continue
            for rid in (row.meta or {}).get("related_ids", []):
                if rid in seen:
                    continue
                seen.add(rid)
                nxt.append(rid)
                rr = db.query(AIPMemory).filter(AIPMemory.id == rid).first()
                if rr:
                    result.append({"memory_id": rr.id, "content": rr.content,
                                   "memory_type": rr.memory_type})
        frontier = nxt
    return result


# ---------------------------------------------------------------------------
# Summaries (compression)
# ---------------------------------------------------------------------------
def summarize(db: Session, *, scope: str, scope_ref: Optional[str] = None,
              tenant_id: Optional[int] = None, max_points: int = 8) -> AIPMemorySummary:
    q = db.query(AIPMemory).filter(AIPMemory.tenant_id == tenant_id,
                                   AIPMemory.scope == scope,
                                   AIPMemory.superseded.is_(False))
    if scope_ref is not None:
        q = q.filter(AIPMemory.scope_ref == scope_ref)
    rows = q.order_by(AIPMemory.importance.desc(), AIPMemory.id.desc()).all()
    top = rows[:max_points]
    lines = [f"- ({m.memory_type}) {common.truncate(m.content, 180)}" for m in top]
    summary = (f"Summary of {len(rows)} memories in scope '{scope}'"
               f"{('/' + scope_ref) if scope_ref else ''}:\n" + "\n".join(lines)) \
        if rows else "No memories to summarize."
    row = AIPMemorySummary(tenant_id=tenant_id, scope=scope, scope_ref=scope_ref,
                           summary=summary, covered_ids=[m.id for m in rows],
                           memory_count=len(rows), created_at=common.utcnow())
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


# ---------------------------------------------------------------------------
# Forgetting strategy (decay-based pruning)
# ---------------------------------------------------------------------------
def effective_importance(memory: AIPMemory) -> float:
    age_days = max(0.0, (common.utcnow() - memory.created_at).total_seconds() / 86400.0) \
        if memory.created_at else 0.0
    reinforcement = 1.0 + min(0.5, math.log1p(memory.access_count) / 5.0)
    return common.clamp(memory.importance * math.exp(-memory.decay * age_days) * reinforcement)


def apply_forgetting(db: Session, *, scope: Optional[str] = None,
                     tenant_id: Optional[int] = None, threshold: float = 0.15,
                     hard_delete: bool = False) -> Dict[str, Any]:
    q = db.query(AIPMemory).filter(AIPMemory.tenant_id == tenant_id,
                                   AIPMemory.superseded.is_(False))
    if scope is not None:
        q = q.filter(AIPMemory.scope == scope)
    forgotten = []
    store = vectorstore.get_vector_store()
    for m in q.all():
        if effective_importance(m) < threshold:
            forgotten.append(m.id)
            store.delete(db, namespace=_ns(m.scope), ref_type="memory",
                         ref_id=str(m.id), tenant_id=tenant_id)
            if hard_delete:
                db.delete(m)
            else:
                m.superseded = True
    db.commit()
    return {"forgotten": len(forgotten), "memory_ids": forgotten,
            "strategy": "hard_delete" if hard_delete else "supersede",
            "threshold": threshold}


def stats(db: Session, *, tenant_id: Optional[int] = None) -> Dict[str, Any]:
    rows = db.query(AIPMemory).filter(AIPMemory.tenant_id == tenant_id).all()
    by_type: Dict[str, int] = {}
    for m in rows:
        by_type[m.memory_type] = by_type.get(m.memory_type, 0) + 1
    return {"total": len(rows), "active": sum(1 for m in rows if not m.superseded),
            "by_type": by_type,
            "summaries": db.query(AIPMemorySummary)
            .filter(AIPMemorySummary.tenant_id == tenant_id).count()}


def list_memories(db: Session, *, scope: Optional[str] = None,
                  scope_ref: Optional[str] = None, tenant_id: Optional[int] = None,
                  limit: int = 100) -> List[AIPMemory]:
    q = db.query(AIPMemory).filter(AIPMemory.tenant_id == tenant_id,
                                   AIPMemory.superseded.is_(False))
    if scope is not None:
        q = q.filter(AIPMemory.scope == scope)
    if scope_ref is not None:
        q = q.filter(AIPMemory.scope_ref == scope_ref)
    return q.order_by(AIPMemory.id.desc()).limit(limit).all()
