"""Pydantic schemas for the Document Intelligence API (Task 11)."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class DocumentType(str, Enum):
    balance_sheet = "balance_sheet"
    profit_loss = "profit_loss"
    profit_and_loss = "profit_and_loss"
    cash_flow = "cash_flow"
    bank_statement = "bank_statement"
    financial_summary = "financial_summary"
    gst_return = "gst_return"
    income_tax_return = "income_tax_return"
    business_registration = "business_registration"
    other = "other"


class DocumentStatus(str, Enum):
    uploaded = "uploaded"
    queued = "queued"
    processing = "processing"
    extracting = "processing"  # legacy alias
    extracted = "extracted"
    needs_review = "needs_review"
    reviewed = "reviewed"  # legacy alias
    approved = "approved"
    partially_approved = "partially_approved"
    rejected = "rejected"
    failed = "failed"
    deletion_pending = "deletion_pending"
    deleted = "deleted"


class ConfidenceLevel(str, Enum):
    high = "high"
    medium = "medium"
    low = "low"


def confidence_level(score: Optional[float]) -> ConfidenceLevel:
    if score is None:
        return ConfidenceLevel.low
    if score >= 0.85:
        return ConfidenceLevel.high
    if score >= 0.60:
        return ConfidenceLevel.medium
    return ConfidenceLevel.low


class BoundingBoxSchema(BaseModel):
    x: float
    y: float
    width: float
    height: float
    page: int = 0


class ExtractedFieldSchema(BaseModel):
    key: str
    label: str
    type: str
    value: Optional[Any] = None
    extracted_value: Optional[Any] = None
    normalized_value: Optional[Any] = None
    raw_text: Optional[str] = None
    confidence: Optional[float] = None
    confidence_level: ConfidenceLevel = ConfidenceLevel.low
    bbox: Optional[BoundingBoxSchema] = None
    edited: bool = False


class ValidationIssueSchema(BaseModel):
    field: Optional[str] = None
    severity: str
    message: str


class DocumentSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: int
    company_id: Optional[int] = None
    fiscal_year: Optional[int] = None
    currency: Optional[str] = None
    unit: str = "units"
    document_type: str
    original_filename: str
    mime_type: str
    size_bytes: int
    status: str
    ocr_source: Optional[str] = None
    page_count: Optional[int] = None
    content_hash: str
    reviewed_by: Optional[int] = None
    reviewed_at: Optional[datetime] = None
    approved_by: Optional[int] = None
    approved_at: Optional[datetime] = None
    rejected_by: Optional[int] = None
    rejected_at: Optional[datetime] = None
    rejection_reason: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None


class DocumentExtractionSchema(BaseModel):
    version: int
    is_current: bool
    source: Optional[str] = None
    provider: Optional[str] = None
    provider_version: Optional[str] = None
    overall_confidence: Optional[float] = None
    fields: List[ExtractedFieldSchema] = Field(default_factory=list)
    validation: List[ValidationIssueSchema] = Field(default_factory=list)
    created_at: datetime


class DocumentDetail(DocumentSummary):
    current_extraction: Optional[DocumentExtractionSchema] = None


class UploadResponse(BaseModel):
    documents: List[DocumentSummary]
    duplicates: List[str] = Field(default_factory=list)


class ExtractResponse(BaseModel):
    document: DocumentDetail


class ReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Map of field key -> corrected value.
    fields: Dict[str, Any] = Field(default_factory=dict)
    document_type: Optional[DocumentType] = None
    company_id: Optional[int] = None
    fiscal_year: Optional[int] = Field(default=None, ge=1900, le=2200)
    currency: Optional[str] = Field(default=None, pattern=r"^[A-Za-z]{3}$")
    unit: Optional[Literal["units", "thousands", "millions", "lakhs", "crores"]] = None


class ApproveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    acknowledged_warnings: List[str] = Field(default_factory=list)
    replace_existing_financials: bool = False


class RejectRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=1, max_length=1000)


class HistoryResponse(BaseModel):
    documents: List[DocumentSummary]
