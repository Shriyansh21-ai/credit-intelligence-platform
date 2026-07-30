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
    # Enterprise Banking Operating System (Phase 10)
    ("policy.view", "Banking OS", "View business policies, versions and evaluations"),
    ("policy.manage", "Banking OS", "Author, version, publish and archive business policies"),
    ("policy.evaluate", "Banking OS", "Execute policy evaluations in real time"),
    ("committee.view", "Banking OS", "View loan committees, meetings, agendas and decisions"),
    ("committee.participate", "Banking OS", "Attend meetings and cast committee votes"),
    ("committee.manage", "Banking OS", "Manage committees, meetings, agendas and minutes"),
    ("prompt.view", "Banking OS", "View prompt templates, versions and evaluations"),
    ("prompt.manage", "Banking OS", "Author, evaluate, approve and deploy prompts"),
    ("llm.view", "Banking OS", "View the multi-LLM provider registry and analytics"),
    ("llm.manage", "Banking OS", "Manage LLM providers and routing configuration"),
    ("fabric.view", "Banking OS", "View the enterprise data fabric catalog, lineage and quality"),
    ("fabric.manage", "Banking OS", "Manage datasets, data contracts and quality rules"),
    ("workflowstudio.view", "Banking OS", "View enterprise workflow designs and runs"),
    ("workflowstudio.manage", "Banking OS", "Design, version and execute enterprise workflows"),
    ("marketplace.view", "Banking OS", "View the AI recommendation marketplace"),
    ("marketplace.manage", "Banking OS", "Install and configure recommendation plugins"),
    # AI Intelligence Platform (Track 2)
    ("aip.rag.view", "AI Intelligence Platform", "View knowledge sources, documents and RAG queries"),
    ("aip.rag.query", "AI Intelligence Platform", "Run retrieval-augmented queries against knowledge"),
    ("aip.rag.manage", "AI Intelligence Platform", "Register sources, ingest and re-index documents"),
    ("aip.agents.run", "AI Intelligence Platform", "Run the multi-agent AI system"),
    ("aip.memory.view", "AI Intelligence Platform", "View long-term AI memory"),
    ("aip.memory.manage", "AI Intelligence Platform", "Write, summarise and forget AI memory"),
    ("aip.prompts.view", "AI Intelligence Platform", "View prompts, versions and experiments"),
    ("aip.prompts.manage", "AI Intelligence Platform", "Author, version, approve, deploy and A/B test prompts"),
    ("aip.eval.run", "AI Intelligence Platform", "Run AI evaluations and produce scorecards"),
    ("aip.investigate.run", "AI Intelligence Platform", "Run autonomous company investigations"),
    ("aip.reports.generate", "AI Intelligence Platform", "Generate AI enterprise reports"),
    ("aip.workflows.view", "AI Intelligence Platform", "View AI workflow designs and runs"),
    ("aip.workflows.manage", "AI Intelligence Platform", "Design, version and execute AI workflows"),
    ("aip.chat.use", "AI Intelligence Platform", "Use the enterprise conversational AI assistant"),
    ("aip.research.run", "AI Intelligence Platform", "Run the autonomous AI research assistant"),
    ("aip.learning.view", "AI Intelligence Platform", "View continuous-learning feedback and signals"),
    ("aip.learning.manage", "AI Intelligence Platform", "Manage feedback, learning signals and training events"),
    ("aip.governance.view", "AI Intelligence Platform", "View the AI asset governance registry and lineage"),
    ("aip.governance.manage", "AI Intelligence Platform", "Register, validate, approve and deploy AI assets"),
    ("aip.explain.view", "AI Intelligence Platform", "View explainability artifacts for AI decisions"),
    ("aip.monitoring.view", "AI Intelligence Platform", "View AI monitoring metrics and incidents"),
    ("aip.monitoring.manage", "AI Intelligence Platform", "Record AI metrics and manage AI incidents"),
    # Advanced Financial Intelligence Platform (Track 3)
    ("fin.treasury.view", "Financial Intelligence Platform", "View treasury positions, liquidity, ALM/LCR/NSFR and KPIs"),
    ("fin.treasury.manage", "Financial Intelligence Platform", "Manage funding sources and run treasury analytics/scenarios"),
    ("fin.portfolio.view", "Financial Intelligence Platform", "View portfolios, concentration, loss and RAROC analytics"),
    ("fin.portfolio.manage", "Financial Intelligence Platform", "Build portfolios and run optimization/simulation/migration"),
    ("fin.regulatory.view", "Financial Intelligence Platform", "View Basel III / IFRS 9 calculations and regulatory dashboards"),
    ("fin.regulatory.run", "Financial Intelligence Platform", "Run ECL, RWA, CAR, leverage and provisioning calculations"),
    ("fin.economic.view", "Financial Intelligence Platform", "View macroeconomic indicators and scenarios"),
    ("fin.economic.manage", "Financial Intelligence Platform", "Manage indicators and generate/propagate economic scenarios"),
    ("fin.esg.view", "Financial Intelligence Platform", "View ESG scores, climate risk and ESG portfolio analytics"),
    ("fin.esg.manage", "Financial Intelligence Platform", "Run ESG assessments and climate stress testing"),
    ("fin.market.view", "Financial Intelligence Platform", "View market data, curves, news and sentiment"),
    ("fin.market.manage", "Financial Intelligence Platform", "Ingest market instruments, quotes and news"),
    ("fin.altdata.view", "Financial Intelligence Platform", "View alternative-data signals and derived risk signals"),
    ("fin.altdata.manage", "Financial Intelligence Platform", "Ingest alternative data and derive risk signals"),
    ("fin.forecast.view", "Financial Intelligence Platform", "View enterprise forecasts"),
    ("fin.forecast.run", "Financial Intelligence Platform", "Run multi-horizon enterprise forecasts"),
    ("fin.quant.view", "Financial Intelligence Platform", "View quantitative risk simulations"),
    ("fin.quant.run", "Financial Intelligence Platform", "Run Monte Carlo, VaR, ES, stress and sensitivity models"),
    ("fin.benchmark.view", "Financial Intelligence Platform", "View corporate benchmarking and peer rankings"),
    ("fin.benchmark.run", "Financial Intelligence Platform", "Run corporate benchmarking and generate reports"),
    ("fin.exec.view", "Financial Intelligence Platform", "View executive intelligence dashboards"),
    ("fin.optimize.view", "Financial Intelligence Platform", "View decision-optimization results"),
    ("fin.optimize.run", "Financial Intelligence Platform", "Run decision optimization (pricing, limits, allocation, capital)"),
    ("fin.twin.view", "Financial Intelligence Platform", "View financial digital twins and simulations"),
    ("fin.twin.manage", "Financial Intelligence Platform", "Build and simulate financial digital twins"),
    ("fin.strategic.view", "Financial Intelligence Platform", "View strategic intelligence reports"),
    ("fin.strategic.generate", "Financial Intelligence Platform", "Generate strategic intelligence reports and briefings"),
    # Enterprise Productization & Commercial Readiness (Track 4)
    ("ent.ux.view", "Enterprise Platform", "View UX preferences and saved layouts"),
    ("ent.ux.manage", "Enterprise Platform", "Manage personalization, themes and saved layouts"),
    ("ent.workspace.view", "Enterprise Platform", "View workspaces, collections and shared views"),
    ("ent.workspace.manage", "Enterprise Platform", "Create and manage workspaces, members and items"),
    ("ent.developer.view", "Enterprise Platform", "View the developer platform, API keys and request history"),
    ("ent.developer.manage", "Enterprise Platform", "Manage API keys, webhooks and sandbox testing"),
    ("ent.marketplace.view", "Enterprise Platform", "Browse the plugin marketplace and analytics"),
    ("ent.marketplace.manage", "Enterprise Platform", "Publish, approve, version and install plugins"),
    ("ent.integration.view", "Enterprise Platform", "View integration pipelines and runs"),
    ("ent.integration.manage", "Enterprise Platform", "Build, schedule and run integration pipelines"),
    ("ent.data.view", "Enterprise Platform", "View master data, golden records and quality results"),
    ("ent.data.manage", "Enterprise Platform", "Manage MDM records, data rules and bulk jobs"),
    ("ent.ops.view", "Enterprise Platform", "View the operations center, health and incidents"),
    ("ent.ops.manage", "Enterprise Platform", "Manage incidents, runbooks and operations"),
    ("ent.security.view", "Enterprise Platform", "View the security center, events and access reviews"),
    ("ent.security.manage", "Enterprise Platform", "Manage security events, access reviews and key rotation"),
    ("ent.success.view", "Enterprise Platform", "View customer success, health and adoption"),
    ("ent.success.manage", "Enterprise Platform", "Manage customers, onboarding and lifecycle events"),
    ("ent.deploy.view", "Enterprise Platform", "View environments, deployments and release history"),
    ("ent.deploy.manage", "Enterprise Platform", "Manage environments, deployments, canaries and rollbacks"),
    ("ent.monitoring.view", "Enterprise Platform", "View distributed tracing, SLAs and monitoring dashboards"),
    ("ent.bi.view", "Enterprise Platform", "View executive business-intelligence dashboards and board reports"),
    ("ent.launch.view", "Enterprise Platform", "View launch-readiness checklists and scores"),
    ("ent.launch.manage", "Enterprise Platform", "Generate and manage launch-readiness checklists"),
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

# ---------------------------------------------------------------------------
# Phase 10 — Enterprise Banking Operating System grants.
# The AI-native OS layer (policies, committees, prompts, multi-LLM, data fabric,
# workflow studio, marketplace) is broadly readable by credit-workflow roles;
# authoring/governance is restricted by seniority.
# ---------------------------------------------------------------------------
_PHASE10_READ = [
    "policy.view", "committee.view", "prompt.view", "llm.view", "fabric.view",
    "workflowstudio.view", "marketplace.view",
]
for _role in ("relationship_manager", "credit_analyst", "senior_analyst",
              "risk_manager", "compliance_officer", "auditor"):
    ROLE_PERMISSIONS[_role].extend(_PHASE10_READ)

# Analysts and above evaluate policies, participate in committees and use the
# recommendation marketplace.
for _role in ("credit_analyst", "senior_analyst", "risk_manager"):
    ROLE_PERMISSIONS[_role].extend([
        "policy.evaluate", "committee.participate", "prompt.manage",
    ])
# Senior analysts + risk managers author policies, run the studio and manage LLMs.
for _role in ("senior_analyst", "risk_manager"):
    ROLE_PERMISSIONS[_role].extend([
        "policy.manage", "committee.manage", "workflowstudio.manage",
    ])
# Risk managers own the OS governance surfaces end-to-end.
ROLE_PERMISSIONS["risk_manager"].extend([
    "llm.manage", "fabric.manage", "marketplace.manage",
])

# ---------------------------------------------------------------------------
# Track 2 — AI Intelligence Platform grants.
# The AI layer (RAG, agents, memory, prompts, eval, investigation, reports,
# workflows, chat, research, learning, governance, explainability, monitoring)
# is broadly readable/usable by credit-workflow roles; authoring, governance and
# retraining are restricted by seniority.
# ---------------------------------------------------------------------------
_TRACK2_READ = [
    "aip.rag.view", "aip.rag.query", "aip.chat.use", "aip.reports.generate",
    "aip.explain.view", "aip.prompts.view", "aip.workflows.view",
    "aip.memory.view", "aip.governance.view", "aip.monitoring.view",
    "aip.learning.view",
]
for _role in ("relationship_manager", "credit_analyst", "senior_analyst",
              "risk_manager", "compliance_officer", "auditor"):
    ROLE_PERMISSIONS[_role].extend(_TRACK2_READ)

# Analysts and above run the heavier AI engines and submit feedback.
for _role in ("credit_analyst", "senior_analyst", "risk_manager"):
    ROLE_PERMISSIONS[_role].extend([
        "aip.agents.run", "aip.investigate.run", "aip.research.run",
        "aip.eval.run", "aip.memory.manage", "aip.learning.manage",
    ])
# Senior analysts + risk managers author prompts/workflows and manage the RAG index.
for _role in ("senior_analyst", "risk_manager"):
    ROLE_PERMISSIONS[_role].extend([
        "aip.rag.manage", "aip.prompts.manage", "aip.workflows.manage",
    ])
# Risk managers own AI governance + monitoring end-to-end.
ROLE_PERMISSIONS["risk_manager"].extend(["aip.governance.manage", "aip.monitoring.manage"])
# Oversight roles get read on governance/monitoring (already in _TRACK2_READ) plus eval.
for _role in ("compliance_officer", "auditor"):
    ROLE_PERMISSIONS[_role].extend(["aip.eval.run"])

# ---------------------------------------------------------------------------
# Track 3 — Advanced Financial Intelligence Platform grants.
# Treasury, portfolio, regulatory, economic, ESG, market, alt-data, forecasting,
# quant risk, benchmarking, executive, optimization, digital-twin and strategic
# intelligence. Read/view surfaces are broadly available to credit-workflow and
# oversight roles; execution and management are restricted by seniority.
# ---------------------------------------------------------------------------
_TRACK3_READ = [
    "fin.treasury.view", "fin.portfolio.view", "fin.regulatory.view",
    "fin.economic.view", "fin.esg.view", "fin.market.view", "fin.altdata.view",
    "fin.forecast.view", "fin.quant.view", "fin.benchmark.view", "fin.exec.view",
    "fin.optimize.view", "fin.twin.view", "fin.strategic.view",
]
for _role in ("relationship_manager", "credit_analyst", "senior_analyst",
              "risk_manager", "compliance_officer", "auditor"):
    ROLE_PERMISSIONS[_role].extend(_TRACK3_READ)

# Analysts and above run the analytical engines (read-heavy, non-destructive).
for _role in ("credit_analyst", "senior_analyst", "risk_manager"):
    ROLE_PERMISSIONS[_role].extend([
        "fin.regulatory.run", "fin.forecast.run", "fin.quant.run",
        "fin.benchmark.run", "fin.optimize.run", "fin.esg.manage",
        "fin.strategic.generate",
    ])
# Senior analysts + risk managers manage the treasury, portfolio and twin surfaces.
for _role in ("senior_analyst", "risk_manager"):
    ROLE_PERMISSIONS[_role].extend([
        "fin.treasury.manage", "fin.portfolio.manage", "fin.twin.manage",
    ])
# Risk managers own market/economic/alt-data ingestion end-to-end.
ROLE_PERMISSIONS["risk_manager"].extend([
    "fin.economic.manage", "fin.market.manage", "fin.altdata.manage",
])

# ---------------------------------------------------------------------------
# Track 4 — Enterprise Productization & Commercial Readiness grants.
# The productization surfaces (UX, workspaces, developer platform, marketplace,
# integration, data management, operations, security, customer success,
# deployment, monitoring, BI, launch readiness) are broadly viewable by every
# workflow role; platform/operations management is restricted to admins and the
# platform_admin persona.
# ---------------------------------------------------------------------------
_TRACK4_READ = [
    "ent.ux.view", "ent.ux.manage", "ent.workspace.view", "ent.workspace.manage",
    "ent.developer.view", "ent.marketplace.view", "ent.integration.view",
    "ent.data.view", "ent.ops.view", "ent.security.view", "ent.success.view",
    "ent.deploy.view", "ent.monitoring.view", "ent.bi.view", "ent.launch.view",
]
for _role in ("relationship_manager", "credit_analyst", "senior_analyst",
              "risk_manager", "compliance_officer", "auditor"):
    ROLE_PERMISSIONS[_role].extend(_TRACK4_READ)

# Senior analysts + risk managers run integration, developer and data surfaces.
for _role in ("senior_analyst", "risk_manager"):
    ROLE_PERMISSIONS[_role].extend([
        "ent.developer.manage", "ent.integration.manage", "ent.data.manage",
        "ent.success.manage", "ent.launch.manage",
    ])
# Risk managers additionally own operations, security and the marketplace.
ROLE_PERMISSIONS["risk_manager"].extend([
    "ent.ops.manage", "ent.security.manage", "ent.marketplace.manage",
])
# The SaaS platform_admin persona owns the full enterprise-platform surface.
_TRACK4_ALL = [
    "ent.ux.view", "ent.ux.manage", "ent.workspace.view", "ent.workspace.manage",
    "ent.developer.view", "ent.developer.manage", "ent.marketplace.view",
    "ent.marketplace.manage", "ent.integration.view", "ent.integration.manage",
    "ent.data.view", "ent.data.manage", "ent.ops.view", "ent.ops.manage",
    "ent.security.view", "ent.security.manage", "ent.success.view", "ent.success.manage",
    "ent.deploy.view", "ent.deploy.manage", "ent.monitoring.view", "ent.bi.view",
    "ent.launch.view", "ent.launch.manage",
]
ROLE_PERMISSIONS["platform_admin"].extend(_TRACK4_ALL)
# Compliance/audit get read on security + access reviews (already via _TRACK4_READ).

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
