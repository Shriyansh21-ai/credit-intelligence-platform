"""Collaboration API (Phase 5, Milestone 8).

    GET    /api/collaboration/applications/{app_id}/notes      threaded notes (pinned first)
    POST   /api/collaboration/applications/{app_id}/notes      add a note / reply
    PATCH  /api/collaboration/notes/{id}                        edit a note
    DELETE /api/collaboration/notes/{id}                        soft-delete a note
    POST   /api/collaboration/notes/{id}/pin                    pin / unpin
    POST   /api/collaboration/notes/{id}/attachments           upload an attachment
    GET    /api/collaboration/applications/{app_id}/activity    unified activity feed
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status as http_status
from sqlalchemy.orm import Session

from backend.app.db.database import get_db
from backend.app.models.collaboration import Note
from backend.app.models.user import User
from backend.app.schemas.collaboration import NoteCreate, NoteEdit, PinUpdate
from backend.app.services import collaboration
from backend.app.services.collaboration.service import threaded_notes
from backend.app.services.rbac import require_permission

router = APIRouter(prefix="/api/collaboration", tags=["Collaboration"])


def _get_note(db: Session, note_id: int) -> Note:
    note = db.query(Note).filter(Note.id == note_id).first()
    if note is None:
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="Note not found")
    return note


@router.get("/applications/{application_id}/notes")
def list_notes(
    application_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(require_permission("collaboration.view")),
):
    return {"notes": threaded_notes(db, application_id)}


@router.post("/applications/{application_id}/notes", status_code=http_status.HTTP_201_CREATED)
def add_note(
    application_id: int,
    payload: NoteCreate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("collaboration.participate")),
):
    note = collaboration.create_note(
        db,
        application_id=application_id,
        actor=actor,
        body=payload.body,
        parent_id=payload.parent_id,
        mentions=payload.mentions,
    )
    return collaboration.serialize_note(note)


@router.patch("/notes/{note_id}")
def edit_note(
    note_id: int,
    payload: NoteEdit,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("collaboration.participate")),
):
    note = _get_note(db, note_id)
    collaboration.edit_note(db, note, actor=actor, body=payload.body)
    return collaboration.serialize_note(note)


@router.delete("/notes/{note_id}")
def delete_note(
    note_id: int,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("collaboration.participate")),
):
    note = _get_note(db, note_id)
    collaboration.delete_note(db, note, actor=actor)
    return {"deleted": True, "id": note_id}


@router.post("/notes/{note_id}/pin")
def pin_note(
    note_id: int,
    payload: PinUpdate,
    db: Session = Depends(get_db),
    _user: User = Depends(require_permission("collaboration.participate")),
):
    note = _get_note(db, note_id)
    collaboration.set_pinned(db, note, pinned=payload.pinned)
    return collaboration.serialize_note(note)


@router.post("/notes/{note_id}/attachments", status_code=http_status.HTTP_201_CREATED)
async def upload_attachment(
    note_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("collaboration.participate")),
):
    note = _get_note(db, note_id)
    data = await file.read()
    attachment = collaboration.add_attachment(
        db, note,
        filename=file.filename or "attachment",
        data=data,
        mime_type=file.content_type,
        actor=actor,
    )
    return {
        "id": attachment.id,
        "note_id": attachment.note_id,
        "filename": attachment.filename,
        "size_bytes": attachment.size_bytes,
        "mime_type": attachment.mime_type,
    }


@router.get("/applications/{application_id}/activity")
def activity(
    application_id: int,
    limit: int = 100,
    db: Session = Depends(get_db),
    _user: User = Depends(require_permission("collaboration.view")),
):
    return {"activity": collaboration.activity_feed(db, application_id, limit=limit)}
