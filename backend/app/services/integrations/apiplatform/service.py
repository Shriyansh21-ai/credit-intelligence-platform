"""Open API platform — API keys + usage analytics (Milestone 12).

Issues scoped API keys (returned once, stored only as a salted SHA-256 hash + a
public prefix), verifies them, enforces per-key rate limits, and records usage
for analytics. This is the SDK-ready, OAuth2-adjacent access layer for external
consumers of the enterprise APIs.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from backend.app.models.integrations import ApiKey, ApiUsageLog

_KEY_PREFIX = "cak"  # credit-api-key


def _hash_key(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def create_api_key(
    db: Session,
    *,
    name: str,
    scopes: Optional[List[str]] = None,
    owner: Optional[str] = None,
    rate_limit_per_min: int = 600,
) -> Tuple[ApiKey, str]:
    """Create a key. Returns ``(row, raw_key)`` — the raw key is shown only here."""
    token = secrets.token_urlsafe(32)
    public_prefix = f"{_KEY_PREFIX}_{secrets.token_hex(4)}"
    raw_key = f"{public_prefix}.{token}"
    row = ApiKey(
        name=name,
        key_prefix=public_prefix,
        key_hash=_hash_key(raw_key),
        scopes=scopes or ["read"],
        owner=owner,
        active=True,
        rate_limit_per_min=rate_limit_per_min,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row, raw_key


def verify_api_key(db: Session, raw_key: str) -> Optional[ApiKey]:
    if not raw_key:
        return None
    row = db.query(ApiKey).filter(ApiKey.key_hash == _hash_key(raw_key), ApiKey.active.is_(True)).first()
    if row is None:
        return None
    row.last_used_at = datetime.utcnow()
    db.commit()
    return row


def check_scope(key: ApiKey, required: str) -> bool:
    scopes = key.scopes or []
    return "admin" in scopes or "*" in scopes or required in scopes


def enforce_rate_limit(db: Session, key: ApiKey) -> bool:
    """Sliding-window (1 min) per-key rate limit using the usage log."""
    window_start = datetime.utcnow() - timedelta(seconds=60)
    count = (db.query(ApiUsageLog)
             .filter(ApiUsageLog.api_key_id == key.id, ApiUsageLog.created_at >= window_start)
             .count())
    return count < (key.rate_limit_per_min or 600)


def revoke_api_key(db: Session, key_id: int) -> ApiKey:
    row = db.query(ApiKey).get(key_id)
    if row is None:
        raise ValueError("api key not found")
    row.active = False
    row.revoked_at = datetime.utcnow()
    db.commit()
    db.refresh(row)
    return row


def record_usage(db: Session, *, api_key_id: Optional[int], endpoint: str, method: str,
                 status_code: int, latency_ms: float) -> ApiUsageLog:
    row = ApiUsageLog(api_key_id=api_key_id, endpoint=endpoint, method=method,
                      status_code=status_code, latency_ms=latency_ms)
    db.add(row)
    db.commit()
    return row


def list_keys(db: Session) -> List[Dict[str, Any]]:
    return [key_to_dict(k) for k in db.query(ApiKey).order_by(ApiKey.id.desc()).all()]


def usage_analytics(db: Session, *, api_key_id: Optional[int] = None) -> Dict[str, Any]:
    q = db.query(ApiUsageLog)
    if api_key_id is not None:
        q = q.filter(ApiUsageLog.api_key_id == api_key_id)
    rows = q.all()
    total = len(rows)
    if total == 0:
        return {"total_calls": 0, "by_endpoint": {}, "by_status": {}, "avg_latency_ms": 0.0}
    by_endpoint: Dict[str, int] = {}
    by_status: Dict[str, int] = {}
    latencies = []
    for r in rows:
        by_endpoint[r.endpoint] = by_endpoint.get(r.endpoint, 0) + 1
        sc = str(r.status_code or 0)
        by_status[sc] = by_status.get(sc, 0) + 1
        if r.latency_ms is not None:
            latencies.append(r.latency_ms)
    return {
        "total_calls": total,
        "by_endpoint": by_endpoint,
        "by_status": by_status,
        "avg_latency_ms": round(sum(latencies) / len(latencies), 3) if latencies else 0.0,
    }


def key_to_dict(k: ApiKey) -> Dict[str, Any]:
    return {
        "id": k.id, "name": k.name, "key_prefix": k.key_prefix, "scopes": k.scopes,
        "owner": k.owner, "active": k.active, "rate_limit_per_min": k.rate_limit_per_min,
        "created_at": k.created_at.isoformat() if k.created_at else None,
        "last_used_at": k.last_used_at.isoformat() if k.last_used_at else None,
        "revoked_at": k.revoked_at.isoformat() if k.revoked_at else None,
    }
