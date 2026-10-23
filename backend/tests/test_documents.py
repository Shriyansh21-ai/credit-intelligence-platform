import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from backend.app.models.document import Document
from backend.app.routes.documents import _detect_file_mime
from backend.app.services.documents.document_service import DocumentService
from backend.app.schemas.document import DocumentType
from backend.app.services.documents.field_extraction import FinancialStatementExtractor
from backend.app.services.documents.ocr.registry import get_ocr_engine
from backend.app.services.documents.storage import LocalStorageBackend
from backend.app.services.documents.text_extraction import DocumentTextExtractor
from backend.app.services.documents.validation import DocumentValidationService

try:
    import fitz  # PyMuPDF
except Exception:  # pragma: no cover
    fitz = None


def _build_pdf() -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text(
        (60, 60),
        "Meridian Industrial Pvt Ltd\n"
        "Financial Year: 2024-25\n"
        "Revenue from operations: 24,000,000\n"
        "Gross Profit: 8,400,000\n"
        "Net Profit: 2,600,000\n"
        "Current Assets: 9,200,000\n"
        "Current Liabilities: 4,400,000\n"
        "GSTIN: 27ABCDE1234F1Z5",
        fontsize=11,
    )
    data = doc.tobytes()
    doc.close()
    return data


class StorageTests(unittest.TestCase):
    def test_roundtrip_and_delete(self):
        with tempfile.TemporaryDirectory() as tmp:
            backend = LocalStorageBackend(tmp)
            stored = backend.save("ns", "file.pdf", b"hello")
            self.assertTrue(backend.exists(stored.uri))
            self.assertEqual(backend.open(stored.uri), b"hello")
            self.assertEqual(stored.size, 5)
            backend.delete(stored.uri)
            self.assertFalse(backend.exists(stored.uri))

    def test_rejects_path_traversal(self):
        with tempfile.TemporaryDirectory() as tmp:
            backend = LocalStorageBackend(tmp)
            with self.assertRaises(ValueError):
                backend.open("local://../../etc/passwd")

    def test_atomic_save_leaves_no_tmp_orphans(self):
        with tempfile.TemporaryDirectory() as tmp:
            backend = LocalStorageBackend(tmp)
            stored = backend.save("ns", "report.pdf", b"hello")
            self.assertTrue(backend.exists(stored.uri))
            self.assertFalse(any(p.name.startswith(".report.pdf") for p in Path(tmp).rglob("*")))

    def test_save_failure_cleans_temp_and_keeps_existing_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            backend = LocalStorageBackend(tmp)
            existing = backend.save("ns", "report.pdf", b"original")
            original_path = backend._path_for_uri(existing.uri)

            with patch("backend.app.services.documents.storage.os.fsync", side_effect=OSError("fsync failed")):
                with self.assertRaises(OSError):
                    backend.save("ns", "report.pdf", b"new-data")

            self.assertTrue(backend.exists(existing.uri))
            self.assertEqual(backend.open(existing.uri), b"original")
            self.assertFalse(any(p.name.startswith(".report.pdf") for p in Path(tmp).rglob("*")))
            self.assertTrue(original_path.exists())

    def test_upload_commit_failure_cleans_staged_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            from backend.tests._demo_portfolio_helpers import fresh_session

            engine, session_factory = fresh_session()
            try:
                db = session_factory()
                backend = LocalStorageBackend(tmp)
                service = DocumentService(db, storage=backend)
                db.commit = Mock(side_effect=RuntimeError("commit failed"))
                with self.assertRaises(RuntimeError):
                    service.upload(
                        tenant_id=1,
                        user_id=1,
                        filename="statement.pdf",
                        mime_type="application/pdf",
                        data=b"pdf-data",
                        document_type="balance_sheet",
                    )
                self.assertEqual(db.query(Document).count(), 0)
                self.assertFalse(any(path.is_file() for path in Path(tmp).rglob("*")))
            finally:
                db.close()
                engine.dispose()

    def test_delete_failure_leaves_pending_state_and_reconcile_reports_missing_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            from backend.tests._demo_portfolio_helpers import fresh_session

            engine, session_factory = fresh_session()
            try:
                backend = LocalStorageBackend(tmp)
                stored = backend.save("tenant-1", "delete-me.pdf", b"data")
                db = session_factory()
                try:
                    doc = Document(
                        tenant_id=1,
                        user_id=1,
                        original_filename="delete-me.pdf",
                        mime_type="application/pdf",
                        size_bytes=4,
                        storage_uri=stored.uri,
                        content_hash=stored.content_hash,
                        status="uploaded",
                    )
                    db.add(doc)
                    db.commit()

                    failing_backend = Mock()
                    failing_backend.exists.side_effect = lambda uri: uri == stored.uri and False
                    failing_backend.iter_uris.return_value = []
                    failing_backend.delete.side_effect = OSError("disk failed")
                    service = DocumentService(db, storage=failing_backend)
                    with self.assertRaises(OSError):
                        service.delete(doc, actor_id=1)
                    db.refresh(doc)
                    self.assertEqual(doc.status, "deletion_pending")
                    self.assertIn(stored.uri, service.reconcile_storage()["missing_referenced_files"])
                finally:
                    db.close()
            finally:
                engine.dispose()

    def test_reconcile_storage_flags_orphans_and_missing_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            from backend.tests._demo_portfolio_helpers import fresh_session

            engine, session_factory = fresh_session()
            try:
                backend = LocalStorageBackend(tmp)
                live = backend.save("tenant-1", "live.pdf", b"live")
                orphan = backend.save("tenant-1", "orphan.pdf", b"orphan")
                missing_uri = "local://tenant-1/missing.pdf"

                db = session_factory()
                try:
                    db.add(
                        Document(
                            tenant_id=1,
                            user_id=1,
                            original_filename="live.pdf",
                            mime_type="application/pdf",
                            size_bytes=len(b"live"),
                            storage_uri=live.uri,
                            content_hash=live.content_hash,
                            status="uploaded",
                        )
                    )
                    db.add(
                        Document(
                            tenant_id=1,
                            user_id=1,
                            original_filename="missing.pdf",
                            mime_type="application/pdf",
                            size_bytes=12,
                            storage_uri=missing_uri,
                            content_hash="missing",
                            status="uploaded",
                        )
                    )
                    db.commit()
                    report = DocumentService(db, storage=backend).reconcile_storage()
                    self.assertIn(orphan.uri, report["orphaned_files"])
                    self.assertIn(missing_uri, report["missing_referenced_files"])
                    self.assertNotIn(live.uri, report["orphaned_files"])
                    self.assertEqual(report, DocumentService(db, storage=backend).reconcile_storage())
                    with self.assertRaises(RuntimeError):
                        DocumentService(db, storage=backend).reconcile_storage(execute=True)
                finally:
                    db.close()
            finally:
                engine.dispose()

    def test_detects_supported_content_types(self):
        self.assertEqual(_detect_file_mime(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"), "application/pdf")
        self.assertEqual(_detect_file_mime(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"), "image/png")
        self.assertEqual(_detect_file_mime(b"\xff\xd8\xff\xe0\x00\x10JFIF"), "image/jpeg")


class SchemaTests(unittest.TestCase):
    def test_supported_document_type_values(self):
        self.assertEqual(DocumentType.balance_sheet.value, "balance_sheet")
        self.assertEqual(DocumentType.profit_loss.value, "profit_loss")
        self.assertEqual(DocumentType.profit_and_loss.value, "profit_and_loss")
        self.assertEqual(DocumentType.cash_flow.value, "cash_flow")
        self.assertEqual(DocumentType.bank_statement.value, "bank_statement")
        self.assertEqual(DocumentType.financial_summary.value, "financial_summary")
        self.assertEqual(DocumentType.other.value, "other")

    def test_none_ocr_engine_is_supported(self):
        engine = get_ocr_engine("none")
        self.assertEqual(engine.name, "none")
        self.assertEqual(engine.recognize(b"dummy", "image/png").engine, "none")
        self.assertEqual(DocumentTextExtractor("none").extract(b"hello", "text/plain").source, "text")

    def test_document_model_tracks_company_and_reporting_period(self):
        columns = {column.key for column in Document.__table__.columns}
        self.assertIn("tenant_id", columns)
        self.assertIn("company_id", columns)
        self.assertIn("fiscal_year", columns)


@unittest.skipIf(fitz is None, "PyMuPDF not available")
class ExtractionTests(unittest.TestCase):
    def test_extracts_fields_with_boxes_from_pdf(self):
        result = DocumentTextExtractor().extract(_build_pdf(), "application/pdf")
        self.assertEqual(result.source, "pdf-text")
        fields = FinancialStatementExtractor().extract(result)
        self.assertIn("revenue", fields)
        self.assertEqual(fields["revenue"].value, 24000000.0)
        self.assertIsNotNone(fields["revenue"].bbox)
        self.assertEqual(fields["gst_number"].value, "27ABCDE1234F1Z5")
        # cost of revenue must not steal the revenue label
        self.assertIn("company_name", fields)


class ValidationTests(unittest.TestCase):
    def setUp(self):
        self.validator = DocumentValidationService()

    def test_flags_negative_revenue_and_missing_name(self):
        issues = self.validator.validate({"revenue": -1})
        fields = {i.field for i in issues}
        self.assertIn("revenue", fields)
        self.assertIn("company_name", fields)  # required + missing

    def test_flags_invalid_gst(self):
        issues = self.validator.validate({"company_name": "X", "revenue": 100, "gst_number": "BADGST"})
        self.assertTrue(any(i.field == "gst_number" and i.severity == "error" for i in issues))

    def test_accepts_valid_gst(self):
        issues = self.validator.validate({"company_name": "X", "revenue": 100, "gst_number": "27ABCDE1234F1Z5"})
        self.assertFalse(any(i.field == "gst_number" for i in issues))


if __name__ == "__main__":
    unittest.main()
