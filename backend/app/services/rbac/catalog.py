"""Canonical RBAC catalog — the single source of truth for seed data.

This module contains **pure data only** (no ORM/SQLAlchemy imports) so it can be
imported safely from Alembic migrations, the runtime bootstrap, and tests alike.

Permissions are fine-grained and grouped by ``category``. Roles map to a set of
permission codes; the sentinel ``"*"`` grants every permission (Administrator).

Changing this catalog and running ``sync_rbac`` (or a fresh migration) keeps the
database in step — no permission is ever hardcoded in route logic.
"""

from __future__ import annotations

from typing import Dict, List, Tuple

# ---------------------------------------------------------------------------
# Permissions: (code, category, description)
# ---------------------------------------------------------------------------

PERMISSIONS: List[Tuple[str, str, str]] = [
    # Applications / lifecycle
    ("applications.view", "Applications", "View credit applications"),
    ("applications.create", "Applications", "Create new credit applications"),
    ("applications.edit", "Applications", "Edit application details"),
    ("applications.submit", "Applications", "Submit an application into the workflow"),
    ("applications.transition", "Applications", "Move an application between lifecycle states"),
    ("applications.rollback", "Applications", "Roll a lifecycle transition back"),
    ("applications.cancel", "Applications", "Cancel an application"),
    # Approvals / workflow
    ("approvals.view", "Approvals", "View approval workflow and timeline"),
    ("approvals.approve", "Approvals", "Approve at an assigned stage"),
    ("approvals.reject", "Approvals", "Reject at an assigned stage"),
    ("approvals.request_changes", "Approvals", "Request changes at a stage"),
    ("approvals.escalate", "Approvals", "Escalate to a higher stage"),
    ("approvals.hold", "Approvals", "Place an approval on hold"),
    ("approvals.override", "Approvals", "Administrative override of the workflow"),
    ("approvals.configure", "Approvals", "Configure approval workflows / matrix"),
    # Documents
    ("documents.view", "Documents", "View uploaded documents"),
    ("documents.upload", "Documents", "Upload documents"),
    ("documents.delete", "Documents", "Delete documents"),
    # Financial analysis & ML
    ("analysis.run", "Analysis", "Run financial analysis"),
    ("ml.predict", "Analysis", "Run AI risk predictions"),
    ("ml.explain", "Analysis", "View AI explanations"),
    ("stress.run", "Analysis", "Run stress tests and scenarios"),
    ("models.configure", "Analysis", "Configure risk models"),
    # Portfolio
    ("portfolio.view", "Portfolio", "View the portfolio"),
    # Covenants
    ("covenants.view", "Covenants", "View loan covenants"),
    ("covenants.manage", "Covenants", "Create and manage covenants"),
    # Monitoring
    ("monitoring.view", "Monitoring", "View post-disbursement monitoring"),
    ("monitoring.manage", "Monitoring", "Manage monitoring records and alerts"),
    # Tasks
    ("tasks.view", "Tasks", "View tasks"),
    ("tasks.manage", "Tasks", "Create, assign and complete tasks"),
    # Collaboration
    ("collaboration.view", "Collaboration", "View notes and comments"),
    ("collaboration.participate", "Collaboration", "Post notes, comments and mentions"),
    # Reports
    ("reports.view", "Reports", "View generated reports"),
    ("reports.export", "Reports", "Export reports (PDF / Excel / Word)"),
    # Notifications
    ("notifications.view", "Notifications", "View own notifications"),
    # Search
    ("search.use", "Search", "Use enterprise-wide search"),
    # Machine Learning platform (Phase 6)
    ("mlops.view", "Machine Learning", "View ML models, training, monitoring and dashboards"),
    ("mlops.train", "Machine Learning", "Train and register ML models"),
    ("mlops.deploy", "Machine Learning", "Approve, promote, roll back and retrain models"),
    ("mlops.predict", "Machine Learning", "Run ML inference (serving)"),
    ("mlops.fraud", "Machine Learning", "Run ML fraud and anomaly scoring"),
    # Banking Ecosystem Integration Platform (Phase 7)
    ("integrations.view", "Integrations", "View connectors, snapshots, imports and observability"),
    ("integrations.manage", "Integrations", "Configure connectors and trigger data imports"),
    ("integrations.sync", "Integrations", "Run and manage portfolio synchronization jobs"),
    ("collateral.view", "Integrations", "View collateral records and coverage"),
    ("collateral.manage", "Integrations", "Create, revalue and inspect collateral"),
    ("customer360.view", "Integrations", "View the unified Customer 360 profile"),
    ("apiplatform.view", "Integrations", "View Open API keys, webhooks and usage"),
    ("apiplatform.manage", "Integrations", "Manage Open API keys and webhook subscriptions"),
    # Multi-Tenant Enterprise SaaS Platform (Phase 8)
    ("tenancy.view", "SaaS Platform", "View organizations, tenants and hierarchy"),
    ("tenancy.manage", "SaaS Platform", "Create/manage orgs, tenants, members and invitations"),
    ("branding.view", "SaaS Platform", "View white-label branding"),
    ("branding.manage", "SaaS Platform", "Manage white-label branding and custom domains"),
    ("billing.view", "SaaS Platform", "View subscriptions, usage and invoices"),
    ("billing.manage", "SaaS Platform", "Manage subscriptions, plans and invoicing"),
    ("flags.view", "SaaS Platform", "View feature flags"),
    ("flags.manage", "SaaS Platform", "Manage feature flags and overrides"),
    ("bgjobs.view", "SaaS Platform", "View the background job platform"),
    ("bgjobs.manage", "SaaS Platform", "Enqueue, cancel and replay background jobs"),
    ("storage.view", "SaaS Platform", "View cloud storage objects"),
    ("storage.manage", "SaaS Platform", "Upload, version and delete cloud storage objects"),
    ("realtime.view", "SaaS Platform", "Subscribe to real-time channels and activity"),
    ("observability.view", "SaaS Platform", "View tracing, metrics and health"),
    ("cache.manage", "SaaS Platform", "Manage and inspect the cache platform"),
    ("security.view", "SaaS Platform", "View sessions, devices and security config"),
    ("security.manage", "SaaS Platform", "Manage secrets, IP allow-lists, sessions and IdPs"),
    ("analytics.view", "SaaS Platform", "View SaaS analytics dashboards"),
    ("platform.admin", "SaaS Platform", "Full super-admin console across all tenants"),
    # Autonomous AI Banking Intelligence (Phase 9)
    ("intelligence.view", "Autonomous Intelligence", "View the AI knowledge graph, monitoring, EWS and alerts"),
    ("intelligence.manage", "Autonomous Intelligence", "Run monitoring, resolve alerts and manage the knowledge graph"),
    ("copilot.use", "Autonomous Intelligence", "Use the AI Credit Copilot and natural-language analytics"),
    ("simulation.run", "Autonomous Intelligence", "Run scenario simulations and stress tests"),
    ("portfolio.optimize", "Autonomous Intelligence", "Run portfolio optimization and capital allocation"),
    ("rm.workspace", "Autonomous Intelligence", "Use the Relationship Manager workspace"),
    ("command.center", "Autonomous Intelligence", "View the executive command center dashboards"),
    ("recommendations.view", "Autonomous Intelligence", "View AI recommendations and workflow actions"),
    ("recommendations.act", "Autonomous Intelligence", "Accept/reject recommendations and execute workflow actions"),
    ("governance.view", "Autonomous Intelligence", "View the model governance platform"),
    ("governance.manage", "Autonomous Intelligence", "Validate, approve and govern ML models"),
    ("datalake.view", "Autonomous Intelligence", "Query the enterprise data lake"),
    ("datalake.manage", "Autonomous Intelligence", "Ingest into and manage the enterprise data lake"),
    # Audit & compliance
    ("audit.view", "Audit", "View the audit log / dashboard"),
    # Administration
    ("users.manage", "Administration", "Manage users"),
    ("roles.manage", "Administration", "Manage roles and permissions"),
    ("config.view", "Administration", "View system configuration"),
    ("config.manage", "Administration", "Manage system configuration"),
]

ALL_PERMISSION_CODES: List[str] = [code for code, _cat, _desc in PERMISSIONS]

# ---------------------------------------------------------------------------
# Roles: (name, display_name, description)
# ---------------------------------------------------------------------------

ROLES: List[Tuple[str, str, str]] = [
    ("administrator", "Administrator", "Full platform access and configuration"),
    ("relationship_manager", "Relationship Manager", "Originates and manages client applications"),
    ("credit_analyst", "Credit Analyst", "Analyses applications and prepares assessments"),
    ("senior_analyst", "Senior Analyst", "Reviews analyst work and approves at senior stage"),
    ("risk_manager", "Risk Manager", "Owns risk policy, covenants and monitoring"),
    ("auditor", "Auditor", "Read-only access with full audit visibility"),
    ("compliance_officer", "Compliance Officer", "Compliance oversight and reporting"),
    ("viewer", "Viewer", "Read-only access to applications and portfolio"),
    ("platform_admin", "Platform Admin", "Super-admin of the multi-tenant SaaS platform (Phase 8)"),
]

# Phase 8 SaaS-platform permission codes, grouped for reuse below.
_SAAS_PLATFORM_PERMISSIONS: List[str] = [
    "tenancy.view", "tenancy.manage", "branding.view", "branding.manage",
    "billing.view", "billing.manage", "flags.view", "flags.manage",
    "bgjobs.view", "bgjobs.manage", "storage.view", "storage.manage",
    "realtime.view", "observability.view", "cache.manage",
    "security.view", "security.manage", "analytics.view", "platform.admin",
]

# ---------------------------------------------------------------------------
# Role -> permission codes. "*" means "all permissions".
# ---------------------------------------------------------------------------

ROLE_PERMISSIONS: Dict[str, List[str]] = {
    "administrator": ["*"],
    "relationship_manager": [
        "applications.view", "applications.create", "applications.edit",
        "applications.submit", "applications.cancel",
        "documents.view", "documents.upload",
        "portfolio.view", "analysis.run",
        "tasks.view", "tasks.manage",
        "collaboration.view", "collaboration.participate",
        "reports.view", "notifications.view", "search.use",
        "approvals.view",
    ],
    "credit_analyst": [
        "applications.view", "applications.edit",
        "documents.view", "documents.upload",
        "analysis.run", "ml.predict", "ml.explain",
        "approvals.view", "approvals.request_changes",
        "tasks.view", "tasks.manage",
        "collaboration.view", "collaboration.participate",
        "covenants.view", "monitoring.view",
        "reports.view", "notifications.view", "search.use",
        "portfolio.view",
        "mlops.view", "mlops.predict",
        "integrations.view", "collateral.view", "customer360.view",
    ],
    "senior_analyst": [
        "applications.view", "applications.edit", "applications.transition",
        "documents.view", "documents.upload",
        "analysis.run", "ml.predict", "ml.explain", "stress.run",
        "approvals.view", "approvals.approve", "approvals.reject",
        "approvals.request_changes", "approvals.escalate",
        "tasks.view", "tasks.manage",
        "collaboration.view", "collaboration.participate",
        "covenants.view", "monitoring.view",
        "reports.view", "reports.export",
        "notifications.view", "search.use", "portfolio.view",
        "mlops.view", "mlops.train", "mlops.predict", "mlops.fraud",
        "integrations.view", "integrations.manage",
        "collateral.view", "collateral.manage", "customer360.view",
    ],
    "risk_manager": [
        "applications.view", "applications.transition", "applications.rollback",
        "documents.view",
        "analysis.run", "ml.predict", "ml.explain", "stress.run", "models.configure",
        "approvals.view", "approvals.approve", "approvals.reject",
        "approvals.escalate", "approvals.hold", "approvals.configure",
        "portfolio.view",
        "covenants.view", "covenants.manage",
        "monitoring.view", "monitoring.manage",
        "tasks.view", "tasks.manage",
        "collaboration.view", "collaboration.participate",
        "reports.view", "reports.export",
        "notifications.view", "search.use",
        "mlops.view", "mlops.train", "mlops.deploy", "mlops.predict", "mlops.fraud",
        "integrations.view", "integrations.manage", "integrations.sync",
        "collateral.view", "collateral.manage", "customer360.view",
        "apiplatform.view", "apiplatform.manage",
    ],
    "auditor": [
        "applications.view", "approvals.view", "documents.view",
        "portfolio.view", "covenants.view", "monitoring.view",
        "audit.view", "reports.view", "reports.export",
        "collaboration.view",
        "notifications.view", "search.use",
        "mlops.view",
        "integrations.view", "collateral.view", "customer360.view", "apiplatform.view",
    ],
    "compliance_officer": [
        "applications.view", "approvals.view", "documents.view",
        "portfolio.view", "covenants.view", "monitoring.view",
        "audit.view", "config.view",
        "reports.view", "reports.export",
        "collaboration.view", "collaboration.participate",
        "notifications.view", "search.use",
        "mlops.view",
        "integrations.view", "collateral.view", "customer360.view", "apiplatform.view",
    ],
    "viewer": [
        "applications.view", "portfolio.view",
        "reports.view", "notifications.view", "search.use",
        "realtime.view",
    ],
    # Phase 8: dedicated super-admin of the SaaS platform. Holds every platform
    # permission but not the credit-workflow permissions (separation of duties).
    "platform_admin": list(_SAAS_PLATFORM_PERMISSIONS) + [
        "audit.view", "config.view", "config.manage", "users.manage", "roles.manage",
    ],
}

# Grant read-only platform visibility to the oversight roles.
for _role in ("risk_manager", "compliance_officer", "auditor"):
    ROLE_PERMISSIONS[_role].extend([
        "billing.view", "analytics.view", "observability.view", "tenancy.view",
        "flags.view", "realtime.view",
    ])
# Risk managers additionally operate the background-job + storage platforms.
ROLE_PERMISSIONS["risk_manager"].extend(["bgjobs.view", "storage.view", "branding.view"])

# ---------------------------------------------------------------------------
# Phase 9 — Autonomous AI Banking Intelligence grants.
# The "AI Brain" is broadly readable by the credit-workflow roles; running heavy
# engines (simulation, optimization, governance) is restricted by seniority.
# ---------------------------------------------------------------------------
_PHASE9_READ = [
    "intelligence.view", "copilot.use", "recommendations.view",
    "rm.workspace", "datalake.view",
]
for _role in ("relationship_manager", "credit_analyst", "senior_analyst",
              "risk_manager", "compliance_officer", "auditor"):
    ROLE_PERMISSIONS[_role].extend(_PHASE9_READ)

# Analysts and above can drive simulations and act on recommendations.
for _role in ("credit_analyst", "senior_analyst", "risk_manager"):
    ROLE_PERMISSIONS[_role].extend([
        "simulation.run", "recommendations.act", "command.center",
    ])
# Senior analysts + risk managers additionally manage intelligence + governance.
for _role in ("senior_analyst", "risk_manager"):
    ROLE_PERMISSIONS[_role].extend([
        "intelligence.manage", "portfolio.optimize", "governance.view",
    ])
# Risk managers own model governance + data-lake management.
ROLE_PERMISSIONS["risk_manager"].extend(["governance.manage", "datalake.manage"])
# Oversight roles see the command center and governance read-only.
for _role in ("compliance_officer", "auditor"):
    ROLE_PERMISSIONS[_role].extend(["command.center", "governance.view"])

# The role backfilled onto pre-existing users so nobody is locked out after the
# RBAC migration. Kept intentionally broad for continuity with single-tenant dev
# accounts; production onboarding should assign least-privilege roles explicitly.
DEFAULT_BACKFILL_ROLE = "administrator"

# The role granted to brand-new signups.
DEFAULT_SIGNUP_ROLE = "credit_analyst"


def resolved_role_permissions(role_name: str) -> List[str]:
    """Return the explicit permission codes for a role, expanding ``"*"``."""
    codes = ROLE_PERMISSIONS.get(role_name, [])
    if "*" in codes:
        return list(ALL_PERMISSION_CODES)
    return list(codes)
