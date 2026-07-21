"""Task management models (Phase 5, Milestone 9).

A ``Task`` is a unit of work usually attached to an application (collect GST,
verify bank statement, review financials, ...), with an owner, priority, due
date and status. ``TaskComment`` threads discussion on a task.
"""

from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from backend.app.db.database import Base


class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    application_id = Column(
        Integer, ForeignKey("applications.id", ondelete="CASCADE"), nullable=True, index=True
    )

    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    task_type = Column(String, nullable=True, index=True)

    owner_id = Column(Integer, nullable=True, index=True)  # assignee
    created_by = Column(Integer, nullable=True)

    priority = Column(String, nullable=False, default="medium")  # low/medium/high/urgent
    status = Column(String, nullable=False, default="open", index=True)  # open/in_progress/blocked/completed/cancelled

    due_date = Column(DateTime, nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    comments = relationship(
        "TaskComment",
        back_populates="task",
        order_by="TaskComment.created_at",
        cascade="all, delete-orphan",
    )


class TaskComment(Base):
    __tablename__ = "task_comments"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True)
    author_id = Column(Integer, nullable=True)
    author_email = Column(String, nullable=True)
    body = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    task = relationship("Task", back_populates="comments")
