"""M14 — AI monitoring.

Continuously measures the health of the AI platform and raises incidents when
quality degrades. Monitored dimensions: hallucination rate, prompt drift
embedding/output drift, retrieval quality, latency, cost, model accuracy
feedback score and business-KPI impact.

Metrics are computed from the artifacts the platform already produces — M5
evaluations, M1 RAG queries and M11 feedback — so monitoring needs no separate
instrumentation and is fully deterministic. ``run_monitoring`` snapshots the
current metrics into ``aip_ai_metrics`` and opens ``aip_ai_incidents`` on breach
``dashboard`` rolls everything up for the operations console.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from backend.app.models.ai_platform import (
    AIPAgentRun, AIPEvaluation, AIPFeedback, AIPIncident, AIPMetric, AIPRagQuery,
)
from backend.app.services.ai_platform import common

# Breach thresholds: (metric, comparator, threshold, severity).
_THRESHOLDS = [
    ("hallucination", "gt", 0.30, "high"),
    ("retrieval_quality", "lt", 0.40, "medium"),
    ("latency", "gt", 3000.0, "medium"),
    ("cost", "gt", 0.08, "low"),
    ("accuracy", "lt", 0.60, "high"),
    ("feedback_score", "lt", 0.50, "high"),
    ("drift", "gt", 0.25, "medium"),
]


def _mean(values: List[float]) -> Optional[float]:
    values = [v for v in values if v is not None]
    return sum(values) / len(values) if values else None


def _breached(value: Optional[float], comparator: str, threshold: float) -> bool:
    if value is None:
        return False
    return value > threshold if comparator == "gt" else value < threshold


def compute_metrics(db: Session, *, tenant_id: Optional[int] = None) -> Dict[str, Any]:
    evals = (db.query(AIPEvaluation).filter(AIPEvaluation.tenant_id == tenant_id)
             .order_by(AIPEvaluation.id).all())
    queries = db.query(AIPRagQuery).filter(AIPRagQuery.tenant_id == tenant_id).all()
    feedback = db.query(AIPFeedback).filter(AIPFeedback.tenant_id == tenant_id).all()

    hallucination = _mean([(e.metrics or {}).get("hallucination_rate") for e in evals])
    retrieval_quality = _mean([(e.scores or {}).get("groundedness") for e in evals])
    accuracy = _mean([e.overall_score for e in evals])
    latency = _mean([(e.metrics or {}).get("latency_ms") for e in evals]
                    + [q.latency_ms for q in queries])
    cost = _mean([(e.metrics or {}).get("cost_usd") for e in evals])
    feedback_score = _mean([f.rating for f in feedback])

    # Drift: change in mean accuracy between the older and newer half of evals.
    drift = None
    if len(evals) >= 4:
        mid = len(evals) // 2
        old = _mean([e.overall_score for e in evals[:mid]])
        new = _mean([e.overall_score for e in evals[mid:]])
        if old is not None and new is not None:
            drift = abs(old - new)

    return {
        "hallucination": common.round_opt(hallucination, 4),
        "retrieval_quality": common.round_opt(retrieval_quality, 4),
        "accuracy": common.round_opt(accuracy, 4),
        "latency": common.round_opt(latency, 2),
        "cost": common.round_opt(cost, 6),
        "feedback_score": common.round_opt(feedback_score, 4),
        "drift": common.round_opt(drift, 4),
        "sample": {"evaluations": len(evals), "queries": len(queries),
                   "feedback": len(feedback)},
    }


def run_monitoring(db: Session, *, tenant_id: Optional[int] = None,
                   thresholds: Optional[List] = None) -> Dict[str, Any]:
    metrics = compute_metrics(db, tenant_id=tenant_id)
    # Snapshot metrics.
    for name in ("hallucination", "retrieval_quality", "accuracy", "latency",
                 "cost", "feedback_score", "drift"):
        val = metrics.get(name)
        if val is None:
            continue
        db.add(AIPMetric(tenant_id=tenant_id, metric_type=name, subject="platform",
                         value=float(val), window="cumulative",
                         meta={"sample": metrics["sample"]}, created_at=common.utcnow()))
    db.commit()

    # Evaluate thresholds → incidents.
    checks = thresholds or _THRESHOLDS
    incidents: List[Dict[str, Any]] = []
    for name, comparator, threshold, severity in checks:
        val = metrics.get(name)
        if _breached(val, comparator, threshold):
            # Avoid duplicate open incidents for the same metric.
            existing = (db.query(AIPIncident)
                        .filter(AIPIncident.tenant_id == tenant_id,
                                AIPIncident.incident_type == name,
                                AIPIncident.status == "open").first())
            if existing:
                existing.value = float(val)
                incidents.append({"incident_id": existing.id, "type": name, "value": val,
                                  "severity": severity, "status": "open"})
                continue
            inc = AIPIncident(tenant_id=tenant_id, incident_type=name, severity=severity,
                              subject="platform",
                              description=f"{name} {comparator} {threshold} (observed {val})",
                              value=float(val), threshold=float(threshold), status="open",
                              detail={"comparator": comparator}, created_at=common.utcnow())
            db.add(inc)
            db.commit()
            db.refresh(inc)
            incidents.append({"incident_id": inc.id, "type": name, "value": val,
                              "severity": severity, "status": "open"})
    db.commit()
    return {"metrics": metrics, "incidents": incidents,
            "incident_count": len(incidents), "healthy": not incidents}


def record_metric(db: Session, *, metric_type: str, value: float,
                  subject: Optional[str] = None, unit: Optional[str] = None,
                  window: Optional[str] = None, meta: Optional[Dict[str, Any]] = None,
                  tenant_id: Optional[int] = None) -> AIPMetric:
    row = AIPMetric(tenant_id=tenant_id, metric_type=metric_type, subject=subject,
                    value=value, unit=unit, window=window, meta=meta or {},
                    created_at=common.utcnow())
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def resolve_incident(db: Session, *, incident_id: int) -> AIPIncident:
    inc = db.query(AIPIncident).filter(AIPIncident.id == incident_id).first()
    if inc is None:
        raise ValueError("incident not found")
    inc.status = "resolved"
    inc.resolved_at = common.utcnow()
    db.commit()
    db.refresh(inc)
    return inc


def list_incidents(db, *, tenant_id=None, status=None, limit=100) -> List[Dict[str, Any]]:
    q = db.query(AIPIncident).filter(AIPIncident.tenant_id == tenant_id)
    if status:
        q = q.filter(AIPIncident.status == status)
    return [{"incident_id": i.id, "type": i.incident_type, "severity": i.severity,
             "value": i.value, "threshold": i.threshold, "status": i.status,
             "description": i.description, "created_at": common.iso(i.created_at)}
            for i in q.order_by(AIPIncident.id.desc()).limit(limit).all()]


def dashboard(db: Session, *, tenant_id: Optional[int] = None) -> Dict[str, Any]:
    metrics = compute_metrics(db, tenant_id=tenant_id)
    open_incidents = list_incidents(db, tenant_id=tenant_id, status="open")
    # Latest recorded metric per type for a trend snapshot.
    recent = (db.query(AIPMetric).filter(AIPMetric.tenant_id == tenant_id)
              .order_by(AIPMetric.id.desc()).limit(50).all())
    latest_by_type: Dict[str, float] = {}
    for m in recent:
        latest_by_type.setdefault(m.metric_type, m.value)
    health = "healthy" if not open_incidents else (
        "critical" if any(i["severity"] in ("high", "critical") for i in open_incidents) else "degraded")
    return {"health": health, "metrics": metrics,
            "open_incidents": open_incidents, "open_incident_count": len(open_incidents),
            "latest_metrics": latest_by_type}
