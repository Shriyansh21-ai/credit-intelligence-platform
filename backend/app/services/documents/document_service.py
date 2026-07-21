"""High-level orchestration for the Document Intelligence pipeline.

Ties together storage, text extraction, field extraction, validation and
persistence so the route layer stays thin. All DB access is scoped to the
provided session.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from backend.app.models.document import Document, DocumentExtraction
from backend.app.services.documents.field_extraction import (
    FIELD_SPECS,
    FinancialStatementExtractor,
)
from backend.app.services.documents.storage import get_storage
from backend.app.services.documents.text_extraction import DocumentTextExtractor
from backend.app.services.documents.validation import DocumentValidationService

_SPEC_LABELS = {spec.key: (spec.label, spec.type) for spec in FIELD_SPECS}


class DocumentService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.storage = get_storage()
        self.text_extractor = DocumentTextExtractor()
        self.field_extractor = FinancialStatementExtractor()
        self.validator = DocumentValidationService()

    # -- upload -----------------------------------------------------------

    def find_duplicate(self, user_id: int, content_hash: str) -> Optional[Document]:
        return (
            self.db.query(Document)
            .filter(Document.user_id == user_id, Document.content_hash == content_hash)
            .first()
        )

    def upload(
        self,
        *,
        user_id: int,
        filename: str,
        mime_type: str,
        data: bytes,
        document_type: str = "other",
        assessment_id: Optional[int] = None,
    ) -> Document:
        stored = self.storage.save(namespace=f"user-{user_id}", filename=filename, data=data)
        document = Document(
            user_id=user_id,
            assessment_id=assessment_id,
            document_type=document_type,
            original_filename=filename,
            mime_type=mime_type,
            size_bytes=stored.size,
            storage_uri=stored.uri,
            content_hash=stored.content_hash,
            status="uploaded",
        )
        self.db.add(document)
        self.db.commit()
        self.db.refresh(document)
        return document

    # -- extraction -------------------------------------------------------

    def extract(self, document: Document) -> DocumentExtraction:
        data = self.storage.open(document.storage_uri)
        ocr_result = self.text_extractor.extract(data, document.mime_type)
        extracted = self.field_extractor.extract(ocr_result)

        fields = [self._field_dict(ef) for ef in extracted.values()]
        values = {ef.key: ef.value for ef in extracted.values()}
        issues = [issue.as_dict() for issue in self.validator.validate(values)]
        overall = self._overall_confidence(fields)

        document.ocr_engine = ocr_result.engine
        document.ocr_source = ocr_result.source
        document.page_count = len(ocr_result.pages) or None
        document.status = "extracted" if ocr_result.text.strip() else "failed"

        extraction = self._new_version(document, fields, issues, ocr_result.source, overall)
        self.db.commit()
        self.db.refresh(extraction)
        return extraction

    # -- review -----------------------------------------------------------

    def review(
        self,
        document: Document,
        edited: Dict[str, Any],
        *,
        document_type: Optional[str] = None,
        mark_reviewed: bool = True,
    ) -> DocumentExtraction:
        current = self.current_extraction(document)
        existing = {f["key"]: dict(f) for f in (current.fields if current else [])}

        for key, value in edited.items():
            if key in existing:
                previous = existing[key].get("value")
                existing[key]["value"] = value
                existing[key]["edited"] = existing[key].get("edited", False) or value != previous
                if existing[key]["edited"]:
                    existing[key]["confidence"] = 1.0  # user-verified
            else:
                label, ftype = _SPEC_LABELS.get(key, (key.replace("_", " ").title(), "text"))
                existing[key] = {
                    "key": key, "label": label, "type": ftype, "value": value,
                    "raw_text": None, "confidence": 1.0, "bbox": None, "edited": True,
                }

        fields = list(existing.values())
        values = {f["key"]: f.get("value") for f in fields}
        issues = [issue.as_dict() for issue in self.validator.validate(values)]

        if document_type:
            document.document_type = document_type
        if mark_reviewed:
            document.status = "reviewed"

        extraction = self._new_version(
            document, fields, issues,
            source=current.source if current else None,
            overall=self._overall_confidence(fields),
        )
        self.db.commit()
        self.db.refresh(extraction)
        return extraction

    # -- reads ------------------------------------------------------------

    def get(self, user_id: int, document_id: int) -> Optional[Document]:
        return (
            self.db.query(Document)
            .filter(Document.id == document_id, Document.user_id == user_id)
            .first()
        )

    def current_extraction(self, document: Document) -> Optional[DocumentExtraction]:
        return (
            self.db.query(DocumentExtraction)
            .filter(DocumentExtraction.document_id == document.id, DocumentExtraction.is_current.is_(True))
            .first()
        )

    def history(self, user_id: int) -> List[Document]:
        return (
            self.db.query(Document)
            .filter(Document.user_id == user_id)
            .order_by(Document.created_at.desc())
            .all()
        )

    def delete(self, document: Document) -> None:
        self.db.query(DocumentExtraction).filter(DocumentExtraction.document_id == document.id).delete()
        try:
            self.storage.delete(document.storage_uri)
        except Exception:
            pass  # best-effort file cleanup; DB row removal is authoritative
        self.db.delete(document)
        self.db.commit()

    def file_bytes(self, document: Document) -> bytes:
        return self.storage.open(document.storage_uri)

    # -- internal ---------------------------------------------------------

    def _new_version(self, document, fields, issues, source, overall) -> DocumentExtraction:
        self.db.query(DocumentExtraction).filter(
            DocumentExtraction.document_id == document.id,
            DocumentExtraction.is_current.is_(True),
        ).update({DocumentExtraction.is_current: False})

        last = (
            self.db.query(DocumentExtraction)
            .filter(DocumentExtraction.document_id == document.id)
            .order_by(DocumentExtraction.version.desc())
            .first()
        )
        version = (last.version + 1) if last else 1

        extraction = DocumentExtraction(
            document_id=document.id,
            version=version,
            is_current=True,
            fields=fields,
            validation=issues,
            overall_confidence=overall,
            source=source,
        )
        self.db.add(extraction)
        return extraction

    @staticmethod
    def _field_dict(ef) -> dict:
        d = ef.as_dict()
        d["edited"] = False
        return d

    @staticmethod
    def _overall_confidence(fields: List[dict]) -> Optional[float]:
        confs = [f.get("confidence", 0.0) for f in fields if f.get("confidence") is not None]
        return round(sum(confs) / len(confs), 4) if confs else None
