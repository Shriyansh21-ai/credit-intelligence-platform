"""Pydantic schemas for the notification API."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class PreferenceUpdate(BaseModel):
    event_type: str
    in_app: Optional[bool] = None
    email: Optional[bool] = None
    webhook: Optional[bool] = None
