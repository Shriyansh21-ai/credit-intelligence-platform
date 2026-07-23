"""Customer 360 aggregation (Milestone 10).

Assembles one unified enterprise profile from every subsystem — the application,
assessment, financial analysis, ML results, documents, GST/MCA/bureau/ERP/payment
snapshots, bank-statement analytics, collateral, monitoring, tasks, approvals,
audit and a derived relationship network + timeline.

Each section is loaded defensively: a missing table (isolated test) or absent
data degrades that section to ``None``/``[]`` rather than failing the whole
profile. The result is the complete customer journey in a single payload.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session


def _safe(db: Session, fn, default):
    try:
        return fn()
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
        return default


def build_profile(
    db: Session,
    *,
    application_id: Optional[int] = None,
    entity_ref: Optional[str] = None,
) -> Dict[str, Any]:
    """Build the Customer 360 profile for an application and/or entity reference."""
    application = None
    if application_id is not None:
        application = _safe(db, lambda: _load_application(db, application_id), None)
        # Derive an entity_ref from the application if not supplied.
        if entity_ref is None and application is not None:
            entity_ref = application.get("gstin") or application.get("pan")

    sections: Dict[str, Any] = {
        "application": application,
        "entity_ref": entity_ref,
        "assessment": _safe(db, lambda: _load_assessment(db, application), None),
        "financial_analysis": _safe(db, lambda: _load_financials(db, application), None),
        "ml_results": _safe(db, lambda: _load_ml(db, application), []),
        "documents": _safe(db, lambda: _load_documents(db, application), []),
        "gst": _safe(db, lambda: _load_snapshot(db, "gst", entity_ref), None),
        "mca": _safe(db, lambda: _load_snapshot(db, "mca", entity_ref), None),
        "bureau": _safe(db, lambda: _load_snapshot(db, "bureau", entity_ref), None),
        "erp": _safe(db, lambda: _load_snapshot(db, "erp", entity_ref), None),
        "payments": _safe(db, lambda: _load_snapshot(db, "payments", entity_ref), None),
        "bank_analytics": _safe(db, lambda: _load_bank_analytics(db, entity_ref), None),
        "collateral": _safe(db, lambda: _load_collateral(db, application_id, entity_ref), {}),
        "monitoring": _safe(db, lambda: _load_monitoring(db, application_id), []),
        "tasks": _safe(db, lambda: _load_tasks(db, application_id), []),
        "approvals": _safe(db, lambda: _load_approvals(db, application_id), []),
        "audit": _safe(db, lambda: _load_audit(db, application_id), []),
    }
    sections["relationship_network"] = _safe(db, lambda: _relationship_network(sections), {})
    sections["timeline"] = _safe(db, lambda: _timeline(sections), [])
    sections["completeness"] = _completeness(sections)
    return sections


# ---------------------------------------------------------------------------
# Section loaders
# ---------------------------------------------------------------------------
def _load_application(db: Session, application_id: int) -> Optional[Dict[str, Any]]:
    from backend.app.models.application import Application
    a = db.query(Application).get(application_id)
    if a is None:
        return None
    return {
        "id": a.id, "reference": a.reference, "company_name": a.company_name,
        "industry": a.industry, "gstin": a.gstin, "pan": a.pan, "loan_id": a.loan_id,
        "requested_amount": a.requested_amount, "status": a.status,
        "risk_rating": a.risk_rating, "risk_grade": a.risk_grade,
        "assessment_id": a.assessment_id,
        "created_at": a.created_at.isoformat() if a.created_at else None,
    }


def _load_assessment(db: Session, application: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not application or not application.get("assessment_id"):
        return None
    from backend.app.models.enterprise_assessment import EnterpriseAssessment
    a = db.query(EnterpriseAssessment).get(application["assessment_id"])
    if a is None:
        return None
    return {
        "id": a.id, "company_name": a.company_name, "industry": a.industry,
        "enterprise_credit_score": a.enterprise_credit_score,
        "probability_of_default": a.probability_of_default,
        "expected_loss": a.expected_loss, "risk_rating": a.risk_rating,
        "recommended_loan_amount": a.recommended_loan_amount,
        "loan_recommendation": a.loan_recommendation,
    }


def _load_financials(db: Session, application: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not application or not application.get("assessment_id"):
        return None
    from backend.app.models.financial_analysis import FinancialAnalysis
    f = (db.query(FinancialAnalysis)
         .filter(FinancialAnalysis.assessment_id == application["assessment_id"])
         .order_by(FinancialAnalysis.id.desc()).first())
    if f is None:
        return None
    return {"id": f.id, "assessment_id": f.assessment_id}


def _load_ml(db: Session, application: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not application or not application.get("assessment_id"):
        return []
    from backend.app.models.risk_explanation import RiskExplanation
    rows = (db.query(RiskExplanation)
            .filter(RiskExplanation.assessment_id == application["assessment_id"])
            .order_by(RiskExplanation.id.desc()).limit(5).all())
    return [{"id": r.id, "assessment_id": r.assessment_id} for r in rows]


def _load_documents(db: Session, application: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not application or not application.get("assessment_id"):
        return []
    from backend.app.models.document import Document
    rows = (db.query(Document)
            .filter(Document.assessment_id == application["assessment_id"])
            .order_by(Document.id.desc()).all())
    return [{"id": d.id, "document_type": d.document_type, "filename": d.original_filename,
             "status": d.status} for d in rows]


def _load_snapshot(db: Session, connector_key: str, entity_ref: Optional[str]) -> Optional[Dict[str, Any]]:
    if not entity_ref:
        return None
    from backend.app.models.integrations import IntegrationSnapshot
    rows = (db.query(IntegrationSnapshot)
            .filter(IntegrationSnapshot.connector_key == connector_key,
                    IntegrationSnapshot.entity_ref == entity_ref,
                    IntegrationSnapshot.is_current.is_(True))
            .all())
    if not rows:
        return None
    return {r.dataset: r.payload for r in rows}


def _load_bank_analytics(db: Session, entity_ref: Optional[str]) -> Optional[Dict[str, Any]]:
    if not entity_ref:
        return None
    from backend.app.models.integrations import StatementAnalytics
    row = (db.query(StatementAnalytics)
           .filter(StatementAnalytics.entity_ref == entity_ref)
           .order_by(StatementAnalytics.id.desc()).first())
    if row is None:
        return None
    return {"bank_health_score": row.bank_health_score, "scope": row.scope,
            "metrics": row.metrics}


def _load_collateral(db: Session, application_id: Optional[int], entity_ref: Optional[str]) -> Dict[str, Any]:
    from backend.app.services.integrations.collateral import service as coll_svc
    if application_id is not None:
        items = coll_svc.list_for_application(db, application_id)
        summary = coll_svc.coverage_summary(db, application_id=application_id)
    elif entity_ref is not None:
        items = coll_svc.list_for_entity(db, entity_ref)
        summary = coll_svc.coverage_summary(db, entity_ref=entity_ref)
    else:
        return {}
    return {"summary": summary, "items": [coll_svc.to_dict(i) for i in items]}


def _load_monitoring(db: Session, application_id: Optional[int]) -> List[Dict[str, Any]]:
    if application_id is None:
        return []
    from backend.app.models.monitoring import MonitoringRecord
    rows = (db.query(MonitoringRecord)
            .filter(MonitoringRecord.application_id == application_id)
            .order_by(MonitoringRecord.recorded_at.desc()).limit(20).all())
    return [{"id": r.id, "record_type": r.record_type, "health_score": r.health_score,
             "risk_rating": r.risk_rating, "payment_status": r.payment_status,
             "recorded_at": r.recorded_at.isoformat() if r.recorded_at else None} for r in rows]


def _load_tasks(db: Session, application_id: Optional[int]) -> List[Dict[str, Any]]:
    if application_id is None:
        return []
    from backend.app.models.task import Task
    rows = (db.query(Task).filter(Task.application_id == application_id)
            .order_by(Task.id.desc()).all())
    return [{"id": t.id, "title": t.title, "status": t.status, "priority": t.priority,
             "task_type": t.task_type} for t in rows]


def _load_approvals(db: Session, application_id: Optional[int]) -> List[Dict[str, Any]]:
    if application_id is None:
        return []
    from backend.app.models.approval import ApprovalDecision
    rows = (db.query(ApprovalDecision).filter(ApprovalDecision.application_id == application_id)
            .order_by(ApprovalDecision.created_at.desc()).all())
    return [{"id": d.id, "action": d.action, "stage_name": d.stage_name,
             "actor_email": d.actor_email, "to_status": d.to_status,
             "created_at": d.created_at.isoformat() if d.created_at else None} for d in rows]


def _load_audit(db: Session, application_id: Optional[int]) -> List[Dict[str, Any]]:
    if application_id is None:
        return []
    from backend.app.models.audit import AuditLog
    rows = (db.query(AuditLog)
            .filter(AuditLog.entity_type == "application", AuditLog.entity_id == application_id)
            .order_by(AuditLog.id.desc()).limit(25).all())
    return [{"id": r.id, "action": r.action,
             "created_at": r.created_at.isoformat() if getattr(r, "created_at", None) else None} for r in rows]


# ---------------------------------------------------------------------------
# Derived views
# ---------------------------------------------------------------------------
def _relationship_network(sections: Dict[str, Any]) -> Dict[str, Any]:
    """Build a director/company relationship graph from the MCA snapshot."""
    mca = sections.get("mca") or {}
    nodes: List[Dict[str, Any]] = []
    edges: List[Dict[str, Any]] = []
    app = sections.get("application") or {}
    root = app.get("company_name") or sections.get("entity_ref") or "Entity"
    nodes.append({"id": root, "type": "company", "root": True})

    net = (mca.get("get_director_network") or {}).get("network", []) if mca else []
    for d in net:
        nodes.append({"id": d.get("din"), "type": "director", "name": d.get("name")})
        edges.append({"from": root, "to": d.get("din"), "relationship": "director_of"})
        for c in d.get("linked_companies", []):
            cid = c.get("cin")
            nodes.append({"id": cid, "type": "company"})
            edges.append({"from": d.get("din"), "to": cid, "relationship": "director_of"})

    rels = (mca.get("get_company_relationships") or {}).get("relationships", []) if mca else []
    for r in rels:
        nodes.append({"id": r.get("related_cin"), "type": "company"})
        edges.append({"from": root, "to": r.get("related_cin"), "relationship": r.get("relationship")})

    # Dedup nodes by id.
    seen = set()
    unique_nodes = []
    for n in nodes:
        if n["id"] in seen:
            continue
        seen.add(n["id"])
        unique_nodes.append(n)
    return {"nodes": unique_nodes, "edges": edges, "node_count": len(unique_nodes), "edge_count": len(edges)}


def _timeline(sections: Dict[str, Any]) -> List[Dict[str, Any]]:
    events: List[Dict[str, Any]] = []
    app = sections.get("application")
    if app and app.get("created_at"):
        events.append({"at": app["created_at"], "type": "application_created",
                       "detail": app.get("reference") or f"Application {app.get('id')}"})
    for d in sections.get("approvals", []):
        if d.get("created_at"):
            events.append({"at": d["created_at"], "type": f"approval_{d.get('action')}",
                           "detail": d.get("stage_name")})
    for m in sections.get("monitoring", []):
        if m.get("recorded_at"):
            events.append({"at": m["recorded_at"], "type": "monitoring",
                           "detail": f"{m.get('record_type')} / health={m.get('health_score')}"})
    for a in sections.get("audit", []):
        if a.get("created_at"):
            events.append({"at": a["created_at"], "type": "audit", "detail": a.get("action")})
    events.sort(key=lambda e: e["at"] or "", reverse=True)
    return events


def _completeness(sections: Dict[str, Any]) -> Dict[str, Any]:
    """A quick data-completeness score across the profile's data sources."""
    checks = {
        "application": sections.get("application") is not None,
        "assessment": sections.get("assessment") is not None,
        "gst": sections.get("gst") is not None,
        "mca": sections.get("mca") is not None,
        "bureau": sections.get("bureau") is not None,
        "erp": sections.get("erp") is not None,
        "payments": sections.get("payments") is not None,
        "bank_analytics": sections.get("bank_analytics") is not None,
        "collateral": bool((sections.get("collateral") or {}).get("items")),
    }
    present = sum(1 for v in checks.values() if v)
    return {"sources_present": present, "sources_total": len(checks),
            "score": round(present / len(checks), 3), "detail": checks}
