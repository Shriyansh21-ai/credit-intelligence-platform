"""Feature-flag evaluation + management (Phase 8, Milestone 5).

Evaluation order for a flag, given (tenant, roles):

1. Flag missing            -> off
2. Expired                 -> off
3. Unmet dependency        -> off  (a prerequisite flag is off)
4. Explicit tenant override -> use it (wins over everything below)
5. Role targeting          -> off if target_roles set and no role matches
6. Global enabled          -> on
7. Percentage rollout      -> deterministic per (key, tenant) bucket < percentage

Rollout bucketing is a stable hash of ``key:tenant_id`` so a tenant's result is
consistent across calls and independent of other tenants (true canary).
"""

from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence

from sqlalchemy.orm import Session

from backend.app.models.feature_flags import FeatureFlag, FeatureFlagOverride
from backend.app.services.saas.flags import catalog


def sync_flags(db: Session) -> int:
    """Idempotently register catalog flags. Metadata (name/description/kind/
    targeting/dependencies) is always refreshed; ``enabled``/``rollout`` are
    seeded only on first creation so admin/ops changes survive re-sync."""
    touched = 0
    for spec in catalog.FLAGS:
        row = db.query(FeatureFlag).filter(FeatureFlag.key == spec["key"]).first()
        is_new = row is None
        if is_new:
            row = FeatureFlag(
                key=spec["key"],
                enabled=spec.get("enabled", False),
                rollout_percentage=spec.get("rollout_percentage", 0.0),
            )
            db.add(row)
        row.name = spec["name"]
        row.description = spec.get("description")
        row.kind = spec.get("kind", "release")
        row.target_roles = spec.get("target_roles", [])
        row.dependencies = spec.get("dependencies", [])
        touched += 1
    db.commit()
    return touched


def _bucket(key: str, tenant_id: Optional[int]) -> int:
    digest = hashlib.sha256(f"{key}:{tenant_id if tenant_id is not None else 'global'}".encode()).hexdigest()
    return int(digest[:8], 16) % 100


def _override(db: Session, key: str, tenant_id: Optional[int]) -> Optional[FeatureFlagOverride]:
    if tenant_id is None:
        return None
    return (
        db.query(FeatureFlagOverride)
        .filter(FeatureFlagOverride.flag_key == key,
                FeatureFlagOverride.tenant_id == tenant_id)
        .first()
    )


def is_enabled(db: Session, key: str, *, tenant_id: Optional[int] = None,
               roles: Optional[Sequence[str]] = None, _seen: Optional[set] = None) -> bool:
    flag = db.query(FeatureFlag).filter(FeatureFlag.key == key).first()
    if flag is None:
        return False
    if flag.expires_at and flag.expires_at < datetime.utcnow():
        return False
    # Dependencies (guard against cycles).
    _seen = _seen or set()
    if key in _seen:
        return False
    _seen.add(key)
    for dep in (flag.dependencies or []):
        if not is_enabled(db, dep, tenant_id=tenant_id, roles=roles, _seen=_seen):
            return False
    # Explicit override wins.
    ov = _override(db, key, tenant_id)
    if ov is not None:
        return bool(ov.enabled)
    # Role targeting.
    if flag.target_roles:
        if not roles or not set(roles) & set(flag.target_roles):
            return False
    if flag.enabled:
        return True
    # Percentage rollout / canary.
    if flag.rollout_percentage and flag.rollout_percentage > 0:
        return _bucket(key, tenant_id) < flag.rollout_percentage
    return False


def evaluate_all(db: Session, *, tenant_id: Optional[int] = None,
                 roles: Optional[Sequence[str]] = None) -> Dict[str, bool]:
    flags = db.query(FeatureFlag).all()
    return {f.key: is_enabled(db, f.key, tenant_id=tenant_id, roles=roles) for f in flags}


# -- management -------------------------------------------------------------
def list_flags(db: Session) -> List[FeatureFlag]:
    return db.query(FeatureFlag).order_by(FeatureFlag.key).all()


def upsert_flag(db: Session, key: str, **fields) -> FeatureFlag:
    row = db.query(FeatureFlag).filter(FeatureFlag.key == key).first()
    if row is None:
        row = FeatureFlag(key=key, name=fields.get("name", key))
        db.add(row)
    for k, v in fields.items():
        if hasattr(row, k) and v is not None:
            setattr(row, k, v)
    row.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(row)
    return row


def set_override(db: Session, key: str, tenant_id: int, enabled: bool, *,
                 reason: Optional[str] = None,
                 organization_id: Optional[int] = None) -> FeatureFlagOverride:
    ov = _override(db, key, tenant_id)
    if ov is None:
        ov = FeatureFlagOverride(flag_key=key, tenant_id=tenant_id,
                                 organization_id=organization_id)
        db.add(ov)
    ov.enabled = enabled
    ov.reason = reason
    db.commit()
    db.refresh(ov)
    return ov


def clear_override(db: Session, key: str, tenant_id: int) -> None:
    ov = _override(db, key, tenant_id)
    if ov:
        db.delete(ov)
        db.commit()
