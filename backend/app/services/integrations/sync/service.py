"""Portfolio synchronization engine.

Synchronises enterprise data from external connectors into the platform with

* **Full** and **incremental** sync (incremental skips snapshots not yet due for
  refresh, using the snapshot store's ``refresh_due_at`` watermark).
* **Conflict detection + resolution** — when a re-fetch produces content that
  differs from the current snapshot, the change is recorded as a conflict and
  resolved by the configured strategy (``latest_wins`` by default; the versioned
  snapshot store keeps the prior version regardless).
* **Versioning** — every accepted change appends a new snapshot version.
* **Background jobs** — :func:`start_job` records a :class:`PortfolioSyncJob`
  :func:`process_job` executes it (call it from a worker / job runner).
* **Retry queue + dead-letter queue** — failed targets are retried up to a limit
  exhausted failures land in :class:`SyncDeadLetter` for later replay.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from backend.app.models.integrations import PortfolioSyncJob, SyncDeadLetter
from backend.app.services.integrations import service as import_svc
from backend.app.services.integrations import snapshots as snap_store

# Default operation per connector used during portfolio sync.
_DEFAULT_OPERATIONS = {
    "gst": "get_profile",
    "mca": "get_company_master",
    "bureau": "get_business_score",
    "erp": "get_financial_statements",
    "payments": "get_transaction_health",
}


def start_job(
    db: Session,
    *,
    sync_type: str = "incremental",
    connectors: Optional[List[str]] = None,
    entity_refs: Optional[List[str]] = None,
    scope: Optional[Dict[str, Any]] = None,
) -> PortfolioSyncJob:
    connectors = connectors or list(_DEFAULT_OPERATIONS.keys())
    scope = dict(scope or {})
    if entity_refs:
        scope["entity_refs"] = entity_refs
    job = PortfolioSyncJob(
        sync_type=sync_type if sync_type in ("full", "incremental") else "incremental",
        connectors=connectors,
        status="pending",
        scope=scope,
        stats={},
        conflicts=[],
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def process_job(
    db: Session,
    job_id: int,
    *,
    max_retries: int = 2,
    conflict_strategy: str = "latest_wins",
    operations: Optional[Dict[str, str]] = None,
) -> PortfolioSyncJob:
    """Execute a sync job: fetch each (entity, connector), version snapshots, track conflicts."""
    job = db.query(PortfolioSyncJob).get(job_id)
    if job is None:
        raise ValueError("sync job not found")
    if job.status in ("completed", "running"):
        return job

    job.status = "running"
    job.started_at = datetime.utcnow()
    db.commit()

    entity_refs = (job.scope or {}).get("entity_refs", [])
    op_map = {**_DEFAULT_OPERATIONS, **(operations or {})}
    targets = [(e, c) for e in entity_refs for c in job.connectors]

    processed = failed = skipped = conflicts_found = 0
    conflicts: List[Dict[str, Any]] = []

    for entity_ref, connector_key in targets:
        operation = op_map.get(connector_key)
        if operation is None:
            continue

        # Incremental: skip if a current snapshot exists and isn't due for refresh.
        if job.sync_type == "incremental":
            current = snap_store.current_snapshot(db, connector_key=connector_key,
                                                   entity_ref=entity_ref, dataset=operation)
            if current is not None and (current.refresh_due_at is None or current.refresh_due_at > datetime.utcnow()):
                skipped += 1
                continue

        prev = snap_store.current_snapshot(db, connector_key=connector_key,
                                           entity_ref=entity_ref, dataset=operation)
        prev_hash = prev.content_hash if prev else None

        ok = _sync_one(db, job, entity_ref, connector_key, operation, max_retries)
        if not ok:
            failed += 1
            continue

        new = snap_store.current_snapshot(db, connector_key=connector_key,
                                          entity_ref=entity_ref, dataset=operation)
        if prev_hash is not None and new is not None and new.content_hash != prev_hash:
            conflicts_found += 1
            conflicts.append({
                "entity_ref": entity_ref, "connector_key": connector_key, "dataset": operation,
                "from_version": prev.version, "to_version": new.version,
                "resolution": conflict_strategy,
            })
        processed += 1

    job.total = len(targets)
    job.processed = processed
    job.failed = failed
    job.conflicts = conflicts
    job.stats = {"processed": processed, "failed": failed, "skipped": skipped,
                 "conflicts": conflicts_found, "targets": len(targets)}
    job.finished_at = datetime.utcnow()
    job.cursor = job.finished_at.isoformat()
    job.status = "completed" if failed == 0 else "partial"
    db.commit()
    db.refresh(job)
    return job


def _sync_one(db: Session, job: PortfolioSyncJob, entity_ref: str, connector_key: str,
              operation: str, max_retries: int) -> bool:
    """Import one target with bounded retries; dead-letter on exhaustion."""
    last_error = None
    for attempt in range(1, max_retries + 2):  # initial + retries
        try:
            resp, _snap = import_svc.import_dataset(
                db, connector_key=connector_key, entity_ref=entity_ref,
                operation=operation, dataset=operation, refresh_after_days=30,
            )
            if resp.success:
                return True
            last_error = resp.error
        except Exception as exc:  # noqa: BLE001
            last_error = str(exc)
            try:
                db.rollback()
            except Exception:
                pass
    # Exhausted → dead-letter.
    db.add(SyncDeadLetter(
        job_id=job.id, connector_key=connector_key, entity_ref=entity_ref,
        operation=operation, payload={"operation": operation}, error=last_error or "unknown",
        retries=max_retries,
    ))
    db.commit()
    return False


def replay_dead_letters(db: Session, *, job_id: Optional[int] = None, limit: int = 50) -> Dict[str, Any]:
    """Reprocess unresolved dead-letter entries."""
    q = db.query(SyncDeadLetter).filter(SyncDeadLetter.resolved.is_(False))
    if job_id is not None:
        q = q.filter(SyncDeadLetter.job_id == job_id)
    entries = q.order_by(SyncDeadLetter.id).limit(limit).all()
    resolved = still_failed = 0
    for dl in entries:
        try:
            resp, _ = import_svc.import_dataset(
                db, connector_key=dl.connector_key, entity_ref=dl.entity_ref,
                operation=dl.operation or "get_profile", dataset=dl.operation, refresh_after_days=30,
            )
            if resp.success:
                dl.resolved = True
                resolved += 1
            else:
                dl.retries += 1
                still_failed += 1
        except Exception as exc:  # noqa: BLE001
            dl.retries += 1
            dl.error = str(exc)
            still_failed += 1
            try:
                db.rollback()
            except Exception:
                pass
    db.commit()
    return {"replayed": len(entries), "resolved": resolved, "still_failed": still_failed}


def run_sync(
    db: Session,
    *,
    sync_type: str = "incremental",
    connectors: Optional[List[str]] = None,
    entity_refs: Optional[List[str]] = None,
    max_retries: int = 2,
    conflict_strategy: str = "latest_wins",
) -> PortfolioSyncJob:
    """Convenience: create a job and process it synchronously."""
    job = start_job(db, sync_type=sync_type, connectors=connectors, entity_refs=entity_refs)
    return process_job(db, job.id, max_retries=max_retries, conflict_strategy=conflict_strategy)


def job_to_dict(job: PortfolioSyncJob) -> Dict[str, Any]:
    return {
        "id": job.id, "sync_type": job.sync_type, "connectors": job.connectors,
        "status": job.status, "scope": job.scope, "cursor": job.cursor,
        "stats": job.stats, "conflicts": job.conflicts, "total": job.total,
        "processed": job.processed, "failed": job.failed,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "finished_at": job.finished_at.isoformat() if job.finished_at else None,
        "created_at": job.created_at.isoformat() if job.created_at else None,
    }
