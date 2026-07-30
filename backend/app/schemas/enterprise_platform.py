"""Inbound Pydantic schemas for the Enterprise Platform APIs (Track 4).

Request bodies only — responses are plain JSON dicts assembled by the services
(mirroring the Phase 9/10 / Tracks 2-3 convention). Grouped by milestone.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# --- M1 UX ----------------------------------------------------------------
class PreferencesUpdate(BaseModel):
    theme: Optional[str] = None
    density: Optional[str] = None
    accent: Optional[str] = None
    sidebar_collapsed: Optional[bool] = None
    shortcuts_enabled: Optional[bool] = None
    settings: Optional[Dict[str, Any]] = None


class LayoutSave(BaseModel):
    name: str
    config: Dict[str, Any] = Field(default_factory=dict)
    surface: Optional[str] = None
    scope: str = "personal"
    is_default: bool = False
    key: Optional[str] = None


# --- M2 Workspaces --------------------------------------------------------
class WorkspaceCreate(BaseModel):
    name: str
    workspace_type: str = "personal"
    description: Optional[str] = None
    owner_ref: Optional[str] = None
    settings: Dict[str, Any] = Field(default_factory=dict)
    key: Optional[str] = None


class WorkspaceMemberAdd(BaseModel):
    workspace_id: int
    user_ref: str
    role: str = "member"


class WorkspaceItemAdd(BaseModel):
    workspace_id: int
    item_type: str
    title: str
    ref: Optional[str] = None
    payload: Dict[str, Any] = Field(default_factory=dict)


# --- M3 Developer ---------------------------------------------------------
class ApiKeyCreate(BaseModel):
    name: str
    scopes: Optional[List[str]] = None
    environment: str = "sandbox"
    rate_limit_per_min: int = 600


class WebhookCreate(BaseModel):
    url: str
    events: List[str]
    description: Optional[str] = None


class WebhookTest(BaseModel):
    webhook_id: int
    event: Optional[str] = None
    payload: Optional[Dict[str, Any]] = None
    simulate_status: int = 200


class SandboxRequest(BaseModel):
    method: str = "GET"
    path: str
    body: Optional[Dict[str, Any]] = None
    api_key_prefix: Optional[str] = None


class RateLimitTest(BaseModel):
    api_key_id: int
    requests: int = 100


# --- M4 Marketplace -------------------------------------------------------
class PluginPublish(BaseModel):
    key: str
    name: str
    version: str = "0.1.0"
    publisher: Optional[str] = None
    category: str = "integration"
    permissions: Optional[List[str]] = None
    dependencies: Optional[List[str]] = None
    compatibility: Optional[Dict[str, Any]] = None
    billing_model: str = "free"
    description: Optional[str] = None


class PluginVersionAdd(BaseModel):
    plugin_id: int
    version: str
    changelog: Optional[str] = None
    manifest: Optional[Dict[str, Any]] = None


class PluginReview(BaseModel):
    version_id: int
    approve: bool = True


# --- M5 Integration -------------------------------------------------------
class PipelineSave(BaseModel):
    name: str
    graph: Dict[str, Any]
    key: Optional[str] = None
    description: Optional[str] = None
    schedule: Optional[str] = None
    retry_policy: Optional[Dict[str, Any]] = None


class PipelineRun(BaseModel):
    pipeline_id: int
    sample_input: Optional[Dict[str, Any]] = None
    trigger: str = "manual"


# --- M6 Data Management ---------------------------------------------------
class GoldenUpsert(BaseModel):
    entity_type: str
    natural_key: str
    record: Dict[str, Any]
    source: str = "manual"
    steward: Optional[str] = None


class DuplicateScan(BaseModel):
    entity_type: str
    threshold: float = 0.85
    field: str = "name"


class MergeRecords(BaseModel):
    survivor_id: int
    duplicate_id: int


class EntityResolve(BaseModel):
    entity_type: str
    record: Dict[str, Any]
    field: str = "name"
    threshold: float = 0.85


class DataRuleCreate(BaseModel):
    name: str
    dimension: str = "completeness"
    entity_type: Optional[str] = None
    field: Optional[str] = None
    expression: Optional[Dict[str, Any]] = None
    severity: str = "warning"


class BulkImport(BaseModel):
    entity_type: str
    records: List[Dict[str, Any]]
    key_field: str = "id"
    dedupe: bool = True


# --- M7 Operations --------------------------------------------------------
class IncidentOpen(BaseModel):
    title: str
    component: str
    severity: str = "sev3"
    summary: Optional[str] = None
    runbook_key: Optional[str] = None


class IncidentUpdate(BaseModel):
    incident_id: int
    status: Optional[str] = None
    note: Optional[str] = None
    root_cause: Optional[str] = None


class RunbookCreate(BaseModel):
    title: str
    steps: List[Dict[str, Any]]
    key: Optional[str] = None
    category: str = "operations"
    trigger: Optional[str] = None
    severity: Optional[str] = None


# --- M8 Security ----------------------------------------------------------
class SecurityEventRecord(BaseModel):
    event_type: str
    subject_ref: Optional[str] = None
    severity: str = "low"
    source_ip: Optional[str] = None
    detail: Optional[Dict[str, Any]] = None


class SessionAnalyze(BaseModel):
    subject_ref: str
    source_ip: Optional[str] = None
    failed_logins: int = 0
    new_device: bool = False
    impossible_travel: bool = False
    off_hours: bool = False


class EscalationCheck(BaseModel):
    subject_ref: str
    granted_permissions: List[str]
    sensitive: Optional[List[str]] = None


class AccessReviewStart(BaseModel):
    scope: str
    reviewer: Optional[str] = None


class AccessReviewComplete(BaseModel):
    review_id: int
    decision: str = "approved"
    summary: Optional[str] = None


# --- M9 Customer Success --------------------------------------------------
class CustomerCreate(BaseModel):
    name: str
    segment: str = "enterprise"
    tier: str = "standard"
    arr: float = 0.0
    csm: Optional[str] = None
    renewal_date: Optional[str] = None


class CustomerEventRecord(BaseModel):
    customer_id: int
    event_type: str
    title: str
    status: str = "open"
    impact: Optional[float] = None
    detail: Optional[Dict[str, Any]] = None


class OnboardingAdvance(BaseModel):
    customer_id: int
    stage: Optional[str] = None


# --- M10 Deployment -------------------------------------------------------
class EnvironmentCreate(BaseModel):
    name: str
    env_type: str = "development"
    config: Optional[Dict[str, Any]] = None


class DeployRequest(BaseModel):
    environment_id: int
    version: str
    strategy: str = "rolling"
    canary_percent: Optional[int] = None
    release_notes: Optional[str] = None


class RollbackRequest(BaseModel):
    environment_id: int
    to_version: Optional[str] = None


# --- M11 Monitoring -------------------------------------------------------
class TraceRecord(BaseModel):
    root_service: str
    operation: str
    spans: List[Dict[str, Any]]
    status: str = "ok"
    trace_id: Optional[str] = None


class SlaRecord(BaseModel):
    service: str
    metric: str = "availability"
    target: float = 0.999
    actual: float = 0.999
    window: str = "30d"


# --- M12 BI ---------------------------------------------------------------
class DashboardSave(BaseModel):
    name: str
    category: str
    widgets: List[Dict[str, Any]]
    layout: Optional[Dict[str, Any]] = None
    is_board_report: bool = False
    key: Optional[str] = None


# --- M13 Launch -----------------------------------------------------------
class ChecklistGenerate(BaseModel):
    checklist_type: str


class ChecklistItemUpdate(BaseModel):
    checklist_id: int
    item_key: str
    status: str = "done"
