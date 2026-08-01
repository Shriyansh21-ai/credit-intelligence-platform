"""Pydantic schemas for the monitoring API."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class MonitoringRecordCreate(BaseModel):
    record_type: str
    period: Optional[str] = None
    health_score: Optional[float] = None
    risk_rating: Optional[str] = None
    payment_status: Optional[str] = None
    data: Optional[dict] = None
    note: Optional[str] = None


class MonitoringAlertUpdate(BaseModel):
    status: str
