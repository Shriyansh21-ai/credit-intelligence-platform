"""Observability platform (Phase 8, Milestone 9).

Correlation IDs, distributed tracing spans, an in-process metrics registry,
slow-query detection, structured logging and error analytics — shaped to be
OpenTelemetry-compatible so the durable sinks can be swapped for OTLP exporters
without changing call sites.

* Correlation/trace IDs live in contextvars, set by the observability
  middleware (see ``core/observability_middleware.py``).
* :func:`record_span` persists a :class:`TraceSpan`; :func:`trace` is a context
  manager that times a block and records it.
* :class:`MetricsRegistry` holds counters / gauges / histograms in memory and is
  exposed via the observability + admin routes.
"""

from __future__ import annotations

import contextvars
import threading
import time
import uuid
from collections import defaultdict, deque
from contextlib import contextmanager
from typing import Any, Deque, Dict, List, Optional

from sqlalchemy.orm import Session

from backend.app.models.platform_ops import TraceSpan

# -- correlation / trace context -------------------------------------------
_correlation_id: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "obs_correlation_id", default=None)
_trace_id: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "obs_trace_id", default=None)
_span_stack: contextvars.ContextVar[Optional[list]] = contextvars.ContextVar(
    "obs_span_stack", default=None)


def new_correlation_id() -> str:
    return uuid.uuid4().hex


def start_context(correlation_id: Optional[str] = None) -> str:
    cid = correlation_id or new_correlation_id()
    _correlation_id.set(cid)
    _trace_id.set(uuid.uuid4().hex)
    _span_stack.set([])
    return cid


def current_correlation_id() -> Optional[str]:
    return _correlation_id.get()


def current_trace_id() -> Optional[str]:
    return _trace_id.get()


# ===========================================================================
# Metrics registry (in-memory; Prometheus/OTLP-swappable)
# ===========================================================================
class MetricsRegistry:
    def __init__(self):
        self._lock = threading.Lock()
        self._counters: Dict[str, float] = defaultdict(float)
        self._gauges: Dict[str, float] = {}
        self._histograms: Dict[str, List[float]] = defaultdict(list)

    def incr(self, name: str, value: float = 1.0, **tags) -> None:
        with self._lock:
            self._counters[_key(name, tags)] += value

    def gauge(self, name: str, value: float, **tags) -> None:
        with self._lock:
            self._gauges[_key(name, tags)] = value

    def observe(self, name: str, value: float, **tags) -> None:
        with self._lock:
            self._histograms[_key(name, tags)].append(value)

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            hist = {}
            for k, vals in self._histograms.items():
                if not vals:
                    continue
                ordered = sorted(vals)
                hist[k] = {
                    "count": len(ordered),
                    "avg": round(sum(ordered) / len(ordered), 3),
                    "p50": _pct(ordered, 50), "p95": _pct(ordered, 95),
                    "p99": _pct(ordered, 99), "max": ordered[-1],
                }
            return {
                "counters": dict(self._counters),
                "gauges": dict(self._gauges),
                "histograms": hist,
            }

    def reset(self) -> None:
        with self._lock:
            self._counters.clear()
            self._gauges.clear()
            self._histograms.clear()


def _key(name: str, tags: Dict[str, Any]) -> str:
    if not tags:
        return name
    return name + "{" + ",".join(f"{k}={v}" for k, v in sorted(tags.items())) + "}"


def _pct(ordered: List[float], p: int) -> float:
    if not ordered:
        return 0.0
    idx = min(len(ordered) - 1, int(round((p / 100.0) * (len(ordered) - 1))))
    return round(ordered[idx], 3)


metrics = MetricsRegistry()


# ===========================================================================
# Tracing
# ===========================================================================
def record_span(db: Session, name: str, *, duration_ms: float, kind: str = "internal",
                service: str = "api", status: str = "ok", tenant_id: Optional[int] = None,
                parent_span_id: Optional[str] = None,
                attributes: Optional[Dict] = None) -> TraceSpan:
    span = TraceSpan(
        correlation_id=current_correlation_id() or new_correlation_id(),
        trace_id=current_trace_id() or uuid.uuid4().hex,
        span_id=uuid.uuid4().hex, parent_span_id=parent_span_id,
        tenant_id=tenant_id, name=name, kind=kind, service=service,
        status=status, duration_ms=duration_ms, attributes=attributes or {},
    )
    db.add(span)
    db.commit()
    db.refresh(span)
    metrics.observe("span.duration_ms", duration_ms, name=name)
    return span


@contextmanager
def trace(db: Session, name: str, *, kind: str = "internal", service: str = "api",
          tenant_id: Optional[int] = None, attributes: Optional[Dict] = None):
    start = time.perf_counter()
    status = "ok"
    try:
        yield
    except Exception:
        status = "error"
        raise
    finally:
        elapsed = (time.perf_counter() - start) * 1000.0
        try:
            record_span(db, name, duration_ms=elapsed, kind=kind, service=service,
                        tenant_id=tenant_id, status=status, attributes=attributes)
        except Exception:
            db.rollback()


def trace_timeline(db: Session, correlation_id: str) -> List[TraceSpan]:
    return (
        db.query(TraceSpan)
        .filter(TraceSpan.correlation_id == correlation_id)
        .order_by(TraceSpan.started_at)
        .all()
    )


# ===========================================================================
# Slow-query detection + error analytics (in-memory rolling windows)
# ===========================================================================
_SLOW_QUERY_MS = 200.0
_slow_queries: Deque[dict] = deque(maxlen=200)
_errors: Deque[dict] = deque(maxlen=500)
_error_counts: Dict[str, int] = defaultdict(int)


def record_query(statement: str, duration_ms: float, *, tenant_id: Optional[int] = None) -> None:
    metrics.observe("db.query_ms", duration_ms)
    if duration_ms >= _SLOW_QUERY_MS:
        _slow_queries.append({
            "statement": statement[:500], "duration_ms": round(duration_ms, 2),
            "tenant_id": tenant_id, "correlation_id": current_correlation_id(),
        })
        metrics.incr("db.slow_query")


def slow_queries(limit: int = 50) -> List[dict]:
    return list(_slow_queries)[-limit:]


def record_error(kind: str, message: str, *, path: Optional[str] = None,
                 tenant_id: Optional[int] = None) -> None:
    _error_counts[kind] += 1
    _errors.append({
        "kind": kind, "message": message[:500], "path": path,
        "tenant_id": tenant_id, "correlation_id": current_correlation_id(),
    })
    metrics.incr("errors", kind=kind)


def error_analytics(limit: int = 20) -> Dict[str, Any]:
    top = sorted(_error_counts.items(), key=lambda kv: kv[1], reverse=True)[:limit]
    return {
        "total": sum(_error_counts.values()),
        "by_kind": dict(top),
        "recent": list(_errors)[-limit:],
    }


# ===========================================================================
# Health + dependency / service map
# ===========================================================================
_DEPENDENCIES = [
    {"name": "database", "kind": "db", "critical": True},
    {"name": "cache", "kind": "cache", "critical": False},
    {"name": "object-storage", "kind": "storage", "critical": False},
    {"name": "job-broker", "kind": "queue", "critical": False},
]


def health_report(db: Optional[Session] = None) -> Dict[str, Any]:
    checks = []
    db_ok = True
    if db is not None:
        try:
            db.execute  # attribute access; a lightweight liveness ping
            from sqlalchemy import text
            db.execute(text("SELECT 1"))
        except Exception:
            db_ok = False
    checks.append({"name": "database", "status": "up" if db_ok else "down", "critical": True})
    for dep in _DEPENDENCIES[1:]:
        checks.append({"name": dep["name"], "status": "up", "critical": dep["critical"]})
    healthy = all(c["status"] == "up" for c in checks if c["critical"])
    return {
        "status": "healthy" if healthy else "degraded",
        "checks": checks,
        "metrics": metrics.snapshot(),
    }


def service_map() -> Dict[str, Any]:
    return {
        "service": "ai-credit-platform",
        "dependencies": _DEPENDENCIES,
        "edges": [{"from": "api", "to": d["name"]} for d in _DEPENDENCIES],
    }
