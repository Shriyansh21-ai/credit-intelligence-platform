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
    ],
    "auditor": [
        "applications.view", "approvals.view", "documents.view",
        "portfolio.view", "covenants.view", "monitoring.view",
        "audit.view", "reports.view", "reports.export",
        "collaboration.view",
        "notifications.view", "search.use",
    ],
    "compliance_officer": [
        "applications.view", "approvals.view", "documents.view",
        "portfolio.view", "covenants.view", "monitoring.view",
        "audit.view", "config.view",
        "reports.view", "reports.export",
        "collaboration.view", "collaboration.participate",
        "notifications.view", "search.use",
    ],
    "viewer": [
        "applications.view", "portfolio.view",
        "reports.view", "notifications.view", "search.use",
    ],
}

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
