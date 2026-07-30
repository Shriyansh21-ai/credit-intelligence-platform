"""Enterprise Productization & Commercial Readiness persistence (Track 4).

Every table here is **additive** — nothing from Phases 1-11 / Tracks 1-3 is
altered or dropped. Schema is created by the Alembic migration
``b2c3d4e5f6a7_enterprise_platform_track4`` (the app never calls ``create_all``
at import time).

Rows reference domain objects by stable string refs (``user_ref``, ``tenant_id``,
``subject_ref``) to stay loosely coupled. Multi-tenancy is preserved by an
optional nullable ``tenant_id`` column so legacy single-tenant flows keep working.

Table groups (all prefixed ``ent_``):
    M1  UX            — ent_user_preferences, ent_saved_layouts
    M2  Workspaces    — ent_workspaces, ent_workspace_members, ent_workspace_items
    M3  Developer     — ent_api_keys, ent_webhooks, ent_webhook_deliveries, ent_api_requests
    M4  Marketplace   — ent_plugins, ent_plugin_versions, ent_plugin_installs
    M5  Integration   — ent_pipelines, ent_pipeline_runs
    M6  Data Mgmt     — ent_mdm_records, ent_data_rules, ent_data_jobs
    M7  Operations    — ent_ops_incidents, ent_runbooks
    M8  Security      — ent_security_events, ent_access_reviews
    M9  Cust. Success — ent_customers, ent_customer_events
    M10 Deployment    — ent_environments, ent_deployments
    M11 Monitoring    — ent_traces, ent_sla_records
    M12 BI            — ent_bi_dashboards
    M13 Launch        — ent_checklists
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean, Column, DateTime, Float, ForeignKey, Integer, JSON, String, Text,
    UniqueConstraint,
)

from backend.app.db.database import Base


# ===========================================================================
# M1 — Enterprise UX Platform (personalization persistence)
# ===========================================================================
class EntUserPreference(Base):
    __tablename__ = "ent_user_preferences"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, nullable=True, index=True)
    user_ref = Column(String, nullable=False, index=True)
    theme = Column(String, nullable=False, default="system")  # light|dark|system
    density = Column(String, nullable=False, default="comfortable")
    accent = Column(String, nullable=True)
    sidebar_collapsed = Column(Boolean, nullable=False, default=False)
    shortcuts_enabled = Column(Boolean, nullable=False, default=True)
    settings = Column(JSON, nullable=False, default=dict)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (UniqueConstraint("tenant_id", "user_ref", name="uq_ent_pref_user"),)


class EntSavedLayout(Base):
    __tablename__ = "ent_saved_layouts"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, nullable=True, index=True)
    user_ref = Column(String, nullable=False, index=True)
    key = Column(String, nullable=False, index=True)
    name = Column(String, nullable=False)
    scope = Column(String, nullable=False, default="personal")  # personal|shared
    surface = Column(String, nullable=True)  # which page/route the layout applies to
    config = Column(JSON, nullable=False, default=dict)  # panels/splits/docked state
    is_default = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)


# ===========================================================================
# M2 — Enterprise Workspace Platform
# ===========================================================================
class EntWorkspace(Base):
    __tablename__ = "ent_workspaces"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, nullable=True, index=True)
    key = Column(String, nullable=False, index=True)
    name = Column(String, nullable=False)
    workspace_type = Column(String, nullable=False, default="personal")  # personal|team|department|organization|shared
    description = Column(Text, nullable=True)
    owner_ref = Column(String, nullable=True)
    settings = Column(JSON, nullable=False, default=dict)
    created_by = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (UniqueConstraint("tenant_id", "key", name="uq_ent_workspace_key"),)


class EntWorkspaceMember(Base):
    __tablename__ = "ent_workspace_members"

    id = Column(Integer, primary_key=True, index=True)
    workspace_id = Column(Integer, ForeignKey("ent_workspaces.id"), nullable=False, index=True)
    user_ref = Column(String, nullable=False, index=True)
    role = Column(String, nullable=False, default="member")  # owner|admin|member|viewer
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (UniqueConstraint("workspace_id", "user_ref", name="uq_ent_ws_member"),)


class EntWorkspaceItem(Base):
    __tablename__ = "ent_workspace_items"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, nullable=True, index=True)
    workspace_id = Column(Integer, ForeignKey("ent_workspaces.id"), nullable=False, index=True)
    item_type = Column(String, nullable=False, index=True)  # pinned_dashboard|saved_report|shared_view|collection|bookmark|template
    title = Column(String, nullable=False)
    ref = Column(String, nullable=True)   # route/href/report id
    payload = Column(JSON, nullable=False, default=dict)
    created_by = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


# ===========================================================================
# M3 — Enterprise Developer Platform
# ===========================================================================
class EntApiKey(Base):
    __tablename__ = "ent_api_keys"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, nullable=True, index=True)
    name = Column(String, nullable=False)
    prefix = Column(String, nullable=False, index=True)   # display prefix only
    key_hash = Column(String, nullable=False)             # sha256 of the full secret
    scopes = Column(JSON, nullable=False, default=list)
    rate_limit_per_min = Column(Integer, nullable=False, default=600)
    environment = Column(String, nullable=False, default="sandbox")  # sandbox|production
    status = Column(String, nullable=False, default="active")        # active|revoked
    last_used_at = Column(DateTime, nullable=True)
    created_by = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class EntWebhook(Base):
    __tablename__ = "ent_webhooks"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, nullable=True, index=True)
    url = Column(String, nullable=False)
    events = Column(JSON, nullable=False, default=list)
    signing_secret = Column(String, nullable=False)
    status = Column(String, nullable=False, default="active")  # active|paused
    description = Column(String, nullable=True)
    created_by = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class EntWebhookDelivery(Base):
    __tablename__ = "ent_webhook_deliveries"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, nullable=True, index=True)
    webhook_id = Column(Integer, ForeignKey("ent_webhooks.id"), nullable=False, index=True)
    event = Column(String, nullable=False, index=True)
    payload = Column(JSON, nullable=False, default=dict)
    status = Column(String, nullable=False, default="pending")  # pending|delivered|failed
    status_code = Column(Integer, nullable=True)
    attempts = Column(Integer, nullable=False, default=0)
    signature = Column(String, nullable=True)
    is_replay = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class EntApiRequest(Base):
    __tablename__ = "ent_api_requests"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, nullable=True, index=True)
    method = Column(String, nullable=False)
    path = Column(String, nullable=False, index=True)
    status_code = Column(Integer, nullable=False, default=200)
    latency_ms = Column(Float, nullable=False, default=0.0)
    api_key_prefix = Column(String, nullable=True, index=True)
    environment = Column(String, nullable=False, default="sandbox")
    request_body = Column(JSON, nullable=True)
    response_body = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


# ===========================================================================
# M4 — Enterprise Plugin Marketplace
# ===========================================================================
class EntPlugin(Base):
    __tablename__ = "ent_plugins"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, nullable=True, index=True)
    key = Column(String, nullable=False, index=True)
    name = Column(String, nullable=False)
    publisher = Column(String, nullable=True)
    category = Column(String, nullable=False, default="integration")
    latest_version = Column(String, nullable=False, default="0.1.0")
    status = Column(String, nullable=False, default="draft")  # draft|submitted|approved|published|suspended
    permissions = Column(JSON, nullable=False, default=list)
    dependencies = Column(JSON, nullable=False, default=list)
    compatibility = Column(JSON, nullable=False, default=dict)  # min/max platform version
    health = Column(String, nullable=False, default="unknown")
    install_count = Column(Integer, nullable=False, default=0)
    billing_model = Column(String, nullable=False, default="free")  # free|subscription|usage
    description = Column(Text, nullable=True)
    created_by = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (UniqueConstraint("tenant_id", "key", name="uq_ent_plugin_key"),)


class EntPluginVersion(Base):
    __tablename__ = "ent_plugin_versions"

    id = Column(Integer, primary_key=True, index=True)
    plugin_id = Column(Integer, ForeignKey("ent_plugins.id"), nullable=False, index=True)
    version = Column(String, nullable=False)
    status = Column(String, nullable=False, default="submitted")  # submitted|approved|rejected|published
    changelog = Column(Text, nullable=True)
    manifest = Column(JSON, nullable=False, default=dict)
    approved_by = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class EntPluginInstall(Base):
    __tablename__ = "ent_plugin_installs"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, nullable=True, index=True)
    plugin_id = Column(Integer, ForeignKey("ent_plugins.id"), nullable=False, index=True)
    version = Column(String, nullable=True)
    status = Column(String, nullable=False, default="active")  # active|disabled|uninstalled
    installed_by = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


# ===========================================================================
# M5 — Enterprise Integration Studio
# ===========================================================================
class EntPipeline(Base):
    __tablename__ = "ent_pipelines"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, nullable=True, index=True)
    key = Column(String, nullable=False, index=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    graph = Column(JSON, nullable=False, default=dict)  # {nodes:[], edges:[]}
    schedule = Column(String, nullable=True)            # cron-like or interval
    retry_policy = Column(JSON, nullable=False, default=dict)
    status = Column(String, nullable=False, default="draft")  # draft|active|paused
    version = Column(Integer, nullable=False, default=1)
    created_by = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (UniqueConstraint("tenant_id", "key", name="uq_ent_pipeline_key"),)


class EntPipelineRun(Base):
    __tablename__ = "ent_pipeline_runs"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, nullable=True, index=True)
    pipeline_id = Column(Integer, ForeignKey("ent_pipelines.id"), nullable=False, index=True)
    status = Column(String, nullable=False, default="succeeded")  # succeeded|failed|running
    trigger = Column(String, nullable=False, default="manual")    # manual|schedule|event
    node_results = Column(JSON, nullable=False, default=list)
    logs = Column(JSON, nullable=False, default=list)
    metrics = Column(JSON, nullable=False, default=dict)
    duration_ms = Column(Float, nullable=False, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)


# ===========================================================================
# M6 — Enterprise Data Management (MDM)
# ===========================================================================
class EntMdmRecord(Base):
    __tablename__ = "ent_mdm_records"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, nullable=True, index=True)
    entity_type = Column(String, nullable=False, index=True)  # customer|counterparty|vendor|instrument
    natural_key = Column(String, nullable=False, index=True)
    golden_record = Column(JSON, nullable=False, default=dict)
    source_records = Column(JSON, nullable=False, default=list)
    resolution_confidence = Column(Float, nullable=False, default=1.0)
    quality_score = Column(Float, nullable=True)
    is_duplicate_of = Column(Integer, nullable=True, index=True)
    steward = Column(String, nullable=True)
    status = Column(String, nullable=False, default="active")  # active|merged|quarantined
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class EntDataRule(Base):
    __tablename__ = "ent_data_rules"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, nullable=True, index=True)
    name = Column(String, nullable=False)
    entity_type = Column(String, nullable=True, index=True)
    dimension = Column(String, nullable=False, default="completeness")  # completeness|validity|uniqueness|consistency|accuracy
    field = Column(String, nullable=True)
    expression = Column(JSON, nullable=False, default=dict)  # {op, value, ...}
    severity = Column(String, nullable=False, default="warning")
    enabled = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class EntDataJob(Base):
    __tablename__ = "ent_data_jobs"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, nullable=True, index=True)
    job_type = Column(String, nullable=False, index=True)  # import|export|dq_scan|dedup|entity_resolution
    entity_type = Column(String, nullable=True)
    status = Column(String, nullable=False, default="completed")
    summary = Column(JSON, nullable=False, default=dict)
    created_by = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


# ===========================================================================
# M7 — Enterprise Operations Center
# ===========================================================================
class EntOpsIncident(Base):
    __tablename__ = "ent_ops_incidents"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, nullable=True, index=True)
    title = Column(String, nullable=False)
    component = Column(String, nullable=False, index=True)  # platform|ai|ml|connectors|storage|queues|jobs|tenant
    severity = Column(String, nullable=False, default="sev3")  # sev1|sev2|sev3|sev4
    status = Column(String, nullable=False, default="open")    # open|investigating|mitigated|resolved
    summary = Column(Text, nullable=True)
    timeline = Column(JSON, nullable=False, default=list)
    root_cause = Column(Text, nullable=True)
    runbook_key = Column(String, nullable=True)
    created_by = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)


class EntRunbook(Base):
    __tablename__ = "ent_runbooks"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, nullable=True, index=True)
    key = Column(String, nullable=False, index=True)
    title = Column(String, nullable=False)
    category = Column(String, nullable=False, default="operations")
    trigger = Column(Text, nullable=True)
    steps = Column(JSON, nullable=False, default=list)
    severity = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (UniqueConstraint("tenant_id", "key", name="uq_ent_runbook_key"),)


# ===========================================================================
# M8 — Enterprise Security Center
# ===========================================================================
class EntSecurityEvent(Base):
    __tablename__ = "ent_security_events"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, nullable=True, index=True)
    event_type = Column(String, nullable=False, index=True)  # session|threat|anomaly|escalation|device|access
    subject_ref = Column(String, nullable=True, index=True)
    severity = Column(String, nullable=False, default="low")  # low|medium|high|critical
    risk_score = Column(Float, nullable=False, default=0.0)
    source_ip = Column(String, nullable=True)
    detail = Column(JSON, nullable=False, default=dict)
    status = Column(String, nullable=False, default="open")  # open|reviewed|dismissed
    created_at = Column(DateTime, default=datetime.utcnow)


class EntAccessReview(Base):
    __tablename__ = "ent_access_reviews"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, nullable=True, index=True)
    scope = Column(String, nullable=False)  # role:x|user:y|tenant
    reviewer = Column(String, nullable=True)
    status = Column(String, nullable=False, default="pending")  # pending|approved|revoked|completed
    findings = Column(JSON, nullable=False, default=list)
    summary = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)


# ===========================================================================
# M9 — Enterprise Customer Success Platform
# ===========================================================================
class EntCustomer(Base):
    __tablename__ = "ent_customers"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, nullable=True, index=True)
    name = Column(String, nullable=False)
    segment = Column(String, nullable=False, default="enterprise")  # enterprise|mid_market|smb
    tier = Column(String, nullable=False, default="standard")       # standard|premium|strategic
    status = Column(String, nullable=False, default="onboarding")   # prospect|onboarding|live|at_risk|churned
    health_score = Column(Float, nullable=False, default=70.0)
    arr = Column(Float, nullable=False, default=0.0)
    adoption_score = Column(Float, nullable=False, default=0.0)
    onboarding_stage = Column(String, nullable=True)
    renewal_date = Column(String, nullable=True)
    csm = Column(String, nullable=True)
    meta = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class EntCustomerEvent(Base):
    __tablename__ = "ent_customer_events"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, nullable=True, index=True)
    customer_id = Column(Integer, ForeignKey("ent_customers.id"), nullable=False, index=True)
    event_type = Column(String, nullable=False, index=True)  # onboarding|milestone|ticket|training|adoption|renewal|qbr
    title = Column(String, nullable=False)
    status = Column(String, nullable=False, default="open")
    impact = Column(Float, nullable=True)
    detail = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)


# ===========================================================================
# M10 — Enterprise Deployment Platform
# ===========================================================================
class EntEnvironment(Base):
    __tablename__ = "ent_environments"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, nullable=True, index=True)
    name = Column(String, nullable=False, index=True)
    env_type = Column(String, nullable=False, default="development")  # development|testing|staging|production
    status = Column(String, nullable=False, default="healthy")
    current_version = Column(String, nullable=True)
    config = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (UniqueConstraint("tenant_id", "name", name="uq_ent_env_name"),)


class EntDeployment(Base):
    __tablename__ = "ent_deployments"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, nullable=True, index=True)
    environment_id = Column(Integer, ForeignKey("ent_environments.id"), nullable=False, index=True)
    version = Column(String, nullable=False)
    strategy = Column(String, nullable=False, default="rolling")  # rolling|blue_green|canary|recreate
    status = Column(String, nullable=False, default="succeeded")  # pending|in_progress|succeeded|failed|rolled_back
    canary_percent = Column(Integer, nullable=True)
    release_notes = Column(Text, nullable=True)
    rolled_back_from = Column(String, nullable=True)
    steps = Column(JSON, nullable=False, default=list)
    created_by = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


# ===========================================================================
# M11 — Enterprise Monitoring Platform
# ===========================================================================
class EntTrace(Base):
    __tablename__ = "ent_traces"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, nullable=True, index=True)
    trace_id = Column(String, nullable=False, index=True)
    root_service = Column(String, nullable=False, index=True)
    operation = Column(String, nullable=False)
    duration_ms = Column(Float, nullable=False, default=0.0)
    status = Column(String, nullable=False, default="ok")  # ok|error
    spans = Column(JSON, nullable=False, default=list)     # [{service, op, duration_ms, parent}]
    created_at = Column(DateTime, default=datetime.utcnow)


class EntSlaRecord(Base):
    __tablename__ = "ent_sla_records"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, nullable=True, index=True)
    service = Column(String, nullable=False, index=True)
    metric = Column(String, nullable=False, default="availability")  # availability|latency|error_rate
    target = Column(Float, nullable=False, default=0.999)
    actual = Column(Float, nullable=False, default=0.999)
    window = Column(String, nullable=False, default="30d")
    breached = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)


# ===========================================================================
# M12 — Enterprise Business Intelligence Platform
# ===========================================================================
class EntBiDashboard(Base):
    __tablename__ = "ent_bi_dashboards"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, nullable=True, index=True)
    key = Column(String, nullable=False, index=True)
    name = Column(String, nullable=False)
    category = Column(String, nullable=False, default="executive")  # revenue|product|customer|risk|ai|operational|financial|growth|executive
    widgets = Column(JSON, nullable=False, default=list)
    layout = Column(JSON, nullable=False, default=dict)
    is_board_report = Column(Boolean, nullable=False, default=False)
    created_by = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (UniqueConstraint("tenant_id", "key", name="uq_ent_bi_key"),)


# ===========================================================================
# M13 — Enterprise Launch Readiness
# ===========================================================================
class EntChecklist(Base):
    __tablename__ = "ent_checklists"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, nullable=True, index=True)
    checklist_type = Column(String, nullable=False, index=True)  # production|security|operational|release|dr|bcp|scaling|performance|monitoring
    title = Column(String, nullable=False)
    items = Column(JSON, nullable=False, default=list)  # [{key, label, status, category}]
    completed = Column(Integer, nullable=False, default=0)
    total = Column(Integer, nullable=False, default=0)
    readiness_score = Column(Float, nullable=False, default=0.0)
    status = Column(String, nullable=False, default="in_progress")
    created_by = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
