"""Dashboard aggregation functions.

Each returns a plain dict tuned for one dashboard. All queries are read-only and
grouped/counted in SQL where practical.
"""

from __future__ import annotations

from typing import Any, Dict, List

from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.app.models.application import Application
from backend.app.models.approval import ApprovalDecision
from backend.app.models.audit import AuditLog
from backend.app.models.covenant import CovenantAlert
from backend.app.models.monitoring import MonitoringAlert
from backend.app.models.notification import Notification
from backend.app.models.rbac import Role
from backend.app.models.system_config import SystemConfig
from backend.app.models.task import Task
from backend.app.models.user import User
from backend.app.services.audit.query import audit_stats
from backend.app.services.lifecycle.service import serialize as serialize_application

# Statuses that represent applications actively awaiting a human decision.
_PENDING_APPROVAL_STATUSES = [
    "analyst_review",
    "senior_analyst_review",
    "credit_committee",
]
_OPEN_TASK_STATUSES = ["open", "in_progress", "blocked"]


def _status_counts(db: Session) -> List[Dict[str, Any]]:
    rows = (
        db.query(Application.status, func.count(Application.id))
        .group_by(Application.status)
        .all()
    )
    return [{"status": s, "count": c} for s, c in rows]


def _count(query) -> int:
    return query.count()


def _recent_applications(db: Session, limit: int = 8) -> List[Dict[str, Any]]:
    rows = (
        db.query(Application)
        .order_by(Application.updated_at.desc(), Application.id.desc())
        .limit(limit)
        .all()
    )
    return [serialize_application(a) for a in rows]


def _total_exposure(db: Session) -> float:
    return float(db.query(func.coalesce(func.sum(Application.requested_amount), 0.0)).scalar() or 0.0)


def operations_dashboard(db: Session) -> Dict[str, Any]:
    total_apps = db.query(func.count(Application.id)).scalar() or 0
    pending = (
        db.query(func.count(Application.id))
        .filter(Application.status.in_(_PENDING_APPROVAL_STATUSES))
        .scalar()
        or 0
    )
    open_tasks = (
        db.query(func.count(Task.id)).filter(Task.status.in_(_OPEN_TASK_STATUSES)).scalar() or 0
    )
    open_cov = db.query(func.count(CovenantAlert.id)).filter(CovenantAlert.status == "open").scalar() or 0
    open_mon = db.query(func.count(MonitoringAlert.id)).filter(MonitoringAlert.status == "open").scalar() or 0
    return {
        "totals": {
            "applications": total_apps,
            "pending_approvals": pending,
            "open_tasks": open_tasks,
            "open_alerts": open_cov + open_mon,
            "total_exposure": _total_exposure(db),
        },
        "status_breakdown": _status_counts(db),
        "recent_applications": _recent_applications(db),
    }


def admin_dashboard(db: Session) -> Dict[str, Any]:
    return {
        "totals": {
            "users": db.query(func.count(User.id)).scalar() or 0,
            "roles": db.query(func.count(Role.id)).scalar() or 0,
            "config_keys": db.query(func.count(SystemConfig.id)).scalar() or 0,
            "applications": db.query(func.count(Application.id)).scalar() or 0,
        },
        "audit": audit_stats(db),
        "status_breakdown": _status_counts(db),
    }


def analyst_dashboard(db: Session, user_id: int) -> Dict[str, Any]:
    my_tasks = db.query(Task).filter(Task.owner_id == user_id).all()
    by_status: Dict[str, int] = {}
    for t in my_tasks:
        by_status[t.status] = by_status.get(t.status, 0) + 1

    my_apps = (
        db.query(Application)
        .filter((Application.assigned_to == user_id) | (Application.user_id == user_id))
        .order_by(Application.updated_at.desc())
        .limit(10)
        .all()
    )
    unread = (
        db.query(func.count(Notification.id))
        .filter(Notification.user_id == user_id, Notification.is_read == False)  # noqa: E712
        .scalar()
        or 0
    )
    return {
        "totals": {
            "my_open_tasks": sum(
                v for k, v in by_status.items() if k in _OPEN_TASK_STATUSES
            ),
            "my_applications": len(my_apps),
            "unread_notifications": unread,
        },
        "my_tasks_by_status": [{"status": k, "count": v} for k, v in by_status.items()],
        "my_applications": [serialize_application(a) for a in my_apps],
    }


def manager_dashboard(db: Session) -> Dict[str, Any]:
    pending = (
        db.query(Application)
        .filter(Application.status.in_(_PENDING_APPROVAL_STATUSES))
        .order_by(Application.updated_at.desc())
        .all()
    )
    pending_by_stage: Dict[str, int] = {}
    for a in pending:
        pending_by_stage[a.status] = pending_by_stage.get(a.status, 0) + 1

    # Approval throughput by action.
    action_rows = (
        db.query(ApprovalDecision.action, func.count(ApprovalDecision.id))
        .group_by(ApprovalDecision.action)
        .all()
    )
    exposure_by_rating = (
        db.query(Application.risk_rating, func.coalesce(func.sum(Application.requested_amount), 0.0))
        .group_by(Application.risk_rating)
        .all()
    )
    return {
        "totals": {
            "pending_approvals": len(pending),
            "total_exposure": _total_exposure(db),
        },
        "pending_by_stage": [{"stage": k, "count": v} for k, v in pending_by_stage.items()],
        "approval_actions": [{"action": a, "count": c} for a, c in action_rows],
        "exposure_by_rating": [
            {"rating": r or "Unrated", "exposure": float(e or 0)} for r, e in exposure_by_rating
        ],
        "pending_applications": [serialize_application(a) for a in pending[:10]],
    }


def portfolio_dashboard(db: Session) -> Dict[str, Any]:
    def group(column):
        rows = (
            db.query(column, func.count(Application.id), func.coalesce(func.sum(Application.requested_amount), 0.0))
            .group_by(column)
            .all()
        )
        return [
            {"value": v or "Unspecified", "count": c, "exposure": float(e or 0)}
            for v, c, e in rows
        ]

    return {
        "totals": {
            "applications": db.query(func.count(Application.id)).scalar() or 0,
            "total_exposure": _total_exposure(db),
        },
        "by_status": group(Application.status),
        "by_industry": group(Application.industry),
        "by_rating": group(Application.risk_rating),
        "by_grade": group(Application.risk_grade),
    }


def compliance_dashboard(db: Session) -> Dict[str, Any]:
    open_cov = db.query(func.count(CovenantAlert.id)).filter(CovenantAlert.status == "open").scalar() or 0
    open_mon = db.query(func.count(MonitoringAlert.id)).filter(MonitoringAlert.status == "open").scalar() or 0
    recent_audit = (
        db.query(AuditLog).order_by(AuditLog.timestamp.desc()).limit(15).all()
    )
    return {
        "totals": {
            "open_covenant_alerts": open_cov,
            "open_monitoring_alerts": open_mon,
            "audit_events": db.query(func.count(AuditLog.id)).scalar() or 0,
        },
        "audit": audit_stats(db),
        "recent_audit": [
            {
                "timestamp": r.timestamp.isoformat() if r.timestamp else None,
                "user": r.user_email,
                "action": r.action,
                "status": r.status,
            }
            for r in recent_audit
        ],
    }


def monitoring_dashboard(db: Session) -> Dict[str, Any]:
    open_mon = db.query(func.count(MonitoringAlert.id)).filter(MonitoringAlert.status == "open").scalar() or 0
    by_category = (
        db.query(MonitoringAlert.category, func.count(MonitoringAlert.id))
        .group_by(MonitoringAlert.category)
        .all()
    )
    by_severity = (
        db.query(MonitoringAlert.severity, func.count(MonitoringAlert.id))
        .group_by(MonitoringAlert.severity)
        .all()
    )
    recent = (
        db.query(MonitoringAlert).order_by(MonitoringAlert.created_at.desc()).limit(15).all()
    )
    return {
        "totals": {"open_alerts": open_mon},
        "by_category": [{"category": c, "count": n} for c, n in by_category],
        "by_severity": [{"severity": s, "count": n} for s, n in by_severity],
        "recent_alerts": [
            {
                "application_id": a.application_id,
                "category": a.category,
                "severity": a.severity,
                "status": a.status,
                "message": a.message,
                "created_at": a.created_at.isoformat() if a.created_at else None,
            }
            for a in recent
        ],
    }
