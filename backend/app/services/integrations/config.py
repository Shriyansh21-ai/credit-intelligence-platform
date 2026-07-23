"""Connector configuration service (Milestones 1, 14).

``ConnectorConfig`` rows decide which provider mode is active for each connector
key and hold non-secret settings (base URLs, timeouts, rate limits). Credentials
are stored only as an encrypted envelope. :func:`sync_connector_configs` seeds a
default (``mock``, enabled) row per registered connector so the platform is
usable immediately and every connector is independently configurable.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from backend.app.models.integrations import ConnectorConfig
from backend.app.services.integrations.base.registry import registry
from backend.app.services.integrations.base.security import encrypt_secret


def sync_connector_configs(db: Session) -> int:
    """Idempotently create a default config row for each registered connector."""
    # Ensure all domain providers are registered before enumerating them.
    from backend.app.services.integrations.factory import register_all
    register_all()
    created = 0
    for entry in registry.describe():
        key = entry["key"]
        existing = db.query(ConnectorConfig).filter(ConnectorConfig.connector_key == key).first()
        if existing is not None:
            continue
        db.add(ConnectorConfig(
            connector_key=key,
            category=entry["category"] or "banking",
            provider_mode="mock",
            enabled=True,
            config={},
        ))
        created += 1
    if created:
        db.commit()
    return created


def get_config(db: Session, connector_key: str) -> Optional[ConnectorConfig]:
    return db.query(ConnectorConfig).filter(ConnectorConfig.connector_key == connector_key).first()


def resolve_mode(db: Optional[Session], connector_key: str, default: str = "mock") -> str:
    """The active provider mode for a connector (falls back to ``default``)."""
    if db is None:
        return default
    cfg = get_config(db, connector_key)
    if cfg is None:
        return default
    return cfg.provider_mode or default


def set_mode(db: Session, connector_key: str, mode: str) -> ConnectorConfig:
    cfg = get_config(db, connector_key)
    if cfg is None:
        entry = next((e for e in registry.describe() if e["key"] == connector_key), None)
        cfg = ConnectorConfig(
            connector_key=connector_key,
            category=(entry["category"] if entry else "banking") or "banking",
            provider_mode=mode,
        )
        db.add(cfg)
    else:
        cfg.provider_mode = mode
    db.commit()
    db.refresh(cfg)
    return cfg


def update_config(
    db: Session,
    connector_key: str,
    *,
    enabled: Optional[bool] = None,
    config: Optional[Dict[str, Any]] = None,
    credentials: Optional[Dict[str, Any]] = None,
    rate_limit_per_sec: Optional[float] = None,
    timeout_seconds: Optional[float] = None,
) -> ConnectorConfig:
    cfg = get_config(db, connector_key)
    if cfg is None:
        cfg = set_mode(db, connector_key, "mock")
    if enabled is not None:
        cfg.enabled = enabled
    if config is not None:
        cfg.config = config
    if credentials is not None:
        # Store only an encrypted envelope; never the raw secret.
        import json
        cfg.credentials_encrypted = encrypt_secret(json.dumps(credentials, sort_keys=True))
    if rate_limit_per_sec is not None:
        cfg.rate_limit_per_sec = rate_limit_per_sec
    if timeout_seconds is not None:
        cfg.timeout_seconds = timeout_seconds
    db.commit()
    db.refresh(cfg)
    return cfg


def config_to_dict(cfg: ConnectorConfig) -> Dict[str, Any]:
    return {
        "connector_key": cfg.connector_key,
        "category": cfg.category,
        "provider_mode": cfg.provider_mode,
        "enabled": cfg.enabled,
        "config": cfg.config,
        "has_credentials": bool(cfg.credentials_encrypted),
        "rate_limit_per_sec": cfg.rate_limit_per_sec,
        "timeout_seconds": cfg.timeout_seconds,
        "updated_at": cfg.updated_at.isoformat() if cfg.updated_at else None,
    }


def list_configs(db: Session) -> List[Dict[str, Any]]:
    return [config_to_dict(c) for c in db.query(ConnectorConfig).order_by(ConnectorConfig.connector_key).all()]
