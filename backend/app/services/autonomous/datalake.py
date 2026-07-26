"""M14 — Enterprise Data Lake.

A unified, append-only analytical store (``datalake_objects`` + a
``datalake_datasets`` catalog) that mirrors historical assessments, connector
snapshots, ML features/predictions, drift metrics, portfolio history, simulation
outputs and monitoring history into content-hashed, partitioned records. Reads
are served from here so heavy analytics never touch the transactional path.

Ingestion is idempotent (dedup on ``namespace + partition + content_hash``) so a
job can be re-run safely. Built-in adapters copy from the live tables; callers can
also push arbitrary records via :func:`ingest`.
"""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from sqlalchemy.orm import Session

from backend.app.models.autonomous import DataLakeDataset, DataLakeObject

NAMESPACES = [
    "assessments", "documents", "connector_snapshots", "ml_features", "predictions",
    "drift_metrics", "portfolio_history", "simulation_outputs", "monitoring_history",
]


def _hash(content: Dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(content, sort_keys=True, default=str).encode()).hexdigest()[:32]


def _touch_dataset(db: Session, namespace: str, tenant_id: Optional[int], fields: List[str]):
    ds = (db.query(DataLakeDataset)
          .filter(DataLakeDataset.tenant_id == tenant_id, DataLakeDataset.namespace == namespace)
          .first())
    if ds is None:
        ds = DataLakeDataset(tenant_id=tenant_id, namespace=namespace, schema_fields=fields,
                             record_count=0, description=f"Data lake dataset: {namespace}")
        db.add(ds)
    else:
        merged = sorted(set(ds.schema_fields or []) | set(fields))
        ds.schema_fields = merged
    ds.last_ingested_at = datetime.utcnow()
    return ds


def ingest(db: Session, namespace: str, content: Dict[str, Any], *, partition: Optional[str] = None,
           entity_ref: Optional[str] = None, tenant_id: Optional[int] = None) -> Dict[str, Any]:
    """Idempotently append one record; returns ``{ingested: bool, id}``."""
    chash = _hash(content)
    existing = (db.query(DataLakeObject)
                .filter(DataLakeObject.namespace == namespace, DataLakeObject.partition == partition,
                        DataLakeObject.content_hash == chash).first())
    if existing is not None:
        return {"ingested": False, "id": existing.id, "duplicate": True}
    obj = DataLakeObject(tenant_id=tenant_id, namespace=namespace, partition=partition,
                         entity_ref=entity_ref, content_hash=chash, content=content)
    db.add(obj)
    ds = _touch_dataset(db, namespace, tenant_id, list(content.keys()))
    ds.record_count = (ds.record_count or 0) + 1
    db.commit()
    db.refresh(obj)
    return {"ingested": True, "id": obj.id, "duplicate": False}


def ingest_batch(db: Session, namespace: str, records: List[Dict[str, Any]], *,
                 partition_key: Optional[str] = None, entity_key: Optional[str] = None,
                 tenant_id: Optional[int] = None) -> Dict[str, Any]:
    ingested = duplicates = 0
    for rec in records:
        part = str(rec.get(partition_key)) if partition_key and rec.get(partition_key) is not None else None
        ent = str(rec.get(entity_key)) if entity_key and rec.get(entity_key) is not None else None
        res = ingest(db, namespace, rec, partition=part, entity_ref=ent, tenant_id=tenant_id)
        if res["ingested"]:
            ingested += 1
        else:
            duplicates += 1
    return {"namespace": namespace, "ingested": ingested, "duplicates": duplicates,
            "total": len(records)}


# ---------------------------------------------------------------------------
# Built-in ingestion adapters (copy from live tables)
# ---------------------------------------------------------------------------
def ingest_assessments(db: Session, *, tenant_id: Optional[int] = None) -> Dict[str, Any]:
    from . import data_access
    profs = [p for p in (data_access.profile(a) for a in data_access.all_assessments(db)) if p]
    for p in profs:
        p["_month"] = (p.get("created_at") or "")[:7]
    return ingest_batch(db, "assessments", profs, partition_key="_month",
                        entity_key="company_ref", tenant_id=tenant_id)


def ingest_simulations(db: Session, *, tenant_id: Optional[int] = None) -> Dict[str, Any]:
    from backend.app.models.autonomous import SimulationRun
    rows = db.query(SimulationRun).all()
    recs = [{"id": r.id, "company_ref": r.company_ref, "scenario_types": r.scenario_types,
             "delta": r.delta, "result": r.result} for r in rows]
    return ingest_batch(db, "simulation_outputs", recs, entity_key="company_ref", tenant_id=tenant_id)


def ingest_monitoring(db: Session, *, tenant_id: Optional[int] = None) -> Dict[str, Any]:
    from backend.app.models.autonomous import MonitoringSignal
    rows = db.query(MonitoringSignal).all()
    recs = [{"id": r.id, "company_ref": r.company_ref, "source": r.source,
             "signal_type": r.signal_type, "severity": r.severity,
             "detected_at": r.detected_at.isoformat() if r.detected_at else None} for r in rows]
    return ingest_batch(db, "monitoring_history", recs, entity_key="company_ref", tenant_id=tenant_id)


_ADAPTERS: Dict[str, Callable] = {
    "assessments": ingest_assessments, "simulation_outputs": ingest_simulations,
    "monitoring_history": ingest_monitoring,
}


def run_ingestion(db: Session, namespace: str, *, tenant_id: Optional[int] = None) -> Dict[str, Any]:
    adapter = _ADAPTERS.get(namespace)
    if adapter is None:
        raise ValueError(f"no built-in ingestion adapter for '{namespace}'")
    return adapter(db, tenant_id=tenant_id)


def run_all_ingestion(db: Session, *, tenant_id: Optional[int] = None) -> Dict[str, Any]:
    return {ns: _ADAPTERS[ns](db, tenant_id=tenant_id) for ns in _ADAPTERS}


# ---------------------------------------------------------------------------
# Query + analytics
# ---------------------------------------------------------------------------
def query(db: Session, namespace: str, *, partition: Optional[str] = None,
          entity_ref: Optional[str] = None, tenant_id: Optional[int] = None,
          limit: int = 200) -> List[Dict[str, Any]]:
    q = db.query(DataLakeObject).filter(DataLakeObject.namespace == namespace)
    if tenant_id is not None:
        q = q.filter(DataLakeObject.tenant_id == tenant_id)
    if partition is not None:
        q = q.filter(DataLakeObject.partition == partition)
    if entity_ref is not None:
        q = q.filter(DataLakeObject.entity_ref == entity_ref)
    return [{"id": o.id, "partition": o.partition, "entity_ref": o.entity_ref,
             "ingested_at": o.ingested_at.isoformat() if o.ingested_at else None, **o.content}
            for o in q.order_by(DataLakeObject.ingested_at.desc()).limit(limit).all()]


def aggregate(db: Session, namespace: str, *, group_by: str, metric: Optional[str] = None,
              agg: str = "count", tenant_id: Optional[int] = None) -> Dict[str, Any]:
    """Group-by analytics over a namespace (count/sum/avg of a numeric field)."""
    rows = query(db, namespace, tenant_id=tenant_id, limit=100000)
    buckets: Dict[str, List[float]] = defaultdict(list)
    for r in rows:
        key = str(r.get(group_by, "unknown"))
        if metric is not None and isinstance(r.get(metric), (int, float)):
            buckets[key].append(r[metric])
        else:
            buckets[key].append(1.0)
    out = {}
    for k, vals in buckets.items():
        if agg == "sum":
            out[k] = round(sum(vals), 4)
        elif agg == "avg":
            out[k] = round(sum(vals) / len(vals), 4) if vals else 0.0
        else:
            out[k] = len(vals)
    return {"namespace": namespace, "group_by": group_by, "metric": metric, "agg": agg,
            "buckets": dict(sorted(out.items(), key=lambda kv: -kv[1]))}


def catalog(db: Session, *, tenant_id: Optional[int] = None) -> List[Dict[str, Any]]:
    q = db.query(DataLakeDataset)
    if tenant_id is not None:
        q = q.filter(DataLakeDataset.tenant_id == tenant_id)
    return [{"namespace": d.namespace, "description": d.description,
             "record_count": d.record_count, "schema_fields": d.schema_fields,
             "last_ingested_at": d.last_ingested_at.isoformat() if d.last_ingested_at else None}
            for d in q.order_by(DataLakeDataset.namespace.asc()).all()]


def stats(db: Session, *, tenant_id: Optional[int] = None) -> Dict[str, Any]:
    cat = catalog(db, tenant_id=tenant_id)
    return {"datasets": len(cat), "total_records": sum(c["record_count"] for c in cat),
            "namespaces": [c["namespace"] for c in cat]}
