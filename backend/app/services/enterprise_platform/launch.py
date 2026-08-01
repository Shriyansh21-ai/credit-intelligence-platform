"""M13 — Enterprise Launch Readiness.

Generates and tracks the checklists that gate a commercial release: production
configuration, deployment, security, operational, release, disaster-recovery
business-continuity, scaling, performance and monitoring. Each checklist is
seeded from a deterministic template, scored as items are completed, and rolled
up into an overall launch-readiness score. Backed by ``ent_checklists``.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from backend.app.models.enterprise_platform import EntChecklist
from .common import iso, safe_div, score_to_grade, utcnow

CHECKLIST_TYPES = ["production", "deployment", "security", "operational", "release",
                   "dr", "bcp", "scaling", "performance", "monitoring"]

# Deterministic templates — each item defaults to done=True where the platform
# already provides the capability (additive tracks), else pending for the team.
TEMPLATES: Dict[str, List[Dict[str, Any]]] = {
    "production": [
        {"key": "env_config", "label": "Production configuration reviewed", "status": "done", "category": "config"},
        {"key": "secrets", "label": "Secrets stored in a vault (no plaintext)", "status": "done", "category": "security"},
        {"key": "migrations", "label": "All migrations reversible and applied", "status": "done", "category": "data"},
        {"key": "rbac", "label": "RBAC roles & permissions finalised", "status": "done", "category": "security"},
        {"key": "backups", "label": "Automated backups configured", "status": "pending", "category": "ops"},
    ],
    "deployment": [
        {"key": "environments", "label": "dev/test/staging/prod environments provisioned", "status": "done", "category": "deploy"},
        {"key": "strategy", "label": "Blue-green / canary strategy chosen", "status": "done", "category": "deploy"},
        {"key": "rollback", "label": "Rollback tested", "status": "done", "category": "deploy"},
        {"key": "release_notes", "label": "Release-notes process in place", "status": "done", "category": "process"},
    ],
    "security": [
        {"key": "zero_trust", "label": "Zero-trust access controls enabled", "status": "done", "category": "security"},
        {"key": "threat_detection", "label": "Threat & anomaly detection live", "status": "done", "category": "security"},
        {"key": "access_reviews", "label": "Access review cadence scheduled", "status": "done", "category": "security"},
        {"key": "key_rotation", "label": "API-key rotation policy set", "status": "done", "category": "security"},
        {"key": "pentest", "label": "Third-party penetration test completed", "status": "pending", "category": "security"},
    ],
    "operational": [
        {"key": "runbooks", "label": "Runbooks authored for top incidents", "status": "done", "category": "ops"},
        {"key": "oncall", "label": "On-call rotation defined", "status": "pending", "category": "ops"},
        {"key": "incident_process", "label": "Incident management process live", "status": "done", "category": "ops"},
        {"key": "sla", "label": "SLA targets defined & tracked", "status": "done", "category": "ops"},
    ],
    "release": [
        {"key": "changelog", "label": "CHANGELOG.md current", "status": "done", "category": "process"},
        {"key": "version", "label": "Semantic version tagged (v1.0.0)", "status": "done", "category": "process"},
        {"key": "docs", "label": "Docs & API reference published", "status": "done", "category": "docs"},
        {"key": "signoff", "label": "Stakeholder sign-off obtained", "status": "pending", "category": "process"},
    ],
    "dr": [
        {"key": "rpo_rto", "label": "RPO/RTO targets documented", "status": "done", "category": "dr"},
        {"key": "restore_test", "label": "Backup restore tested", "status": "pending", "category": "dr"},
        {"key": "failover", "label": "Region failover procedure documented", "status": "done", "category": "dr"},
    ],
    "bcp": [
        {"key": "continuity_plan", "label": "Business continuity plan documented", "status": "done", "category": "bcp"},
        {"key": "comms", "label": "Customer comms / status page ready", "status": "done", "category": "bcp"},
        {"key": "vendor_risk", "label": "Critical-vendor fallback identified", "status": "pending", "category": "bcp"},
    ],
    "scaling": [
        {"key": "horizontal", "label": "Stateless services scale horizontally", "status": "done", "category": "scale"},
        {"key": "capacity_plan", "label": "Capacity planning in place", "status": "done", "category": "scale"},
        {"key": "load_test", "label": "Load test to 3× peak completed", "status": "pending", "category": "scale"},
        {"key": "multi_tenant", "label": "Multi-tenant isolation verified", "status": "done", "category": "scale"},
    ],
    "performance": [
        {"key": "p99", "label": "p99 latency within budget", "status": "done", "category": "perf"},
        {"key": "profiling", "label": "Performance profiling completed", "status": "done", "category": "perf"},
        {"key": "query_opt", "label": "Hot queries indexed & optimised", "status": "done", "category": "perf"},
    ],
    "monitoring": [
        {"key": "tracing", "label": "Distributed tracing enabled", "status": "done", "category": "monitor"},
        {"key": "dashboards", "label": "Operational & executive dashboards live", "status": "done", "category": "monitor"},
        {"key": "alerts", "label": "Alerting on golden signals", "status": "done", "category": "monitor"},
        {"key": "cost", "label": "AI/ML cost monitoring enabled", "status": "done", "category": "monitor"},
    ],
}


def _score(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    total = len(items)
    done = sum(1 for i in items if i.get("status") == "done")
    return {"completed": done, "total": total,
            "readiness_score": round(100.0 * safe_div(done, total, 0.0), 1)}


def generate(db: Session, *, checklist_type: str, tenant_id: Optional[int] = None,
             created_by: Optional[str] = None) -> Dict[str, Any]:
    if checklist_type not in CHECKLIST_TYPES:
        raise ValueError(f"unknown checklist_type '{checklist_type}'")
    items = [dict(i) for i in TEMPLATES.get(checklist_type, [])]
    sc = _score(items)
    row = EntChecklist(tenant_id=tenant_id, checklist_type=checklist_type,
                       title=f"{checklist_type.title()} Readiness Checklist", items=items,
                       completed=sc["completed"], total=sc["total"],
                       readiness_score=sc["readiness_score"],
                       status="ready" if sc["readiness_score"] == 100 else "in_progress",
                       created_by=created_by)
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"checklist_id": row.id, "checklist_type": checklist_type, **sc,
            "grade": score_to_grade(sc["readiness_score"]), "items": items}


def generate_all(db: Session, *, tenant_id: Optional[int] = None,
                 created_by: Optional[str] = None) -> Dict[str, Any]:
    results = [generate(db, checklist_type=ct, tenant_id=tenant_id, created_by=created_by)
               for ct in CHECKLIST_TYPES]
    overall = round(sum(r["readiness_score"] for r in results) / len(results), 1)
    return {"checklists": len(results), "overall_readiness_score": overall,
            "grade": score_to_grade(overall),
            "commercial_ready": overall >= 85,
            "breakdown": {r["checklist_type"]: r["readiness_score"] for r in results}}


def update_item(db: Session, *, checklist_id: int, item_key: str, status: str = "done") -> Dict[str, Any]:
    c = db.query(EntChecklist).filter(EntChecklist.id == checklist_id).first()
    if not c:
        raise ValueError("checklist not found")
    items = [dict(i) for i in (c.items or [])]
    found = False
    for i in items:
        if i.get("key") == item_key:
            i["status"] = status
            found = True
    if not found:
        raise ValueError(f"item '{item_key}' not found")
    c.items = items
    sc = _score(items)
    c.completed = sc["completed"]
    c.total = sc["total"]
    c.readiness_score = sc["readiness_score"]
    c.status = "ready" if sc["readiness_score"] == 100 else "in_progress"
    db.commit()
    return {"checklist_id": checklist_id, **sc, "status": c.status}


def list_checklists(db: Session, *, checklist_type: Optional[str] = None,
                    tenant_id: Optional[int] = None) -> List[Dict[str, Any]]:
    q = db.query(EntChecklist)
    if tenant_id is not None:
        q = q.filter(EntChecklist.tenant_id == tenant_id)
    if checklist_type:
        q = q.filter(EntChecklist.checklist_type == checklist_type)
    return [{"checklist_id": c.id, "checklist_type": c.checklist_type, "title": c.title,
             "completed": c.completed, "total": c.total, "readiness_score": c.readiness_score,
             "status": c.status, "created_at": iso(c.created_at)}
            for c in q.order_by(EntChecklist.id.desc()).all()]


def readiness_summary(db: Session, *, tenant_id: Optional[int] = None) -> Dict[str, Any]:
    """Overall commercial-readiness score across the latest checklist per type."""
    latest: Dict[str, Any] = {}
    q = db.query(EntChecklist)
    if tenant_id is not None:
        q = q.filter(EntChecklist.tenant_id == tenant_id)
    for c in q.order_by(EntChecklist.id.desc()).all():
        if c.checklist_type not in latest:
            latest[c.checklist_type] = c.readiness_score
    if not latest:
        return {"checklists": 0, "overall_readiness_score": None, "commercial_ready": False}
    overall = round(sum(latest.values()) / len(latest), 1)
    return {"checklists": len(latest), "overall_readiness_score": overall,
            "grade": score_to_grade(overall), "commercial_ready": overall >= 85,
            "by_type": latest, "generated_at": iso(utcnow())}
