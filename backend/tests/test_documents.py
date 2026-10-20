import tempfile
import unittest

from backend.app.models.document import Document
from backend.app.routes.documents import _detect_file_mime
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
