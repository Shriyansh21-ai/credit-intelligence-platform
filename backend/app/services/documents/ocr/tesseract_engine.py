"""Tesseract OCR adapter.

Recognises text from raster images (and rasterised PDF pages) with per-word
confidence and bounding boxes. It degrades gracefully: if Pillow/pytesseract or
the Tesseract binary is unavailable, :meth:`available` is False and
``recognize`` returns an empty result rather than raising — the pipeline then
reports low confidence instead of crashing.
"""

from __future__ import annotations

from io import BytesIO
from typing import List, Optional

from .base import BoundingBox, OcrPage, OcrResult, OcrWord

try:  # pragma: no cover - import guard
    from PIL import Image
except Exception:  # pragma: no cover
    Image = None

try:  # pragma: no cover - import guard
    import pytesseract
except Exception:  # pragma: no cover
    pytesseract = None


class TesseractOcrEngine:
    name = "tesseract"

    def __init__(self) -> None:
        self._binary_ok: Optional[bool] = None

    def available(self) -> bool:
        """Whether image OCR can actually run (libs + binary present)."""
        if Image is None or pytesseract is None:
            return False
        if self._binary_ok is None:
            try:
                pytesseract.get_tesseract_version()
                self._binary_ok = True
            except Exception:
                self._binary_ok = False
        return self._binary_ok

    def supports(self, mime: str) -> bool:
        return mime.startswith("image/")

    def recognize(self, data: bytes, mime: str) -> OcrResult:
        if not self.available():
            return OcrResult(pages=[], engine=self.name, source="ocr")

        image = Image.open(BytesIO(data))
        image.load()
        return OcrResult(pages=[self._recognize_image(image, page_number=0)], engine=self.name, source="ocr")

    def recognize_image(self, image, page_number: int = 0) -> OcrPage:
        """Recognise an already-decoded PIL image (used for rasterised PDFs)."""
        return self._recognize_image(image, page_number)

    # -- internal ---------------------------------------------------------

    def _recognize_image(self, image, page_number: int) -> OcrPage:
        width = float(image.width) or 1.0
        height = float(image.height) or 1.0
        data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)

        words: List[OcrWord] = []
        for i, text in enumerate(data["text"]):
            if not text or not text.strip():
                continue
            raw_conf = data["conf"][i]
            try:
                conf = float(raw_conf)
            except (TypeError, ValueError):
                conf = -1.0
            if conf < 0:
                continue
            words.append(
                OcrWord(
                    text=text,
                    confidence=max(0.0, min(1.0, conf / 100.0)),
                    box=BoundingBox(
                        x=data["left"][i] / width,
                        y=data["top"][i] / height,
                        width=data["width"][i] / width,
                        height=data["height"][i] / height,
                        page=page_number,
                    ),
                )
            )
        return OcrPage(page_number=page_number, width=width, height=height, words=words)
