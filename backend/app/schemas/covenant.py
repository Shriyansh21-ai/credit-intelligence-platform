"""Pydantic schemas for the covenant API (Phase 5, Milestone 5)."""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel


class CovenantCreate(BaseModel):
    metric_key: str
    threshold: float
    operator: Optional[str] = None
    name: Optional[str] = None
    unit: Optional[str] = None
    description: Optional[str] = None


class MeasurementCreate(BaseModel):
    value: Optional[float] = None
    period: Optional[str] = None
    source: Optional[str] = None
    note: Optional[str] = None


class AlertStatusUpdate(BaseModel):
    status: str


class BatchMeasurementItem(BaseModel):
    covenant_id: int
    value: Optional[float] = None
    period: Optional[str] = None
    source: Optional[str] = None


class BatchMeasurementRequest(BaseModel):
    items: List[BatchMeasurementItem]
