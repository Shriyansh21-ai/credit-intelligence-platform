"""System config service — seed, read, update.

``sync_config`` inserts any missing default keys (idempotent; never overwrites a
value an admin has changed). ``get_config`` returns the stored value or a
supplied fallback. ``set_config`` updates a value and audits the change.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from backend.app.core.cache import TTLCache
from backend.app.models.system_config import SystemConfig
from backend.app.services import audit
from backend.app.services.config.catalog import CONFIG_DEFAULTS

# Config is read often and changes rarely — cache resolved values briefly.
_config_cache = TTLCache(ttl_seconds=30.0)


def sync_config(db: Session) -> None:
    """Insert missing default keys. Existing keys are left untouched."""
    existing = {c.key for c in db.query(SystemConfig).all()}
    created = False
    for key, spec in CONFIG_DEFAULTS.items():
        if key in existing:
            continue
        db.add(
            SystemConfig(
                key=key,
                value=spec["value"],
                value_type=spec.get("value_type", "json"),
                category=spec.get("category", "General"),
                description=spec.get("description"),
            )
        )
        created = True
    if created:
        db.commit()


def get_config(db: Session, key: str, default: Any = None) -> Any:
    cached = _config_cache.get(key)
    if cached is not None:
        return cached
    row = db.query(SystemConfig).filter(SystemConfig.key == key).first()
    if row is None:
        # Fall back to the catalog default, then the supplied default.
        spec = CONFIG_DEFAULTS.get(key)
        if spec is not None:
            return spec["value"]
        return default
    _config_cache.set(key, row.value)
    return row.value


def get_all_config(db: Session, category: Optional[str] = None) -> List[Dict[str, Any]]:
    query = db.query(SystemConfig)
    if category:
        query = query.filter(SystemConfig.category == category)
    rows = query.order_by(SystemConfig.category, SystemConfig.key).all()
    return [serialize(r) for r in rows]


def set_config(db: Session, key: str, value: Any, *, actor: Any = None) -> Dict[str, Any]:
    row = db.query(SystemConfig).filter(SystemConfig.key == key).first()
    before = row.value if row else None
    if row is None:
        spec = CONFIG_DEFAULTS.get(key, {})
        row = SystemConfig(
            key=key,
            value=value,
            value_type=spec.get("value_type", "json"),
            category=spec.get("category", "General"),
            description=spec.get("description"),
        )
        db.add(row)
    else:
        row.value = value
    row.updated_by = getattr(actor, "id", None)
    db.commit()
    db.refresh(row)
    _config_cache.invalidate(key)  # keep cache coherent after a write

    audit.record_safe(
        db, action="config.update", actor=actor,
        entity_type="system_config", entity_id=row.id,
        previous_value={"value": before}, new_value={"value": value},
        reason=f"Updated config {key}",
    )
    return serialize(row)


def list_categories(db: Session) -> List[str]:
    rows = db.query(SystemConfig.category).distinct().order_by(SystemConfig.category).all()
    return [r[0] for r in rows]


def serialize(row: SystemConfig) -> Dict[str, Any]:
    return {
        "key": row.key,
        "value": row.value,
        "value_type": row.value_type,
        "category": row.category,
        "description": row.description,
        "updated_by": row.updated_by,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }
