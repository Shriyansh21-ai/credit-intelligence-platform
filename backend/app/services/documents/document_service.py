"""High-level orchestration for the Document Intelligence pipeline.

Ties together storage, text extraction, field extraction, validation and
persistence so the route layer stays thin. All DB access is scoped to the
provided session.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.models.company import Company, CompanyFinancials
from backend.app.models.document import Document, DocumentExtraction, DocumentReviewEvent
from backend.app.services.documents.field_extraction import (
    FIELD_SPECS,
    FinancialStatementExtractor,
)
from backend.app.services.documents.storage import get_storage
from backend.app.services.documents.text_extraction import DocumentTextExtractor
from backend.app.services.documents.validation import DocumentValidationService

_SPEC_LABELS = {spec.key: (spec.label, spec.type) for spec in FIELD_SPECS}
_FINANCIAL_FIELD_MAP = {
    "revenue": "revenue",
    "ebitda": "ebitda",
    "ebit": "ebit",
    "net_profit": "net_income",
    "total_assets": "total_assets",
    "total_liabilities": "total_liabilities",
    "equity": "equity",
    "current_assets": "current_assets",
    "current_liabilities": "current_liabilities",
    "cash": "cash",
    "operating_cash_flow": "operating_cash_flow",
    "free_cash_flow": "free_cash_flow",
}


class DocumentConflictError(Exception):
    """A document action conflicts with its current workflow state."""


class DocumentValidationError(Exception):
    """A document is not eligible for the requested workflow action."""


class DocumentService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.storage = get_storage()
        self.text_extractor = DocumentTextExtractor()
        self.field_extractor = FinancialStatementExtractor()
        self.validator = DocumentValidationService()

    # -- upload -----------------------------------------------------------

    def find_duplicate(self, tenant_id: int, content_hash: str) -> Optional[Document]:
        return (
            self.db.query(Document)
            .filter(Document.tenant_id == tenant_id, Document.content_hash == content_hash)
            .first()
        )

    def upload(
        self,
        *,
        tenant_id: int,
        user_id: int,
        filename: str,
        mime_type: str,
        data: bytes,
        document_type: str = "other",
        assessment_id: Optional[int] = None,
        company_id: Optional[int] = None,
        fiscal_year: Optional[int] = None,
        currency: Optional[str] = None,
        unit: str = "units",
    ) -> Document:
        stored = self.storage.save(namespace=f"tenant-{tenant_id}", filename=filename, data=data)
        try:
            document = Document(
                tenant_id=tenant_id,
                user_id=user_id,
                assessment_id=assessment_id,
                company_id=company_id,
                fiscal_year=fiscal_year,
                currency=currency,
                unit=unit,
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
        except Exception:
            self.db.rollback()
            self.storage.delete(stored.uri)
            raise

    # -- extraction -------------------------------------------------------

    def extract(self, document: Document) -> DocumentExtraction:
        if document.status == "approved":
            raise DocumentConflictError("Approved documents cannot be reprocessed.")
        document.status = "processing"
        self.db.commit()
        try:
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
            document.status = "needs_review" if ocr_result.text.strip() else "failed"

            extraction = self._new_version(
                document, fields, issues, ocr_result.source, overall, provider=ocr_result.engine
            )
            self.db.commit()
            self.db.refresh(extraction)
            return extraction
        except Exception:
            self.db.rollback()
            document.status = "failed"
            self.db.commit()
            raise

    # -- review -----------------------------------------------------------

    def review(
        self,
        document: Document,
        edited: Dict[str, Any],
        *,
        actor_id: int,
        document_type: Optional[str] = None,
        company_id: Optional[int] = None,
        fiscal_year: Optional[int] = None,
        currency: Optional[str] = None,
        unit: Optional[str] = None,
    ) -> DocumentExtraction:
        if document.status not in {"needs_review", "extracted", "reviewed", "rejected"}:
            raise DocumentConflictError("Document is not in a reviewable state.")
        current = self.current_extraction(document)
        if current is None:
            raise DocumentValidationError("Extract the document before reviewing it.")
        unknown = set(edited) - set(_SPEC_LABELS)
        if unknown:
            raise DocumentValidationError(f"Unsupported financial fields: {', '.join(sorted(unknown))}")
        existing = {f["key"]: dict(f) for f in (current.fields or [])}
        changes: Dict[str, Dict[str, Any]] = {}

        for key, value in edited.items():
            if value == "":
                value = None
            if value is not None and _SPEC_LABELS[key][1] == "currency":
                try:
                    value = float(value)
                except (TypeError, ValueError) as exc:
                    raise DocumentValidationError(f"{key} must be numeric.") from exc
                if not math.isfinite(value):
                    raise DocumentValidationError(f"{key} must be finite.")
            if key in existing:
                previous = existing[key].get("value")
                if previous != value:
                    existing[key]["value"] = value
                    existing[key]["normalized_value"] = value
                    existing[key]["edited"] = True
                    changes[key] = {"from": previous, "to": value}
            else:
                label, ftype = _SPEC_LABELS[key]
                existing[key] = {
                    "key": key, "label": label, "type": ftype, "value": value,
                    "extracted_value": None, "normalized_value": value, "raw_text": None,
                    "confidence": None, "bbox": None, "edited": True,
                }
                changes[key] = {"from": None, "to": value}

        fields = list(existing.values())
        values = {f["key"]: f.get("value") for f in fields}
        issues = [issue.as_dict() for issue in self.validator.validate(values)]

        previous_metadata = {
            "company_id": document.company_id,
            "fiscal_year": document.fiscal_year,
            "currency": document.currency,
            "unit": document.unit,
            "document_type": document.document_type,
        }
        if company_id is not None:
            company = (
                self.db.query(Company)
                .filter(Company.id == company_id, Company.tenant_id == document.tenant_id)
                .first()
            )
            if company is None:
                raise DocumentValidationError("Company not found for this tenant.")
            document.company_id = company_id
        if fiscal_year is not None:
            document.fiscal_year = fiscal_year
        if currency is not None:
            document.currency = currency.upper()
        if unit is not None:
            document.unit = unit
        if document_type is not None:
            document.document_type = document_type
        from_status = document.status
        document.status = (
            "needs_review"
            if any(issue["severity"] == "error" for issue in issues)
            else "reviewed"
        )
        document.reviewed_by = actor_id
        document.reviewed_at = self._utc_now()
        changes["_metadata"] = {
            "from": previous_metadata,
            "to": {
                "company_id": document.company_id,
                "fiscal_year": document.fiscal_year,
                "currency": document.currency,
                "unit": document.unit,
                "document_type": document.document_type,
            },
        }

        extraction = self._new_version(
            document, fields, issues,
            source=current.source,
            overall=self._overall_confidence(fields),
            provider=current.provider,
            provider_version=current.provider_version,
        )
        self.db.add(DocumentReviewEvent(
            document_id=document.id,
            document_reference_id=document.id,
            tenant_id=document.tenant_id,
            actor_id=actor_id,
            event_type="review",
            from_status=from_status,
            to_status=document.status,
            changes=changes,
        ))
        self.db.commit()
        self.db.refresh(extraction)
        return extraction

    def approve(
        self,
        document: Document,
        *,
        actor_id: int,
        acknowledged_warnings: List[str],
        replace_existing: bool = False,
    ) -> CompanyFinancials:
        if document.status == "approved":
            approved = (
                self.db.query(CompanyFinancials)
                .filter(
                    CompanyFinancials.tenant_id == document.tenant_id,
                    CompanyFinancials.source_document_id == document.id,
                )
                .first()
            )
            if approved is not None:
                return approved
        if document.status != "reviewed":
            raise DocumentConflictError("Only reviewed documents can be approved.")
        if document.company_id is None or document.fiscal_year is None or document.currency is None:
            raise DocumentValidationError(
                "Company, fiscal year, and currency must be confirmed before approval."
            )

        extraction = self.current_extraction(document)
        if extraction is None:
            raise DocumentValidationError("A current extraction is required for approval.")
        issues = extraction.validation or []
        if any(issue.get("severity") == "error" for issue in issues):
            raise DocumentValidationError("Resolve all blocking validation errors before approval.")
        warning_messages = {
            issue["message"] for issue in issues if issue.get("severity") == "warning"
        }
        if warning_messages - set(acknowledged_warnings):
            raise DocumentValidationError("Acknowledge all unresolved validation warnings before approval.")

        company = (
            self.db.query(Company)
            .filter(Company.id == document.company_id, Company.tenant_id == document.tenant_id)
            .first()
        )
        if company is None:
            raise DocumentValidationError("Company not found for this tenant.")

        fields = {item["key"]: item.get("value") for item in (extraction.fields or [])}
        financial_values = self._financial_values(fields)
        if financial_values.get("revenue") is None:
            raise DocumentValidationError("Revenue is required for financial persistence.")

        period = (
            self.db.query(CompanyFinancials)
            .filter(
                CompanyFinancials.company_id == company.id,
                CompanyFinancials.tenant_id == document.tenant_id,
                CompanyFinancials.fiscal_year == document.fiscal_year,
            )
            .with_for_update()
            .first()
        )
        if period is not None and period.source_document_id == document.id:
            return period
        if period is not None and not replace_existing:
            raise DocumentConflictError(
                "Financials already exist for this company and fiscal year; explicit conflict resolution is required."
            )

        prior_values = self._period_values(period)
        if period is None:
            period = CompanyFinancials(
                tenant_id=document.tenant_id,
                company_id=company.id,
                fiscal_year=document.fiscal_year,
            )
        for name, value in financial_values.items():
            if value is not None:
                setattr(period, name, value)
        period.currency = document.currency
        period.unit = document.unit
        period.source_document_id = document.id
        period.source_document_extraction_id = extraction.id
        period.reviewed_by = document.reviewed_by
        document.status = "approved"
        document.approved_by = actor_id
        document.approved_at = self._utc_now()
        self.db.add(period)
        self.db.add(DocumentReviewEvent(
            document_id=document.id,
            document_reference_id=document.id,
            tenant_id=document.tenant_id,
            actor_id=actor_id,
            event_type="approval" if prior_values is None else "restatement",
            from_status="reviewed",
            to_status="approved",
            changes={
                "replaced_financials": prior_values,
                "financials": self._period_values(period),
            },
        ))
        try:
            self.db.commit()
            self.db.refresh(period)
            return period
        except IntegrityError as exc:
            self.db.rollback()
            raise DocumentConflictError(
                "Financials for this company and fiscal year were concurrently persisted; reload and resolve the conflict."
            ) from exc
        except Exception:
            self.db.rollback()
            raise

    def reject(self, document: Document, *, actor_id: int, reason: str) -> None:
        if document.status not in {"needs_review", "extracted", "reviewed"}:
            raise DocumentConflictError("Document cannot be rejected from its current state.")
        from_status = document.status
        document.status = "rejected"
        document.rejected_by = actor_id
        document.rejected_at = self._utc_now()
        document.rejection_reason = reason
        self.db.add(DocumentReviewEvent(
            document_id=document.id,
            document_reference_id=document.id,
            tenant_id=document.tenant_id,
            actor_id=actor_id,
            event_type="rejection",
            from_status=from_status,
            to_status="rejected",
            changes={},
            reason=reason,
        ))
        self.db.commit()

    # -- reads ------------------------------------------------------------

    def get(self, tenant_id: int, document_id: int) -> Optional[Document]:
        return (
            self.db.query(Document)
            .filter(Document.id == document_id, Document.tenant_id == tenant_id)
            .first()
        )

    def current_extraction(self, document: Document) -> Optional[DocumentExtraction]:
        return (
            self.db.query(DocumentExtraction)
            .filter(DocumentExtraction.document_id == document.id, DocumentExtraction.is_current.is_(True))
            .first()
        )

    def history(self, tenant_id: int) -> List[Document]:
        return (
            self.db.query(Document)
            .filter(Document.tenant_id == tenant_id, Document.status != "deletion_pending")
            .order_by(Document.created_at.desc())
            .all()
        )

    def delete(self, document: Document, *, actor_id: int) -> None:
        persisted_financials = (
            self.db.query(CompanyFinancials.id)
            .filter(
                CompanyFinancials.tenant_id == document.tenant_id,
                CompanyFinancials.source_document_id == document.id,
            )
            .first()
        )
        if persisted_financials is not None:
            raise DocumentConflictError(
                "A document referenced by approved financials cannot be deleted."
            )
        self.storage.delete(document.storage_uri)
        self.db.query(DocumentExtraction).filter(
            DocumentExtraction.document_id == document.id
        ).delete(synchronize_session=False)
        self.db.query(DocumentReviewEvent).filter(
            DocumentReviewEvent.document_id == document.id
        ).update(
            {DocumentReviewEvent.document_id: None},
            synchronize_session=False,
        )
        self.db.add(DocumentReviewEvent(
            document_id=None,
            document_reference_id=document.id,
            tenant_id=document.tenant_id,
            actor_id=actor_id,
            event_type="deletion",
            from_status=document.status,
            to_status="deleted",
            changes={},
        ))
        self.db.delete(document)
        try:
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

    def file_bytes(self, document: Document) -> bytes:
        return self.storage.open(document.storage_uri)

    # -- internal ---------------------------------------------------------

    def _new_version(
        self,
        document,
        fields,
        issues,
        source,
        overall,
        *,
        provider=None,
        provider_version=None,
    ) -> DocumentExtraction:
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
            provider=provider,
            provider_version=provider_version,
        )
        self.db.add(extraction)
        return extraction

    @staticmethod
    def _utc_now():
        return datetime.now(timezone.utc).replace(tzinfo=None)

    @staticmethod
    def _field_dict(ef) -> dict:
        d = ef.as_dict()
        d["edited"] = False
        d["extracted_value"] = d["value"]
        d["normalized_value"] = d["value"]
        return d

    @staticmethod
    def _financial_values(fields: Dict[str, Any]) -> Dict[str, Optional[float]]:
        values: Dict[str, Optional[float]] = {}
        for source, target in _FINANCIAL_FIELD_MAP.items():
            raw = fields.get(source)
            if raw is None or raw == "":
                values[target] = None
                continue
            try:
                parsed = float(raw)
            except (TypeError, ValueError) as exc:
                raise DocumentValidationError(f"{source} must be numeric.") from exc
            if not math.isfinite(parsed):
                raise DocumentValidationError(f"{source} must be finite.")
            values[target] = parsed

        short_term = fields.get("short_term_debt")
        long_term = fields.get("long_term_debt")
        if short_term is not None and long_term is not None:
            try:
                debt = float(short_term) + float(long_term)
            except (TypeError, ValueError) as exc:
                raise DocumentValidationError("Debt values must be numeric.") from exc
            if not math.isfinite(debt):
                raise DocumentValidationError("Debt must be finite.")
            values["debt"] = debt
        return values

    @staticmethod
    def _period_values(period: Optional[CompanyFinancials]) -> Optional[dict]:
        if period is None:
            return None
        names = (
            "revenue", "ebitda", "ebit", "net_income", "total_assets",
            "total_liabilities", "equity", "current_assets", "current_liabilities",
            "cash", "debt", "operating_cash_flow", "free_cash_flow", "currency",
            "unit", "source_document_id", "source_document_extraction_id",
        )
        return {name: getattr(period, name) for name in names}

    @staticmethod
    def _overall_confidence(fields: List[dict]) -> Optional[float]:
        confs = [f.get("confidence", 0.0) for f in fields if f.get("confidence") is not None]
        return round(sum(confs) / len(confs), 4) if confs else None
