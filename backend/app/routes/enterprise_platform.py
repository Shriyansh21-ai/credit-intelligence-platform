"""Enterprise Productization & Commercial Readiness APIs (Track 4).

Additive routers exposing the productization layer under ``/api/ent/*``. Every
route is new; no existing route is modified. RBAC is enforced with the Track 4
permission catalog (``ent.*``). Routers are collected into ``ROUTERS`` and mounted
in ``main.py``.

    /api/ent/ux           enterprise UX / personalization (M1)
    /api/ent/workspaces   enterprise workspaces (M2)
    /api/ent/developer    developer platform (M3)
    /api/ent/marketplace  plugin marketplace (M4)
    /api/ent/integration  integration studio (M5)
    /api/ent/data         data management / MDM (M6)
    /api/ent/operations   operations center (M7)
    /api/ent/security     security center (M8)
    /api/ent/success      customer success (M9)
    /api/ent/deployment   deployment platform (M10)
    /api/ent/monitoring   monitoring platform (M11)
    /api/ent/bi           business intelligence (M12)
    /api/ent/launch       launch readiness (M13)
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.app.core.dependencies import get_current_user
from backend.app.db.database import get_db
from backend.app.models.user import User
from backend.app.services.rbac import require_permission
from backend.app.schemas.enterprise_platform import (
    AccessReviewComplete, AccessReviewStart, ApiKeyCreate, BulkImport, ChecklistGenerate,
    ChecklistItemUpdate, CustomerCreate, CustomerEventRecord, DashboardSave, DataRuleCreate,
    DeployRequest, DuplicateScan, EnvironmentCreate, EntityResolve, EscalationCheck,
    GoldenUpsert, IncidentOpen, IncidentUpdate, LayoutSave, MergeRecords, OnboardingAdvance,
    PipelineRun, PipelineSave, PluginPublish, PluginReview, PluginVersionAdd, PreferencesUpdate,
    RateLimitTest, RollbackRequest, RunbookCreate, SandboxRequest, SecurityEventRecord,
    SessionAnalyze, SlaRecord, TraceRecord, WebhookCreate, WebhookTest, WorkspaceCreate,
    WorkspaceItemAdd, WorkspaceMemberAdd,
)
from backend.app.services.enterprise_platform import (
    bi as bi_svc, customer_success as success_svc, data_mgmt as data_svc,
    deployment as deploy_svc, developer as dev_svc, integration as integration_svc,
    launch as launch_svc, marketplace as marketplace_svc, monitoring as monitoring_svc,
    operations as ops_svc, security_center as security_svc, ux as ux_svc,
    workspaces as workspaces_svc,
)


def _tenant(explicit: Optional[int] = None) -> Optional[int]:
    if explicit is not None:
        return explicit
    try:
        from backend.app.services.saas import context as tenant_ctx
        return tenant_ctx.current_tenant_id()
    except Exception:
        return None


def _uref(user: Optional[User]) -> Optional[str]:
    return getattr(user, "email", None) if user else None


def _bad(exc: Exception):
    raise HTTPException(status_code=400, detail=str(exc))


# ===========================================================================
# M1 — Enterprise UX Platform
# ===========================================================================
ux_router = APIRouter(prefix="/api/ent/ux", tags=["ENT: UX"])


@ux_router.get("/preferences")
def get_preferences(tenant_id: Optional[int] = None, db: Session = Depends(get_db),
                    user=Depends(get_current_user), _u=Depends(require_permission("ent.ux.view"))):
    return ux_svc.get_preferences(db, user_ref=_uref(user) or "anon", tenant_id=_tenant(tenant_id))


@ux_router.post("/preferences")
def save_preferences(body: PreferencesUpdate, tenant_id: Optional[int] = None,
                     db: Session = Depends(get_db), user=Depends(get_current_user),
                     _u=Depends(require_permission("ent.ux.manage"))):
    try:
        return ux_svc.save_preferences(db, user_ref=_uref(user) or "anon", theme=body.theme,
                                       density=body.density, accent=body.accent,
                                       sidebar_collapsed=body.sidebar_collapsed,
                                       shortcuts_enabled=body.shortcuts_enabled, settings=body.settings,
                                       tenant_id=_tenant(tenant_id))
    except ValueError as e:
        _bad(e)


@ux_router.get("/layouts")
def list_layouts(surface: Optional[str] = None, tenant_id: Optional[int] = None,
                 db: Session = Depends(get_db), user=Depends(get_current_user),
                 _u=Depends(require_permission("ent.ux.view"))):
    return {"layouts": ux_svc.list_layouts(db, user_ref=_uref(user) or "anon", surface=surface,
                                           tenant_id=_tenant(tenant_id))}


@ux_router.post("/layouts")
def save_layout(body: LayoutSave, tenant_id: Optional[int] = None, db: Session = Depends(get_db),
                user=Depends(get_current_user), _u=Depends(require_permission("ent.ux.manage"))):
    return ux_svc.save_layout(db, user_ref=_uref(user) or "anon", name=body.name, config=body.config,
                              surface=body.surface, scope=body.scope, is_default=body.is_default,
                              key=body.key, tenant_id=_tenant(tenant_id))


@ux_router.get("/commands")
def commands(query: Optional[str] = None, _u=Depends(require_permission("ent.ux.view"))):
    return {"commands": ux_svc.command_catalog(query)}


# ===========================================================================
# M2 — Enterprise Workspace Platform
# ===========================================================================
workspaces_router = APIRouter(prefix="/api/ent/workspaces", tags=["ENT: Workspaces"])


@workspaces_router.get("/types")
def workspace_types(_u=Depends(require_permission("ent.workspace.view"))):
    return {"workspace_types": workspaces_svc.WORKSPACE_TYPES, "item_types": workspaces_svc.ITEM_TYPES}


@workspaces_router.get("")
def list_workspaces(workspace_type: Optional[str] = None, tenant_id: Optional[int] = None,
                    db: Session = Depends(get_db), _u=Depends(require_permission("ent.workspace.view"))):
    return {"workspaces": workspaces_svc.list_workspaces(db, workspace_type=workspace_type,
                                                        tenant_id=_tenant(tenant_id))}


@workspaces_router.post("")
def create_workspace(body: WorkspaceCreate, tenant_id: Optional[int] = None, db: Session = Depends(get_db),
                     user=Depends(get_current_user), _u=Depends(require_permission("ent.workspace.manage"))):
    try:
        return workspaces_svc.create_workspace(db, name=body.name, workspace_type=body.workspace_type,
                                               description=body.description,
                                               owner_ref=body.owner_ref or _uref(user),
                                               settings=body.settings, key=body.key,
                                               tenant_id=_tenant(tenant_id), created_by=_uref(user))
    except ValueError as e:
        _bad(e)


@workspaces_router.get("/{workspace_id}")
def get_workspace(workspace_id: int, db: Session = Depends(get_db),
                  _u=Depends(require_permission("ent.workspace.view"))):
    out = workspaces_svc.get_workspace(db, workspace_id)
    if not out:
        raise HTTPException(status_code=404, detail="workspace not found")
    return out


@workspaces_router.post("/members")
def add_member(body: WorkspaceMemberAdd, db: Session = Depends(get_db),
               _u=Depends(require_permission("ent.workspace.manage"))):
    try:
        return workspaces_svc.add_member(db, workspace_id=body.workspace_id, user_ref=body.user_ref,
                                         role=body.role)
    except ValueError as e:
        _bad(e)


@workspaces_router.post("/items")
def add_item(body: WorkspaceItemAdd, tenant_id: Optional[int] = None, db: Session = Depends(get_db),
             user=Depends(get_current_user), _u=Depends(require_permission("ent.workspace.manage"))):
    try:
        return workspaces_svc.add_item(db, workspace_id=body.workspace_id, item_type=body.item_type,
                                       title=body.title, ref=body.ref, payload=body.payload,
                                       tenant_id=_tenant(tenant_id), created_by=_uref(user))
    except ValueError as e:
        _bad(e)


@workspaces_router.get("/{workspace_id}/items")
def list_items(workspace_id: int, item_type: Optional[str] = None, db: Session = Depends(get_db),
               _u=Depends(require_permission("ent.workspace.view"))):
    return {"items": workspaces_svc.list_items(db, workspace_id=workspace_id, item_type=item_type)}


@workspaces_router.get("/{workspace_id}/analytics")
def workspace_analytics(workspace_id: int, db: Session = Depends(get_db),
                        _u=Depends(require_permission("ent.workspace.view"))):
    try:
        return workspaces_svc.analytics(db, workspace_id=workspace_id)
    except ValueError as e:
        _bad(e)


# ===========================================================================
# M3 — Enterprise Developer Platform
# ===========================================================================
developer_router = APIRouter(prefix="/api/ent/developer", tags=["ENT: Developer"])


@developer_router.get("/explorer")
def api_explorer(db: Session = Depends(get_db), _u=Depends(require_permission("ent.developer.view"))):
    return dev_svc.api_explorer(db)


@developer_router.get("/keys")
def list_api_keys(tenant_id: Optional[int] = None, db: Session = Depends(get_db),
                  _u=Depends(require_permission("ent.developer.view"))):
    return {"api_keys": dev_svc.list_api_keys(db, tenant_id=_tenant(tenant_id))}


@developer_router.post("/keys")
def create_api_key(body: ApiKeyCreate, tenant_id: Optional[int] = None, db: Session = Depends(get_db),
                   user=Depends(get_current_user), _u=Depends(require_permission("ent.developer.manage"))):
    return dev_svc.create_api_key(db, name=body.name, scopes=body.scopes, environment=body.environment,
                                  rate_limit_per_min=body.rate_limit_per_min,
                                  tenant_id=_tenant(tenant_id), created_by=_uref(user))


@developer_router.post("/keys/{api_key_id}/revoke")
def revoke_api_key(api_key_id: int, db: Session = Depends(get_db),
                   _u=Depends(require_permission("ent.developer.manage"))):
    try:
        return dev_svc.revoke_api_key(db, api_key_id=api_key_id)
    except ValueError as e:
        _bad(e)


@developer_router.post("/keys/rate-limit-test")
def rate_limit_test(body: RateLimitTest, tenant_id: Optional[int] = None, db: Session = Depends(get_db),
                    _u=Depends(require_permission("ent.developer.manage"))):
    try:
        return dev_svc.rate_limit_test(db, api_key_id=body.api_key_id, requests=body.requests,
                                       tenant_id=_tenant(tenant_id))
    except ValueError as e:
        _bad(e)


@developer_router.get("/webhooks")
def list_webhooks(tenant_id: Optional[int] = None, db: Session = Depends(get_db),
                  _u=Depends(require_permission("ent.developer.view"))):
    return {"webhooks": dev_svc.list_webhooks(db, tenant_id=_tenant(tenant_id))}


@developer_router.post("/webhooks")
def create_webhook(body: WebhookCreate, tenant_id: Optional[int] = None, db: Session = Depends(get_db),
                   user=Depends(get_current_user), _u=Depends(require_permission("ent.developer.manage"))):
    try:
        return dev_svc.create_webhook(db, url=body.url, events=body.events, description=body.description,
                                      tenant_id=_tenant(tenant_id), created_by=_uref(user))
    except ValueError as e:
        _bad(e)


@developer_router.post("/webhooks/test")
def test_webhook(body: WebhookTest, tenant_id: Optional[int] = None, db: Session = Depends(get_db),
                 _u=Depends(require_permission("ent.developer.manage"))):
    try:
        return dev_svc.test_webhook(db, webhook_id=body.webhook_id, event=body.event, payload=body.payload,
                                    simulate_status=body.simulate_status, tenant_id=_tenant(tenant_id))
    except ValueError as e:
        _bad(e)


@developer_router.post("/webhooks/deliveries/{delivery_id}/replay")
def replay_delivery(delivery_id: int, tenant_id: Optional[int] = None, db: Session = Depends(get_db),
                    _u=Depends(require_permission("ent.developer.manage"))):
    try:
        return dev_svc.replay_delivery(db, delivery_id=delivery_id, tenant_id=_tenant(tenant_id))
    except ValueError as e:
        _bad(e)


@developer_router.get("/webhooks/deliveries")
def list_deliveries(webhook_id: Optional[int] = None, tenant_id: Optional[int] = None,
                    db: Session = Depends(get_db), _u=Depends(require_permission("ent.developer.view"))):
    return {"deliveries": dev_svc.list_deliveries(db, webhook_id=webhook_id, tenant_id=_tenant(tenant_id))}


@developer_router.post("/sandbox")
def sandbox(body: SandboxRequest, tenant_id: Optional[int] = None, db: Session = Depends(get_db),
            _u=Depends(require_permission("ent.developer.manage"))):
    return dev_svc.sandbox_request(db, method=body.method, path=body.path, body=body.body,
                                   api_key_prefix=body.api_key_prefix, tenant_id=_tenant(tenant_id))


@developer_router.get("/requests")
def request_history(path: Optional[str] = None, tenant_id: Optional[int] = None,
                    db: Session = Depends(get_db), _u=Depends(require_permission("ent.developer.view"))):
    return {"requests": dev_svc.request_history(db, path=path, tenant_id=_tenant(tenant_id))}


# ===========================================================================
# M4 — Enterprise Plugin Marketplace
# ===========================================================================
marketplace_router = APIRouter(prefix="/api/ent/marketplace", tags=["ENT: Marketplace"])


@marketplace_router.get("")
def list_plugins(status: Optional[str] = None, category: Optional[str] = None,
                 tenant_id: Optional[int] = None, db: Session = Depends(get_db),
                 _u=Depends(require_permission("ent.marketplace.view"))):
    return {"plugins": marketplace_svc.list_plugins(db, status=status, category=category,
                                                   tenant_id=_tenant(tenant_id))}


@marketplace_router.post("/publish")
def publish_plugin(body: PluginPublish, tenant_id: Optional[int] = None, db: Session = Depends(get_db),
                   user=Depends(get_current_user), _u=Depends(require_permission("ent.marketplace.manage"))):
    try:
        return marketplace_svc.publish_plugin(db, key=body.key, name=body.name, version=body.version,
                                              publisher=body.publisher, category=body.category,
                                              permissions=body.permissions, dependencies=body.dependencies,
                                              compatibility=body.compatibility, billing_model=body.billing_model,
                                              description=body.description, tenant_id=_tenant(tenant_id),
                                              created_by=_uref(user))
    except ValueError as e:
        _bad(e)


@marketplace_router.post("/versions")
def add_version(body: PluginVersionAdd, db: Session = Depends(get_db),
                _u=Depends(require_permission("ent.marketplace.manage"))):
    try:
        return marketplace_svc.add_version(db, plugin_id=body.plugin_id, version=body.version,
                                           changelog=body.changelog, manifest=body.manifest)
    except ValueError as e:
        _bad(e)


@marketplace_router.post("/review")
def review_version(body: PluginReview, db: Session = Depends(get_db), user=Depends(get_current_user),
                   _u=Depends(require_permission("ent.marketplace.manage"))):
    try:
        return marketplace_svc.review_version(db, version_id=body.version_id, approve=body.approve,
                                              reviewer=_uref(user))
    except ValueError as e:
        _bad(e)


@marketplace_router.post("/{plugin_id}/publish")
def publish_approved(plugin_id: int, db: Session = Depends(get_db),
                     _u=Depends(require_permission("ent.marketplace.manage"))):
    try:
        return marketplace_svc.publish_approved(db, plugin_id=plugin_id)
    except ValueError as e:
        _bad(e)


@marketplace_router.get("/{plugin_id}/compatibility")
def check_compatibility(plugin_id: int, db: Session = Depends(get_db),
                        _u=Depends(require_permission("ent.marketplace.view"))):
    try:
        return marketplace_svc.check_compatibility(db, plugin_id=plugin_id)
    except ValueError as e:
        _bad(e)


@marketplace_router.post("/{plugin_id}/install")
def install_plugin(plugin_id: int, tenant_id: Optional[int] = None, db: Session = Depends(get_db),
                   user=Depends(get_current_user), _u=Depends(require_permission("ent.marketplace.manage"))):
    try:
        return marketplace_svc.install_plugin(db, plugin_id=plugin_id, tenant_id=_tenant(tenant_id),
                                              installed_by=_uref(user))
    except ValueError as e:
        _bad(e)


@marketplace_router.get("/{plugin_id}")
def get_plugin(plugin_id: int, db: Session = Depends(get_db),
               _u=Depends(require_permission("ent.marketplace.view"))):
    out = marketplace_svc.get_plugin(db, plugin_id)
    if not out:
        raise HTTPException(status_code=404, detail="plugin not found")
    return out


@marketplace_router.get("/analytics/summary")
def marketplace_analytics(tenant_id: Optional[int] = None, db: Session = Depends(get_db),
                          _u=Depends(require_permission("ent.marketplace.view"))):
    return marketplace_svc.analytics(db, tenant_id=_tenant(tenant_id))


# ===========================================================================
# M5 — Enterprise Integration Studio
# ===========================================================================
integration_router = APIRouter(prefix="/api/ent/integration", tags=["ENT: Integration"])


@integration_router.get("/node-types")
def node_types(_u=Depends(require_permission("ent.integration.view"))):
    return {"node_types": integration_svc.NODE_TYPES, "triggers": integration_svc.TRIGGERS}


@integration_router.post("/validate")
def validate_pipeline(body: PipelineSave, _u=Depends(require_permission("ent.integration.view"))):
    return integration_svc.validate(body.graph)


@integration_router.get("")
def list_pipelines(tenant_id: Optional[int] = None, db: Session = Depends(get_db),
                   _u=Depends(require_permission("ent.integration.view"))):
    return {"pipelines": integration_svc.list_pipelines(db, tenant_id=_tenant(tenant_id))}


@integration_router.post("")
def save_pipeline(body: PipelineSave, tenant_id: Optional[int] = None, db: Session = Depends(get_db),
                  user=Depends(get_current_user), _u=Depends(require_permission("ent.integration.manage"))):
    try:
        return integration_svc.save_pipeline(db, name=body.name, graph=body.graph, key=body.key,
                                             description=body.description, schedule=body.schedule,
                                             retry_policy=body.retry_policy, tenant_id=_tenant(tenant_id),
                                             created_by=_uref(user))
    except ValueError as e:
        _bad(e)


@integration_router.post("/run")
def run_pipeline(body: PipelineRun, tenant_id: Optional[int] = None, db: Session = Depends(get_db),
                 _u=Depends(require_permission("ent.integration.manage"))):
    try:
        return integration_svc.run_pipeline(db, pipeline_id=body.pipeline_id,
                                            sample_input=body.sample_input, trigger=body.trigger,
                                            tenant_id=_tenant(tenant_id))
    except ValueError as e:
        _bad(e)


@integration_router.get("/{pipeline_id}")
def get_pipeline(pipeline_id: int, db: Session = Depends(get_db),
                 _u=Depends(require_permission("ent.integration.view"))):
    out = integration_svc.get_pipeline(db, pipeline_id)
    if not out:
        raise HTTPException(status_code=404, detail="pipeline not found")
    return out


@integration_router.get("/{pipeline_id}/runs")
def pipeline_runs(pipeline_id: int, tenant_id: Optional[int] = None, db: Session = Depends(get_db),
                  _u=Depends(require_permission("ent.integration.view"))):
    return {"runs": integration_svc.list_runs(db, pipeline_id=pipeline_id, tenant_id=_tenant(tenant_id))}


# ===========================================================================
# M6 — Enterprise Data Management
# ===========================================================================
data_router = APIRouter(prefix="/api/ent/data", tags=["ENT: Data Management"])


@data_router.get("/entity-types")
def entity_types(_u=Depends(require_permission("ent.data.view"))):
    return {"entity_types": data_svc.ENTITY_TYPES, "dq_dimensions": data_svc.DQ_DIMENSIONS}


@data_router.post("/golden")
def upsert_golden(body: GoldenUpsert, tenant_id: Optional[int] = None, db: Session = Depends(get_db),
                  _u=Depends(require_permission("ent.data.manage"))):
    try:
        return data_svc.upsert_golden(db, entity_type=body.entity_type, natural_key=body.natural_key,
                                      record=body.record, source=body.source, steward=body.steward,
                                      tenant_id=_tenant(tenant_id))
    except ValueError as e:
        _bad(e)


@data_router.get("/golden")
def list_golden(entity_type: Optional[str] = None, tenant_id: Optional[int] = None,
                db: Session = Depends(get_db), _u=Depends(require_permission("ent.data.view"))):
    return {"records": data_svc.list_golden(db, entity_type=entity_type, tenant_id=_tenant(tenant_id))}


@data_router.post("/duplicates")
def detect_duplicates(body: DuplicateScan, tenant_id: Optional[int] = None, db: Session = Depends(get_db),
                      user=Depends(get_current_user), _u=Depends(require_permission("ent.data.manage"))):
    return data_svc.detect_duplicates(db, entity_type=body.entity_type, threshold=body.threshold,
                                      field=body.field, tenant_id=_tenant(tenant_id), created_by=_uref(user))


@data_router.post("/merge")
def merge_records(body: MergeRecords, tenant_id: Optional[int] = None, db: Session = Depends(get_db),
                  _u=Depends(require_permission("ent.data.manage"))):
    try:
        return data_svc.merge_records(db, survivor_id=body.survivor_id, duplicate_id=body.duplicate_id,
                                      tenant_id=_tenant(tenant_id))
    except ValueError as e:
        _bad(e)


@data_router.post("/resolve")
def resolve_entity(body: EntityResolve, tenant_id: Optional[int] = None, db: Session = Depends(get_db),
                   _u=Depends(require_permission("ent.data.view"))):
    return data_svc.resolve_entity(db, entity_type=body.entity_type, record=body.record, field=body.field,
                                   threshold=body.threshold, tenant_id=_tenant(tenant_id))


@data_router.post("/rules")
def create_rule(body: DataRuleCreate, tenant_id: Optional[int] = None, db: Session = Depends(get_db),
                _u=Depends(require_permission("ent.data.manage"))):
    try:
        return data_svc.create_rule(db, name=body.name, dimension=body.dimension,
                                    entity_type=body.entity_type, field=body.field,
                                    expression=body.expression, severity=body.severity,
                                    tenant_id=_tenant(tenant_id))
    except ValueError as e:
        _bad(e)


@data_router.post("/quality-scan")
def quality_scan(entity_type: str, tenant_id: Optional[int] = None, db: Session = Depends(get_db),
                 user=Depends(get_current_user), _u=Depends(require_permission("ent.data.manage"))):
    return data_svc.run_quality_scan(db, entity_type=entity_type, tenant_id=_tenant(tenant_id),
                                     created_by=_uref(user))


@data_router.post("/import")
def bulk_import(body: BulkImport, tenant_id: Optional[int] = None, db: Session = Depends(get_db),
                user=Depends(get_current_user), _u=Depends(require_permission("ent.data.manage"))):
    return data_svc.bulk_import(db, entity_type=body.entity_type, records=body.records,
                                key_field=body.key_field, dedupe=body.dedupe,
                                tenant_id=_tenant(tenant_id), created_by=_uref(user))


@data_router.get("/export")
def bulk_export(entity_type: str, tenant_id: Optional[int] = None, db: Session = Depends(get_db),
                user=Depends(get_current_user), _u=Depends(require_permission("ent.data.view"))):
    return data_svc.bulk_export(db, entity_type=entity_type, tenant_id=_tenant(tenant_id),
                                created_by=_uref(user))


@data_router.get("/catalog")
def data_catalog(tenant_id: Optional[int] = None, db: Session = Depends(get_db),
                 _u=Depends(require_permission("ent.data.view"))):
    return data_svc.catalog(db, tenant_id=_tenant(tenant_id))


@data_router.get("/jobs")
def data_jobs(job_type: Optional[str] = None, tenant_id: Optional[int] = None,
              db: Session = Depends(get_db), _u=Depends(require_permission("ent.data.view"))):
    return {"jobs": data_svc.list_jobs(db, job_type=job_type, tenant_id=_tenant(tenant_id))}


# ===========================================================================
# M7 — Enterprise Operations Center
# ===========================================================================
operations_router = APIRouter(prefix="/api/ent/operations", tags=["ENT: Operations"])


@operations_router.get("/dashboard")
def ops_dashboard(tenant_id: Optional[int] = None, db: Session = Depends(get_db),
                  _u=Depends(require_permission("ent.ops.view"))):
    return ops_svc.dashboard(db, tenant_id=_tenant(tenant_id))


@operations_router.get("/incidents")
def list_incidents(status: Optional[str] = None, component: Optional[str] = None,
                   tenant_id: Optional[int] = None, db: Session = Depends(get_db),
                   _u=Depends(require_permission("ent.ops.view"))):
    return {"incidents": ops_svc.list_incidents(db, status=status, component=component,
                                               tenant_id=_tenant(tenant_id))}


@operations_router.post("/incidents")
def open_incident(body: IncidentOpen, tenant_id: Optional[int] = None, db: Session = Depends(get_db),
                  user=Depends(get_current_user), _u=Depends(require_permission("ent.ops.manage"))):
    try:
        return ops_svc.open_incident(db, title=body.title, component=body.component, severity=body.severity,
                                     summary=body.summary, runbook_key=body.runbook_key,
                                     tenant_id=_tenant(tenant_id), created_by=_uref(user))
    except ValueError as e:
        _bad(e)


@operations_router.post("/incidents/update")
def update_incident(body: IncidentUpdate, db: Session = Depends(get_db), user=Depends(get_current_user),
                    _u=Depends(require_permission("ent.ops.manage"))):
    try:
        return ops_svc.update_incident(db, incident_id=body.incident_id, status=body.status,
                                       note=body.note, root_cause=body.root_cause, actor=_uref(user))
    except ValueError as e:
        _bad(e)


@operations_router.get("/incidents/{incident_id}/rca")
def rca(incident_id: int, db: Session = Depends(get_db),
        _u=Depends(require_permission("ent.ops.view"))):
    try:
        return ops_svc.root_cause_analysis(db, incident_id=incident_id)
    except ValueError as e:
        _bad(e)


@operations_router.post("/runbooks")
def create_runbook(body: RunbookCreate, tenant_id: Optional[int] = None, db: Session = Depends(get_db),
                   _u=Depends(require_permission("ent.ops.manage"))):
    try:
        return ops_svc.create_runbook(db, title=body.title, steps=body.steps, key=body.key,
                                      category=body.category, trigger=body.trigger, severity=body.severity,
                                      tenant_id=_tenant(tenant_id))
    except ValueError as e:
        _bad(e)


@operations_router.post("/runbooks/seed")
def seed_runbooks(tenant_id: Optional[int] = None, db: Session = Depends(get_db),
                  _u=Depends(require_permission("ent.ops.manage"))):
    return ops_svc.seed_runbooks(db, tenant_id=_tenant(tenant_id))


@operations_router.get("/runbooks")
def list_runbooks(category: Optional[str] = None, tenant_id: Optional[int] = None,
                  db: Session = Depends(get_db), _u=Depends(require_permission("ent.ops.view"))):
    return {"runbooks": ops_svc.list_runbooks(db, category=category, tenant_id=_tenant(tenant_id))}


# ===========================================================================
# M8 — Enterprise Security Center
# ===========================================================================
security_router = APIRouter(prefix="/api/ent/security", tags=["ENT: Security"])


@security_router.get("/dashboard")
def security_dashboard(tenant_id: Optional[int] = None, db: Session = Depends(get_db),
                       _u=Depends(require_permission("ent.security.view"))):
    return security_svc.dashboard(db, tenant_id=_tenant(tenant_id))


@security_router.get("/events")
def list_events(event_type: Optional[str] = None, severity: Optional[str] = None,
                status: Optional[str] = None, tenant_id: Optional[int] = None,
                db: Session = Depends(get_db), _u=Depends(require_permission("ent.security.view"))):
    return {"events": security_svc.list_events(db, event_type=event_type, severity=severity,
                                             status=status, tenant_id=_tenant(tenant_id))}


@security_router.post("/events")
def record_event(body: SecurityEventRecord, tenant_id: Optional[int] = None, db: Session = Depends(get_db),
                 _u=Depends(require_permission("ent.security.manage"))):
    try:
        return security_svc.record_event(db, event_type=body.event_type, subject_ref=body.subject_ref,
                                         severity=body.severity, source_ip=body.source_ip,
                                         detail=body.detail, tenant_id=_tenant(tenant_id))
    except ValueError as e:
        _bad(e)


@security_router.post("/analyze-session")
def analyze_session(body: SessionAnalyze, tenant_id: Optional[int] = None, db: Session = Depends(get_db),
                    _u=Depends(require_permission("ent.security.view"))):
    return security_svc.analyze_session(db, subject_ref=body.subject_ref, source_ip=body.source_ip,
                                        failed_logins=body.failed_logins, new_device=body.new_device,
                                        impossible_travel=body.impossible_travel, off_hours=body.off_hours,
                                        tenant_id=_tenant(tenant_id))


@security_router.post("/escalation-check")
def escalation_check(body: EscalationCheck, tenant_id: Optional[int] = None, db: Session = Depends(get_db),
                     _u=Depends(require_permission("ent.security.view"))):
    return security_svc.detect_privilege_escalation(db, subject_ref=body.subject_ref,
                                                    granted_permissions=body.granted_permissions,
                                                    sensitive=body.sensitive, tenant_id=_tenant(tenant_id))


@security_router.post("/access-reviews")
def start_access_review(body: AccessReviewStart, tenant_id: Optional[int] = None,
                        db: Session = Depends(get_db), user=Depends(get_current_user),
                        _u=Depends(require_permission("ent.security.manage"))):
    return security_svc.start_access_review(db, scope=body.scope, reviewer=body.reviewer or _uref(user),
                                            tenant_id=_tenant(tenant_id))


@security_router.post("/access-reviews/complete")
def complete_access_review(body: AccessReviewComplete, db: Session = Depends(get_db),
                           _u=Depends(require_permission("ent.security.manage"))):
    try:
        return security_svc.complete_access_review(db, review_id=body.review_id, decision=body.decision,
                                                   summary=body.summary)
    except ValueError as e:
        _bad(e)


@security_router.get("/access-reviews")
def list_access_reviews(status: Optional[str] = None, tenant_id: Optional[int] = None,
                        db: Session = Depends(get_db), _u=Depends(require_permission("ent.security.view"))):
    return {"reviews": security_svc.list_access_reviews(db, status=status, tenant_id=_tenant(tenant_id))}


@security_router.get("/key-rotation")
def key_rotation(tenant_id: Optional[int] = None, db: Session = Depends(get_db),
                 _u=Depends(require_permission("ent.security.view"))):
    return security_svc.key_rotation_status(db, tenant_id=_tenant(tenant_id))


# ===========================================================================
# M9 — Enterprise Customer Success Platform
# ===========================================================================
success_router = APIRouter(prefix="/api/ent/success", tags=["ENT: Customer Success"])


@success_router.get("/dashboard")
def success_dashboard(tenant_id: Optional[int] = None, db: Session = Depends(get_db),
                      _u=Depends(require_permission("ent.success.view"))):
    return success_svc.dashboard(db, tenant_id=_tenant(tenant_id))


@success_router.get("")
def list_customers(status: Optional[str] = None, segment: Optional[str] = None,
                   tenant_id: Optional[int] = None, db: Session = Depends(get_db),
                   _u=Depends(require_permission("ent.success.view"))):
    return {"customers": success_svc.list_customers(db, status=status, segment=segment,
                                                   tenant_id=_tenant(tenant_id))}


@success_router.post("")
def create_customer(body: CustomerCreate, tenant_id: Optional[int] = None, db: Session = Depends(get_db),
                    _u=Depends(require_permission("ent.success.manage"))):
    try:
        return success_svc.create_customer(db, name=body.name, segment=body.segment, tier=body.tier,
                                           arr=body.arr, csm=body.csm, renewal_date=body.renewal_date,
                                           tenant_id=_tenant(tenant_id))
    except ValueError as e:
        _bad(e)


@success_router.post("/events")
def record_customer_event(body: CustomerEventRecord, tenant_id: Optional[int] = None,
                          db: Session = Depends(get_db), _u=Depends(require_permission("ent.success.manage"))):
    try:
        return success_svc.record_event(db, customer_id=body.customer_id, event_type=body.event_type,
                                        title=body.title, status=body.status, impact=body.impact,
                                        detail=body.detail, tenant_id=_tenant(tenant_id))
    except ValueError as e:
        _bad(e)


@success_router.post("/onboarding/advance")
def advance_onboarding(body: OnboardingAdvance, db: Session = Depends(get_db),
                       _u=Depends(require_permission("ent.success.manage"))):
    try:
        return success_svc.advance_onboarding(db, customer_id=body.customer_id, stage=body.stage)
    except ValueError as e:
        _bad(e)


@success_router.get("/{customer_id}")
def get_customer(customer_id: int, db: Session = Depends(get_db),
                 _u=Depends(require_permission("ent.success.view"))):
    out = success_svc.get_customer(db, customer_id)
    if not out:
        raise HTTPException(status_code=404, detail="customer not found")
    return out


@success_router.get("/{customer_id}/recommendations")
def customer_recommendations(customer_id: int, db: Session = Depends(get_db),
                             _u=Depends(require_permission("ent.success.view"))):
    try:
        return success_svc.recommendations(db, customer_id=customer_id)
    except ValueError as e:
        _bad(e)


# ===========================================================================
# M10 — Enterprise Deployment Platform
# ===========================================================================
deployment_router = APIRouter(prefix="/api/ent/deployment", tags=["ENT: Deployment"])


@deployment_router.get("/environments")
def list_environments(tenant_id: Optional[int] = None, db: Session = Depends(get_db),
                      _u=Depends(require_permission("ent.deploy.view"))):
    return {"environments": deploy_svc.list_environments(db, tenant_id=_tenant(tenant_id))}


@deployment_router.post("/environments")
def create_environment(body: EnvironmentCreate, tenant_id: Optional[int] = None,
                       db: Session = Depends(get_db), _u=Depends(require_permission("ent.deploy.manage"))):
    try:
        return deploy_svc.create_environment(db, name=body.name, env_type=body.env_type, config=body.config,
                                             tenant_id=_tenant(tenant_id))
    except ValueError as e:
        _bad(e)


@deployment_router.post("/environments/seed")
def seed_environments(tenant_id: Optional[int] = None, db: Session = Depends(get_db),
                      _u=Depends(require_permission("ent.deploy.manage"))):
    return deploy_svc.seed_environments(db, tenant_id=_tenant(tenant_id))


@deployment_router.post("/deploy")
def deploy(body: DeployRequest, tenant_id: Optional[int] = None, db: Session = Depends(get_db),
           user=Depends(get_current_user), _u=Depends(require_permission("ent.deploy.manage"))):
    try:
        return deploy_svc.deploy(db, environment_id=body.environment_id, version=body.version,
                                 strategy=body.strategy, canary_percent=body.canary_percent,
                                 release_notes=body.release_notes, tenant_id=_tenant(tenant_id),
                                 created_by=_uref(user))
    except ValueError as e:
        _bad(e)


@deployment_router.post("/rollback")
def rollback(body: RollbackRequest, tenant_id: Optional[int] = None, db: Session = Depends(get_db),
             user=Depends(get_current_user), _u=Depends(require_permission("ent.deploy.manage"))):
    try:
        return deploy_svc.rollback(db, environment_id=body.environment_id, to_version=body.to_version,
                                   tenant_id=_tenant(tenant_id), created_by=_uref(user))
    except ValueError as e:
        _bad(e)


@deployment_router.get("/history")
def deployment_history(environment_id: Optional[int] = None, tenant_id: Optional[int] = None,
                       db: Session = Depends(get_db), _u=Depends(require_permission("ent.deploy.view"))):
    return {"deployments": deploy_svc.list_deployments(db, environment_id=environment_id,
                                                      tenant_id=_tenant(tenant_id))}


@deployment_router.get("/versions")
def version_dashboard(tenant_id: Optional[int] = None, db: Session = Depends(get_db),
                      _u=Depends(require_permission("ent.deploy.view"))):
    return deploy_svc.version_dashboard(db, tenant_id=_tenant(tenant_id))


# ===========================================================================
# M11 — Enterprise Monitoring Platform
# ===========================================================================
monitoring_router = APIRouter(prefix="/api/ent/monitoring", tags=["ENT: Monitoring"])


@monitoring_router.post("/traces")
def record_trace(body: TraceRecord, tenant_id: Optional[int] = None, db: Session = Depends(get_db),
                 _u=Depends(require_permission("ent.monitoring.view"))):
    return monitoring_svc.record_trace(db, root_service=body.root_service, operation=body.operation,
                                       spans=body.spans, status=body.status, trace_id=body.trace_id,
                                       tenant_id=_tenant(tenant_id))


@monitoring_router.get("/traces")
def list_traces(root_service: Optional[str] = None, status: Optional[str] = None,
                tenant_id: Optional[int] = None, db: Session = Depends(get_db),
                _u=Depends(require_permission("ent.monitoring.view"))):
    return {"traces": monitoring_svc.list_traces(db, root_service=root_service, status=status,
                                               tenant_id=_tenant(tenant_id))}


@monitoring_router.get("/dependency-graph")
def dependency_graph(tenant_id: Optional[int] = None, db: Session = Depends(get_db),
                     _u=Depends(require_permission("ent.monitoring.view"))):
    return monitoring_svc.dependency_graph(db, tenant_id=_tenant(tenant_id))


@monitoring_router.get("/latency")
def latency_analysis(root_service: Optional[str] = None, tenant_id: Optional[int] = None,
                     db: Session = Depends(get_db), _u=Depends(require_permission("ent.monitoring.view"))):
    return monitoring_svc.latency_analysis(db, root_service=root_service, tenant_id=_tenant(tenant_id))


@monitoring_router.post("/sla")
def record_sla(body: SlaRecord, tenant_id: Optional[int] = None, db: Session = Depends(get_db),
               _u=Depends(require_permission("ent.monitoring.view"))):
    try:
        return monitoring_svc.record_sla(db, service=body.service, metric=body.metric, target=body.target,
                                         actual=body.actual, window=body.window, tenant_id=_tenant(tenant_id))
    except ValueError as e:
        _bad(e)


@monitoring_router.get("/sla")
def sla_dashboard(tenant_id: Optional[int] = None, db: Session = Depends(get_db),
                  _u=Depends(require_permission("ent.monitoring.view"))):
    return monitoring_svc.sla_dashboard(db, tenant_id=_tenant(tenant_id))


@monitoring_router.get("/cost")
def cost_monitoring(tenant_id: Optional[int] = None, db: Session = Depends(get_db),
                    _u=Depends(require_permission("ent.monitoring.view"))):
    return monitoring_svc.cost_monitoring(db, tenant_id=_tenant(tenant_id))


@monitoring_router.get("/capacity")
def capacity_planning(tenant_id: Optional[int] = None, db: Session = Depends(get_db),
                      _u=Depends(require_permission("ent.monitoring.view"))):
    return monitoring_svc.capacity_planning(db, tenant_id=_tenant(tenant_id))


@monitoring_router.get("/dashboard")
def monitoring_dashboard(tenant_id: Optional[int] = None, db: Session = Depends(get_db),
                         _u=Depends(require_permission("ent.monitoring.view"))):
    return monitoring_svc.executive_dashboard(db, tenant_id=_tenant(tenant_id))


# ===========================================================================
# M12 — Enterprise Business Intelligence Platform
# ===========================================================================
bi_router = APIRouter(prefix="/api/ent/bi", tags=["ENT: Business Intelligence"])


@bi_router.get("/categories")
def bi_categories(_u=Depends(require_permission("ent.bi.view"))):
    return {"categories": bi_svc.CATEGORIES}


@bi_router.get("/analytics")
def bi_analytics(category: str = "executive", tenant_id: Optional[int] = None,
                 db: Session = Depends(get_db), _u=Depends(require_permission("ent.bi.view"))):
    try:
        return bi_svc.analytics(db, category=category, tenant_id=_tenant(tenant_id))
    except ValueError as e:
        _bad(e)


@bi_router.get("/board-report")
def board_report(tenant_id: Optional[int] = None, db: Session = Depends(get_db),
                 _u=Depends(require_permission("ent.bi.view"))):
    return bi_svc.board_report(db, tenant_id=_tenant(tenant_id))


@bi_router.get("/dashboards")
def list_dashboards(category: Optional[str] = None, tenant_id: Optional[int] = None,
                    db: Session = Depends(get_db), _u=Depends(require_permission("ent.bi.view"))):
    return {"dashboards": bi_svc.list_dashboards(db, category=category, tenant_id=_tenant(tenant_id))}


@bi_router.post("/dashboards")
def save_dashboard(body: DashboardSave, tenant_id: Optional[int] = None, db: Session = Depends(get_db),
                   user=Depends(get_current_user), _u=Depends(require_permission("ent.bi.view"))):
    try:
        return bi_svc.save_dashboard(db, name=body.name, category=body.category, widgets=body.widgets,
                                     layout=body.layout, is_board_report=body.is_board_report, key=body.key,
                                     tenant_id=_tenant(tenant_id), created_by=_uref(user))
    except ValueError as e:
        _bad(e)


# ===========================================================================
# M13 — Enterprise Launch Readiness
# ===========================================================================
launch_router = APIRouter(prefix="/api/ent/launch", tags=["ENT: Launch Readiness"])


@launch_router.get("/checklist-types")
def checklist_types(_u=Depends(require_permission("ent.launch.view"))):
    return {"checklist_types": launch_svc.CHECKLIST_TYPES}


@launch_router.post("/generate")
def generate_checklist(body: ChecklistGenerate, tenant_id: Optional[int] = None,
                       db: Session = Depends(get_db), user=Depends(get_current_user),
                       _u=Depends(require_permission("ent.launch.manage"))):
    try:
        return launch_svc.generate(db, checklist_type=body.checklist_type, tenant_id=_tenant(tenant_id),
                                   created_by=_uref(user))
    except ValueError as e:
        _bad(e)


@launch_router.post("/generate-all")
def generate_all(tenant_id: Optional[int] = None, db: Session = Depends(get_db),
                 user=Depends(get_current_user), _u=Depends(require_permission("ent.launch.manage"))):
    return launch_svc.generate_all(db, tenant_id=_tenant(tenant_id), created_by=_uref(user))


@launch_router.post("/items/update")
def update_item(body: ChecklistItemUpdate, db: Session = Depends(get_db),
                _u=Depends(require_permission("ent.launch.manage"))):
    try:
        return launch_svc.update_item(db, checklist_id=body.checklist_id, item_key=body.item_key,
                                      status=body.status)
    except ValueError as e:
        _bad(e)


@launch_router.get("/checklists")
def list_checklists(checklist_type: Optional[str] = None, tenant_id: Optional[int] = None,
                    db: Session = Depends(get_db), _u=Depends(require_permission("ent.launch.view"))):
    return {"checklists": launch_svc.list_checklists(db, checklist_type=checklist_type,
                                                    tenant_id=_tenant(tenant_id))}


@launch_router.get("/readiness")
def readiness_summary(tenant_id: Optional[int] = None, db: Session = Depends(get_db),
                      _u=Depends(require_permission("ent.launch.view"))):
    return launch_svc.readiness_summary(db, tenant_id=_tenant(tenant_id))


# ===========================================================================
# ROUTERS — mounted in main.py.
# ===========================================================================
ROUTERS = [
    ux_router,
    workspaces_router,
    developer_router,
    marketplace_router,
    integration_router,
    data_router,
    operations_router,
    security_router,
    success_router,
    deployment_router,
    monitoring_router,
    bi_router,
    launch_router,
]
