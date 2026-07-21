"""Background jobs API (Phase 5, Milestone 14).

    GET  /api/jobs             list registered jobs        (config.view)
    POST /api/jobs/run-all      run every job              (config.manage)
    POST /api/jobs/run/{name}   run a single job           (config.manage)
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status as http_status
from sqlalchemy.orm import Session

from backend.app.db.database import get_db
from backend.app.models.user import User
from backend.app.services import audit, jobs
from backend.app.services.rbac import require_permission

router = APIRouter(prefix="/api/jobs", tags=["Jobs"])


@router.get("")
def get_jobs(_user: User = Depends(require_permission("config.view"))):
    return {"jobs": jobs.list_jobs()}


@router.post("/run-all")
def run_all(
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("config.manage")),
):
    results = jobs.run_all_jobs(db)
    audit.record_safe(db, action="jobs.run_all", actor=actor, entity_type="jobs", meta={"count": len(results)})
    return {"results": results}


@router.post("/run/{name}")
def run_one(
    name: str,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("config.manage")),
):
    try:
        result = jobs.run_job(db, name)
    except KeyError as exc:
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail=str(exc))
    audit.record_safe(db, action="jobs.run", actor=actor, entity_type="jobs", meta={"job": name})
    return result
