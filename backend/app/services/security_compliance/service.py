"""DB-backed orchestration for the Security & Compliance module.

Persists scan runs and findings, compliance assessments, the risk register,
privacy (DSAR) requests and posture snapshots. Function-based, tenant-scoped,
mirroring the platform's service conventions. Serializers return plain dicts.
"""

from __future__ import annotations

from datetime import datetime
from typing import Callable, Dict, List, Optional

from sqlalchemy.orm import Session

from backend.app.models.security_compliance import (
    ComplianceAssessment,
    PostureSnapshot,
    PrivacyRequest,
    RiskRegisterEntry,
    SecretAuditRecord,
    SecurityFinding,
    SecurityScan,
)

from . import (
    ai_ml,
    authz,
    compliance as compliance_mod,
    data_protection,
    hardening,
    owasp,
    posture as posture_mod,
    privacy as privacy_mod,
    secrets as secrets_mod,
    supply_chain,
    threat_model,
)
from .common import grade_from_score, risk_level, risk_score, score_from_findings

# ---------------------------------------------------------------------------
# Scan dispatch — each entry returns a dict with at least "findings" + "score".
# ---------------------------------------------------------------------------
SCAN_ENGINES: Dict[str, Callable[[], Dict[str, object]]] = {
    "owasp": owasp.owasp_assessment,
    "threat": threat_model.build_threat_model,
    "authz": authz.authz_audit,
    "tenant": authz.tenant_isolation_audit,
    "secrets": secrets_mod.secret_inventory,
    "data_protection": data_protection.data_protection_report,
    "supply_chain": supply_chain.supply_chain_report,
    "container": hardening.container_hardening,
    "ai_security": ai_ml.ai_security,
    "ml_security": ai_ml.ml_security,
    "privacy": privacy_mod.privacy_overview,
}

SCAN_TYPES = list(SCAN_ENGINES.keys()) + ["full"]


# ---------------------------------------------------------------------------
# Serializers
# ---------------------------------------------------------------------------
def scan_dict(s: SecurityScan) -> dict:
    return {
        "id": s.id, "tenant_id": s.tenant_id, "scan_type": s.scan_type,
        "status": s.status, "score": s.score, "grade": s.grade,
        "summary": s.summary or {}, "findings_count": s.findings_count,
        "critical_count": s.critical_count, "high_count": s.high_count,
        "triggered_by": s.triggered_by,
        "created_at": s.created_at.isoformat() if s.created_at else None,
    }


def finding_dict(f: SecurityFinding) -> dict:
    return {
        "id": f.id, "tenant_id": f.tenant_id, "scan_id": f.scan_id, "code": f.code,
        "category": f.category, "severity": f.severity, "title": f.title,
        "description": f.description, "recommendation": f.recommendation,
        "reference": f.reference, "component": f.component, "status": f.status,
        "evidence": f.evidence or {},
        "created_at": f.created_at.isoformat() if f.created_at else None,
        "updated_at": f.updated_at.isoformat() if f.updated_at else None,
    }


def compliance_dict(c: ComplianceAssessment) -> dict:
    return {
        "id": c.id, "tenant_id": c.tenant_id, "framework": c.framework,
        "version": c.version, "score": c.score, "readiness": c.readiness,
        "total_controls": c.total_controls, "satisfied": c.satisfied,
        "partial": c.partial, "gaps": c.gaps, "results": c.results or [],
        "gap_items": c.gap_items or [],
        "created_at": c.created_at.isoformat() if c.created_at else None,
    }


def risk_dict(r: RiskRegisterEntry) -> dict:
    return {
        "id": r.id, "tenant_id": r.tenant_id, "title": r.title, "category": r.category,
        "description": r.description, "likelihood": r.likelihood, "impact": r.impact,
        "inherent_score": r.inherent_score, "inherent_level": risk_level(r.inherent_score),
        "treatment": r.treatment, "residual_likelihood": r.residual_likelihood,
        "residual_impact": r.residual_impact, "residual_score": r.residual_score,
        "residual_level": risk_level(r.residual_score), "mitigations": r.mitigations or [],
        "owner": r.owner, "status": r.status,
        "created_at": r.created_at.isoformat() if r.created_at else None,
        "updated_at": r.updated_at.isoformat() if r.updated_at else None,
    }


def privacy_dict(p: PrivacyRequest) -> dict:
    return {
        "id": p.id, "tenant_id": p.tenant_id, "subject_ref": p.subject_ref,
        "request_type": p.request_type, "status": p.status, "legal_basis": p.legal_basis,
        "notes": p.notes, "due_at": p.due_at.isoformat() if p.due_at else None,
        "completed_at": p.completed_at.isoformat() if p.completed_at else None,
        "created_at": p.created_at.isoformat() if p.created_at else None,
    }


def posture_snapshot_dict(p: PostureSnapshot) -> dict:
    return {
        "id": p.id, "tenant_id": p.tenant_id, "overall_score": p.overall_score,
        "grade": p.grade, "dimensions": p.dimensions or {},
        "open_findings": p.open_findings, "open_critical": p.open_critical,
        "created_at": p.created_at.isoformat() if p.created_at else None,
    }


# ---------------------------------------------------------------------------
# Scans + findings
# ---------------------------------------------------------------------------
def run_scan(db: Session, *, scan_type: str, tenant_id: Optional[int] = None,
             user_id: Optional[int] = None) -> dict:
    """Run an assessment engine, persist the scan + its findings, return both."""
    if scan_type == "full":
        return _run_full_scan(db, tenant_id=tenant_id, user_id=user_id)
    engine = SCAN_ENGINES.get(scan_type)
    if engine is None:
        raise ValueError(f"Unknown scan_type: {scan_type}")
    result = engine()
    raw_findings = _collect_findings(result)
    score = float(result.get("score", result.get("overall_score", score_from_findings(raw_findings))))
    return _persist_scan(db, scan_type=scan_type, score=score, findings=raw_findings,
                         summary=_summary(result), tenant_id=tenant_id, user_id=user_id)


def _run_full_scan(db: Session, *, tenant_id: Optional[int], user_id: Optional[int]) -> dict:
    all_findings: List[dict] = []
    dim_scores: Dict[str, float] = {}
    for stype, engine in SCAN_ENGINES.items():
        result = engine()
        all_findings.extend(_collect_findings(result))
        dim_scores[stype] = float(result.get("score", result.get("overall_score", 0.0)))
    overall = round(sum(dim_scores.values()) / max(1, len(dim_scores)), 1)
    return _persist_scan(db, scan_type="full", score=overall, findings=all_findings,
                         summary={"dimensions": dim_scores}, tenant_id=tenant_id, user_id=user_id)


def _collect_findings(result: Dict[str, object]) -> List[dict]:
    findings = list(result.get("findings", []) or [])
    # Some aggregate engines nest findings under sub-results.
    for key in ("top10", "api_top10", "authentication", "authorization"):
        sub = result.get(key)
        if isinstance(sub, dict):
            findings.extend(sub.get("findings", []) or [])
    return findings


def _summary(result: Dict[str, object]) -> dict:
    return {k: v for k, v in result.items()
            if k in ("score", "overall_score", "open_findings", "passed",
                     "total_checks", "readiness", "high_risk", "model_health_score")}


def _persist_scan(db: Session, *, scan_type: str, score: float, findings: List[dict],
                  summary: dict, tenant_id: Optional[int], user_id: Optional[int]) -> dict:
    sev_counts = {"critical": 0, "high": 0}
    for f in findings:
        sev = str(f.get("severity", "info"))
        if sev in sev_counts:
            sev_counts[sev] += 1
    scan = SecurityScan(
        tenant_id=tenant_id, scan_type=scan_type, status="completed", score=score,
        grade=grade_from_score(score), summary=summary, findings_count=len(findings),
        critical_count=sev_counts["critical"], high_count=sev_counts["high"],
        triggered_by=user_id,
    )
    db.add(scan)
    db.commit()
    db.refresh(scan)
    stored: List[dict] = []
    for f in findings:
        row = SecurityFinding(
            tenant_id=tenant_id, scan_id=scan.id, code=str(f.get("code", "SEC-UNKNOWN")),
            category=str(f.get("category", scan_type)), severity=str(f.get("severity", "info")),
            title=str(f.get("title", "")), description=str(f.get("description", "")),
            recommendation=str(f.get("recommendation", "")),
            reference=f.get("reference"), component=f.get("component"),
            evidence=f.get("evidence") or {},
        )
        db.add(row)
        stored.append(f)
    db.commit()
    return {"scan": scan_dict(scan), "findings": stored, "findings_count": len(stored)}


def list_scans(db: Session, *, tenant_id: Optional[int] = None,
               scan_type: Optional[str] = None, limit: int = 50) -> List[dict]:
    q = db.query(SecurityScan)
    if tenant_id is not None:
        q = q.filter(SecurityScan.tenant_id == tenant_id)
    if scan_type:
        q = q.filter(SecurityScan.scan_type == scan_type)
    rows = q.order_by(SecurityScan.created_at.desc()).limit(limit).all()
    return [scan_dict(r) for r in rows]


def get_scan(db: Session, scan_id: int, *, tenant_id: Optional[int] = None) -> Optional[dict]:
    q = db.query(SecurityScan).filter(SecurityScan.id == scan_id)
    if tenant_id is not None:
        q = q.filter(SecurityScan.tenant_id == tenant_id)
    scan = q.first()
    if scan is None:
        return None
    findings = db.query(SecurityFinding).filter(SecurityFinding.scan_id == scan_id).all()
    return {"scan": scan_dict(scan), "findings": [finding_dict(f) for f in findings]}


def list_findings(db: Session, *, tenant_id: Optional[int] = None, status: Optional[str] = None,
                  category: Optional[str] = None, severity: Optional[str] = None,
                  limit: int = 200) -> List[dict]:
    q = db.query(SecurityFinding)
    if tenant_id is not None:
        q = q.filter(SecurityFinding.tenant_id == tenant_id)
    if status:
        q = q.filter(SecurityFinding.status == status)
    if category:
        q = q.filter(SecurityFinding.category == category)
    if severity:
        q = q.filter(SecurityFinding.severity == severity)
    rows = q.order_by(SecurityFinding.created_at.desc()).limit(limit).all()
    return [finding_dict(r) for r in rows]


_FINDING_STATES = {"open", "acknowledged", "resolved", "accepted", "false_positive"}


def update_finding_status(db: Session, finding_id: int, *, status: str,
                          user_id: Optional[int] = None,
                          tenant_id: Optional[int] = None) -> Optional[dict]:
    if status not in _FINDING_STATES:
        raise ValueError(f"Invalid finding status: {status}")
    q = db.query(SecurityFinding).filter(SecurityFinding.id == finding_id)
    if tenant_id is not None:
        q = q.filter(SecurityFinding.tenant_id == tenant_id)
    row = q.first()
    if row is None:
        return None
    row.status = status
    if status in ("resolved", "false_positive"):
        row.resolved_by = user_id
        row.resolved_at = datetime.utcnow()
    db.commit()
    db.refresh(row)
    return finding_dict(row)


# ---------------------------------------------------------------------------
# Compliance
# ---------------------------------------------------------------------------
def record_compliance_assessment(db: Session, *, framework: str, tenant_id: Optional[int] = None,
                                 user_id: Optional[int] = None) -> dict:
    res = compliance_mod.assess_framework(framework)
    row = ComplianceAssessment(
        tenant_id=tenant_id, framework=framework, version=res.get("version"),
        score=res["score"], readiness=res["readiness"], total_controls=res["total_controls"],
        satisfied=res["satisfied"], partial=res["partial"], gaps=res["gaps"],
        results=res["results"], gap_items=res["gap_items"], assessed_by=user_id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return compliance_dict(row)


def list_compliance_assessments(db: Session, *, tenant_id: Optional[int] = None,
                                framework: Optional[str] = None, limit: int = 50) -> List[dict]:
    q = db.query(ComplianceAssessment)
    if tenant_id is not None:
        q = q.filter(ComplianceAssessment.tenant_id == tenant_id)
    if framework:
        q = q.filter(ComplianceAssessment.framework == framework)
    rows = q.order_by(ComplianceAssessment.created_at.desc()).limit(limit).all()
    return [compliance_dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Risk register
# ---------------------------------------------------------------------------
def create_risk(db: Session, *, title: str, category: str, likelihood: int, impact: int,
                description: str = "", treatment: str = "mitigate",
                residual_likelihood: Optional[int] = None, residual_impact: Optional[int] = None,
                mitigations: Optional[List[str]] = None, owner: Optional[str] = None,
                tenant_id: Optional[int] = None, user_id: Optional[int] = None) -> dict:
    if treatment not in ("mitigate", "accept", "transfer", "avoid"):
        raise ValueError(f"Invalid treatment: {treatment}")
    rl = residual_likelihood if residual_likelihood is not None else max(1, likelihood - 1)
    ri = residual_impact if residual_impact is not None else max(1, impact - 1)
    row = RiskRegisterEntry(
        tenant_id=tenant_id, title=title, category=category, description=description,
        likelihood=likelihood, impact=impact, inherent_score=risk_score(likelihood, impact),
        treatment=treatment, residual_likelihood=rl, residual_impact=ri,
        residual_score=risk_score(rl, ri), mitigations=mitigations or [], owner=owner,
        created_by=user_id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return risk_dict(row)


def list_risks(db: Session, *, tenant_id: Optional[int] = None, status: Optional[str] = None,
               limit: int = 200) -> List[dict]:
    q = db.query(RiskRegisterEntry)
    if tenant_id is not None:
        q = q.filter(RiskRegisterEntry.tenant_id == tenant_id)
    if status:
        q = q.filter(RiskRegisterEntry.status == status)
    rows = q.order_by(RiskRegisterEntry.inherent_score.desc()).limit(limit).all()
    return [risk_dict(r) for r in rows]


def update_risk(db: Session, risk_id: int, *, tenant_id: Optional[int] = None,
                **fields) -> Optional[dict]:
    q = db.query(RiskRegisterEntry).filter(RiskRegisterEntry.id == risk_id)
    if tenant_id is not None:
        q = q.filter(RiskRegisterEntry.tenant_id == tenant_id)
    row = q.first()
    if row is None:
        return None
    for key in ("title", "category", "description", "treatment", "owner", "status", "mitigations"):
        if key in fields and fields[key] is not None:
            setattr(row, key, fields[key])
    for key in ("likelihood", "impact"):
        if key in fields and fields[key] is not None:
            setattr(row, key, fields[key])
    row.inherent_score = risk_score(row.likelihood, row.impact)
    for key in ("residual_likelihood", "residual_impact"):
        if key in fields and fields[key] is not None:
            setattr(row, key, fields[key])
    row.residual_score = risk_score(row.residual_likelihood, row.residual_impact)
    db.commit()
    db.refresh(row)
    return risk_dict(row)


# ---------------------------------------------------------------------------
# Privacy (DSAR) requests
# ---------------------------------------------------------------------------
def create_privacy_request(db: Session, *, subject_ref: str, request_type: str,
                           legal_basis: Optional[str] = None, notes: str = "",
                           tenant_id: Optional[int] = None, user_id: Optional[int] = None) -> dict:
    if request_type not in privacy_mod.REQUEST_TYPES:
        raise ValueError(f"Invalid request_type: {request_type}")
    now = datetime.utcnow()
    row = PrivacyRequest(
        tenant_id=tenant_id, subject_ref=subject_ref, request_type=request_type,
        legal_basis=legal_basis, notes=notes, due_at=privacy_mod.request_sla_due(request_type, now),
        created_by=user_id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return privacy_dict(row)


def list_privacy_requests(db: Session, *, tenant_id: Optional[int] = None,
                          status: Optional[str] = None, limit: int = 200) -> List[dict]:
    q = db.query(PrivacyRequest)
    if tenant_id is not None:
        q = q.filter(PrivacyRequest.tenant_id == tenant_id)
    if status:
        q = q.filter(PrivacyRequest.status == status)
    rows = q.order_by(PrivacyRequest.created_at.desc()).limit(limit).all()
    return [privacy_dict(r) for r in rows]


def update_privacy_request(db: Session, request_id: int, *, status: str,
                           notes: Optional[str] = None, tenant_id: Optional[int] = None) -> Optional[dict]:
    if status not in privacy_mod.REQUEST_STATES:
        raise ValueError(f"Invalid privacy request status: {status}")
    q = db.query(PrivacyRequest).filter(PrivacyRequest.id == request_id)
    if tenant_id is not None:
        q = q.filter(PrivacyRequest.tenant_id == tenant_id)
    row = q.first()
    if row is None:
        return None
    row.status = status
    if notes is not None:
        row.notes = notes
    if status == "completed":
        row.completed_at = datetime.utcnow()
    db.commit()
    db.refresh(row)
    return privacy_dict(row)


# ---------------------------------------------------------------------------
# Posture snapshots + dashboard
# ---------------------------------------------------------------------------
def snapshot_posture(db: Session, *, tenant_id: Optional[int] = None) -> dict:
    p = posture_mod.security_posture()
    open_findings = _open_findings_count(db, tenant_id=tenant_id)
    open_critical = _open_findings_count(db, tenant_id=tenant_id, severity="critical")
    row = PostureSnapshot(
        tenant_id=tenant_id, overall_score=float(p["overall_score"]), grade=str(p["grade"]),
        dimensions=p["dimensions"], open_findings=open_findings, open_critical=open_critical,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return posture_snapshot_dict(row)


def list_posture_snapshots(db: Session, *, tenant_id: Optional[int] = None, limit: int = 30) -> List[dict]:
    q = db.query(PostureSnapshot)
    if tenant_id is not None:
        q = q.filter(PostureSnapshot.tenant_id == tenant_id)
    rows = q.order_by(PostureSnapshot.created_at.desc()).limit(limit).all()
    return [posture_snapshot_dict(r) for r in rows]


def _open_findings_count(db: Session, *, tenant_id: Optional[int] = None,
                         severity: Optional[str] = None) -> int:
    q = db.query(SecurityFinding).filter(SecurityFinding.status.in_(["open", "acknowledged"]))
    if tenant_id is not None:
        q = q.filter(SecurityFinding.tenant_id == tenant_id)
    if severity:
        q = q.filter(SecurityFinding.severity == severity)
    return q.count()


def security_dashboard(db: Session, *, tenant_id: Optional[int] = None) -> dict:
    """The full security administration dashboard (Milestone 14).

    Combines the live posture (config-derived) with DB counters: open findings,
    risk register, compliance history, privacy queue and recent scans.
    """
    p = posture_mod.security_posture()
    open_findings = list_findings(db, tenant_id=tenant_id, status="open", limit=200)
    by_severity = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}
    for f in open_findings:
        sev = f["severity"]
        if sev in by_severity:
            by_severity[sev] += 1
    risks = list_risks(db, tenant_id=tenant_id, status="open", limit=200)
    top_risks = sorted(risks, key=lambda r: r["inherent_score"], reverse=True)[:5]
    privacy_queue = list_privacy_requests(db, tenant_id=tenant_id, limit=200)
    open_privacy = [r for r in privacy_queue if r["status"] not in ("completed", "rejected")]
    recent_scans = list_scans(db, tenant_id=tenant_id, limit=10)
    compliance_history = list_compliance_assessments(db, tenant_id=tenant_id, limit=20)

    return {
        "posture": p,
        "findings": {
            "open_total": len(open_findings),
            "by_severity": by_severity,
        },
        "risk_register": {
            "open_total": len(risks),
            "top": top_risks,
        },
        "compliance": compliance_mod.compliance_matrix(),
        "compliance_history_count": len(compliance_history),
        "privacy": {
            "open_requests": len(open_privacy),
            "total_requests": len(privacy_queue),
        },
        "secrets": {
            "insecure_critical": secrets_mod.secret_inventory()["insecure_critical"],
            "missing_critical": secrets_mod.secret_inventory()["missing_critical"],
        },
        "recent_scans": recent_scans,
        "sessions": _session_stats(db, tenant_id=tenant_id),
    }


def _session_stats(db: Session, *, tenant_id: Optional[int] = None) -> dict:
    """Live active-session / device counters from the Phase 8 security tables."""
    try:
        from backend.app.models.saas_security import SecurityDevice, SecuritySession

        sq = db.query(SecuritySession).filter(SecuritySession.status == "active")
        dq = db.query(SecurityDevice)
        if tenant_id is not None:
            sq = sq.filter(SecuritySession.tenant_id == tenant_id)
            dq = dq.filter(SecurityDevice.tenant_id == tenant_id)
        return {"active_sessions": sq.count(), "devices": dq.count()}
    except Exception:
        return {"active_sessions": 0, "devices": 0}
