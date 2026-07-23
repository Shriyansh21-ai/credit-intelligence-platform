"""Connector observability dashboard (Milestone 13).

Aggregates the live in-process metrics (:data:`base.observability.metrics`),
durable call logs and per-connector circuit/health state into the payloads that
back the observability dashboard: latency, availability, failure rate, retries,
success %, response times, health status, circuit-breaker state and provider
metrics.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from backend.app.models.integrations import ConnectorCallLog
from backend.app.services.integrations.base.observability import metrics
from backend.app.services.integrations.base.registry import registry
from backend.app.services.integrations.factory import get_connector, register_all


def metrics_snapshot() -> Dict[str, Any]:
    return {"providers": metrics.snapshot(), "totals": metrics.totals()}


def call_log_stats(db: Session, *, since_hours: int = 24) -> Dict[str, Any]:
    since = datetime.utcnow() - timedelta(hours=since_hours)
    rows = db.query(ConnectorCallLog).filter(ConnectorCallLog.created_at >= since).all()
    total = len(rows)
    by_connector: Dict[str, Dict[str, Any]] = {}
    for r in rows:
        b = by_connector.setdefault(r.connector_key, {
            "calls": 0, "successes": 0, "failures": 0, "cache_hits": 0,
            "total_latency": 0.0, "retries": 0})
        b["calls"] += 1
        b["successes"] += 1 if r.success else 0
        b["failures"] += 0 if r.success else 1
        b["cache_hits"] += 1 if r.from_cache else 0
        b["retries"] += max(0, (r.attempts or 1) - 1)
        b["total_latency"] += r.latency_ms or 0.0
    for b in by_connector.values():
        c = b.pop("total_latency")
        b["avg_latency_ms"] = round(c / b["calls"], 3) if b["calls"] else 0.0
        b["success_rate"] = round(b["successes"] / b["calls"], 4) if b["calls"] else 0.0
    return {"window_hours": since_hours, "total_calls": total, "by_connector": by_connector}


def health_all(db: Optional[Session] = None) -> List[Dict[str, Any]]:
    """Run a health check for each registered connector using its configured mode."""
    register_all()
    reports = []
    for entry in registry.describe():
        key = entry["key"]
        try:
            conn = get_connector(db, key)
            reports.append(conn.health_check(db=db).to_dict())
        except Exception as exc:  # noqa: BLE001
            reports.append({"provider": key, "category": entry["category"],
                            "status": "unknown", "detail": str(exc)})
    return reports


def connector_overview(db: Session) -> Dict[str, Any]:
    """Per-connector summary combining config, live metrics and recent call stats."""
    from backend.app.services.integrations import config as cfg_svc
    register_all()

    live = {m["category"] + ":" + m["provider"]: m for m in metrics.snapshot()}
    log_stats = call_log_stats(db)["by_connector"]
    configs = {c["connector_key"]: c for c in cfg_svc.list_configs(db)}

    connectors = []
    for entry in registry.describe():
        key = entry["key"]
        cfg = configs.get(key, {})
        mode = cfg.get("provider_mode", "mock")
        connectors.append({
            "connector_key": key,
            "category": entry["category"],
            "modes_available": entry["modes"],
            "active_mode": mode,
            "enabled": cfg.get("enabled", True),
            "recent": log_stats.get(key, {}),
        })
    return {
        "connectors": connectors,
        "live_metrics": list(live.values()),
        "totals": metrics.totals(),
    }
