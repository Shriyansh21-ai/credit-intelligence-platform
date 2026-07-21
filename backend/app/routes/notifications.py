"""Notification API (Phase 5, Milestone 10).

All endpoints operate on the *current user's* own notifications.

    GET   /api/notifications                 list (unread filter + paginate)
    GET   /api/notifications/unread-count     unread badge count
    GET   /api/notifications/events           event catalog
    POST  /api/notifications/{id}/read        mark one read
    POST  /api/notifications/read-all         mark all read
    GET   /api/notifications/preferences      per-event channel preferences
    PUT   /api/notifications/preferences      update a preference
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status as http_status
from sqlalchemy.orm import Session

from backend.app.core.dependencies import get_current_user
from backend.app.db.database import get_db
from backend.app.models.user import User
from backend.app.schemas.notification import PreferenceUpdate
from backend.app.services import notifications
from backend.app.services.notifications.catalog import EVENT_TYPES

router = APIRouter(prefix="/api/notifications", tags=["Notifications"])


@router.get("")
def list_notifications(
    unread_only: bool = False,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return notifications.list_notifications(
        db, user.id, unread_only=unread_only, page=page, page_size=page_size
    )


@router.get("/unread-count")
def unread_count(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return {"unread": notifications.unread_count(db, user.id)}


@router.get("/events")
def events(_user: User = Depends(get_current_user)):
    return {"events": [{"event_type": k, **v} for k, v in EVENT_TYPES.items()]}


@router.post("/{notification_id}/read")
def mark_read(
    notification_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    n = notifications.mark_read(db, user.id, notification_id)
    if n is None:
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="Notification not found")
    return notifications.service.serialize(n)


@router.post("/read-all")
def mark_all_read(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return {"updated": notifications.mark_all_read(db, user.id)}


@router.get("/preferences")
def get_preferences(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return {"preferences": notifications.get_preferences(db, user.id)}


@router.put("/preferences")
def update_preference(
    payload: PreferenceUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return notifications.set_preference(
        db, user.id, payload.event_type,
        in_app=payload.in_app, email=payload.email, webhook=payload.webhook,
    )
