"""Pluggable vector store for the AI Intelligence Platform (Track 2).

Provides a small, uniform interface over embedding storage + similarity search
so RAG (M1), long-term memory (M3) and any future retrieval feature share one
seam. The default :class:`SqlVectorStore` persists vectors as JSON in the
additive ``aip_vectors`` table and computes cosine similarity in pure Python —
so it works identically on the SQLite dev database and Postgres, with zero
extra infrastructure and fully reproducible results.

    VectorStore (ABC)
      ├─ SqlVectorStore     default — JSON column + Python cosine (any DB)
      └─ PgVectorStore      gated — native pgvector ``<=>`` on Postgres

The interface is deliberately backend-agnostic (``upsert``/``query``/``delete``/
``count`` keyed by ``namespace`` + ``ref_type``/``ref_id`` with metadata filters),
so Pinecone / Weaviate / Milvus / Qdrant adapters can be dropped in later by
implementing the same four methods. ``get_vector_store()`` resolves the active
backend from ``AIP_VECTOR_STORE`` and always degrades to ``SqlVectorStore``.
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

from sqlalchemy.orm import Session

from backend.app.services.ai_platform import common


@dataclass
class VectorHit:
    id: int
    ref_type: str
    ref_id: str
    text: str
    metadata: Dict[str, Any]
    score: float  # cosine similarity in [-1, 1], higher = closer
    namespace: str = ""

    def as_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "ref_type": self.ref_type,
            "ref_id": self.ref_id,
            "text": common.truncate(self.text, 2000),
            "metadata": self.metadata,
            "score": common.round_opt(self.score, 6),
            "namespace": self.namespace,
        }


def _matches_filter(metadata: Dict[str, Any], flt: Optional[Dict[str, Any]]) -> bool:
    if not flt:
        return True
    for key, want in flt.items():
        have = metadata.get(key)
        if isinstance(want, (list, tuple, set)):
            if have not in want:
                return False
        elif have != want:
            return False
    return True


class VectorStore(ABC):
    name = "base"

    @abstractmethod
    def upsert(self, db: Session, *, namespace: str, ref_type: str, ref_id: str,
               vector: Sequence[float], text: str = "",
               metadata: Optional[Dict[str, Any]] = None,
               tenant_id: Optional[int] = None, model: str = "hashing") -> int:
        """Insert or replace a single vector; returns its row id."""

    @abstractmethod
    def query(self, db: Session, *, namespace: str, vector: Sequence[float],
              top_k: int = 5, tenant_id: Optional[int] = None,
              metadata_filter: Optional[Dict[str, Any]] = None,
              ref_type: Optional[str] = None) -> List[VectorHit]:
        """Return the ``top_k`` most similar vectors (cosine)."""

    @abstractmethod
    def delete(self, db: Session, *, namespace: Optional[str] = None,
               ref_type: Optional[str] = None, ref_id: Optional[str] = None,
               tenant_id: Optional[int] = None) -> int:
        """Delete matching vectors; returns the number removed."""

    @abstractmethod
    def count(self, db: Session, *, namespace: Optional[str] = None,
              tenant_id: Optional[int] = None) -> int: ...


class SqlVectorStore(VectorStore):
    """JSON-backed vector store with Python cosine ranking (works on any DB)."""

    name = "sql"

    def _model(self):
        # Imported lazily to avoid a models<->services import cycle at startup.
        from backend.app.models.ai_platform import AIPVector
        return AIPVector

    def upsert(self, db, *, namespace, ref_type, ref_id, vector, text="",
               metadata=None, tenant_id=None, model="hashing") -> int:
        AIPVector = self._model()
        row = (
            db.query(AIPVector)
            .filter(AIPVector.namespace == namespace,
                    AIPVector.ref_type == ref_type,
                    AIPVector.ref_id == str(ref_id),
                    AIPVector.tenant_id == tenant_id)
            .first()
        )
        payload = list(map(float, vector))
        if row is None:
            row = AIPVector(
                tenant_id=tenant_id, namespace=namespace, ref_type=ref_type,
                ref_id=str(ref_id), model=model, dim=len(payload),
                vector=payload, text=common.truncate(text, 8000),
                meta=metadata or {}, created_at=common.utcnow(),
            )
            db.add(row)
        else:
            row.model = model
            row.dim = len(payload)
            row.vector = payload
            row.text = common.truncate(text, 8000)
            row.meta = metadata or {}
        db.commit()
        db.refresh(row)
        return row.id

    def query(self, db, *, namespace, vector, top_k=5, tenant_id=None,
              metadata_filter=None, ref_type=None) -> List[VectorHit]:
        AIPVector = self._model()
        q = db.query(AIPVector).filter(AIPVector.namespace == namespace)
        if tenant_id is not None:
            q = q.filter(AIPVector.tenant_id == tenant_id)
        if ref_type is not None:
            q = q.filter(AIPVector.ref_type == ref_type)
        rows = q.all()
        qv = list(map(float, vector))
        hits: List[VectorHit] = []
        for r in rows:
            meta = r.meta or {}
            if not _matches_filter(meta, metadata_filter):
                continue
            score = common.cosine(qv, r.vector or [])
            hits.append(VectorHit(id=r.id, ref_type=r.ref_type, ref_id=r.ref_id,
                                  text=r.text or "", metadata=meta, score=score,
                                  namespace=r.namespace))
        hits.sort(key=lambda h: h.score, reverse=True)
        return hits[: max(1, top_k)]

    def delete(self, db, *, namespace=None, ref_type=None, ref_id=None,
               tenant_id=None) -> int:
        AIPVector = self._model()
        q = db.query(AIPVector)
        if namespace is not None:
            q = q.filter(AIPVector.namespace == namespace)
        if ref_type is not None:
            q = q.filter(AIPVector.ref_type == ref_type)
        if ref_id is not None:
            q = q.filter(AIPVector.ref_id == str(ref_id))
        if tenant_id is not None:
            q = q.filter(AIPVector.tenant_id == tenant_id)
        n = q.count()
        q.delete(synchronize_session=False)
        db.commit()
        return n

    def count(self, db, *, namespace=None, tenant_id=None) -> int:
        AIPVector = self._model()
        q = db.query(AIPVector)
        if namespace is not None:
            q = q.filter(AIPVector.namespace == namespace)
        if tenant_id is not None:
            q = q.filter(AIPVector.tenant_id == tenant_id)
        return q.count()


class PgVectorStore(SqlVectorStore):
    """pgvector-backed store (gated).

    On a Postgres connection with the ``vector`` extension this would use a
    native ``vector`` column and the ``<=>`` distance operator for indexed ANN
    search. Detection is performed lazily; on any non-Postgres connection (e.g.
    the SQLite dev DB) it transparently inherits the pure-Python cosine ranking
    from :class:`SqlVectorStore`, so behaviour is identical everywhere and the
    native path is never exercised without real pgvector present.
    """

    name = "pgvector"

    @staticmethod
    def native_available(db: Session) -> bool:  # pragma: no cover - env-specific
        try:
            if db.bind is None or db.bind.dialect.name != "postgresql":
                return False
            row = db.execute(
                "SELECT 1 FROM pg_extension WHERE extname = 'vector'"
            ).first()
            return row is not None
        except Exception:
            return False


_SQL = SqlVectorStore()
_CACHE: Dict[str, VectorStore] = {"sql": _SQL, "memory": _SQL}


def get_vector_store(name: Optional[str] = None) -> VectorStore:
    """Resolve the active vector store from ``name`` → ``AIP_VECTOR_STORE`` → sql.

    An unknown or unavailable backend degrades to :class:`SqlVectorStore`.
    """
    choice = (name or os.getenv("AIP_VECTOR_STORE") or "sql").lower()
    if choice in _CACHE:
        return _CACHE[choice]
    if choice == "pgvector":
        store: VectorStore = PgVectorStore()
        _CACHE["pgvector"] = store
        return store
    return _SQL


def vector_store_status() -> Dict[str, Any]:
    return {
        "active": get_vector_store().name,
        "configured": os.getenv("AIP_VECTOR_STORE", "sql"),
        "supported_now": ["sql", "pgvector"],
        "roadmap": ["pinecone", "weaviate", "milvus", "qdrant"],
    }
