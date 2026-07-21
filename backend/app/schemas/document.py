"""Pydantic schemas for the Document Intelligence API (Task 11)."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class DocumentType(str, Enum):
    balance_sheet = "balance_sheet"
    profit_loss = "profit_loss"
    cash_flow = "cash_flow"
    bank_statement = "bank_statement"
    gst_return = "gst_return"
    income_tax_return = "income_tax_return"
    business_registration = "business_registration"
    other = "other"


class DocumentStatus(str, Enum):
    uploaded = "uploaded"
    extracting = "extracting"
    extracted = "extracted"
    reviewed = "reviewed"
    failed = "failed"


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
    raw_text: Optional[str] = None
    confidence: float = 0.0
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
    document_type: str
    original_filename: str
    mime_type: str
    size_bytes: int
    status: str
    ocr_source: Optional[str] = None
    page_count: Optional[int] = None
    content_hash: str
    created_at: datetime
    updated_at: Optional[datetime] = None


class DocumentExtractionSchema(BaseModel):
    version: int
    is_current: bool
    source: Optional[str] = None
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
    # Map of field key -> corrected value.
    fields: Dict[str, Any]
    document_type: Optional[DocumentType] = None
    mark_reviewed: bool = True


class HistoryResponse(BaseModel):
    documents: List[DocumentSummary]
