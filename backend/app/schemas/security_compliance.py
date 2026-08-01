"""Request schemas for the Security & Compliance API (Stage 4)."""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class ScanRequest(BaseModel):
    scan_type: str = Field(default="full")
    tenant_id: Optional[int] = None


class FindingStatusUpdate(BaseModel):
    status: str  # open|acknowledged|resolved|accepted|false_positive


class ComplianceAssessRequest(BaseModel):
    framework: str
    tenant_id: Optional[int] = None


class RiskCreate(BaseModel):
    title: str
    category: str
    likelihood: int = Field(ge=1, le=5, default=3)
    impact: int = Field(ge=1, le=5, default=3)
    description: str = ""
    treatment: str = "mitigate"
    residual_likelihood: Optional[int] = Field(default=None, ge=1, le=5)
    residual_impact: Optional[int] = Field(default=None, ge=1, le=5)
    mitigations: List[str] = Field(default_factory=list)
    owner: Optional[str] = None
    tenant_id: Optional[int] = None


class RiskUpdate(BaseModel):
    title: Optional[str] = None
    category: Optional[str] = None
    description: Optional[str] = None
    treatment: Optional[str] = None
    owner: Optional[str] = None
    status: Optional[str] = None
    likelihood: Optional[int] = Field(default=None, ge=1, le=5)
    impact: Optional[int] = Field(default=None, ge=1, le=5)
    residual_likelihood: Optional[int] = Field(default=None, ge=1, le=5)
    residual_impact: Optional[int] = Field(default=None, ge=1, le=5)
    mitigations: Optional[List[str]] = None


class PrivacyRequestCreate(BaseModel):
    subject_ref: str
    request_type: str
    legal_basis: Optional[str] = None
    notes: str = ""
    tenant_id: Optional[int] = None


class PrivacyRequestUpdate(BaseModel):
    status: str
    notes: Optional[str] = None
