"""Pydantic schemas for the notification API (Phase 5, Milestone 10)."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class PreferenceUpdate(BaseModel):
    event_type: str
    in_app: Optional[bool] = None
    email: Optional[bool] = None
    webhook: Optional[bool] = None
