"""Generic integration import service (M2, M3, M6, M7, M8).

One reusable path used by every snapshot-backed domain (GST, MCA, bureau, ERP
payments): call the configured connector for an operation, and — on success
persist a versioned, refresh-scheduled snapshot. Domain modules add thin
readable wrappers on top (e.g. ``import_gst_bundle``).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from backend.app.models.integrations import IntegrationSnapshot
from backend.app.services.integrations import snapshots as snap_store
from backend.app.services.integrations.base.types import ConnectorResponse
from backend.app.services.integrations.factory import get_connector


def import_dataset(
    db: Session,
    *,
    connector_key: str,
    entity_ref: str,
    operation: str,
    params: Optional[Dict[str, Any]] = None,
    dataset: Optional[str] = None,
    application_id: Optional[int] = None,
    created_by: Optional[str] = None,
    mode: Optional[str] = None,
    refresh_after_days: Optional[int] = 30,
) -> Tuple[ConnectorResponse, Optional[IntegrationSnapshot]]:
    """Fetch one operation and store its result as a snapshot (on success)."""
    conn = get_connector(db, connector_key, mode=mode)
    call_params = dict(params or {})
    call_params.setdefault("entity_ref", entity_ref)
    resp = conn.call(operation, call_params, db=db)
    snap = None
    if resp.success:
        snap = snap_store.save_snapshot(
            db,
            connector_key=connector_key,
            provider=conn.provider,
            mode=conn.mode.value,
            dataset=dataset or operation,
            entity_ref=entity_ref,
            payload=resp.data,
            application_id=application_id,
            created_by=created_by,
            refresh_after_days=refresh_after_days,
        )
    return resp, snap


def import_bundle(
    db: Session,
    *,
    connector_key: str,
    entity_ref: str,
    operations: List[str],
    params: Optional[Dict[str, Any]] = None,
    application_id: Optional[int] = None,
    created_by: Optional[str] = None,
    mode: Optional[str] = None,
    refresh_after_days: Optional[int] = 30,
) -> Dict[str, Any]:
    """Import several operations for one entity, each stored as its own dataset."""
    results: Dict[str, Any] = {}
    errors: Dict[str, str] = {}
    for op in operations:
        resp, snap = import_dataset(
            db, connector_key=connector_key, entity_ref=entity_ref, operation=op,
            params=params, dataset=op, application_id=application_id,
            created_by=created_by, mode=mode, refresh_after_days=refresh_after_days,
        )
        if resp.success:
            results[op] = {"snapshot_id": snap.id if snap else None, "version": snap.version if snap else None,
                           "data": resp.data}
        else:
            errors[op] = resp.error or "unknown error"
    return {
        "connector_key": connector_key,
        "entity_ref": entity_ref,
        "imported": list(results.keys()),
        "failed": errors,
        "results": results,
    }


def get_current(
    db: Session, *, connector_key: str, entity_ref: str, dataset: str = "default",
) -> Optional[Dict[str, Any]]:
    snap = snap_store.current_snapshot(db, connector_key=connector_key, entity_ref=entity_ref, dataset=dataset)
    return snap_store.snapshot_to_dict(snap) if snap else None


def get_history(
    db: Session, *, connector_key: str, entity_ref: str, dataset: str = "default",
) -> List[Dict[str, Any]]:
    return [snap_store.snapshot_to_dict(s)
            for s in snap_store.snapshot_versions(db, connector_key=connector_key, entity_ref=entity_ref, dataset=dataset)]
