"""M3 — Enterprise Developer Platform.

An internal developer platform: API-key management (create/rotate/revoke with
one-time secrets stored only as hashes), webhook registration + delivery testing
+ replay, a request-history log, a sandbox request runner, rate-limit testing and
an OpenAPI-backed API explorer. Backed by ``ent_api_keys``, ``ent_webhooks``,
``ent_webhook_deliveries`` and ``ent_api_requests``.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from backend.app.models.enterprise_platform import (
    EntApiKey, EntApiRequest, EntWebhook, EntWebhookDelivery,
)
from .common import (
    checksum, generate_api_key, generate_signing_secret, hash_secret, iso, utcnow,
)

WEBHOOK_EVENTS = [
    "assessment.created", "assessment.updated", "application.submitted",
    "application.approved", "application.rejected", "portfolio.analysis.completed",
    "deployment.succeeded", "deployment.failed", "incident.opened", "incident.resolved",
    "plugin.published", "pipeline.run.completed",
]


# ---------------------------------------------------------------------------
# API keys
# ---------------------------------------------------------------------------

def create_api_key(db: Session, *, name: str, scopes: Optional[List[str]] = None,
                   environment: str = "sandbox", rate_limit_per_min: int = 600,
                   tenant_id: Optional[int] = None, created_by: Optional[str] = None) -> Dict[str, Any]:
    prefix = "sk_live" if environment == "production" else "sk_test"
    material = generate_api_key(prefix)
    row = EntApiKey(tenant_id=tenant_id, name=name, prefix=material["prefix"],
                    key_hash=material["hash"], scopes=scopes or ["read"],
                    rate_limit_per_min=rate_limit_per_min, environment=environment,
                    created_by=created_by)
    db.add(row)
    db.commit()
    db.refresh(row)
    # The plaintext secret is returned ONCE and never persisted.
    return {"api_key_id": row.id, "name": row.name, "prefix": row.prefix,
            "secret": material["secret"], "environment": row.environment,
            "scopes": row.scopes, "rate_limit_per_min": row.rate_limit_per_min,
            "warning": "store this secret now — it will not be shown again"}


def list_api_keys(db: Session, *, tenant_id: Optional[int] = None) -> List[Dict[str, Any]]:
    q = db.query(EntApiKey)
    if tenant_id is not None:
        q = q.filter(EntApiKey.tenant_id == tenant_id)
    return [{"api_key_id": k.id, "name": k.name, "prefix": k.prefix, "environment": k.environment,
             "scopes": k.scopes, "status": k.status, "rate_limit_per_min": k.rate_limit_per_min,
             "last_used_at": iso(k.last_used_at), "created_at": iso(k.created_at)}
            for k in q.order_by(EntApiKey.id.desc()).all()]


def revoke_api_key(db: Session, *, api_key_id: int) -> Dict[str, Any]:
    k = db.query(EntApiKey).filter(EntApiKey.id == api_key_id).first()
    if not k:
        raise ValueError("api key not found")
    k.status = "revoked"
    db.commit()
    return {"api_key_id": k.id, "status": k.status}


def verify_api_key(db: Session, *, secret: str, tenant_id: Optional[int] = None) -> Dict[str, Any]:
    """Verify a presented secret against stored hashes; records last-used."""
    h = hash_secret(secret)
    q = db.query(EntApiKey).filter(EntApiKey.key_hash == h, EntApiKey.status == "active")
    if tenant_id is not None:
        q = q.filter(EntApiKey.tenant_id == tenant_id)
    k = q.first()
    if not k:
        return {"valid": False}
    k.last_used_at = utcnow()
    db.commit()
    return {"valid": True, "api_key_id": k.id, "scopes": k.scopes, "environment": k.environment}


# ---------------------------------------------------------------------------
# Webhooks + delivery testing / replay
# ---------------------------------------------------------------------------

def create_webhook(db: Session, *, url: str, events: List[str], description: Optional[str] = None,
                   tenant_id: Optional[int] = None, created_by: Optional[str] = None) -> Dict[str, Any]:
    unknown = [e for e in events if e not in WEBHOOK_EVENTS]
    if unknown:
        raise ValueError(f"unknown events: {unknown}")
    row = EntWebhook(tenant_id=tenant_id, url=url, events=events,
                     signing_secret=generate_signing_secret(), description=description,
                     created_by=created_by)
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"webhook_id": row.id, "url": row.url, "events": row.events,
            "signing_secret": row.signing_secret, "status": row.status}


def list_webhooks(db: Session, *, tenant_id: Optional[int] = None) -> List[Dict[str, Any]]:
    q = db.query(EntWebhook)
    if tenant_id is not None:
        q = q.filter(EntWebhook.tenant_id == tenant_id)
    return [{"webhook_id": w.id, "url": w.url, "events": w.events, "status": w.status,
             "description": w.description, "created_at": iso(w.created_at)}
            for w in q.order_by(EntWebhook.id.desc()).all()]


def test_webhook(db: Session, *, webhook_id: int, event: Optional[str] = None,
                 payload: Optional[dict] = None, simulate_status: int = 200,
                 tenant_id: Optional[int] = None) -> Dict[str, Any]:
    """Simulate a webhook delivery (no real network call) for developer testing."""
    w = db.query(EntWebhook).filter(EntWebhook.id == webhook_id).first()
    if not w:
        raise ValueError("webhook not found")
    event = event or (w.events[0] if w.events else "test.event")
    payload = payload or {"event": event, "sample": True}
    signature = checksum({"secret": w.signing_secret, "payload": payload})
    status = "delivered" if 200 <= simulate_status < 300 else "failed"
    row = EntWebhookDelivery(tenant_id=tenant_id, webhook_id=webhook_id, event=event, payload=payload,
                             status=status, status_code=simulate_status, attempts=1,
                             signature=signature)
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"delivery_id": row.id, "webhook_id": webhook_id, "event": event, "status": status,
            "status_code": simulate_status, "signature": signature}


def replay_delivery(db: Session, *, delivery_id: int, tenant_id: Optional[int] = None) -> Dict[str, Any]:
    d = db.query(EntWebhookDelivery).filter(EntWebhookDelivery.id == delivery_id).first()
    if not d:
        raise ValueError("delivery not found")
    row = EntWebhookDelivery(tenant_id=d.tenant_id, webhook_id=d.webhook_id, event=d.event,
                             payload=d.payload, status="delivered", status_code=200,
                             attempts=d.attempts + 1, signature=d.signature, is_replay=True)
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"delivery_id": row.id, "replay_of": delivery_id, "status": row.status}


def list_deliveries(db: Session, *, webhook_id: Optional[int] = None, limit: int = 50,
                    tenant_id: Optional[int] = None) -> List[Dict[str, Any]]:
    q = db.query(EntWebhookDelivery)
    if tenant_id is not None:
        q = q.filter(EntWebhookDelivery.tenant_id == tenant_id)
    if webhook_id is not None:
        q = q.filter(EntWebhookDelivery.webhook_id == webhook_id)
    return [{"delivery_id": d.id, "webhook_id": d.webhook_id, "event": d.event, "status": d.status,
             "status_code": d.status_code, "attempts": d.attempts, "is_replay": d.is_replay,
             "created_at": iso(d.created_at)}
            for d in q.order_by(EntWebhookDelivery.id.desc()).limit(limit).all()]


# ---------------------------------------------------------------------------
# Sandbox request runner + request history + rate-limit testing
# ---------------------------------------------------------------------------

def sandbox_request(db: Session, *, method: str, path: str, body: Optional[dict] = None,
                    api_key_prefix: Optional[str] = None, tenant_id: Optional[int] = None) -> Dict[str, Any]:
    """Record a sandbox API call into request history (deterministic echo response)."""
    latency = 12.0 + (len(path) % 40)
    response = {"echo": {"method": method.upper(), "path": path, "body": body or {}},
                "sandbox": True}
    row = EntApiRequest(tenant_id=tenant_id, method=method.upper(), path=path, status_code=200,
                        latency_ms=latency, api_key_prefix=api_key_prefix, environment="sandbox",
                        request_body=body or {}, response_body=response)
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"request_id": row.id, "status_code": 200, "latency_ms": latency, "response": response}


def request_history(db: Session, *, path: Optional[str] = None, limit: int = 50,
                    tenant_id: Optional[int] = None) -> List[Dict[str, Any]]:
    q = db.query(EntApiRequest)
    if tenant_id is not None:
        q = q.filter(EntApiRequest.tenant_id == tenant_id)
    if path:
        q = q.filter(EntApiRequest.path == path)
    return [{"request_id": r.id, "method": r.method, "path": r.path, "status_code": r.status_code,
             "latency_ms": r.latency_ms, "environment": r.environment, "created_at": iso(r.created_at)}
            for r in q.order_by(EntApiRequest.id.desc()).limit(limit).all()]


def rate_limit_test(db: Session, *, api_key_id: int, requests: int = 100,
                    tenant_id: Optional[int] = None) -> Dict[str, Any]:
    """Simulate ``requests`` calls against a key's per-minute limit."""
    k = db.query(EntApiKey).filter(EntApiKey.id == api_key_id).first()
    if not k:
        raise ValueError("api key not found")
    limit = k.rate_limit_per_min
    allowed = min(requests, limit)
    throttled = max(requests - limit, 0)
    return {"api_key_id": api_key_id, "rate_limit_per_min": limit, "requested": requests,
            "allowed": allowed, "throttled": throttled,
            "throttled_pct": round(100.0 * throttled / requests, 2) if requests else 0.0}


def api_explorer(db: Session) -> Dict[str, Any]:
    """Summarise the mounted OpenAPI surface for the API explorer."""
    try:
        from backend.app.main import app
        paths = sorted({r.path for r in app.routes if getattr(r, "path", "").startswith("/api/")})
        groups: Dict[str, int] = {}
        for p in paths:
            seg = p.split("/")[2] if len(p.split("/")) > 2 else "root"
            groups[seg] = groups.get(seg, 0) + 1
        return {"openapi_url": "/openapi.json", "docs_url": "/docs", "total_paths": len(paths),
                "groups": dict(sorted(groups.items())), "webhook_events": WEBHOOK_EVENTS}
    except Exception:
        return {"openapi_url": "/openapi.json", "docs_url": "/docs", "total_paths": 0,
                "groups": {}, "webhook_events": WEBHOOK_EVENTS}
