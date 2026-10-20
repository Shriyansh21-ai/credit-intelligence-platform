"""Document Intelligence API.

    POST /documents/upload multi-file upload
    POST /documents/{id}/extract run OCR + field extraction
    GET /documents/{id} document + current extraction
    PUT /documents/{id}/review save corrected values (new version)
    DELETE /documents/{id} remove document + file
    GET /documents/history user's documents
    GET /documents/{id}/file stream original for the viewer
"""

from __future__ import annotations

import hashlib
import logging
from typing import List, Literal, Optional
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile, status
from sqlalchemy.orm import Session

from backend.app.config import settings
from backend.app.core.dependencies import get_current_tenant_id, get_current_user
from backend.app.db.database import get_db
from backend.app.models.company import Company, CompanyFinancials
from backend.app.models.document import Document, DocumentExtraction, DocumentReviewEvent
from backend.app.models.user import User
from backend.app.services.rbac import has_permission, require_permission
from backend.app.schemas.document import (
    ApproveRequest,
    DocumentType,
    RejectRequest,
)
from backend.app.schemas.document import (
    DocumentDetail,
    DocumentExtractionSchema,
    DocumentSummary,
    ExtractResponse,
    ExtractedFieldSchema,
    HistoryResponse,
    ReviewRequest,
    UploadResponse,
    confidence_level,
)
from backend.app.services.documents.document_service import (
    DocumentConflictError,
    DocumentService,
    DocumentValidationError,
)
from backend.app.services.financial_analysis.analysis_service import analyze_mapping

router = APIRouter(prefix="/documents", tags=["Documents"])
logger = logging.getLogger("app.documents")


# ---------------------------------------------------------------------------
# Serialization helpers
# ---------------------------------------------------------------------------

def _extraction_schema(extraction: Optional[DocumentExtraction]) -> Optional[DocumentExtractionSchema]:
    if extraction is None:
        return None
    fields = [
        ExtractedFieldSchema(
            **{**f, "confidence_level": confidence_level(f.get("confidence"))}
        )
        for f in (extraction.fields or [])
    ]
    return DocumentExtractionSchema(
        version=extraction.version,
        is_current=extraction.is_current,
        source=extraction.source,
        provider=extraction.provider,
        provider_version=extraction.provider_version,
        overall_confidence=extraction.overall_confidence,
        fields=fields,
        validation=extraction.validation or [],
        created_at=extraction.created_at,
    )


def _detail(service: DocumentService, document: Document) -> DocumentDetail:
    summary = DocumentSummary.model_validate(document, from_attributes=True)
    return DocumentDetail(
        **summary.model_dump(),
        current_extraction=_extraction_schema(service.current_extraction(document)),
    )


def _detect_file_mime(data: bytes) -> str:
    if data.startswith(b"%PDF"):
        return "application/pdf"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    raise HTTPException(
        status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
        detail="Could not verify the uploaded file type. Please upload a valid PDF, PNG, or JPG image.",
    )


def _validate_upload(file: UploadFile, data: bytes) -> str:
    if len(data) > settings.max_upload_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"{file.filename or 'uploaded file'} exceeds the {settings.MAX_UPLOAD_MB} MB limit.",
        )

    advertised = (file.content_type or "").lower()
    detected = _detect_file_mime(data)
    if detected not in settings.ALLOWED_UPLOAD_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported file type '{advertised or 'unknown'}'. Allowed: PDF, PNG, JPG.",
        )
    return detected


def _validate_company_for_tenant(db: Session, tenant_id: int, company_id: Optional[int]) -> Optional[int]:
    if company_id is None:
        return None
    company = db.query(Company).filter(Company.id == company_id, Company.tenant_id == tenant_id).first()
    if company is None:
        raise HTTPException(status_code=404, detail="Company not found for this tenant")
    return company.id


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/upload", response_model=UploadResponse)
async def upload_documents(
    files: List[UploadFile] = File(...),
    document_type: DocumentType = Form(DocumentType.other),
    company_id: Optional[int] = Form(None, ge=1),
    fiscal_year: Optional[int] = Form(None, ge=1900, le=2200),
    currency: Optional[str] = Form(None, min_length=3, max_length=3, pattern=r"^[A-Za-z]{3}$"),
    unit: Literal["units", "thousands", "millions", "lakhs", "crores"] = Form("units"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: int = Depends(get_current_tenant_id),
    _permission: User = Depends(require_permission("documents.upload")),
):
    service = DocumentService(db)
    created, duplicates = [], []
    validated_company_id = _validate_company_for_tenant(db, tenant_id, company_id)

    for file in files:
        data = await file.read(settings.max_upload_bytes + 1)
        if not data:
            continue
        mime = _validate_upload(file, data)

        if service.find_duplicate(tenant_id, hashlib.sha256(data).hexdigest()):
            duplicates.append(file.filename or "unknown")
            continue

        document = service.upload(
            tenant_id=tenant_id,
            user_id=current_user.id,
            filename=file.filename or "document",
            mime_type=mime,
            data=data,
            document_type=document_type.value,
            company_id=validated_company_id,
            fiscal_year=fiscal_year,
            currency=currency.upper() if currency else None,
            unit=unit,
        )
        created.append(document)

    return UploadResponse(
        documents=[DocumentSummary.model_validate(d, from_attributes=True) for d in created],
        duplicates=duplicates,
    )


@router.get("/companies")
def list_document_companies(
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    _permission: User = Depends(require_permission("documents.view")),
):
    companies = (
        db.query(Company.id, Company.name, Company.industry)
        .filter(Company.tenant_id == tenant_id)
        .order_by(Company.name, Company.id)
        .limit(500)
        .all()
    )
    return {"items": [{"id": row.id, "name": row.name, "industry": row.industry} for row in companies]}


@router.post("/{document_id}/extract", response_model=ExtractResponse)
def extract_document(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: int = Depends(get_current_tenant_id),
    _permission: User = Depends(require_permission("documents.upload")),
):
    service = DocumentService(db)
    document = service.get(tenant_id, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    try:
        service.extract(document)
    except DocumentConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("document extraction failed for document %s", document_id)
        raise HTTPException(status_code=500, detail="Document extraction failed.") from exc
    return ExtractResponse(document=_detail(service, document))


@router.get("/history", response_model=HistoryResponse)
def list_history(
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    _permission: User = Depends(require_permission("documents.view")),
):
    service = DocumentService(db)
    return HistoryResponse(documents=service.history(tenant_id))


@router.get("/{document_id}", response_model=DocumentDetail)
def get_document(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: int = Depends(get_current_tenant_id),
    _permission: User = Depends(require_permission("documents.view")),
):
    service = DocumentService(db)
    document = service.get(tenant_id, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return _detail(service, document)


@router.put("/{document_id}/review", response_model=ExtractResponse)
def review_document(
    document_id: int,
    payload: ReviewRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: int = Depends(get_current_tenant_id),
    _permission: User = Depends(require_permission("documents.upload")),
):
    service = DocumentService(db)
    document = service.get(tenant_id, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    try:
        service.review(
            document,
            payload.fields,
            actor_id=current_user.id,
            document_type=payload.document_type.value if payload.document_type else None,
            company_id=payload.company_id,
            fiscal_year=payload.fiscal_year,
            currency=payload.currency,
            unit=payload.unit,
        )
    except DocumentConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except DocumentValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return ExtractResponse(document=_detail(service, document))


@router.post("/{document_id}/approve")
def approve_document(
    document_id: int,
    payload: ApproveRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("approvals.approve")),
    tenant_id: int = Depends(get_current_tenant_id),
):
    service = DocumentService(db)
    document = service.get(tenant_id, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    if payload.replace_existing_financials and not has_permission(
        db, current_user, "approvals.override"
    ):
        raise HTTPException(status_code=403, detail="Missing required permission: approvals.override")
    try:
        financials = service.approve(
            document,
            actor_id=current_user.id,
            acknowledged_warnings=payload.acknowledged_warnings,
            replace_existing=payload.replace_existing_financials,
        )
    except DocumentConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except DocumentValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("document approval persistence failed for document %s", document_id)
        raise HTTPException(status_code=500, detail="Could not persist approved financials.") from exc
    return {
        "document": _detail(service, document),
        "persistence_status": "persisted",
        "financials": {
            "company_id": financials.company_id,
            "fiscal_year": financials.fiscal_year,
            "currency": financials.currency,
            "unit": financials.unit,
            "source_document_id": financials.source_document_id,
        },
    }


@router.post("/{document_id}/reject")
def reject_document(
    document_id: int,
    payload: RejectRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("approvals.reject")),
    tenant_id: int = Depends(get_current_tenant_id),
):
    service = DocumentService(db)
    document = service.get(tenant_id, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    try:
        service.reject(document, actor_id=current_user.id, reason=payload.reason)
    except DocumentConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return _detail(service, document)


@router.get("/{document_id}/review-history")
def get_review_history(
    document_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    _permission: User = Depends(require_permission("documents.view")),
):
    document = DocumentService(db).get(tenant_id, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    events = (
        db.query(DocumentReviewEvent)
        .filter(
            DocumentReviewEvent.document_id == document_id,
            DocumentReviewEvent.tenant_id == tenant_id,
        )
        .order_by(DocumentReviewEvent.created_at.asc(), DocumentReviewEvent.id.asc())
        .all()
    )
    return {
        "events": [
            {
                "id": event.id,
                "actor_id": event.actor_id,
                "event_type": event.event_type,
                "from_status": event.from_status,
                "to_status": event.to_status,
                "changes": event.changes,
                "reason": event.reason,
                "created_at": event.created_at,
            }
            for event in events
        ]
    }


@router.get("/{document_id}/analysis")
def analyze_approved_document(
    document_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    _permission: User = Depends(require_permission("analysis.run")),
):
    document = DocumentService(db).get(tenant_id, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    if document.status != "approved":
        raise HTTPException(status_code=409, detail="Only approved documents can be analyzed.")
    financials = (
        db.query(CompanyFinancials)
        .filter(
            CompanyFinancials.tenant_id == tenant_id,
            CompanyFinancials.source_document_id == document_id,
        )
        .first()
    )
    if financials is None:
        raise HTTPException(status_code=409, detail="Approved financial values were not persisted.")
    mapping = {
        "revenue": financials.revenue,
        "ebitda": financials.ebitda,
        "operating_income": financials.ebit,
        "net_profit": financials.net_income,
        "total_assets": financials.total_assets,
        "total_equity": financials.equity,
        "current_assets": financials.current_assets,
        "current_liabilities": financials.current_liabilities,
        "cash": financials.cash,
        "long_term_debt": financials.debt,
        "operating_cash_flow": financials.operating_cash_flow,
        "free_cash_flow": financials.free_cash_flow,
        "period": {"label": f"FY{financials.fiscal_year}", "fiscal_year": financials.fiscal_year},
    }
    analysis_available = (
        financials.revenue is not None
        and any(value is not None for value in (
            financials.ebitda, financials.net_income, financials.current_assets,
            financials.current_liabilities, financials.total_assets,
            financials.equity, financials.debt, financials.operating_cash_flow,
        ))
    )
    if not analysis_available:
        return {
            "analysis_status": "incomplete",
            "missing_required_fields": ["revenue and at least one additional financial metric"],
            "analysis": None,
        }
    analysis = analyze_mapping(mapping)
    missing = [
        name for name in (
            "revenue", "net_income", "current_assets", "current_liabilities",
            "total_assets", "equity", "debt",
        )
        if getattr(financials, name if name != "net_income" else "net_income") is None
    ]
    return {
        "analysis_status": "incomplete" if missing else "complete",
        "missing_fields": missing,
        "analysis": analysis,
    }


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: int = Depends(get_current_tenant_id),
    _permission: User = Depends(require_permission("documents.delete")),
):
    service = DocumentService(db)
    document = service.get(tenant_id, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    try:
        service.delete(document, actor_id=current_user.id)
    except DocumentConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        db.rollback()
        logger.exception("document deletion failed for document %s", document_id)
        raise HTTPException(status_code=500, detail="Could not delete document.") from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{document_id}/file")
def get_document_file(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: int = Depends(get_current_tenant_id),
    _permission: User = Depends(require_permission("documents.view")),
):
    service = DocumentService(db)
    document = service.get(tenant_id, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    try:
        data = service.file_bytes(document)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="File not found in storage")
    safe_name = quote(document.original_filename, safe="")
    return Response(
        content=data,
        media_type=document.mime_type,
        headers={
            "Content-Disposition": f"inline; filename=document; filename*=UTF-8''{safe_name}",
            "X-Content-Type-Options": "nosniff",
        },
    )
