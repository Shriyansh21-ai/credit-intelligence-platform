"""Document text-extraction orchestrator.

Chooses the best path per document:

    * born-digital PDF  -> PyMuPDF text layer (exact, with word rects)
    * scanned PDF       -> rasterise pages -> image OCR
    * image             -> image OCR
    * plain text        -> decode as-is

Returns a provider-agnostic :class:`OcrResult`.
"""

from __future__ import annotations

from io import BytesIO
from typing import List

from .ocr.base import BoundingBox, OcrPage, OcrResult, OcrWord
from .ocr.pdf_text import PdfTextExtractor
from .ocr.registry import get_ocr_engine
from .ocr.tesseract_engine import TesseractOcrEngine

try:  # pragma: no cover - import guard
    import fitz  # PyMuPDF
except Exception:  # pragma: no cover
    fitz = None

try:  # pragma: no cover
    from PIL import Image
except Exception:  # pragma: no cover
    Image = None

_RASTER_DPI = 200


class DocumentTextExtractor:
    def __init__(self, ocr_engine_name: str | None = None) -> None:
        self.pdf = PdfTextExtractor()
        self.ocr = get_ocr_engine(ocr_engine_name)

    def extract(self, data: bytes, mime: str) -> OcrResult:
        if mime == "application/pdf":
            result = self.pdf.recognize(data, mime)
            if self.pdf.has_text(result):
                return result
            return self._ocr_scanned_pdf(data)

        if mime.startswith("image/"):
            return self.ocr.recognize(data, mime)

        return self._plain_text(data)

    # -- internal ---------------------------------------------------------

    def _ocr_scanned_pdf(self, data: bytes) -> OcrResult:
        engine = self.ocr
        if fitz is None or Image is None or not isinstance(engine, TesseractOcrEngine) or not engine.available():
            # No OCR capability: return empty so callers surface low confidence.
            return OcrResult(pages=[], engine=self.ocr.name, source="ocr")

        pages: List[OcrPage] = []
        with fitz.open(stream=data, filetype="pdf") as doc:
            for index, page in enumerate(doc):
                pix = page.get_pixmap(dpi=_RASTER_DPI)
                image = Image.open(BytesIO(pix.tobytes("png")))
                image.load()
                pages.append(engine.recognize_image(image, page_number=index))
        return OcrResult(pages=pages, engine=engine.name, source="ocr")

    def _plain_text(self, data: bytes) -> OcrResult:
        try:
            text = data.decode("utf-8")
        except Exception:
            text = data.decode("latin-1", errors="ignore")
        words = [
            OcrWord(text=token, confidence=1.0, box=BoundingBox(0.0, 0.0, 0.0, 0.0, 0))
            for token in text.split()
        ]
        page = OcrPage(page_number=0, width=1.0, height=1.0, words=words)
        # Preserve the raw text (including line breaks) for line-based parsing.
        page._raw_text = text  # type: ignore[attr-defined]
        return OcrResult(pages=[page], engine="text", source="text")
