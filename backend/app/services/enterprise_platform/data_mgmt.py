"""M6 — Enterprise Data Management (MDM).

Master Data Management: golden records, reference data, data-quality rules,
duplicate detection, entity resolution, data stewardship and bulk import/export.
Deterministic string-similarity (token Jaccard + normalized edit ratio) drives
duplicate detection and entity resolution so results are reproducible. Backed by
``ent_mdm_records``, ``ent_data_rules`` and ``ent_data_jobs``.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from backend.app.models.enterprise_platform import EntDataJob, EntDataRule, EntMdmRecord
from .common import clamp, iso, mean, safe_div, slugify, utcnow

ENTITY_TYPES = ["customer", "counterparty", "vendor", "instrument"]
DQ_DIMENSIONS = ["completeness", "validity", "uniqueness", "consistency", "accuracy"]


def _norm(s: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(s or "").lower()).strip()


def _similarity(a: str, b: str) -> float:
    """Token-Jaccard blended with a length-ratio — deterministic and cheap."""
    a, b = _norm(a), _norm(b)
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    ta, tb = set(a.split()), set(b.split())
    jaccard = safe_div(len(ta & tb), len(ta | tb), 0.0) or 0.0
    len_ratio = safe_div(min(len(a), len(b)), max(len(a), len(b)), 0.0) or 0.0
    return round(clamp(0.7 * jaccard + 0.3 * len_ratio), 4)


# ---------------------------------------------------------------------------
# Golden records / MDM
# ---------------------------------------------------------------------------

def upsert_golden(db: Session, *, entity_type: str, natural_key: str, record: Dict[str, Any],
                  source: str = "manual", steward: Optional[str] = None,
                  tenant_id: Optional[int] = None) -> Dict[str, Any]:
    if entity_type not in ENTITY_TYPES:
        raise ValueError(f"unknown entity_type '{entity_type}'")
    existing = (db.query(EntMdmRecord)
                .filter(EntMdmRecord.tenant_id == tenant_id, EntMdmRecord.entity_type == entity_type,
                        EntMdmRecord.natural_key == natural_key).first())
    if existing:
        # Survivorship: fill blanks, keep existing non-null values, append source.
        golden = dict(existing.golden_record or {})
        for k, v in record.items():
            if golden.get(k) in (None, "", []):
                golden[k] = v
        existing.golden_record = golden
        srcs = list(existing.source_records or [])
        srcs.append({"source": source, "record": record})
        existing.source_records = srcs
        existing.resolution_confidence = clamp((existing.resolution_confidence or 1.0))
        db.commit()
        db.refresh(existing)
        row = existing
    else:
        row = EntMdmRecord(tenant_id=tenant_id, entity_type=entity_type, natural_key=natural_key,
                           golden_record=record, source_records=[{"source": source, "record": record}],
                           resolution_confidence=1.0, steward=steward)
        db.add(row)
        db.commit()
        db.refresh(row)
    row.quality_score = _quality_score(db, entity_type, row.golden_record, tenant_id)
    db.commit()
    return {"record_id": row.id, "entity_type": entity_type, "natural_key": natural_key,
            "golden_record": row.golden_record, "quality_score": row.quality_score,
            "source_count": len(row.source_records or [])}


def list_golden(db: Session, *, entity_type: Optional[str] = None, limit: int = 100,
                tenant_id: Optional[int] = None) -> List[Dict[str, Any]]:
    q = db.query(EntMdmRecord)
    if tenant_id is not None:
        q = q.filter(EntMdmRecord.tenant_id == tenant_id)
    if entity_type:
        q = q.filter(EntMdmRecord.entity_type == entity_type)
    return [{"record_id": r.id, "entity_type": r.entity_type, "natural_key": r.natural_key,
             "golden_record": r.golden_record, "quality_score": r.quality_score,
             "status": r.status, "is_duplicate_of": r.is_duplicate_of}
            for r in q.order_by(EntMdmRecord.id.desc()).limit(limit).all()]


def detect_duplicates(db: Session, *, entity_type: str, threshold: float = 0.85,
                      field: str = "name", tenant_id: Optional[int] = None,
                      created_by: Optional[str] = None) -> Dict[str, Any]:
    """Pairwise duplicate detection over golden records by a key field."""
    rows = (db.query(EntMdmRecord)
            .filter(EntMdmRecord.tenant_id == tenant_id, EntMdmRecord.entity_type == entity_type,
                    EntMdmRecord.status == "active").all())
    pairs = []
    for i in range(len(rows)):
        for j in range(i + 1, len(rows)):
            a = (rows[i].golden_record or {}).get(field) or rows[i].natural_key
            b = (rows[j].golden_record or {}).get(field) or rows[j].natural_key
            sim = _similarity(a, b)
            if sim >= threshold:
                pairs.append({"record_a": rows[i].id, "record_b": rows[j].id,
                              "value_a": a, "value_b": b, "similarity": sim})
    summary = {"entity_type": entity_type, "candidates": len(pairs), "threshold": threshold,
               "pairs": pairs}
    _log_job(db, job_type="dedup", entity_type=entity_type, summary=summary,
             tenant_id=tenant_id, created_by=created_by)
    return summary


def merge_records(db: Session, *, survivor_id: int, duplicate_id: int,
                  tenant_id: Optional[int] = None) -> Dict[str, Any]:
    survivor = db.query(EntMdmRecord).filter(EntMdmRecord.id == survivor_id).first()
    dup = db.query(EntMdmRecord).filter(EntMdmRecord.id == duplicate_id).first()
    if not survivor or not dup:
        raise ValueError("record not found")
    golden = dict(survivor.golden_record or {})
    for k, v in (dup.golden_record or {}).items():
        if golden.get(k) in (None, "", []):
            golden[k] = v
    survivor.golden_record = golden
    survivor.source_records = list(survivor.source_records or []) + list(dup.source_records or [])
    dup.status = "merged"
    dup.is_duplicate_of = survivor_id
    db.commit()
    return {"survivor_id": survivor_id, "merged_id": duplicate_id, "golden_record": golden}


def resolve_entity(db: Session, *, entity_type: str, record: Dict[str, Any], field: str = "name",
                   threshold: float = 0.85, tenant_id: Optional[int] = None) -> Dict[str, Any]:
    """Return the best-matching golden record for an inbound record (entity resolution)."""
    rows = (db.query(EntMdmRecord)
            .filter(EntMdmRecord.tenant_id == tenant_id, EntMdmRecord.entity_type == entity_type,
                    EntMdmRecord.status == "active").all())
    value = record.get(field, "")
    best = None
    best_sim = 0.0
    for r in rows:
        sim = _similarity(value, (r.golden_record or {}).get(field) or r.natural_key)
        if sim > best_sim:
            best_sim, best = sim, r
    matched = best is not None and best_sim >= threshold
    return {"entity_type": entity_type, "matched": matched,
            "match_record_id": best.id if matched else None,
            "confidence": best_sim if best else 0.0,
            "action": "link" if matched else "create_new"}


# ---------------------------------------------------------------------------
# Data-quality rules
# ---------------------------------------------------------------------------

def create_rule(db: Session, *, name: str, dimension: str = "completeness",
                entity_type: Optional[str] = None, field: Optional[str] = None,
                expression: Optional[dict] = None, severity: str = "warning",
                tenant_id: Optional[int] = None) -> Dict[str, Any]:
    if dimension not in DQ_DIMENSIONS:
        raise ValueError(f"unknown dimension '{dimension}'")
    row = EntDataRule(tenant_id=tenant_id, name=name, entity_type=entity_type, dimension=dimension,
                      field=field, expression=expression or {}, severity=severity)
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"rule_id": row.id, "name": row.name, "dimension": row.dimension, "severity": row.severity}


def _eval_rule(rule: EntDataRule, record: Dict[str, Any]) -> bool:
    field = rule.field
    val = record.get(field) if field else None
    expr = rule.expression or {}
    if rule.dimension == "completeness":
        return val not in (None, "", [])
    if rule.dimension == "validity":
        pattern = expr.get("regex")
        if pattern and val is not None:
            return re.match(pattern, str(val)) is not None
        allowed = expr.get("in")
        if allowed is not None:
            return val in allowed
        return val is not None
    if rule.dimension == "accuracy":
        lo, hi = expr.get("min"), expr.get("max")
        try:
            v = float(val)
            return (lo is None or v >= lo) and (hi is None or v <= hi)
        except (TypeError, ValueError):
            return False
    return True


def run_quality_scan(db: Session, *, entity_type: str, tenant_id: Optional[int] = None,
                     created_by: Optional[str] = None) -> Dict[str, Any]:
    rules = (db.query(EntDataRule)
             .filter(EntDataRule.tenant_id == tenant_id, EntDataRule.enabled == True)  # noqa: E712
             .filter((EntDataRule.entity_type == entity_type) | (EntDataRule.entity_type.is_(None)))
             .all())
    records = (db.query(EntMdmRecord)
               .filter(EntMdmRecord.tenant_id == tenant_id, EntMdmRecord.entity_type == entity_type,
                       EntMdmRecord.status == "active").all())
    results = []
    total_checks = passed_checks = 0
    for rule in rules:
        violations = 0
        for rec in records:
            total_checks += 1
            if _eval_rule(rule, rec.golden_record or {}):
                passed_checks += 1
            else:
                violations += 1
        results.append({"rule": rule.name, "dimension": rule.dimension, "severity": rule.severity,
                        "violations": violations, "checked": len(records)})
    score = round(100.0 * safe_div(passed_checks, total_checks, 1.0), 2)
    summary = {"entity_type": entity_type, "rules_run": len(rules), "records": len(records),
               "quality_score": score, "results": results}
    _log_job(db, job_type="dq_scan", entity_type=entity_type, summary=summary,
             tenant_id=tenant_id, created_by=created_by)
    return summary


def _quality_score(db: Session, entity_type: str, record: Dict[str, Any],
                   tenant_id: Optional[int]) -> float:
    rules = (db.query(EntDataRule)
             .filter(EntDataRule.tenant_id == tenant_id, EntDataRule.enabled == True)  # noqa: E712
             .filter((EntDataRule.entity_type == entity_type) | (EntDataRule.entity_type.is_(None)))
             .all())
    if not rules:
        # Fall back to completeness of the record's own fields.
        vals = list(record.values())
        return round(100.0 * safe_div(sum(1 for v in vals if v not in (None, "", [])), len(vals) or 1, 1.0), 2)
    passed = sum(1 for r in rules if _eval_rule(r, record))
    return round(100.0 * safe_div(passed, len(rules), 1.0), 2)


# ---------------------------------------------------------------------------
# Bulk import/export + jobs
# ---------------------------------------------------------------------------

def bulk_import(db: Session, *, entity_type: str, records: List[Dict[str, Any]], key_field: str = "id",
                dedupe: bool = True, tenant_id: Optional[int] = None,
                created_by: Optional[str] = None) -> Dict[str, Any]:
    imported = merged = 0
    for rec in records:
        nk = str(rec.get(key_field) or slugify(str(rec.get("name", ""))) or f"rec-{imported}")
        if dedupe:
            match = resolve_entity(db, entity_type=entity_type, record=rec, tenant_id=tenant_id)
            if match["matched"]:
                merged += 1
                continue
        upsert_golden(db, entity_type=entity_type, natural_key=nk, record=rec, source="bulk_import",
                      tenant_id=tenant_id)
        imported += 1
    summary = {"entity_type": entity_type, "received": len(records), "imported": imported,
               "deduped": merged}
    _log_job(db, job_type="import", entity_type=entity_type, summary=summary,
             tenant_id=tenant_id, created_by=created_by)
    return summary


def bulk_export(db: Session, *, entity_type: str, tenant_id: Optional[int] = None,
                created_by: Optional[str] = None) -> Dict[str, Any]:
    rows = list_golden(db, entity_type=entity_type, limit=100000, tenant_id=tenant_id)
    summary = {"entity_type": entity_type, "exported": len(rows)}
    _log_job(db, job_type="export", entity_type=entity_type, summary=summary,
             tenant_id=tenant_id, created_by=created_by)
    return {"entity_type": entity_type, "count": len(rows),
            "records": [r["golden_record"] for r in rows]}


def _log_job(db: Session, *, job_type: str, entity_type: Optional[str], summary: dict,
             tenant_id: Optional[int], created_by: Optional[str]) -> None:
    db.add(EntDataJob(tenant_id=tenant_id, job_type=job_type, entity_type=entity_type,
                      status="completed", summary=summary, created_by=created_by))
    db.commit()


def list_jobs(db: Session, *, job_type: Optional[str] = None, limit: int = 50,
              tenant_id: Optional[int] = None) -> List[Dict[str, Any]]:
    q = db.query(EntDataJob)
    if tenant_id is not None:
        q = q.filter(EntDataJob.tenant_id == tenant_id)
    if job_type:
        q = q.filter(EntDataJob.job_type == job_type)
    return [{"job_id": j.id, "job_type": j.job_type, "entity_type": j.entity_type, "status": j.status,
             "summary": j.summary, "created_at": iso(j.created_at)}
            for j in q.order_by(EntDataJob.id.desc()).limit(limit).all()]


def catalog(db: Session, *, tenant_id: Optional[int] = None) -> Dict[str, Any]:
    """Data catalog: counts and quality per entity type."""
    out = {}
    for et in ENTITY_TYPES:
        rows = (db.query(EntMdmRecord)
                .filter(EntMdmRecord.tenant_id == tenant_id, EntMdmRecord.entity_type == et,
                        EntMdmRecord.status == "active").all())
        scores = [r.quality_score for r in rows if r.quality_score is not None]
        out[et] = {"records": len(rows), "avg_quality": round(mean(scores), 2) if scores else None}
    return {"entities": out, "generated_at": iso(utcnow())}
