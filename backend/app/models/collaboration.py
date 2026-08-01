"""Collaboration models.

``Note`` powers internal notes, comments, threaded review discussions and pinned
notes on an application (a ``parent_id`` makes a note a reply). ``NoteAttachment``
links files (stored via the shared storage backend) to a note.
"""

from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from backend.app.db.database import Base


class Note(Base):
    __tablename__ = "notes"

    id = Column(Integer, primary_key=True, index=True)
    application_id = Column(
        Integer, ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True
    )
    parent_id = Column(Integer, ForeignKey("notes.id", ondelete="CASCADE"), nullable=True, index=True)

    author_id = Column(Integer, nullable=True, index=True)
    author_email = Column(String, nullable=True)

    body = Column(Text, nullable=False)
    # List of mentioned user ids (JSON-ish stored as comma string kept simple).
    is_pinned = Column(Boolean, nullable=False, default=False, index=True)
    is_deleted = Column(Boolean, nullable=False, default=False, index=True)

    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    attachments = relationship(
        "NoteAttachment",
        back_populates="note",
        cascade="all, delete-orphan",
    )
    mentions = relationship(
        "NoteMention",
        back_populates="note",
        cascade="all, delete-orphan",
    )


class NoteMention(Base):
    __tablename__ = "note_mentions"

    id = Column(Integer, primary_key=True, index=True)
    note_id = Column(Integer, ForeignKey("notes.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, nullable=False, index=True)

    note = relationship("Note", back_populates="mentions")


class NoteAttachment(Base):
    __tablename__ = "note_attachments"

    id = Column(Integer, primary_key=True, index=True)
    note_id = Column(Integer, ForeignKey("notes.id", ondelete="CASCADE"), nullable=False, index=True)

    filename = Column(String, nullable=False)
    mime_type = Column(String, nullable=True)
    size_bytes = Column(Integer, nullable=True)
    storage_uri = Column(String, nullable=False)
    uploaded_by = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    note = relationship("Note", back_populates="attachments")
