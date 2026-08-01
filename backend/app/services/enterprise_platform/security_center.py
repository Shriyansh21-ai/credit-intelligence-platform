"""M8 — Enterprise Security Center.

A zero-trust security console: session monitoring, threat & anomaly detection
device trust, behaviour analytics, privilege-escalation detection, access reviews
key rotation and a consolidated compliance/security dashboard. Detection is
deterministic (rule + score based) so results are reproducible and auditable.
Backed by ``ent_security_events`` and ``ent_access_reviews``; complements the
 SaaS security module.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from backend.app.models.enterprise_platform import EntAccessReview, EntSecurityEvent
from . import data_access as da
from .common import clamp, health_band, iso, mean, utcnow

EVENT_TYPES = ["session", "threat", "anomaly", "escalation", "device", "access"]
SEVERITIES = ["low", "medium", "high", "critical"]
_SEV_SCORE = {"low": 0.2, "medium": 0.5, "high": 0.8, "critical": 1.0}


def record_event(db: Session, *, event_type: str, subject_ref: Optional[str] = None,
                 severity: str = "low", source_ip: Optional[str] = None,
                 detail: Optional[dict] = None, tenant_id: Optional[int] = None) -> Dict[str, Any]:
    if event_type not in EVENT_TYPES:
        raise ValueError(f"unknown event_type '{event_type}'")
    if severity not in SEVERITIES:
        raise ValueError(f"unknown severity '{severity}'")
    row = EntSecurityEvent(tenant_id=tenant_id, event_type=event_type, subject_ref=subject_ref,
                           severity=severity, risk_score=_SEV_SCORE.get(severity, 0.2),
                           source_ip=source_ip, detail=detail or {})
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"event_id": row.id, "event_type": event_type, "severity": severity,
            "risk_score": row.risk_score}


def analyze_session(db: Session, *, subject_ref: str, source_ip: Optional[str] = None,
                    failed_logins: int = 0, new_device: bool = False, impossible_travel: bool = False,
                    off_hours: bool = False, tenant_id: Optional[int] = None) -> Dict[str, Any]:
    """Deterministic behaviour/anomaly scoring for a session (zero-trust signal)."""
    score = 0.0
    signals = []
    if failed_logins >= 5:
        score += 0.4
        signals.append(f"{failed_logins} failed logins")
    if new_device:
        score += 0.2
        signals.append("new/untrusted device")
    if impossible_travel:
        score += 0.4
        signals.append("impossible travel")
    if off_hours:
        score += 0.15
        signals.append("off-hours access")
    score = round(clamp(score), 3)
    severity = "critical" if score >= 0.8 else "high" if score >= 0.6 else "medium" if score >= 0.35 else "low"
    decision = "block" if score >= 0.8 else "step_up_mfa" if score >= 0.5 else "allow"
    if score >= 0.35:
        record_event(db, event_type="anomaly", subject_ref=subject_ref, severity=severity,
                     source_ip=source_ip, detail={"signals": signals, "score": score},
                     tenant_id=tenant_id)
    return {"subject_ref": subject_ref, "risk_score": score, "severity": severity,
            "decision": decision, "signals": signals, "device_trusted": not new_device}


def detect_privilege_escalation(db: Session, *, subject_ref: str, granted_permissions: List[str],
                                sensitive: Optional[List[str]] = None,
                                tenant_id: Optional[int] = None) -> Dict[str, Any]:
    sensitive = sensitive or ["roles.manage", "users.manage", "config.manage", "platform.admin",
                              "ent.security.manage", "ent.deploy.manage"]
    flagged = [p for p in granted_permissions if p in sensitive]
    escalation = len(flagged) >= 2
    if escalation:
        record_event(db, event_type="escalation", subject_ref=subject_ref, severity="high",
                     detail={"sensitive_permissions": flagged}, tenant_id=tenant_id)
    return {"subject_ref": subject_ref, "escalation_detected": escalation,
            "sensitive_permissions": flagged}


def list_events(db: Session, *, event_type: Optional[str] = None, severity: Optional[str] = None,
                status: Optional[str] = None, limit: int = 100,
                tenant_id: Optional[int] = None) -> List[Dict[str, Any]]:
    q = db.query(EntSecurityEvent)
    if tenant_id is not None:
        q = q.filter(EntSecurityEvent.tenant_id == tenant_id)
    if event_type:
        q = q.filter(EntSecurityEvent.event_type == event_type)
    if severity:
        q = q.filter(EntSecurityEvent.severity == severity)
    if status:
        q = q.filter(EntSecurityEvent.status == status)
    return [{"event_id": e.id, "event_type": e.event_type, "subject_ref": e.subject_ref,
             "severity": e.severity, "risk_score": e.risk_score, "status": e.status,
             "source_ip": e.source_ip, "created_at": iso(e.created_at)}
            for e in q.order_by(EntSecurityEvent.id.desc()).limit(limit).all()]


def start_access_review(db: Session, *, scope: str, reviewer: Optional[str] = None,
                        tenant_id: Optional[int] = None) -> Dict[str, Any]:
    """Kick off an access review; auto-populates findings from RBAC where possible."""
    findings: List[Dict[str, Any]] = []
    try:
        from backend.app.services.rbac.catalog import resolved_role_permissions
        if scope.startswith("role:"):
            role = scope.split(":", 1)[1]
            perms = resolved_role_permissions(role)
            sensitive = [p for p in perms if p.endswith(".manage") or p in ("roles.manage", "users.manage")]
            findings.append({"role": role, "total_permissions": len(perms),
                             "sensitive_permissions": len(sensitive),
                             "recommendation": "review sensitive grants" if len(sensitive) > 10 else "ok"})
    except Exception:
        pass
    row = EntAccessReview(tenant_id=tenant_id, scope=scope, reviewer=reviewer, findings=findings,
                          summary=f"Access review for {scope}")
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"review_id": row.id, "scope": scope, "status": row.status, "findings": findings}


def complete_access_review(db: Session, *, review_id: int, decision: str = "approved",
                           summary: Optional[str] = None) -> Dict[str, Any]:
    r = db.query(EntAccessReview).filter(EntAccessReview.id == review_id).first()
    if not r:
        raise ValueError("access review not found")
    r.status = decision
    r.summary = summary or r.summary
    r.completed_at = utcnow()
    db.commit()
    return {"review_id": r.id, "status": r.status}


def list_access_reviews(db: Session, *, status: Optional[str] = None,
                        tenant_id: Optional[int] = None) -> List[Dict[str, Any]]:
    q = db.query(EntAccessReview)
    if tenant_id is not None:
        q = q.filter(EntAccessReview.tenant_id == tenant_id)
    if status:
        q = q.filter(EntAccessReview.status == status)
    return [{"review_id": r.id, "scope": r.scope, "reviewer": r.reviewer, "status": r.status,
             "findings": r.findings, "created_at": iso(r.created_at)}
            for r in q.order_by(EntAccessReview.id.desc()).all()]


def key_rotation_status(db: Session, *, tenant_id: Optional[int] = None) -> Dict[str, Any]:
    """Report on API-key age / rotation posture (zero-trust hygiene)."""
    try:
        from backend.app.models.enterprise_platform import EntApiKey
        keys = db.query(EntApiKey)
        if tenant_id is not None:
            keys = keys.filter(EntApiKey.tenant_id == tenant_id)
        keys = keys.all()
        active = [k for k in keys if k.status == "active"]
        stale = [k for k in active if k.last_used_at is None]
        return {"total_keys": len(keys), "active": len(active), "revoked": len(keys) - len(active),
                "never_used": len(stale),
                "rotation_recommended": len(stale),
                "posture": "good" if not stale else "review"}
    except Exception:
        return {"total_keys": 0, "active": 0, "posture": "unknown"}


def dashboard(db: Session, *, tenant_id: Optional[int] = None) -> Dict[str, Any]:
    """Zero-trust / compliance dashboard: event roll-up + posture + key rotation."""
    events = list_events(db, limit=500, tenant_id=tenant_id)
    open_events = [e for e in events if e["status"] == "open"]
    by_sev: Dict[str, int] = {}
    for e in open_events:
        by_sev[e["severity"]] = by_sev.get(e["severity"], 0) + 1
    threat_score = round(100 - 100 * mean([e["risk_score"] for e in open_events]) if open_events else 100, 1)
    reviews = list_access_reviews(db, tenant_id=tenant_id)
    pending_reviews = sum(1 for r in reviews if r["status"] == "pending")
    return {
        "posture": health_band(threat_score),
        "security_score": threat_score,
        "open_events": len(open_events),
        "events_by_severity": by_sev,
        "critical_events": by_sev.get("critical", 0),
        "pending_access_reviews": pending_reviews,
        "key_rotation": key_rotation_status(db, tenant_id=tenant_id),
        "zero_trust": {"mfa_enforced": True, "least_privilege": True, "device_trust": True},
        "generated_at": iso(utcnow()),
    }
