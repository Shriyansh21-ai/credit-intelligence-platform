"""Pydantic schemas for the collaboration API (Phase 5, Milestone 8)."""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel


class NoteCreate(BaseModel):
    body: str
    parent_id: Optional[int] = None
    mentions: Optional[List[int]] = None


class NoteEdit(BaseModel):
    body: str


class PinUpdate(BaseModel):
    pinned: bool
