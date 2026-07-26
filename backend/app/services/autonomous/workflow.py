"""M12 — Autonomous Workflow Intelligence.

Proactively proposes (and optionally executes) the workflow actions a senior
credit analyst would take: create tasks, assign reviewers, trigger reassessments,
request documents, recommend approvals/escalations/committee review, and set the
right monitoring frequency. Decisions are derived from open alerts, the latest
EWS band and the recommendation engine — every action carries a trigger + rationale.

``mode='proposed'`` only records the plan; ``mode='execute'`` additionally performs
the safe actions (e.g. creating a Phase 5 task) best-effort, never breaking if a
subsystem is absent.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from backend.app.models.autonomous import WorkflowAction
from . import alerts as alerts_svc
from . import data_access, ews, recommendations

ACTION_TYPES = [
    "create_task", "assign_reviewer", "trigger_reassessment", "request_documents",
    "recommend_approval", "recommend_escalation", "recommend_committee_review",
    "set_monitoring_frequency",
]


def _monitoring_frequency(pd: float, ews_band: str) -> str:
    if ews_band == "red" or pd >= 0.15:
        return "weekly"
    if ews_band == "amber" or pd >= 0.08:
        return "monthly"
    return "quarterly"


def plan(db: Session, *, company_ref: Optional[str] = None, assessment_id: Optional[int] = None,
         tenant_id: Optional[int] = None) -> List[Dict[str, Any]]:
    """Compute the proposed workflow actions for a company (no side effects)."""
    assessment = data_access.resolve(db, assessment_id=assessment_id, company_ref=company_ref)
    prof = data_access.profile(assessment)
    ref = (prof or {}).get("company_ref") or company_ref
    if not ref:
        return []
    pd = (prof or {}).get("pd") or 0.08

    open_alerts = alerts_svc.list_alerts(db, company_ref=ref, status="open", tenant_id=tenant_id)
    ews_res = ews.evaluate(db, company_ref=ref, assessment_id=assessment_id, persist=False, escalate=False)
    band = ews_res["ews_band"]
    recs = recommendations.recommend(db, company_ref=ref, assessment_id=assessment_id,
                                     context={"ews_band": band}, persist=False)
    primary = (recs.get("recommendations") or [{}])[0]

    actions: List[Dict[str, Any]] = []

    def add(action_type, trigger, rationale, params=None):
        actions.append({"action_type": action_type, "trigger": trigger,
                        "rationale": rationale, "params": params or {}})

    # Monitoring cadence is always set.
    freq = _monitoring_frequency(pd, band)
    add("set_monitoring_frequency", f"ews_band={band},pd={pd:.2%}",
        f"Set monitoring frequency to {freq} based on risk band.", {"frequency": freq})

    critical = [a for a in open_alerts if a.severity in ("high", "critical")]
    if band == "red" or critical:
        add("recommend_committee_review", "red_band_or_critical_alert",
            "Distress signals warrant credit-committee review.")
        add("trigger_reassessment", "red_band_or_critical_alert",
            "Material change detected — re-run the credit assessment.")
        add("recommend_escalation", "red_band_or_critical_alert",
            "Escalate to the risk owner immediately.", {"to": "risk_manager"})

    if primary.get("action") == "manual_review":
        add("assign_reviewer", "manual_review_recommendation",
            "Assign a senior analyst for manual underwriting.", {"role": "senior_analyst"})
        add("create_task", "manual_review_recommendation",
            f"Manual review of {ref}", {"title": f"Manual review: {ref}", "priority": "high"})
    elif primary.get("action") == "approve":
        add("recommend_approval", "strong_profile",
            f"Profile supports approval ({primary.get('title')}).")

    if primary.get("action") in ("additional_collateral", "restructure") or band != "green":
        add("request_documents", "risk_or_collateral",
            "Request updated financials and collateral valuation.",
            {"documents": ["latest_financials", "collateral_valuation", "bank_statements"]})

    if open_alerts:
        add("create_task", "open_alerts",
            f"Review {len(open_alerts)} open alert(s) for {ref}",
            {"title": f"Review alerts: {ref}", "priority": "medium"})

    return actions


def run(db: Session, *, company_ref: Optional[str] = None, assessment_id: Optional[int] = None,
        mode: str = "proposed", tenant_id: Optional[int] = None,
        actor_user_id: Optional[int] = None) -> Dict[str, Any]:
    """Plan and persist workflow actions; execute the safe ones when mode='execute'."""
    if mode not in ("proposed", "execute"):
        raise ValueError("mode must be 'proposed' or 'execute'")
    proposed = plan(db, company_ref=company_ref, assessment_id=assessment_id, tenant_id=tenant_id)
    ref = company_ref
    if proposed and not ref:
        ref = None
    stored: List[WorkflowAction] = []
    for a in proposed:
        row = WorkflowAction(tenant_id=tenant_id, company_ref=company_ref, assessment_id=assessment_id,
                             action_type=a["action_type"], trigger=a["trigger"],
                             rationale=a["rationale"], params=a["params"], mode=mode,
                             status="pending")
        if mode == "execute":
            row.status, row.result = _execute_action(db, a, company_ref, actor_user_id, tenant_id)
        db.add(row)
        stored.append(row)
    db.commit()
    for row in stored:
        db.refresh(row)
    return {"company_ref": company_ref, "mode": mode, "action_count": len(stored),
            "actions": [as_dict(r) for r in stored]}


def _execute_action(db, action, company_ref, actor_user_id, tenant_id):
    """Best-effort execution of the safe actions. Returns (status, result)."""
    atype = action["action_type"]
    try:
        if atype == "create_task":
            from types import SimpleNamespace
            from backend.app.services import tasks as tasks_svc
            params = action["params"]
            actor = SimpleNamespace(id=actor_user_id, email=None)
            task = tasks_svc.create_task(
                db, title=params.get("title", "AI task"), actor=actor, task_type="review",
                owner_id=actor_user_id, priority=params.get("priority", "medium"),
                description=action["rationale"])
            return "executed", {"task_id": getattr(task, "id", None)}
        # Other actions are advisory (surfaced to humans), so recording is the action.
        return "executed", {"note": "recorded as recommendation"}
    except Exception as e:  # pragma: no cover - defensive
        return "failed", {"error": str(e)}


def as_dict(r: WorkflowAction) -> Dict[str, Any]:
    return {"id": r.id, "company_ref": r.company_ref, "action_type": r.action_type,
            "trigger": r.trigger, "rationale": r.rationale, "params": r.params,
            "mode": r.mode, "status": r.status, "result": r.result,
            "created_at": r.created_at.isoformat() if r.created_at else None}


def list_actions(db: Session, *, company_ref: Optional[str] = None, status: Optional[str] = None,
                 tenant_id: Optional[int] = None, limit: int = 100) -> List[WorkflowAction]:
    q = db.query(WorkflowAction).filter(WorkflowAction.tenant_id == tenant_id)
    if company_ref:
        q = q.filter(WorkflowAction.company_ref == company_ref)
    if status:
        q = q.filter(WorkflowAction.status == status)
    return q.order_by(WorkflowAction.created_at.desc()).limit(limit).all()
