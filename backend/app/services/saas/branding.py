"""White-label branding service (Phase 8, Milestone 3).

Resolves and mutates a tenant's :class:`TenantBranding` row. A code-defined
default theme guarantees every tenant renders sensibly before any customisation;
``get_branding`` deep-merges the stored overrides onto that default so the
frontend always receives a complete, ready-to-apply theme.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from backend.app.models.tenancy import TenantBranding

# The neutral platform default. Tenant overrides are layered on top.
DEFAULT_THEME: Dict[str, Any] = {
    "colors": {
        "primary": "#1e40af",
        "secondary": "#0f172a",
        "accent": "#0891b2",
        "background": "#ffffff",
        "surface": "#f8fafc",
        "text": "#0f172a",
        "success": "#16a34a",
        "warning": "#d97706",
        "danger": "#dc2626",
    },
    "typography": {
        "font_family": "Inter, system-ui, sans-serif",
        "heading_family": "Inter, system-ui, sans-serif",
        "base_size": "14px",
    },
    "shape": {"radius": "8px", "density": "comfortable"},
    "mode": "light",
}

DEFAULT_NAVIGATION: List[Dict[str, Any]] = [
    {"key": "dashboard", "label": "Dashboard", "visible": True},
    {"key": "applications", "label": "Applications", "visible": True},
    {"key": "portfolio", "label": "Portfolio", "visible": True},
    {"key": "analytics", "label": "Analytics", "visible": True},
    {"key": "admin", "label": "Administration", "visible": True},
]


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(base)
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def _row(db: Session, tenant_id: int) -> Optional[TenantBranding]:
    return db.query(TenantBranding).filter(
        TenantBranding.tenant_id == tenant_id).first()


def get_branding(db: Session, tenant_id: int) -> Dict[str, Any]:
    row = _row(db, tenant_id)
    theme = _deep_merge(DEFAULT_THEME, (row.theme if row else {}) or {})
    return {
        "tenant_id": tenant_id,
        "logo_url": row.logo_url if row else None,
        "logo_dark_url": row.logo_dark_url if row else None,
        "favicon_url": row.favicon_url if row else None,
        "theme": theme,
        "email_branding": (row.email_branding if row else {}) or {},
        "login_page": (row.login_page if row else {}) or {},
        "dashboard_config": (row.dashboard_config if row else {}) or {},
        "feature_visibility": (row.feature_visibility if row else {}) or {},
        "navigation": (row.navigation if row and row.navigation else DEFAULT_NAVIGATION),
        "customized": row is not None,
    }


def update_branding(db: Session, tenant_id: int, patch: Dict[str, Any]) -> Dict[str, Any]:
    """Partially update branding. ``theme`` is merged; scalar fields replaced."""
    row = _row(db, tenant_id)
    if row is None:
        row = TenantBranding(tenant_id=tenant_id, theme={}, email_branding={},
                             login_page={}, dashboard_config={},
                             feature_visibility={}, navigation=[])
        db.add(row)
        db.flush()

    if "theme" in patch and patch["theme"] is not None:
        row.theme = _deep_merge(row.theme or {}, patch["theme"])
    for scalar in ("logo_url", "logo_dark_url", "favicon_url"):
        if scalar in patch:
            setattr(row, scalar, patch[scalar])
    for jsonf in ("email_branding", "login_page", "dashboard_config", "feature_visibility"):
        if jsonf in patch and patch[jsonf] is not None:
            setattr(row, jsonf, _deep_merge(getattr(row, jsonf) or {}, patch[jsonf]))
    if "navigation" in patch and patch["navigation"] is not None:
        row.navigation = patch["navigation"]
    row.updated_at = datetime.utcnow()
    db.commit()
    return get_branding(db, tenant_id)


def is_feature_visible(db: Session, tenant_id: int, feature_key: str) -> bool:
    """Feature visibility toggle (distinct from feature flags: this is purely a
    white-label UI concern, defaulting to visible)."""
    row = _row(db, tenant_id)
    vis = (row.feature_visibility if row else {}) or {}
    return bool(vis.get(feature_key, True))
