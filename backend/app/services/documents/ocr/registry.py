"""OCR engine registry.

Maps engine names to singleton adapters so the active image-OCR provider is a
one-line configuration change. Add new providers here as they are implemented.
"""

from __future__ import annotations

from .base import OcrEngine, OcrResult
from .tesseract_engine import TesseractOcrEngine


class NoOpOcrEngine:
    """Null implementation used when OCR is deliberately disabled."""

    name = "none"

    def supports(self, mime: str) -> bool:
        return False

    def recognize(self, data: bytes, mime: str) -> OcrResult:
        return OcrResult(pages=[], engine=self.name, source="ocr")


_ENGINES: dict[str, OcrEngine] = {
    "none": NoOpOcrEngine(),
    "tesseract": TesseractOcrEngine(),
    # "google-vision": GoogleVisionOcrEngine(), # future
    # "azure": AzureOcrEngine(), # future
    # "textract": TextractOcrEngine(), # future
}

_DEFAULT = "tesseract"


def get_ocr_engine(name: str | None = None) -> OcrEngine:
    if not name or name == "auto":
        name = _DEFAULT
    engine = _ENGINES.get(name)
    if engine is None:
        raise ValueError(f"Unknown OCR engine: {name!r}. Available: {sorted(_ENGINES)}")
    return engine


def available_engines() -> list[str]:
    return sorted(_ENGINES)
