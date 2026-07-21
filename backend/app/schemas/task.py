"""Pydantic schemas for the task API (Phase 5, Milestone 9)."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class TaskCreate(BaseModel):
    title: str
    application_id: Optional[int] = None
    description: Optional[str] = None
    task_type: Optional[str] = None
    owner_id: Optional[int] = None
    priority: str = "medium"
    due_date: Optional[datetime] = None


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    task_type: Optional[str] = None
    owner_id: Optional[int] = None
    priority: Optional[str] = None
    status: Optional[str] = None
    due_date: Optional[datetime] = None


class TaskCommentCreate(BaseModel):
    body: str
