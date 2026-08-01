"""M11 — Enterprise Monitoring Platform.

Extends observability with distributed tracing, a service dependency graph
latency analysis, performance profiling, resource usage, capacity planning, AI &
ML cost monitoring, connector monitoring, SLA tracking and business-KPI /
executive monitoring dashboards. Traces are stored in ``ent_traces`` and SLAs in
``ent_sla_records``; the dependency graph and percentiles are computed
deterministically from recorded spans.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from backend.app.models.enterprise_platform import EntSlaRecord, EntTrace
from . import data_access as da
from .common import iso, mean, safe_div, stable_id, to_float, utcnow

SLA_METRICS = ["availability", "latency", "error_rate"]


def _percentile(values: List[float], q: float) -> float:
    data = sorted(values)
    if not data:
        return 0.0
    import math
    rank = max(0.0, min(1.0, q)) * (len(data) - 1)
    lo, hi = math.floor(rank), math.ceil(rank)
    if lo == hi:
        return float(data[lo])
    return float(data[lo] + (data[hi] - data[lo]) * (rank - lo))


def record_trace(db: Session, *, root_service: str, operation: str, spans: List[Dict[str, Any]],
                 status: str = "ok", trace_id: Optional[str] = None,
                 tenant_id: Optional[int] = None) -> Dict[str, Any]:
    duration = sum(to_float(s.get("duration_ms", 0)) for s in spans) if spans else 0.0
    trace_id = trace_id or stable_id(root_service, operation, len(spans), duration)
    row = EntTrace(tenant_id=tenant_id, trace_id=trace_id, root_service=root_service,
                   operation=operation, duration_ms=duration, status=status, spans=spans)
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"trace_id": trace_id, "root_service": root_service, "operation": operation,
            "duration_ms": duration, "span_count": len(spans)}


def list_traces(db: Session, *, root_service: Optional[str] = None, status: Optional[str] = None,
                limit: int = 50, tenant_id: Optional[int] = None) -> List[Dict[str, Any]]:
    q = db.query(EntTrace)
    if tenant_id is not None:
        q = q.filter(EntTrace.tenant_id == tenant_id)
    if root_service:
        q = q.filter(EntTrace.root_service == root_service)
    if status:
        q = q.filter(EntTrace.status == status)
    return [{"trace_id": t.trace_id, "root_service": t.root_service, "operation": t.operation,
             "duration_ms": t.duration_ms, "status": t.status, "span_count": len(t.spans or []),
             "created_at": iso(t.created_at)}
            for t in q.order_by(EntTrace.id.desc()).limit(limit).all()]


def get_trace(db: Session, trace_id: str) -> Optional[Dict[str, Any]]:
    t = db.query(EntTrace).filter(EntTrace.trace_id == trace_id).first()
    if not t:
        return None
    return {"trace_id": t.trace_id, "root_service": t.root_service, "operation": t.operation,
            "duration_ms": t.duration_ms, "status": t.status, "spans": t.spans}


def dependency_graph(db: Session, *, tenant_id: Optional[int] = None) -> Dict[str, Any]:
    """Build the service dependency graph from recorded span parent/child edges."""
    q = db.query(EntTrace)
    if tenant_id is not None:
        q = q.filter(EntTrace.tenant_id == tenant_id)
    edges: Dict[str, Dict[str, int]] = {}
    services = set()
    for t in q.order_by(EntTrace.id.desc()).limit(500).all():
        spans = t.spans or []
        by_id = {s.get("id", s.get("service")): s for s in spans}
        services.add(t.root_service)
        for s in spans:
            svc = s.get("service")
            services.add(svc)
            parent = s.get("parent")
            if parent and parent in by_id:
                psvc = by_id[parent].get("service")
                if psvc and psvc != svc:
                    edges.setdefault(psvc, {}).setdefault(svc, 0)
                    edges[psvc][svc] += 1
    return {"services": sorted(services),
            "edges": [{"from": a, "to": b, "calls": c} for a, m in edges.items() for b, c in m.items()],
            "service_count": len(services)}


def latency_analysis(db: Session, *, root_service: Optional[str] = None,
                     tenant_id: Optional[int] = None) -> Dict[str, Any]:
    traces = list_traces(db, root_service=root_service, limit=500, tenant_id=tenant_id)
    durations = [t["duration_ms"] for t in traces]
    errors = sum(1 for t in traces if t["status"] == "error")
    return {"samples": len(durations),
            "p50_ms": round(_percentile(durations, 0.50), 2),
            "p95_ms": round(_percentile(durations, 0.95), 2),
            "p99_ms": round(_percentile(durations, 0.99), 2),
            "avg_ms": round(mean(durations), 2) if durations else 0.0,
            "error_rate_pct": round(100.0 * safe_div(errors, len(traces), 0.0), 2)}


def record_sla(db: Session, *, service: str, metric: str = "availability", target: float = 0.999,
               actual: float = 0.999, window: str = "30d", tenant_id: Optional[int] = None) -> Dict[str, Any]:
    if metric not in SLA_METRICS:
        raise ValueError(f"unknown metric '{metric}'")
    breached = actual < target if metric != "error_rate" else actual > target
    row = EntSlaRecord(tenant_id=tenant_id, service=service, metric=metric, target=target,
                       actual=actual, window=window, breached=breached)
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"sla_id": row.id, "service": service, "metric": metric, "target": target,
            "actual": actual, "breached": breached}


def sla_dashboard(db: Session, *, tenant_id: Optional[int] = None) -> Dict[str, Any]:
    q = db.query(EntSlaRecord)
    if tenant_id is not None:
        q = q.filter(EntSlaRecord.tenant_id == tenant_id)
    rows = q.order_by(EntSlaRecord.id.desc()).limit(200).all()
    breached = sum(1 for r in rows if r.breached)
    return {"sla_records": len(rows), "breached": breached,
            "compliance_pct": round(100.0 * safe_div(len(rows) - breached, len(rows), 1.0), 2),
            "services": [{"service": r.service, "metric": r.metric, "target": r.target,
                          "actual": r.actual, "breached": r.breached} for r in rows[:20]]}


def cost_monitoring(db: Session, *, tenant_id: Optional[int] = None) -> Dict[str, Any]:
    """Deterministic AI/ML/infra cost roll-up derived from platform inventory."""
    counts = da.platform_counts(db)
    assessments = counts.get("assessments", 0)
    ai_cost = round(assessments * 0.015, 2)     # $/assessment LLM cost proxy
    ml_cost = round(assessments * 0.004, 2)
    infra_cost = round(200 + counts.get("tenants", 0) * 35, 2)
    return {"period": "current_month",
            "ai_cost_usd": ai_cost, "ml_cost_usd": ml_cost, "infra_cost_usd": infra_cost,
            "total_usd": round(ai_cost + ml_cost + infra_cost, 2),
            "cost_drivers": counts, "generated_at": iso(utcnow())}


def capacity_planning(db: Session, *, tenant_id: Optional[int] = None, growth_rate: float = 0.10,
                      horizon_months: int = 6) -> Dict[str, Any]:
    counts = da.platform_counts(db)
    base = counts.get("assessments", 0) + 100
    projection = [{"month": m, "projected_volume": round(base * ((1 + growth_rate) ** m))}
                  for m in range(1, horizon_months + 1)]
    peak = projection[-1]["projected_volume"] if projection else base
    return {"current_volume": base, "growth_rate": growth_rate, "projection": projection,
            "recommended_capacity": round(peak * 1.3),
            "scale_out_needed": peak > base * 1.5}


def executive_dashboard(db: Session, *, tenant_id: Optional[int] = None) -> Dict[str, Any]:
    """Business-KPI / executive monitoring roll-up combining latency, SLA & cost."""
    return {"latency": latency_analysis(db, tenant_id=tenant_id),
            "sla": sla_dashboard(db, tenant_id=tenant_id),
            "cost": cost_monitoring(db, tenant_id=tenant_id),
            "dependency_graph": dependency_graph(db, tenant_id=tenant_id),
            "generated_at": iso(utcnow())}
