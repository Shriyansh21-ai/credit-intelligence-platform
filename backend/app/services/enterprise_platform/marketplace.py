"""M4 — Enterprise Plugin Marketplace.

A full plugin lifecycle on top of the platform: publishing, an approval workflow,
semantic versioning, dependency & compatibility declarations, plugin permissions,
health, install analytics and billing readiness. Backed by ``ent_plugins``,
``ent_plugin_versions`` and ``ent_plugin_installs``. Complements (does not
replace) the Banking-OS marketplace from Phase 10.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from backend.app.models.enterprise_platform import (
    EntPlugin, EntPluginInstall, EntPluginVersion,
)
from .common import iso, slugify, utcnow

PLUGIN_CATEGORIES = ["integration", "analytics", "risk", "reporting", "workflow",
                     "data", "security", "ai"]
BILLING_MODELS = ["free", "subscription", "usage"]
PLUGIN_STATUSES = ["draft", "submitted", "approved", "published", "suspended"]

# platform version used for compatibility checks.
PLATFORM_VERSION = "1.0.0"


def _vtuple(v: str):
    try:
        return tuple(int(x) for x in str(v).split(".")[:3])
    except Exception:
        return (0, 0, 0)


def publish_plugin(db: Session, *, key: str, name: str, version: str = "0.1.0",
                   publisher: Optional[str] = None, category: str = "integration",
                   permissions: Optional[List[str]] = None, dependencies: Optional[List[str]] = None,
                   compatibility: Optional[dict] = None, billing_model: str = "free",
                   description: Optional[str] = None, tenant_id: Optional[int] = None,
                   created_by: Optional[str] = None) -> Dict[str, Any]:
    if category not in PLUGIN_CATEGORIES:
        raise ValueError(f"unknown category '{category}'")
    if billing_model not in BILLING_MODELS:
        raise ValueError(f"unknown billing_model '{billing_model}'")
    key = slugify(key)
    if db.query(EntPlugin).filter(EntPlugin.tenant_id == tenant_id, EntPlugin.key == key).first():
        raise ValueError(f"plugin '{key}' already exists")
    row = EntPlugin(tenant_id=tenant_id, key=key, name=name, publisher=publisher or created_by,
                    category=category, latest_version=version, status="submitted",
                    permissions=permissions or [], dependencies=dependencies or [],
                    compatibility=compatibility or {"min_platform": PLATFORM_VERSION},
                    billing_model=billing_model, description=description, created_by=created_by)
    db.add(row)
    db.commit()
    db.refresh(row)
    db.add(EntPluginVersion(plugin_id=row.id, version=version, status="submitted",
                            changelog="initial submission",
                            manifest={"permissions": permissions or [], "dependencies": dependencies or []}))
    db.commit()
    return {"plugin_id": row.id, "key": row.key, "status": row.status, "version": version}


def add_version(db: Session, *, plugin_id: int, version: str, changelog: Optional[str] = None,
                manifest: Optional[dict] = None) -> Dict[str, Any]:
    p = db.query(EntPlugin).filter(EntPlugin.id == plugin_id).first()
    if not p:
        raise ValueError("plugin not found")
    if _vtuple(version) <= _vtuple(p.latest_version):
        raise ValueError(f"version {version} must be greater than {p.latest_version}")
    row = EntPluginVersion(plugin_id=plugin_id, version=version, status="submitted",
                           changelog=changelog, manifest=manifest or {})
    db.add(row)
    p.latest_version = version
    p.status = "submitted"
    db.commit()
    db.refresh(row)
    return {"version_id": row.id, "plugin_id": plugin_id, "version": version, "status": row.status}


def review_version(db: Session, *, version_id: int, approve: bool, reviewer: Optional[str] = None) -> Dict[str, Any]:
    v = db.query(EntPluginVersion).filter(EntPluginVersion.id == version_id).first()
    if not v:
        raise ValueError("version not found")
    v.status = "approved" if approve else "rejected"
    v.approved_by = reviewer
    p = db.query(EntPlugin).filter(EntPlugin.id == v.plugin_id).first()
    if p and approve:
        p.status = "approved"
    db.commit()
    return {"version_id": v.id, "status": v.status, "plugin_status": p.status if p else None}


def publish_approved(db: Session, *, plugin_id: int) -> Dict[str, Any]:
    p = db.query(EntPlugin).filter(EntPlugin.id == plugin_id).first()
    if not p:
        raise ValueError("plugin not found")
    if p.status != "approved":
        raise ValueError("plugin must be approved before publishing")
    p.status = "published"
    p.health = "healthy"
    latest = (db.query(EntPluginVersion)
              .filter(EntPluginVersion.plugin_id == plugin_id, EntPluginVersion.version == p.latest_version)
              .first())
    if latest:
        latest.status = "published"
    db.commit()
    return {"plugin_id": p.id, "status": p.status}


def check_compatibility(db: Session, *, plugin_id: int, platform_version: str = PLATFORM_VERSION) -> Dict[str, Any]:
    p = db.query(EntPlugin).filter(EntPlugin.id == plugin_id).first()
    if not p:
        raise ValueError("plugin not found")
    min_v = (p.compatibility or {}).get("min_platform", "0.0.0")
    max_v = (p.compatibility or {}).get("max_platform")
    ok = _vtuple(platform_version) >= _vtuple(min_v) and (max_v is None or _vtuple(platform_version) <= _vtuple(max_v))
    missing_deps = [d for d in (p.dependencies or [])
                    if not db.query(EntPlugin).filter(EntPlugin.key == d,
                                                      EntPlugin.status == "published").first()]
    return {"plugin_id": plugin_id, "compatible": ok and not missing_deps,
            "platform_version": platform_version, "min_platform": min_v, "max_platform": max_v,
            "missing_dependencies": missing_deps}


def install_plugin(db: Session, *, plugin_id: int, tenant_id: Optional[int] = None,
                   installed_by: Optional[str] = None) -> Dict[str, Any]:
    p = db.query(EntPlugin).filter(EntPlugin.id == plugin_id).first()
    if not p:
        raise ValueError("plugin not found")
    if p.status != "published":
        raise ValueError("only published plugins can be installed")
    compat = check_compatibility(db, plugin_id=plugin_id)
    if not compat["compatible"]:
        raise ValueError(f"incompatible: {compat}")
    row = EntPluginInstall(tenant_id=tenant_id, plugin_id=plugin_id, version=p.latest_version,
                           installed_by=installed_by)
    db.add(row)
    p.install_count = (p.install_count or 0) + 1
    db.commit()
    db.refresh(row)
    return {"install_id": row.id, "plugin_id": plugin_id, "version": row.version, "status": row.status}


def list_plugins(db: Session, *, status: Optional[str] = None, category: Optional[str] = None,
                 tenant_id: Optional[int] = None) -> List[Dict[str, Any]]:
    q = db.query(EntPlugin)
    if tenant_id is not None:
        q = q.filter(EntPlugin.tenant_id == tenant_id)
    if status:
        q = q.filter(EntPlugin.status == status)
    if category:
        q = q.filter(EntPlugin.category == category)
    return [{"plugin_id": p.id, "key": p.key, "name": p.name, "publisher": p.publisher,
             "category": p.category, "latest_version": p.latest_version, "status": p.status,
             "health": p.health, "install_count": p.install_count, "billing_model": p.billing_model}
            for p in q.order_by(EntPlugin.id.desc()).all()]


def get_plugin(db: Session, plugin_id: int) -> Optional[Dict[str, Any]]:
    p = db.query(EntPlugin).filter(EntPlugin.id == plugin_id).first()
    if not p:
        return None
    versions = db.query(EntPluginVersion).filter(EntPluginVersion.plugin_id == p.id).all()
    return {"plugin_id": p.id, "key": p.key, "name": p.name, "publisher": p.publisher,
            "category": p.category, "latest_version": p.latest_version, "status": p.status,
            "permissions": p.permissions, "dependencies": p.dependencies,
            "compatibility": p.compatibility, "health": p.health, "install_count": p.install_count,
            "billing_model": p.billing_model, "description": p.description,
            "versions": [{"version": v.version, "status": v.status, "changelog": v.changelog}
                         for v in versions]}


def analytics(db: Session, *, tenant_id: Optional[int] = None) -> Dict[str, Any]:
    plugins = list_plugins(db, tenant_id=tenant_id)
    by_status: Dict[str, int] = {}
    by_category: Dict[str, int] = {}
    for p in plugins:
        by_status[p["status"]] = by_status.get(p["status"], 0) + 1
        by_category[p["category"]] = by_category.get(p["category"], 0) + 1
    total_installs = sum(p["install_count"] for p in plugins)
    top = sorted(plugins, key=lambda p: p["install_count"], reverse=True)[:5]
    return {"total_plugins": len(plugins), "published": by_status.get("published", 0),
            "by_status": by_status, "by_category": by_category, "total_installs": total_installs,
            "top_installed": [{"key": p["key"], "installs": p["install_count"]} for p in top],
            "revenue_ready": sum(1 for p in plugins if p["billing_model"] != "free"),
            "generated_at": iso(utcnow())}
