"""Pydantic schemas for the application lifecycle & approval APIs (Phase 5)."""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel


class ApplicationCreate(BaseModel):
    company_name: str
    industry: Optional[str] = None
    gstin: Optional[str] = None
    pan: Optional[str] = None
    requested_amount: Optional[float] = None
    loan_purpose: Optional[str] = None
    tenure_months: Optional[int] = None
    assessment_id: Optional[int] = None
    assigned_to: Optional[int] = None


class ApplicationUpdate(BaseModel):
    company_name: Optional[str] = None
    industry: Optional[str] = None
    gstin: Optional[str] = None
    pan: Optional[str] = None
    requested_amount: Optional[float] = None
    loan_purpose: Optional[str] = None
    tenure_months: Optional[int] = None
    assessment_id: Optional[int] = None
    assigned_to: Optional[int] = None
    loan_id: Optional[str] = None
    risk_rating: Optional[str] = None
    risk_grade: Optional[str] = None


class TransitionRequest(BaseModel):
    to_status: str
    reason: Optional[str] = None
    comment: Optional[str] = None


class RollbackRequest(BaseModel):
    reason: Optional[str] = None


class DecisionRequest(BaseModel):
    action: str
    stage_key: Optional[str] = None
    comment: Optional[str] = None


class WorkflowUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None
    stages: Optional[List[dict]] = None
