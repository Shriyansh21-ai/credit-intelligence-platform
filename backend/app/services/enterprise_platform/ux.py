"""M1 — Enterprise UX Platform (personalization backend).

The visual redesign (design system, command palette, split views, dockable
panels, themes, skeletons, error boundaries) lives in the frontend. This service
is the *persistence* backend behind it: per-user preferences (theme, density,
accent, shortcuts) and saved layouts (panel/split/dock configurations), plus the
static command-palette catalog that powers global search and keyboard-driven
navigation across every module.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from backend.app.models.enterprise_platform import EntSavedLayout, EntUserPreference
from .common import iso, slugify, utcnow

THEMES = ["light", "dark", "system"]
DENSITIES = ["comfortable", "compact", "spacious"]

# The command palette / global-search catalog. One entry per navigable surface;
# the frontend renders these as ⌘K commands so no page is a dead placeholder.
COMMAND_CATALOG: List[Dict[str, str]] = [
    {"id": "goto-dashboard", "label": "Go to Dashboard", "group": "Navigate", "href": "/"},
    {"id": "goto-portfolio", "label": "Portfolio Intelligence", "group": "Financial", "href": "/fin-portfolio"},
    {"id": "goto-treasury", "label": "Treasury Intelligence", "group": "Financial", "href": "/fin-treasury"},
    {"id": "goto-regulatory", "label": "Basel III / IFRS 9", "group": "Financial", "href": "/fin-regulatory"},
    {"id": "goto-executive", "label": "Executive Center", "group": "Financial", "href": "/fin-executive"},
    {"id": "goto-quant", "label": "Quantitative Risk", "group": "Financial", "href": "/fin-quant"},
    {"id": "goto-workspaces", "label": "Workspaces", "group": "Platform", "href": "/ent-workspaces"},
    {"id": "goto-developer", "label": "Developer Platform", "group": "Platform", "href": "/ent-developer"},
    {"id": "goto-marketplace", "label": "Plugin Marketplace", "group": "Platform", "href": "/ent-marketplace"},
    {"id": "goto-integration", "label": "Integration Studio", "group": "Platform", "href": "/ent-integration"},
    {"id": "goto-data", "label": "Data Management", "group": "Platform", "href": "/ent-data"},
    {"id": "goto-operations", "label": "Operations Center", "group": "Platform", "href": "/ent-operations"},
    {"id": "goto-security", "label": "Security Center", "group": "Platform", "href": "/ent-security"},
    {"id": "goto-success", "label": "Customer Success", "group": "Platform", "href": "/ent-success"},
    {"id": "goto-deployment", "label": "Deployment Platform", "group": "Platform", "href": "/ent-deployment"},
    {"id": "goto-monitoring", "label": "Monitoring", "group": "Platform", "href": "/ent-monitoring"},
    {"id": "goto-bi", "label": "Business Intelligence", "group": "Platform", "href": "/ent-bi"},
    {"id": "goto-launch", "label": "Launch Readiness", "group": "Platform", "href": "/ent-launch"},
    {"id": "action-toggle-theme", "label": "Toggle theme", "group": "Actions", "href": ""},
    {"id": "action-command-palette", "label": "Open command palette (⌘K)", "group": "Actions", "href": ""},
]


def get_preferences(db: Session, *, user_ref: str, tenant_id: Optional[int] = None) -> Dict[str, Any]:
    row = (db.query(EntUserPreference)
           .filter(EntUserPreference.tenant_id == tenant_id, EntUserPreference.user_ref == user_ref)
           .first())
    if not row:
        return {"user_ref": user_ref, "theme": "system", "density": "comfortable",
                "accent": None, "sidebar_collapsed": False, "shortcuts_enabled": True,
                "settings": {}, "exists": False}
    return {"user_ref": row.user_ref, "theme": row.theme, "density": row.density,
            "accent": row.accent, "sidebar_collapsed": row.sidebar_collapsed,
            "shortcuts_enabled": row.shortcuts_enabled, "settings": row.settings,
            "updated_at": iso(row.updated_at), "exists": True}


def save_preferences(db: Session, *, user_ref: str, theme: Optional[str] = None,
                     density: Optional[str] = None, accent: Optional[str] = None,
                     sidebar_collapsed: Optional[bool] = None, shortcuts_enabled: Optional[bool] = None,
                     settings: Optional[dict] = None, tenant_id: Optional[int] = None) -> Dict[str, Any]:
    if theme is not None and theme not in THEMES:
        raise ValueError(f"unknown theme '{theme}'")
    if density is not None and density not in DENSITIES:
        raise ValueError(f"unknown density '{density}'")
    row = (db.query(EntUserPreference)
           .filter(EntUserPreference.tenant_id == tenant_id, EntUserPreference.user_ref == user_ref)
           .first())
    if not row:
        row = EntUserPreference(tenant_id=tenant_id, user_ref=user_ref)
        db.add(row)
    if theme is not None:
        row.theme = theme
    if density is not None:
        row.density = density
    if accent is not None:
        row.accent = accent
    if sidebar_collapsed is not None:
        row.sidebar_collapsed = sidebar_collapsed
    if shortcuts_enabled is not None:
        row.shortcuts_enabled = shortcuts_enabled
    if settings is not None:
        row.settings = settings
    db.commit()
    db.refresh(row)
    return get_preferences(db, user_ref=user_ref, tenant_id=tenant_id)


def save_layout(db: Session, *, user_ref: str, name: str, config: dict, surface: Optional[str] = None,
                scope: str = "personal", is_default: bool = False, key: Optional[str] = None,
                tenant_id: Optional[int] = None) -> Dict[str, Any]:
    key = key or slugify(name)
    if is_default:
        # Only one default per (user, surface).
        for r in (db.query(EntSavedLayout)
                  .filter(EntSavedLayout.tenant_id == tenant_id, EntSavedLayout.user_ref == user_ref,
                          EntSavedLayout.surface == surface).all()):
            r.is_default = False
    row = EntSavedLayout(tenant_id=tenant_id, user_ref=user_ref, key=key, name=name, scope=scope,
                         surface=surface, config=config, is_default=is_default)
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"layout_id": row.id, "key": row.key, "name": row.name, "surface": row.surface,
            "is_default": row.is_default}


def list_layouts(db: Session, *, user_ref: str, surface: Optional[str] = None,
                 tenant_id: Optional[int] = None) -> List[Dict[str, Any]]:
    q = db.query(EntSavedLayout).filter(EntSavedLayout.user_ref == user_ref)
    if tenant_id is not None:
        q = q.filter(EntSavedLayout.tenant_id == tenant_id)
    if surface:
        q = q.filter(EntSavedLayout.surface == surface)
    return [{"layout_id": r.id, "key": r.key, "name": r.name, "scope": r.scope,
             "surface": r.surface, "config": r.config, "is_default": r.is_default,
             "created_at": iso(r.created_at)}
            for r in q.order_by(EntSavedLayout.id.desc()).all()]


def command_catalog(query: Optional[str] = None) -> List[Dict[str, str]]:
    if not query:
        return COMMAND_CATALOG
    ql = query.lower()
    return [c for c in COMMAND_CATALOG if ql in c["label"].lower() or ql in c["group"].lower()]
