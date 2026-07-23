"""Banking Ecosystem Integration Platform APIs (Phase 7).

A set of focused routers exposing the whole integration surface. All new,
additive to existing routers:

    /api/integrations/connectors     connector catalog, config, mode switching
    /api/integrations/observability  metrics, health, circuit state, call logs
    /api/integrations/data           import + snapshots for GST/MCA/bureau/ERP/payments
    /api/integrations/aa             Account Aggregator consent + statements + analytics
    /api/integrations/sync           portfolio synchronization jobs + DLQ
    /api/collateral                  collateral management
    /api/customer360                 unified enterprise profile
    /api/platform                    Open API keys, webhooks, usage analytics

Permissions: ``integrations.view``/``integrations.manage``/``integrations.sync``,
``collateral.view``/``collateral.manage``, ``customer360.view``,
``apiplatform.view``/``apiplatform.manage``.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.app.core.dependencies import get_current_user
from backend.app.db.database import get_db
from backend.app.models.user import User
from backend.app.schemas.integrations import (
    ApiKeyCreate, CollateralCreate, CollateralInspect, CollateralRevalue,
    ConnectorConfigUpdate, ConnectorModeUpdate, ConsentCreate, ImportRequest,
    StatementImport, SyncRequest, WebhookCreate, WebhookEmit,
)
from backend.app.services.integrations import config as cfg_svc
from backend.app.services.integrations import dashboard as obs_svc
from backend.app.services.integrations import service as import_svc
from backend.app.services.integrations import snapshots as snap_store
from backend.app.services.integrations.aa import service as aa_svc
from backend.app.services.integrations.analytics import statement as analytics_svc
from backend.app.services.integrations.apiplatform import service as api_svc
from backend.app.services.integrations.apiplatform import webhooks as wh_svc
from backend.app.services.integrations.base.registry import registry
from backend.app.services.integrations.collateral import catalog as coll_catalog
from backend.app.services.integrations.collateral import service as coll_svc
from backend.app.services.integrations.customer360 import build_profile
from backend.app.services.integrations.factory import register_all
from backend.app.services.integrations.logging import recent_calls
from backend.app.services.integrations.sync import service as sync_svc
from backend.app.services.rbac import require_permission

_SNAPSHOT_CONNECTORS = {"gst", "mca", "bureau", "erp", "payments"}


def _actor(user: Optional[User]) -> Optional[str]:
    return getattr(user, "email", None) if user else None


# ===========================================================================
# Connectors + configuration
# ===========================================================================
connectors_router = APIRouter(prefix="/api/integrations/connectors", tags=["Integrations: Connectors"])


@connectors_router.get("")
def list_connectors(db: Session = Depends(get_db), _user=Depends(require_permission("integrations.view"))):
    register_all()
    return {"connectors": registry.describe(), "configs": cfg_svc.list_configs(db)}


@connectors_router.get("/{connector_key}")
def get_connector_config(connector_key: str, db: Session = Depends(get_db),
                         _user=Depends(require_permission("integrations.view"))):
    register_all()
    if not registry.is_registered(connector_key):
        raise HTTPException(status_code=404, detail="connector not found")
    cfg = cfg_svc.get_config(db, connector_key)
    return {
        "connector_key": connector_key,
        "modes": registry.modes(connector_key),
        "category": registry.category_of(connector_key),
        "config": cfg_svc.config_to_dict(cfg) if cfg else None,
    }


@connectors_router.put("/{connector_key}/mode")
def set_connector_mode(connector_key: str, body: ConnectorModeUpdate, db: Session = Depends(get_db),
                       _user=Depends(require_permission("integrations.manage"))):
    register_all()
    if not registry.is_registered(connector_key, body.provider_mode):
        raise HTTPException(status_code=400, detail="mode not available for this connector")
    return cfg_svc.config_to_dict(cfg_svc.set_mode(db, connector_key, body.provider_mode))


@connectors_router.put("/{connector_key}/config")
def update_connector_config(connector_key: str, body: ConnectorConfigUpdate, db: Session = Depends(get_db),
                            _user=Depends(require_permission("integrations.manage"))):
    register_all()
    if not registry.is_registered(connector_key):
        raise HTTPException(status_code=404, detail="connector not found")
    cfg = cfg_svc.update_config(
        db, connector_key, enabled=body.enabled, config=body.config,
        credentials=body.credentials, rate_limit_per_sec=body.rate_limit_per_sec,
        timeout_seconds=body.timeout_seconds,
    )
    return cfg_svc.config_to_dict(cfg)


# ===========================================================================
# Observability
# ===========================================================================
observability_router = APIRouter(prefix="/api/integrations/observability", tags=["Integrations: Observability"])


@observability_router.get("/overview")
def observability_overview(db: Session = Depends(get_db), _user=Depends(require_permission("integrations.view"))):
    return obs_svc.connector_overview(db)


@observability_router.get("/metrics")
def observability_metrics(_user=Depends(require_permission("integrations.view"))):
    return obs_svc.metrics_snapshot()


@observability_router.get("/health")
def observability_health(db: Session = Depends(get_db), _user=Depends(require_permission("integrations.view"))):
    return {"health": obs_svc.health_all(db)}


@observability_router.get("/call-logs")
def observability_call_logs(
    connector_key: Optional[str] = None, provider: Optional[str] = None,
    success: Optional[bool] = None, limit: int = Query(100, le=1000),
    db: Session = Depends(get_db), _user=Depends(require_permission("integrations.view")),
):
    rows = recent_calls(db, connector_key=connector_key, provider=provider, success=success, limit=limit)
    return {"calls": [{
        "id": r.id, "connector_key": r.connector_key, "provider": r.provider, "mode": r.mode,
        "operation": r.operation, "success": r.success, "from_cache": r.from_cache,
        "latency_ms": r.latency_ms, "attempts": r.attempts, "circuit_state": r.circuit_state,
        "error": r.error, "entity_ref": r.entity_ref,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    } for r in rows]}


# ===========================================================================
# Generic data import + snapshots (GST/MCA/bureau/ERP/payments)
# ===========================================================================
data_router = APIRouter(prefix="/api/integrations/data", tags=["Integrations: Data"])


def _require_snapshot_connector(connector_key: str) -> None:
    if connector_key not in _SNAPSHOT_CONNECTORS:
        raise HTTPException(status_code=404, detail="unknown snapshot connector")


@data_router.post("/{connector_key}/import")
def import_data(connector_key: str, body: ImportRequest, db: Session = Depends(get_db),
                user=Depends(require_permission("integrations.manage"))):
    _require_snapshot_connector(connector_key)
    if body.operations:
        return import_svc.import_bundle(
            db, connector_key=connector_key, entity_ref=body.entity_ref,
            operations=body.operations, params=body.params, application_id=body.application_id,
            created_by=_actor(user), mode=body.mode, refresh_after_days=body.refresh_after_days,
        )
    operation = body.operation
    if not operation:
        raise HTTPException(status_code=400, detail="operation or operations is required")
    resp, snap = import_svc.import_dataset(
        db, connector_key=connector_key, entity_ref=body.entity_ref, operation=operation,
        params=body.params, dataset=operation, application_id=body.application_id,
        created_by=_actor(user), mode=body.mode, refresh_after_days=body.refresh_after_days,
    )
    if not resp.success:
        raise HTTPException(status_code=502, detail=resp.error or "import failed")
    return {"response": resp.to_dict(), "snapshot": snap_store.snapshot_to_dict(snap) if snap else None}


@data_router.get("/{connector_key}/{entity_ref}")
def get_current_snapshot(connector_key: str, entity_ref: str, dataset: str = "default",
                         db: Session = Depends(get_db), _user=Depends(require_permission("integrations.view"))):
    _require_snapshot_connector(connector_key)
    snap = import_svc.get_current(db, connector_key=connector_key, entity_ref=entity_ref, dataset=dataset)
    if snap is None:
        raise HTTPException(status_code=404, detail="no snapshot found")
    return snap


@data_router.get("/{connector_key}/{entity_ref}/history")
def get_snapshot_history(connector_key: str, entity_ref: str, dataset: str = "default",
                         db: Session = Depends(get_db), _user=Depends(require_permission("integrations.view"))):
    _require_snapshot_connector(connector_key)
    return {"versions": import_svc.get_history(db, connector_key=connector_key, entity_ref=entity_ref, dataset=dataset)}


# ===========================================================================
# Account Aggregator
# ===========================================================================
aa_router = APIRouter(prefix="/api/integrations/aa", tags=["Integrations: Account Aggregator"])


@aa_router.post("/consents")
def create_consent(body: ConsentCreate, db: Session = Depends(get_db),
                   _user=Depends(require_permission("integrations.manage"))):
    c = aa_svc.create_consent(db, entity_ref=body.entity_ref, purpose=body.purpose,
                              months=body.months, application_id=body.application_id, fi_types=body.fi_types)
    return aa_svc.consent_to_dict(c)


@aa_router.post("/consents/{consent_id}/refresh")
def refresh_consent(consent_id: int, db: Session = Depends(get_db),
                    _user=Depends(require_permission("integrations.manage"))):
    try:
        return aa_svc.consent_to_dict(aa_svc.sync_consent_status(db, consent_id))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@aa_router.post("/consents/{consent_id}/revoke")
def revoke_consent(consent_id: int, db: Session = Depends(get_db),
                   _user=Depends(require_permission("integrations.manage"))):
    try:
        return aa_svc.consent_to_dict(aa_svc.revoke_consent(db, consent_id))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@aa_router.post("/consents/{consent_id}/discover")
def discover_accounts(consent_id: int, db: Session = Depends(get_db),
                      _user=Depends(require_permission("integrations.manage"))):
    try:
        return {"accounts": aa_svc.discover_accounts(db, consent_id)}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@aa_router.post("/statements/import")
def import_statement(body: StatementImport, db: Session = Depends(get_db),
                     _user=Depends(require_permission("integrations.manage"))):
    try:
        stmt = aa_svc.import_statement(
            db, entity_ref=body.entity_ref, account_ref=body.account_ref, months=body.months,
            consent_id=body.consent_id, application_id=body.application_id,
            account_type=body.account_type, bank_name=body.bank_name,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return aa_svc.statement_to_dict(stmt)


@aa_router.get("/statements/{statement_id}")
def get_statement(statement_id: int, with_transactions: bool = False, db: Session = Depends(get_db),
                  _user=Depends(require_permission("integrations.view"))):
    from backend.app.models.integrations import BankStatement
    stmt = db.query(BankStatement).get(statement_id)
    if stmt is None:
        raise HTTPException(status_code=404, detail="statement not found")
    return aa_svc.statement_to_dict(stmt, with_transactions=with_transactions, db=db)


@aa_router.post("/statements/{statement_id}/analyze")
def analyze_statement(statement_id: int, db: Session = Depends(get_db),
                      _user=Depends(require_permission("integrations.view"))):
    try:
        return analytics_svc.analyze_statement(db, statement_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@aa_router.get("/entities/{entity_ref}/analytics")
def entity_analytics(entity_ref: str, db: Session = Depends(get_db),
                     _user=Depends(require_permission("integrations.view"))):
    try:
        return analytics_svc.analyze_entity(db, entity_ref)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ===========================================================================
# Synchronization
# ===========================================================================
sync_router = APIRouter(prefix="/api/integrations/sync", tags=["Integrations: Synchronization"])


@sync_router.post("/run")
def run_sync(body: SyncRequest, db: Session = Depends(get_db),
             _user=Depends(require_permission("integrations.sync"))):
    job = sync_svc.run_sync(db, sync_type=body.sync_type, connectors=body.connectors,
                            entity_refs=body.entity_refs, max_retries=body.max_retries,
                            conflict_strategy=body.conflict_strategy)
    return sync_svc.job_to_dict(job)


@sync_router.get("/jobs")
def list_sync_jobs(limit: int = Query(50, le=200), db: Session = Depends(get_db),
                   _user=Depends(require_permission("integrations.view"))):
    from backend.app.models.integrations import PortfolioSyncJob
    rows = db.query(PortfolioSyncJob).order_by(PortfolioSyncJob.id.desc()).limit(limit).all()
    return {"jobs": [sync_svc.job_to_dict(j) for j in rows]}


@sync_router.get("/jobs/{job_id}")
def get_sync_job(job_id: int, db: Session = Depends(get_db),
                 _user=Depends(require_permission("integrations.view"))):
    from backend.app.models.integrations import PortfolioSyncJob
    job = db.query(PortfolioSyncJob).get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    return sync_svc.job_to_dict(job)


@sync_router.get("/dead-letters")
def list_dead_letters(job_id: Optional[int] = None, db: Session = Depends(get_db),
                      _user=Depends(require_permission("integrations.view"))):
    from backend.app.models.integrations import SyncDeadLetter
    q = db.query(SyncDeadLetter).filter(SyncDeadLetter.resolved.is_(False))
    if job_id is not None:
        q = q.filter(SyncDeadLetter.job_id == job_id)
    rows = q.order_by(SyncDeadLetter.id.desc()).all()
    return {"dead_letters": [{
        "id": d.id, "job_id": d.job_id, "connector_key": d.connector_key,
        "entity_ref": d.entity_ref, "operation": d.operation, "error": d.error,
        "retries": d.retries, "resolved": d.resolved,
    } for d in rows]}


@sync_router.post("/dead-letters/replay")
def replay_dead_letters(job_id: Optional[int] = None, db: Session = Depends(get_db),
                        _user=Depends(require_permission("integrations.sync"))):
    return sync_svc.replay_dead_letters(db, job_id=job_id)


# ===========================================================================
# Collateral
# ===========================================================================
collateral_router = APIRouter(prefix="/api/collateral", tags=["Collateral"])


@collateral_router.get("/types")
def collateral_types(_user=Depends(require_permission("collateral.view"))):
    return {"types": coll_catalog.catalog()}


@collateral_router.post("")
def create_collateral(body: CollateralCreate, db: Session = Depends(get_db),
                      _user=Depends(require_permission("collateral.manage"))):
    try:
        item = coll_svc.create_collateral(
            db, collateral_type=body.collateral_type, description=body.description,
            market_value=body.market_value, entity_ref=body.entity_ref,
            application_id=body.application_id, owner=body.owner, haircut_pct=body.haircut_pct,
            loan_amount=body.loan_amount, charge_type=body.charge_type, details=body.details,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return coll_svc.to_dict(item, db=db)


@collateral_router.get("/{collateral_id}")
def get_collateral(collateral_id: int, db: Session = Depends(get_db),
                   _user=Depends(require_permission("collateral.view"))):
    from backend.app.models.integrations import CollateralItem
    item = db.query(CollateralItem).get(collateral_id)
    if item is None:
        raise HTTPException(status_code=404, detail="collateral not found")
    return coll_svc.to_dict(item, db=db)


@collateral_router.post("/{collateral_id}/revalue")
def revalue_collateral(collateral_id: int, body: CollateralRevalue, db: Session = Depends(get_db),
                       _user=Depends(require_permission("collateral.manage"))):
    try:
        item = coll_svc.revalue(db, collateral_id, market_value=body.market_value,
                                haircut_pct=body.haircut_pct, method=body.method,
                                valuer=body.valuer, notes=body.notes)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return coll_svc.to_dict(item, db=db)


@collateral_router.post("/{collateral_id}/inspect")
def inspect_collateral(collateral_id: int, body: CollateralInspect, db: Session = Depends(get_db),
                       _user=Depends(require_permission("collateral.manage"))):
    try:
        coll_svc.add_inspection(db, collateral_id, inspector=body.inspector,
                                outcome=body.outcome, condition=body.condition, notes=body.notes)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    from backend.app.models.integrations import CollateralItem
    return coll_svc.to_dict(db.query(CollateralItem).get(collateral_id), db=db)


@collateral_router.get("/applications/{application_id}")
def application_collateral(application_id: int, db: Session = Depends(get_db),
                           _user=Depends(require_permission("collateral.view"))):
    items = coll_svc.list_for_application(db, application_id)
    return {"summary": coll_svc.coverage_summary(db, application_id=application_id),
            "items": [coll_svc.to_dict(i) for i in items]}


@collateral_router.get("/entities/{entity_ref}")
def entity_collateral(entity_ref: str, db: Session = Depends(get_db),
                      _user=Depends(require_permission("collateral.view"))):
    items = coll_svc.list_for_entity(db, entity_ref)
    return {"summary": coll_svc.coverage_summary(db, entity_ref=entity_ref),
            "items": [coll_svc.to_dict(i) for i in items]}


# ===========================================================================
# Customer 360
# ===========================================================================
customer360_router = APIRouter(prefix="/api/customer360", tags=["Customer 360"])


@customer360_router.get("/applications/{application_id}")
def customer360_application(application_id: int, db: Session = Depends(get_db),
                            _user=Depends(require_permission("customer360.view"))):
    return build_profile(db, application_id=application_id)


@customer360_router.get("/entities/{entity_ref}")
def customer360_entity(entity_ref: str, db: Session = Depends(get_db),
                       _user=Depends(require_permission("customer360.view"))):
    return build_profile(db, entity_ref=entity_ref)


# ===========================================================================
# Open API platform
# ===========================================================================
platform_router = APIRouter(prefix="/api/platform", tags=["Open API Platform"])


@platform_router.get("/keys")
def list_api_keys(db: Session = Depends(get_db), _user=Depends(require_permission("apiplatform.view"))):
    return {"keys": api_svc.list_keys(db)}


@platform_router.post("/keys")
def create_api_key(body: ApiKeyCreate, db: Session = Depends(get_db),
                   user=Depends(require_permission("apiplatform.manage"))):
    row, raw = api_svc.create_api_key(db, name=body.name, scopes=body.scopes,
                                      owner=body.owner or _actor(user), rate_limit_per_min=body.rate_limit_per_min)
    out = api_svc.key_to_dict(row)
    out["api_key"] = raw  # shown once
    return out


@platform_router.delete("/keys/{key_id}")
def revoke_api_key(key_id: int, db: Session = Depends(get_db),
                   _user=Depends(require_permission("apiplatform.manage"))):
    try:
        return api_svc.key_to_dict(api_svc.revoke_api_key(db, key_id))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@platform_router.get("/usage")
def api_usage(api_key_id: Optional[int] = None, db: Session = Depends(get_db),
              _user=Depends(require_permission("apiplatform.view"))):
    return api_svc.usage_analytics(db, api_key_id=api_key_id)


@platform_router.get("/webhooks/events")
def webhook_events(_user=Depends(require_permission("apiplatform.view"))):
    return {"events": wh_svc.EVENT_TYPES}


@platform_router.get("/webhooks")
def list_webhooks(db: Session = Depends(get_db), _user=Depends(require_permission("apiplatform.view"))):
    return {"subscriptions": [wh_svc.subscription_to_dict(s) for s in wh_svc.list_subscriptions(db)]}


@platform_router.post("/webhooks")
def create_webhook(body: WebhookCreate, db: Session = Depends(get_db),
                   _user=Depends(require_permission("apiplatform.manage"))):
    try:
        sub = wh_svc.create_subscription(db, url=body.url, events=body.events,
                                         secret=body.secret, description=body.description)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return wh_svc.subscription_to_dict(sub)


@platform_router.post("/webhooks/emit")
def emit_webhook(body: WebhookEmit, db: Session = Depends(get_db),
                 _user=Depends(require_permission("apiplatform.manage"))):
    deliveries = wh_svc.emit(db, body.event, body.payload)
    return {"deliveries": [wh_svc.delivery_to_dict(d) for d in deliveries]}


@platform_router.get("/webhooks/{subscription_id}/deliveries")
def webhook_deliveries(subscription_id: int, db: Session = Depends(get_db),
                       _user=Depends(require_permission("apiplatform.view"))):
    return {"deliveries": [wh_svc.delivery_to_dict(d) for d in wh_svc.delivery_history(db, subscription_id=subscription_id)]}


# Exported for main.py — mirrors the Phase 6 ROUTERS pattern.
ROUTERS: List[APIRouter] = [
    connectors_router, observability_router, data_router, aa_router,
    sync_router, collateral_router, customer360_router, platform_router,
]
