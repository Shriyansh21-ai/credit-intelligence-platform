"""Job registry and runner.

Jobs are keyed by name and each returns a JSON-able result. ``run_all_jobs``
executes every registered job, isolating failures so one bad job cannot abort the
batch.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List

from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.app.models.covenant import CovenantAlert
from backend.app.models.monitoring import MonitoringAlert
from backend.app.services import tasks


def job_due_task_scan(db: Session) -> Dict[str, Any]:
    """Notify owners of due/overdue open tasks."""
    notified = tasks.scan_due_tasks(db)
    return {"notified": notified}


def job_open_alert_summary(db: Session) -> Dict[str, Any]:
    """Roll up open covenant and monitoring alerts (health snapshot)."""
    open_cov = db.query(func.count(CovenantAlert.id)).filter(CovenantAlert.status == "open").scalar() or 0
    open_mon = db.query(func.count(MonitoringAlert.id)).filter(MonitoringAlert.status == "open").scalar() or 0
    return {"open_covenant_alerts": open_cov, "open_monitoring_alerts": open_mon}


def job_ml_drift_retrain_scan(db: Session) -> Dict[str, Any]:
    """Scheduled retraining: retrain any production model whose
    latest drift report has breached thresholds. Challengers are left pending
    approval (no auto-promotion) so a human owns the production decision."""
    from backend.app.services.ml import retraining

    outcomes = retraining.scan_and_retrain(db, auto_promote=False, author="scheduled-job")
    return {
        "retrained": len(outcomes),
        "models": [{"model_key": o["model_key"], "challenger_id": o["challenger_id"],
                    "winner": o["comparison"]["winner"]} for o in outcomes],
    }


# name -> (callable, description)
JOBS: Dict[str, Dict[str, Any]] = {
    "due_task_scan": {"fn": job_due_task_scan, "description": "Notify owners of due/overdue tasks."},
    "open_alert_summary": {"fn": job_open_alert_summary, "description": "Summarise open risk alerts."},
    "ml_drift_retrain_scan": {"fn": job_ml_drift_retrain_scan,
                              "description": "Retrain production models with breached drift (M9)."},
}


def list_jobs() -> List[Dict[str, str]]:
    return [{"name": name, "description": spec["description"]} for name, spec in JOBS.items()]


def run_job(db: Session, name: str) -> Dict[str, Any]:
    spec = JOBS.get(name)
    if spec is None:
        raise KeyError(f"Unknown job: {name}")
    result = spec["fn"](db)
    return {"job": name, "ok": True, "result": result}


def run_all_jobs(db: Session) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    for name in JOBS:
        try:
            results.append(run_job(db, name))
        except Exception as exc:  # isolate failures
            results.append({"job": name, "ok": False, "error": str(exc)})
    return results
