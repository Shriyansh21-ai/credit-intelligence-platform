"""M12 — AI governance.

A registry + lifecycle for every AI asset (prompts, models, datasets, agents
workflows, RAG indexes, reports) so that every AI decision is reproducible.
Each asset carries a version, a content checksum and a lineage bundle; every
state change and every use is recorded as an immutable event, giving a full
audit trail from a decision back to the exact prompt/model/dataset that produced
it.

Assets move through a governed state machine

    registered → validated → approved → deployed → retired

This layer is complementary to (not a replacement for) the ML model
registry and the model-governance events — it governs the *AI platform*
artifacts specifically.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from backend.app.models.ai_platform import AIPAsset, AIPAssetEvent
from backend.app.services.ai_platform import common

ASSET_TYPES = ["prompt", "model", "dataset", "agent", "workflow", "rag_index", "report"]

# Allowed state transitions (action → resulting state, valid from-states).
_TRANSITIONS = {
    "validate": ("validated", {"registered"}),
    "approve": ("approved", {"validated"}),
    "deploy": ("deployed", {"approved"}),
    "retire": ("retired", {"registered", "validated", "approved", "deployed"}),
}


def _event(db: Session, asset_id: int, event_type: str, actor: Optional[str],
           detail: Optional[Dict[str, Any]] = None) -> AIPAssetEvent:
    ev = AIPAssetEvent(asset_id=asset_id, event_type=event_type, actor=actor,
                       detail=detail or {}, created_at=common.utcnow())
    db.add(ev)
    return ev


def register_asset(db: Session, *, asset_type: str, asset_ref: str, name: str,
                   version: str = "1", lineage: Optional[Dict[str, Any]] = None,
                   owner: Optional[str] = None, meta: Optional[Dict[str, Any]] = None,
                   tenant_id: Optional[int] = None,
                   actor: Optional[str] = None) -> AIPAsset:
    if asset_type not in ASSET_TYPES:
        raise ValueError(f"unknown asset_type '{asset_type}'")
    lineage = lineage or {}
    checksum = common.content_hash(asset_type, asset_ref, version, sorted(lineage.items()))
    existing = (db.query(AIPAsset)
                .filter(AIPAsset.tenant_id == tenant_id, AIPAsset.asset_type == asset_type,
                        AIPAsset.asset_ref == asset_ref, AIPAsset.version == version).first())
    if existing:
        existing.lineage = lineage
        existing.checksum = checksum
        existing.meta = meta or existing.meta
        db.commit()
        db.refresh(existing)
        return existing
    asset = AIPAsset(tenant_id=tenant_id, asset_type=asset_type, asset_ref=asset_ref,
                     name=name, version=version, state="registered", lineage=lineage,
                     checksum=checksum, owner=owner, meta=meta or {},
                     created_at=common.utcnow(), updated_at=common.utcnow())
    db.add(asset)
    db.commit()
    db.refresh(asset)
    _event(db, asset.id, "register", actor, {"version": version, "checksum": checksum})
    db.commit()
    return asset


def transition(db: Session, *, asset_id: int, action: str,
               actor: Optional[str] = None,
               detail: Optional[Dict[str, Any]] = None) -> AIPAsset:
    if action not in _TRANSITIONS:
        raise ValueError(f"unknown action '{action}'")
    asset = db.query(AIPAsset).filter(AIPAsset.id == asset_id).first()
    if asset is None:
        raise ValueError("asset not found")
    new_state, valid_from = _TRANSITIONS[action]
    if asset.state not in valid_from:
        raise ValueError(f"cannot {action} from state '{asset.state}'")
    asset.state = new_state
    asset.updated_at = common.utcnow()
    _event(db, asset.id, action, actor, detail)
    db.commit()
    db.refresh(asset)
    return asset


def record_use(db: Session, *, asset_id: int, actor: Optional[str] = None,
               detail: Optional[Dict[str, Any]] = None) -> AIPAssetEvent:
    asset = db.query(AIPAsset).filter(AIPAsset.id == asset_id).first()
    if asset is None:
        raise ValueError("asset not found")
    ev = _event(db, asset_id, "use", actor, detail)
    db.commit()
    db.refresh(ev)
    return ev


def lineage(db: Session, *, asset_id: int) -> Dict[str, Any]:
    """Full reproducibility bundle: asset config + version + checksum + event trail."""
    asset = db.query(AIPAsset).filter(AIPAsset.id == asset_id).first()
    if asset is None:
        raise ValueError("asset not found")
    events = (db.query(AIPAssetEvent).filter(AIPAssetEvent.asset_id == asset_id)
              .order_by(AIPAssetEvent.id).all())
    return {"asset_id": asset.id, "asset_type": asset.asset_type, "asset_ref": asset.asset_ref,
            "name": asset.name, "version": asset.version, "state": asset.state,
            "checksum": asset.checksum, "lineage": asset.lineage, "owner": asset.owner,
            "reproducible": bool(asset.checksum),
            "events": [{"event_type": e.event_type, "actor": e.actor, "detail": e.detail,
                        "at": common.iso(e.created_at)} for e in events]}


def get_asset(db, asset_id: int) -> Optional[Dict[str, Any]]:
    a = db.query(AIPAsset).filter(AIPAsset.id == asset_id).first()
    if not a:
        return None
    return lineage(db, asset_id=asset_id)


def list_assets(db, *, tenant_id=None, asset_type=None, state=None, limit=100) -> List[Dict[str, Any]]:
    q = db.query(AIPAsset).filter(AIPAsset.tenant_id == tenant_id)
    if asset_type:
        q = q.filter(AIPAsset.asset_type == asset_type)
    if state:
        q = q.filter(AIPAsset.state == state)
    return [{"id": a.id, "asset_type": a.asset_type, "asset_ref": a.asset_ref,
             "name": a.name, "version": a.version, "state": a.state,
             "checksum": a.checksum, "created_at": common.iso(a.created_at)}
            for a in q.order_by(AIPAsset.id.desc()).limit(limit).all()]


def registry_summary(db, *, tenant_id=None) -> Dict[str, Any]:
    assets = db.query(AIPAsset).filter(AIPAsset.tenant_id == tenant_id).all()
    by_type: Dict[str, int] = {}
    by_state: Dict[str, int] = {}
    for a in assets:
        by_type[a.asset_type] = by_type.get(a.asset_type, 0) + 1
        by_state[a.state] = by_state.get(a.state, 0) + 1
    return {"total": len(assets), "by_type": by_type, "by_state": by_state,
            "reproducible": sum(1 for a in assets if a.checksum)}
