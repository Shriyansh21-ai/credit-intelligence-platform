"""Task management API.

    GET /api/tasks/types supported task types
    POST /api/tasks create a task
    GET /api/tasks list (filter: application_id, owner_id, status, mine)
    GET /api/tasks/{id} task detail (+ comments)
    PATCH /api/tasks/{id} update (status, reassign, ...)
    POST /api/tasks/{id}/comments add a comment
    GET /api/tasks/{id}/comments list comments
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status as http_status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from backend.app.core.dependencies import get_current_tenant_id
from backend.app.db.database import get_db
from backend.app.models.application import Application
from backend.app.models.task import Task
from backend.app.models.user import User
from backend.app.schemas.task import TaskCommentCreate, TaskCreate, TaskUpdate
from backend.app.services import tasks
from backend.app.services.lifecycle.service import find_application_for_tenant
from backend.app.services.tasks.service import serialize_comment
from backend.app.services.rbac import require_permission

router = APIRouter(prefix="/api/tasks", tags=["Tasks"])


def _get_task(db: Session, task_id: int, tenant_id: int) -> Task:
    task = (
        db.query(Task)
        .outerjoin(Application, Application.id == Task.application_id)
        .filter(
            Task.id == task_id,
            or_(Task.application_id.is_(None), Application.tenant_id == tenant_id),
        )
        .first()
    )
    if task is None:
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="Task not found")
    return task


@router.get("/types")
def task_types(_user: User = Depends(require_permission("tasks.view"))):
    return {"task_types": list(tasks.TASK_TYPES)}


@router.post("", status_code=http_status.HTTP_201_CREATED)
def create_task(
    payload: TaskCreate,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    actor: User = Depends(require_permission("tasks.manage")),
):
    if payload.application_id is not None and find_application_for_tenant(
        db, payload.application_id, tenant_id
    ) is None:
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="Application not found")
    task = tasks.create_task(
        db,
        title=payload.title,
        actor=actor,
        application_id=payload.application_id,
        description=payload.description,
        task_type=payload.task_type,
        owner_id=payload.owner_id,
        priority=payload.priority,
        due_date=payload.due_date,
    )
    return tasks.serialize_task(task)


@router.get("")
def list_tasks(
    application_id: Optional[int] = None,
    owner_id: Optional[int] = None,
    status: Optional[str] = None,
    mine: bool = False,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    user: User = Depends(require_permission("tasks.view")),
):
    if mine:
        owner_id = user.id
    if application_id is not None and find_application_for_tenant(
        db, application_id, tenant_id
    ) is None:
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="Application not found")
    rows = tasks.list_tasks(
        db,
        tenant_id=tenant_id,
        application_id=application_id,
        owner_id=owner_id,
        status=status,
    )
    return {"tasks": [tasks.serialize_task(t) for t in rows]}


@router.get("/{task_id}")
def get_task(
    task_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    _user: User = Depends(require_permission("tasks.view")),
):
    task = _get_task(db, task_id, tenant_id)
    data = tasks.serialize_task(task)
    data["comments"] = [serialize_comment(c) for c in tasks.list_comments(db, task)]
    return data


@router.patch("/{task_id}")
def update_task(
    task_id: int,
    payload: TaskUpdate,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    actor: User = Depends(require_permission("tasks.manage")),
):
    task = _get_task(db, task_id, tenant_id)
    updates = payload.model_dump(exclude_unset=True)
    tasks.update_task(db, task, actor=actor, updates=updates)
    return tasks.serialize_task(task)


@router.post("/{task_id}/comments", status_code=http_status.HTTP_201_CREATED)
def add_comment(
    task_id: int,
    payload: TaskCommentCreate,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    actor: User = Depends(require_permission("tasks.view")),
):
    task = _get_task(db, task_id, tenant_id)
    comment = tasks.add_comment(db, task, actor=actor, body=payload.body)
    return serialize_comment(comment)


@router.get("/{task_id}/comments")
def list_comments(
    task_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    _user: User = Depends(require_permission("tasks.view")),
):
    task = _get_task(db, task_id, tenant_id)
    return {"comments": [serialize_comment(c) for c in tasks.list_comments(db, task)]}
