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
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile, status
from sqlalchemy.orm import Session

from backend.app.config import settings
from backend.app.core.dependencies import get_current_user
from backend.app.db.database import get_db
from backend.app.models.document import Document, DocumentExtraction
from backend.app.models.user import User
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
from backend.app.services.documents.document_service import DocumentService

router = APIRouter(prefix="/documents", tags=["Documents"])


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


def _validate_upload(file: UploadFile, data: bytes) -> str:
    if len(data) > settings.max_upload_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"{file.filename} exceeds the {settings.MAX_UPLOAD_MB} MB limit.",
        )
    mime = (file.content_type or "").lower()
    if mime not in settings.ALLOWED_UPLOAD_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported file type '{mime or 'unknown'}'. Allowed: PDF, PNG, JPG.",
        )
    return mime


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/upload", response_model=UploadResponse)
async def upload_documents(
    files: List[UploadFile] = File(...),
    document_type: str = Form("other"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = DocumentService(db)
    created, duplicates = [], []

    for file in files:
        data = await file.read()
        if not data:
            continue
        mime = _validate_upload(file, data)

        if service.find_duplicate(current_user.id, hashlib.sha256(data).hexdigest()):
            duplicates.append(file.filename or "unknown")
            continue

        document = service.upload(
            user_id=current_user.id,
            filename=file.filename or "document",
            mime_type=mime,
            data=data,
            document_type=document_type,
        )
        created.append(document)

    return UploadResponse(
        documents=[DocumentSummary.model_validate(d, from_attributes=True) for d in created],
        duplicates=duplicates,
    )


@router.post("/{document_id}/extract", response_model=ExtractResponse)
def extract_document(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = DocumentService(db)
    document = service.get(current_user.id, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    service.extract(document)
    return ExtractResponse(document=_detail(service, document))


@router.get("/history", response_model=HistoryResponse)
def list_history(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = DocumentService(db)
    return HistoryResponse(documents=service.history(current_user.id))


@router.get("/{document_id}", response_model=DocumentDetail)
def get_document(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = DocumentService(db)
    document = service.get(current_user.id, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return _detail(service, document)


@router.put("/{document_id}/review", response_model=ExtractResponse)
def review_document(
    document_id: int,
    payload: ReviewRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = DocumentService(db)
    document = service.get(current_user.id, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    service.review(
        document,
        payload.fields,
        document_type=payload.document_type.value if payload.document_type else None,
        mark_reviewed=payload.mark_reviewed,
    )
    return ExtractResponse(document=_detail(service, document))


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = DocumentService(db)
    document = service.get(current_user.id, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    service.delete(document)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{document_id}/file")
def get_document_file(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = DocumentService(db)
    document = service.get(current_user.id, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    try:
        data = service.file_bytes(document)
    except Exception:
        raise HTTPException(status_code=404, detail="File not found in storage")
    return Response(
        content=data,
        media_type=document.mime_type,
        headers={"Content-Disposition": f'inline; filename="{document.original_filename}"'},
    )
