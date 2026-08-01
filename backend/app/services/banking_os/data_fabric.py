"""M14 — Enterprise Data Fabric.

A unified data catalog + governance layer over the platform's logical datasets
a searchable catalog (ownership, classification, declared schema), directed
**lineage** with upstream/downstream traversal and **impact analysis**, versioned
**data contracts**, and deterministic **data-quality** evaluation across the
completeness / validity / consistency dimensions. Complements the data
lake (physical storage) with the metadata/governance plane.

The contract-validation core (:func:`evaluate_records`) is pure and DB-free.
"""

from __future__ import annotations

import re
from collections import deque
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from backend.app.models.banking_os import (
    DataContract, DataLineageEdge, DataQualityRun, Dataset,
)
from .common import clamp

CLASSIFICATIONS = ["public", "internal", "confidential", "restricted"]
QUALITY_DIMENSIONS = ["completeness", "validity", "consistency"]

_TYPE_CHECKS = {
    "string": lambda v: isinstance(v, str),
    "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
    "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "boolean": lambda v: isinstance(v, bool),
    "array": lambda v: isinstance(v, list),
    "object": lambda v: isinstance(v, dict),
}


# ---------------------------------------------------------------------------
# Pure contract evaluation
# ---------------------------------------------------------------------------
def _check_value(value: Any, field: Dict[str, Any]) -> Optional[str]:
    """Return a violation string for ``value`` against a field spec, or ``None``."""
    if value is None:
        return None if field.get("nullable", True) else "null-not-allowed"
    ftype = field.get("type")
    if ftype and ftype in _TYPE_CHECKS and not _TYPE_CHECKS[ftype](value):
        return f"type!={ftype}"
    if "allowed" in field and value not in field["allowed"]:
        return "not-in-allowed"
    if "min" in field and isinstance(value, (int, float)) and value < field["min"]:
        return "below-min"
    if "max" in field and isinstance(value, (int, float)) and value > field["max"]:
        return "above-max"
    if "pattern" in field and isinstance(value, str):
        try:
            if not re.search(field["pattern"], value):
                return "pattern-mismatch"
        except re.error:
            return "bad-pattern"
    return None


def evaluate_records(spec: Dict[str, Any], records: List[dict]) -> Dict[str, Any]:
    """Deterministically score ``records`` against a contract ``spec``.

    Produces per-dimension scores (completeness / validity / consistency), an
    overall 0..1 score, and up to 50 sampled violations. Pure — no DB.
    """
    fields = spec.get("fields", []) or []
    required = spec.get("required", []) or [f["name"] for f in fields if not f.get("nullable", True)]
    n = len(records)
    if n == 0:
        return {"score": 0.0, "rows_checked": 0, "checks": [], "violations": [],
                "dimensions": {d: 0.0 for d in QUALITY_DIMENSIONS}}

    total_required = 0
    present_required = 0
    total_values = 0
    valid_values = 0
    violations: List[Dict[str, Any]] = []
    # consistency: a field should hold a single python type across rows
    field_types: Dict[str, set] = {f["name"]: set() for f in fields}

    for i, row in enumerate(records):
        for name in required:
            total_required += 1
            if row.get(name) is not None:
                present_required += 1
            elif len(violations) < 50:
                violations.append({"row": i, "field": name, "issue": "missing-required"})
        for f in fields:
            name = f["name"]
            val = row.get(name)
            if val is not None:
                field_types[name].add(type(val).__name__)
            if name in row:
                total_values += 1
                issue = _check_value(val, f)
                if issue is None:
                    valid_values += 1
                elif len(violations) < 50:
                    violations.append({"row": i, "field": name, "issue": issue})

    completeness = present_required / total_required if total_required else 1.0
    validity = valid_values / total_values if total_values else 1.0
    inconsistent = sum(1 for t in field_types.values() if len(t) > 1)
    consistency = 1.0 - (inconsistent / len(field_types)) if field_types else 1.0
    dims = {"completeness": round(completeness, 4), "validity": round(validity, 4),
            "consistency": round(consistency, 4)}
    score = round(sum(dims.values()) / len(dims), 4)
    checks = [{"name": d, "dimension": d, "score": dims[d], "passed": dims[d] >= 0.95}
              for d in QUALITY_DIMENSIONS]
    return {"score": score, "rows_checked": n, "dimensions": dims, "checks": checks,
            "violations": violations}


# ---------------------------------------------------------------------------
# Catalog
# ---------------------------------------------------------------------------
def register_dataset(db: Session, *, name: str, domain: Optional[str] = None,
                     description: Optional[str] = None, owner: Optional[str] = None,
                     source: Optional[str] = None, classification: str = "internal",
                     schema_fields: Optional[list] = None, tags: Optional[list] = None,
                     tenant_id: Optional[int] = None) -> Dataset:
    name = (name or "").strip()
    if not name:
        raise ValueError("dataset name required")
    if classification not in CLASSIFICATIONS:
        raise ValueError(f"unknown classification '{classification}'")
    row = (db.query(Dataset)
           .filter(Dataset.tenant_id == tenant_id, Dataset.name == name).first())
    if row is None:
        row = Dataset(tenant_id=tenant_id, name=name, domain=domain, description=description,
                      owner=owner, source=source, classification=classification,
                      schema_fields=schema_fields or [], tags=tags or [])
        db.add(row)
    else:
        for attr, val in (("domain", domain), ("description", description), ("owner", owner),
                          ("source", source), ("classification", classification)):
            if val is not None:
                setattr(row, attr, val)
        if schema_fields is not None:
            row.schema_fields = schema_fields
        if tags is not None:
            row.tags = tags
    db.commit()
    db.refresh(row)
    return row


def get_dataset(db: Session, name: str, *, tenant_id: Optional[int] = None) -> Optional[Dataset]:
    return db.query(Dataset).filter(Dataset.tenant_id == tenant_id, Dataset.name == name).first()


def list_datasets(db: Session, *, tenant_id: Optional[int] = None,
                  domain: Optional[str] = None) -> List[Dataset]:
    q = db.query(Dataset).filter(Dataset.tenant_id == tenant_id)
    if domain:
        q = q.filter(Dataset.domain == domain)
    return q.order_by(Dataset.name).all()


# ---------------------------------------------------------------------------
# Lineage + impact analysis
# ---------------------------------------------------------------------------
def add_lineage(db: Session, *, dataset: str, upstream: str, transform: Optional[str] = None,
                tenant_id: Optional[int] = None) -> DataLineageEdge:
    if dataset == upstream:
        raise ValueError("a dataset cannot be its own upstream")
    edge = (db.query(DataLineageEdge)
            .filter(DataLineageEdge.tenant_id == tenant_id, DataLineageEdge.dataset == dataset,
                    DataLineageEdge.upstream == upstream).first())
    if edge is None:
        edge = DataLineageEdge(tenant_id=tenant_id, dataset=dataset, upstream=upstream,
                               transform=transform)
        db.add(edge)
    elif transform is not None:
        edge.transform = transform
    db.commit()
    db.refresh(edge)
    return edge


def _edges(db: Session, tenant_id: Optional[int]) -> List[DataLineageEdge]:
    return db.query(DataLineageEdge).filter(DataLineageEdge.tenant_id == tenant_id).all()


def _traverse(edges: List[DataLineageEdge], start: str, *, downstream: bool) -> List[str]:
    """BFS over lineage edges. downstream=True follows upstream→dataset direction."""
    adj: Dict[str, List[str]] = {}
    for e in edges:
        if downstream:
            adj.setdefault(e.upstream, []).append(e.dataset)
        else:
            adj.setdefault(e.dataset, []).append(e.upstream)
    seen, out, q = {start}, [], deque([start])
    while q:
        cur = q.popleft()
        for nxt in adj.get(cur, []):
            if nxt not in seen:
                seen.add(nxt)
                out.append(nxt)
                q.append(nxt)
    return out


def lineage_graph(db: Session, dataset: str, *, tenant_id: Optional[int] = None) -> Dict[str, Any]:
    edges = _edges(db, tenant_id)
    direct_up = [e.upstream for e in edges if e.dataset == dataset]
    direct_down = [e.dataset for e in edges if e.upstream == dataset]
    return {
        "dataset": dataset,
        "direct_upstream": direct_up,
        "direct_downstream": direct_down,
        "all_upstream": _traverse(edges, dataset, downstream=False),
        "all_downstream": _traverse(edges, dataset, downstream=True),
    }


def impact_analysis(db: Session, dataset: str, *, tenant_id: Optional[int] = None) -> Dict[str, Any]:
    """What breaks if ``dataset`` changes: the full downstream reachable set."""
    edges = _edges(db, tenant_id)
    downstream = _traverse(edges, dataset, downstream=True)
    return {"dataset": dataset, "impacted_count": len(downstream),
            "impacted_datasets": downstream,
            "severity": "high" if len(downstream) >= 5 else "medium" if downstream else "low"}


# ---------------------------------------------------------------------------
# Contracts
# ---------------------------------------------------------------------------
def add_contract(db: Session, *, dataset: str, spec: dict, created_by: Optional[str] = None,
                 tenant_id: Optional[int] = None) -> DataContract:
    if not isinstance(spec, dict) or "fields" not in spec:
        raise ValueError("contract spec needs a 'fields' list")
    next_version = (db.query(DataContract)
                    .filter(DataContract.tenant_id == tenant_id,
                            DataContract.dataset == dataset).count()) + 1
    # Supersede prior active contracts.
    for prior in db.query(DataContract).filter(DataContract.tenant_id == tenant_id,
                                               DataContract.dataset == dataset,
                                               DataContract.status == "active").all():
        prior.status = "superseded"
    c = DataContract(tenant_id=tenant_id, dataset=dataset, version=next_version, spec=spec,
                     status="active", created_by=created_by)
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


def latest_contract(db: Session, dataset: str, *, tenant_id: Optional[int] = None) -> Optional[DataContract]:
    return (db.query(DataContract)
            .filter(DataContract.tenant_id == tenant_id, DataContract.dataset == dataset,
                    DataContract.status == "active")
            .order_by(DataContract.version.desc()).first())


# ---------------------------------------------------------------------------
# Quality
# ---------------------------------------------------------------------------
def run_quality(db: Session, *, dataset: str, records: List[dict],
                spec: Optional[dict] = None, tenant_id: Optional[int] = None) -> Dict[str, Any]:
    """Evaluate ``records`` against the dataset's active contract (or an ad-hoc ``spec``)."""
    if spec is None:
        contract = latest_contract(db, dataset, tenant_id=tenant_id)
        if contract is None:
            raise ValueError(f"no active contract for dataset '{dataset}'")
        spec = contract.spec
    result = evaluate_records(spec, records)
    run = DataQualityRun(tenant_id=tenant_id, dataset=dataset, checks=result["checks"],
                         score=result["score"], passed=result["score"] >= 0.95,
                         rows_checked=result["rows_checked"])
    db.add(run)
    ds = get_dataset(db, dataset, tenant_id=tenant_id)
    if ds is not None:
        ds.quality_score = result["score"]
        ds.row_count = result["rows_checked"]
    db.commit()
    db.refresh(run)
    return {"run_id": run.id, "dataset": dataset, "score": result["score"],
            "passed": run.passed, "dimensions": result["dimensions"],
            "violations": result["violations"], "rows_checked": result["rows_checked"]}


def quality_history(db: Session, dataset: str, *, tenant_id: Optional[int] = None,
                    limit: int = 50) -> List[DataQualityRun]:
    return (db.query(DataQualityRun)
            .filter(DataQualityRun.tenant_id == tenant_id, DataQualityRun.dataset == dataset)
            .order_by(DataQualityRun.created_at.desc()).limit(limit).all())


# ---------------------------------------------------------------------------
# Catalog stats + serialization
# ---------------------------------------------------------------------------
def catalog_stats(db: Session, *, tenant_id: Optional[int] = None) -> Dict[str, Any]:
    datasets = list_datasets(db, tenant_id=tenant_id)
    by_domain: Dict[str, int] = {}
    by_class: Dict[str, int] = {}
    scored = [d.quality_score for d in datasets if d.quality_score is not None]
    for d in datasets:
        by_domain[d.domain or "unknown"] = by_domain.get(d.domain or "unknown", 0) + 1
        by_class[d.classification] = by_class.get(d.classification, 0) + 1
    return {
        "datasets": len(datasets),
        "lineage_edges": db.query(DataLineageEdge).filter(DataLineageEdge.tenant_id == tenant_id).count(),
        "contracts": db.query(DataContract).filter(DataContract.tenant_id == tenant_id).count(),
        "by_domain": by_domain, "by_classification": by_class,
        "avg_quality": round(sum(scored) / len(scored), 4) if scored else None,
    }


def dataset_dict(d: Dataset) -> Dict[str, Any]:
    return {"id": d.id, "name": d.name, "domain": d.domain, "description": d.description,
            "owner": d.owner, "source": d.source, "classification": d.classification,
            "schema_fields": d.schema_fields, "tags": d.tags, "row_count": d.row_count,
            "quality_score": d.quality_score, "status": d.status}


def contract_dict(c: DataContract) -> Dict[str, Any]:
    return {"id": c.id, "dataset": c.dataset, "version": c.version, "spec": c.spec,
            "status": c.status, "created_by": c.created_by,
            "created_at": c.created_at.isoformat() if c.created_at else None}
