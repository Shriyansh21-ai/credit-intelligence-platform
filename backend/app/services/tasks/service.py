"""Task service — CRUD, status transitions, comments, due scans.

Side effects
    - Assigning a task notifies the owner (``task_assigned``).
    - Completing a task notifies the creator (``task_completed``).
    - ``scan_due_tasks`` notifies owners of due/overdue open tasks (``task_due``).
All mutations are audited.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from backend.app.models.task import Task, TaskComment
from backend.app.services import audit, notifications

TASK_TYPES = (
    "collect_gst",
    "verify_bank_statement",
    "review_financials",
    "approve_risk",
    "contact_customer",
    "verify_collateral",
    "other",
)

_OPEN_STATUSES = ("open", "in_progress", "blocked")


def create_task(
    db: Session,
    *,
    title: str,
    actor: Any,
    application_id: Optional[int] = None,
    description: Optional[str] = None,
    task_type: Optional[str] = None,
    owner_id: Optional[int] = None,
    priority: str = "medium",
    due_date: Optional[datetime] = None,
) -> Task:
    task = Task(
        application_id=application_id,
        title=title,
        description=description,
        task_type=task_type,
        owner_id=owner_id,
        created_by=getattr(actor, "id", None),
        priority=priority,
        due_date=due_date,
        status="open",
    )
    db.add(task)
    db.commit()
    db.refresh(task)

    audit.record_safe(
        db, action="task.create", actor=actor, entity_type="task", entity_id=task.id,
        new_value={"title": title, "owner_id": owner_id, "application_id": application_id},
    )
    if owner_id:
        notifications.notify(
            db, user_id=owner_id, event_type="task_assigned",
            title="Task assigned", message=title,
            entity_type="task", entity_id=task.id,
            data={"application_id": application_id, "priority": priority},
        )
    return task


def update_task(
    db: Session,
    task: Task,
    *,
    actor: Any,
    updates: Dict[str, Any],
) -> Task:
    """Apply field updates; fire notifications on (re)assignment and completion."""
    before = serialize_task(task)
    prev_owner = task.owner_id
    prev_status = task.status

    allowed = {"title", "description", "task_type", "owner_id", "priority", "status", "due_date"}
    for field, value in updates.items():
        if field in allowed:
            setattr(task, field, value)

    if task.status == "completed" and prev_status != "completed":
        task.completed_at = datetime.utcnow()

    db.commit()
    db.refresh(task)

    audit.record_safe(
        db, action="task.update", actor=actor, entity_type="task", entity_id=task.id,
        previous_value=before, new_value=serialize_task(task),
    )

    # Reassignment -> notify the new owner.
    if task.owner_id and task.owner_id != prev_owner:
        notifications.notify(
            db, user_id=task.owner_id, event_type="task_assigned",
            title="Task assigned", message=task.title,
            entity_type="task", entity_id=task.id,
        )

    # Completion -> notify the creator (if different from the actor).
    if task.status == "completed" and prev_status != "completed" and task.created_by:
        notifications.notify(
            db, user_id=task.created_by, event_type="task_completed",
            title="Task completed", message=task.title,
            entity_type="task", entity_id=task.id,
        )
    return task


def add_comment(db: Session, task: Task, *, actor: Any, body: str) -> TaskComment:
    comment = TaskComment(
        task_id=task.id,
        author_id=getattr(actor, "id", None),
        author_email=getattr(actor, "email", None),
        body=body,
    )
    db.add(comment)
    db.commit()
    db.refresh(comment)
    # Notify the owner of new activity (unless they authored it).
    if task.owner_id and task.owner_id != getattr(actor, "id", None):
        notifications.notify(
            db, user_id=task.owner_id, event_type="task_assigned",
            title="New comment on your task", message=task.title,
            entity_type="task", entity_id=task.id,
        )
    return comment


def list_tasks(
    db: Session,
    *,
    application_id: Optional[int] = None,
    owner_id: Optional[int] = None,
    status: Optional[str] = None,
) -> List[Task]:
    query = db.query(Task)
    if application_id is not None:
        query = query.filter(Task.application_id == application_id)
    if owner_id is not None:
        query = query.filter(Task.owner_id == owner_id)
    if status:
        query = query.filter(Task.status == status)
    return query.order_by(Task.due_date.is_(None), Task.due_date, Task.id.desc()).all()


def list_comments(db: Session, task: Task) -> List[TaskComment]:
    return (
        db.query(TaskComment)
        .filter(TaskComment.task_id == task.id)
        .order_by(TaskComment.created_at, TaskComment.id)
        .all()
    )


def scan_due_tasks(db: Session, *, now: Optional[datetime] = None) -> int:
    """Notify owners of open tasks that are due/overdue. Returns count notified.

    Intended to be invoked by a scheduled/background job (M14).
    """
    now = now or datetime.utcnow()
    due = (
        db.query(Task)
        .filter(
            Task.status.in_(_OPEN_STATUSES),
            Task.due_date.isnot(None),
            Task.due_date <= now,
            Task.owner_id.isnot(None),
        )
        .all()
    )
    for task in due:
        notifications.notify(
            db, user_id=task.owner_id, event_type="task_due",
            title="Task due", message=task.title,
            entity_type="task", entity_id=task.id,
            data={"due_date": task.due_date.isoformat() if task.due_date else None},
        )
    return len(due)


def serialize_task(task: Task) -> Dict[str, Any]:
    return {
        "id": task.id,
        "application_id": task.application_id,
        "title": task.title,
        "description": task.description,
        "task_type": task.task_type,
        "owner_id": task.owner_id,
        "created_by": task.created_by,
        "priority": task.priority,
        "status": task.status,
        "due_date": task.due_date.isoformat() if task.due_date else None,
        "created_at": task.created_at.isoformat() if task.created_at else None,
        "updated_at": task.updated_at.isoformat() if task.updated_at else None,
        "completed_at": task.completed_at.isoformat() if task.completed_at else None,
    }


def serialize_comment(c: TaskComment) -> Dict[str, Any]:
    return {
        "id": c.id,
        "task_id": c.task_id,
        "author_id": c.author_id,
        "author_email": c.author_email,
        "body": c.body,
        "created_at": c.created_at.isoformat() if c.created_at else None,
    }
