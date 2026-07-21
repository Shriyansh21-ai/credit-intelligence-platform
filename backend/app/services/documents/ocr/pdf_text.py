"""Born-digital PDF text extractor (PyMuPDF).

For PDFs that already contain a text layer this is far more accurate than pixel
OCR and yields exact word rectangles with maximum confidence. Scanned PDFs (no
text layer) return empty pages, letting the orchestrator fall back to OCR.
"""

from __future__ import annotations

from typing import List

from .base import BoundingBox, OcrPage, OcrResult, OcrWord

try:  # pragma: no cover - import guard
    import fitz  # PyMuPDF
except Exception:  # pragma: no cover
    fitz = None


class PdfTextExtractor:
    name = "pdf-text"

    def supports(self, mime: str) -> bool:
        return mime == "application/pdf" and fitz is not None

    def recognize(self, data: bytes, mime: str) -> OcrResult:
        if fitz is None:
            return OcrResult(pages=[], engine=self.name, source="pdf-text")

        pages: List[OcrPage] = []
        with fitz.open(stream=data, filetype="pdf") as doc:
            for index, page in enumerate(doc):
                rect = page.rect
                page_width = float(rect.width) or 1.0
                page_height = float(rect.height) or 1.0
                words: List[OcrWord] = []
                # words(): [x0, y0, x1, y1, "word", block, line, word_no]
                for x0, y0, x1, y1, text, *_ in page.get_text("words"):
                    if not text.strip():
                        continue
                    words.append(
                        OcrWord(
                            text=text,
                            confidence=0.99,  # text layer is exact, not recognised
                            box=BoundingBox(
                                x=x0 / page_width,
                                y=y0 / page_height,
                                width=(x1 - x0) / page_width,
                                height=(y1 - y0) / page_height,
                                page=index,
                            ),
                        )
                    )
                pages.append(OcrPage(page_number=index, width=page_width, height=page_height, words=words))

        return OcrResult(pages=pages, engine=self.name, source="pdf-text")

    def has_text(self, result: OcrResult) -> bool:
        return any(page.words for page in result.pages)
