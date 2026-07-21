"""Collaboration service — notes, threads, mentions, pins, attachments, feed.

Mentions are resolved from an explicit ``mentions`` list of user ids *and* from
``@email`` tokens parsed out of the note body; each mentioned user receives a
``mention`` notification. The activity feed aggregates status history, approval
decisions, notes and tasks into one chronological stream per application.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from backend.app.models.application import ApplicationStatusHistory
from backend.app.models.approval import ApprovalDecision
from backend.app.models.collaboration import Note, NoteAttachment, NoteMention
from backend.app.models.task import Task
from backend.app.models.user import User
from backend.app.services import audit, notifications

_EMAIL_MENTION = re.compile(r"@([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})")


def resolve_mentions(
    db: Session, body: str, explicit: Optional[List[int]] = None
) -> List[int]:
    """Return the set of mentioned user ids from explicit ids + @email tokens."""
    ids = set(explicit or [])
    emails = _EMAIL_MENTION.findall(body or "")
    if emails:
        rows = db.query(User).filter(User.email.in_(emails)).all()
        ids.update(u.id for u in rows)
    return sorted(ids)


def create_note(
    db: Session,
    *,
    application_id: int,
    actor: Any,
    body: str,
    parent_id: Optional[int] = None,
    mentions: Optional[List[int]] = None,
) -> Note:
    note = Note(
        application_id=application_id,
        parent_id=parent_id,
        author_id=getattr(actor, "id", None),
        author_email=getattr(actor, "email", None),
        body=body,
    )
    db.add(note)
    db.commit()
    db.refresh(note)

    mentioned = resolve_mentions(db, body, mentions)
    for uid in mentioned:
        db.add(NoteMention(note_id=note.id, user_id=uid))
    if mentioned:
        db.commit()

    audit.record_safe(
        db, action="collaboration.note", actor=actor,
        entity_type="application", entity_id=application_id,
        new_value={"note_id": note.id, "parent_id": parent_id},
    )

    # Notify mentioned users (except the author).
    author_id = getattr(actor, "id", None)
    for uid in mentioned:
        if uid == author_id:
            continue
        notifications.notify(
            db, user_id=uid, event_type="mention",
            title="You were mentioned",
            message=body[:140],
            entity_type="note", entity_id=note.id,
            data={"application_id": application_id},
        )
    return note


def edit_note(db: Session, note: Note, *, actor: Any, body: str) -> Note:
    note.body = body
    db.commit()
    db.refresh(note)
    audit.record_safe(
        db, action="collaboration.edit", actor=actor,
        entity_type="note", entity_id=note.id,
    )
    return note


def delete_note(db: Session, note: Note, *, actor: Any) -> None:
    note.is_deleted = True
    db.commit()
    audit.record_safe(
        db, action="collaboration.delete", actor=actor,
        entity_type="note", entity_id=note.id,
    )


def set_pinned(db: Session, note: Note, *, pinned: bool) -> Note:
    note.is_pinned = pinned
    db.commit()
    db.refresh(note)
    return note


def add_attachment(
    db: Session,
    note: Note,
    *,
    filename: str,
    data: bytes,
    mime_type: Optional[str],
    actor: Any,
) -> NoteAttachment:
    from backend.app.services.documents.storage import get_storage

    stored = get_storage().save("notes", filename, data)
    attachment = NoteAttachment(
        note_id=note.id,
        filename=filename,
        mime_type=mime_type,
        size_bytes=stored.size,
        storage_uri=stored.uri,
        uploaded_by=getattr(actor, "id", None),
    )
    db.add(attachment)
    db.commit()
    db.refresh(attachment)
    return attachment


def list_notes(
    db: Session, application_id: int, *, include_deleted: bool = False
) -> List[Note]:
    query = db.query(Note).filter(Note.application_id == application_id)
    if not include_deleted:
        query = query.filter(Note.is_deleted == False)  # noqa: E712
    return query.order_by(Note.created_at, Note.id).all()


def serialize_note(note: Note, *, threaded_children: Optional[List[Note]] = None) -> Dict[str, Any]:
    data = {
        "id": note.id,
        "application_id": note.application_id,
        "parent_id": note.parent_id,
        "author_id": note.author_id,
        "author_email": note.author_email,
        "body": note.body if not note.is_deleted else "[deleted]",
        "is_pinned": note.is_pinned,
        "is_deleted": note.is_deleted,
        "mentions": [m.user_id for m in note.mentions],
        "attachments": [
            {
                "id": a.id,
                "filename": a.filename,
                "mime_type": a.mime_type,
                "size_bytes": a.size_bytes,
            }
            for a in note.attachments
        ],
        "created_at": note.created_at.isoformat() if note.created_at else None,
        "updated_at": note.updated_at.isoformat() if note.updated_at else None,
    }
    if threaded_children is not None:
        data["replies"] = [serialize_note(c) for c in threaded_children]
    return data


def threaded_notes(db: Session, application_id: int) -> List[Dict[str, Any]]:
    """Top-level notes with their replies nested (one level)."""
    notes = list_notes(db, application_id)
    by_parent: Dict[Optional[int], List[Note]] = {}
    for n in notes:
        by_parent.setdefault(n.parent_id, []).append(n)

    roots = by_parent.get(None, [])
    # Pinned first, then chronological.
    roots.sort(key=lambda n: (not n.is_pinned, n.created_at or 0, n.id))
    return [serialize_note(r, threaded_children=by_parent.get(r.id, [])) for r in roots]


def activity_feed(db: Session, application_id: int, limit: int = 100) -> List[Dict[str, Any]]:
    """Unified chronological feed across status history, approvals, notes, tasks."""
    events: List[Dict[str, Any]] = []

    for h in (
        db.query(ApplicationStatusHistory)
        .filter(ApplicationStatusHistory.application_id == application_id)
        .all()
    ):
        events.append(
            {
                "kind": "status",
                "at": h.created_at.isoformat() if h.created_at else None,
                "actor": h.actor_email,
                "summary": f"{h.from_status or 'created'} → {h.to_status}",
                "detail": h.reason,
            }
        )

    for d in (
        db.query(ApprovalDecision)
        .filter(ApprovalDecision.application_id == application_id)
        .all()
    ):
        events.append(
            {
                "kind": "approval",
                "at": d.created_at.isoformat() if d.created_at else None,
                "actor": d.actor_email,
                "summary": f"{d.action} @ {d.stage_name or d.stage_key or 'stage'}",
                "detail": d.comment,
            }
        )

    for n in list_notes(db, application_id):
        events.append(
            {
                "kind": "note",
                "at": n.created_at.isoformat() if n.created_at else None,
                "actor": n.author_email,
                "summary": "commented" if n.parent_id else "added a note",
                "detail": n.body if not n.is_deleted else "[deleted]",
            }
        )

    for t in db.query(Task).filter(Task.application_id == application_id).all():
        events.append(
            {
                "kind": "task",
                "at": t.created_at.isoformat() if t.created_at else None,
                "actor": None,
                "summary": f"task '{t.title}' ({t.status})",
                "detail": t.description,
            }
        )

    events.sort(key=lambda e: e["at"] or "", reverse=True)
    return events[:limit]
