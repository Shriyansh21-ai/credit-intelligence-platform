"""OCR engine abstraction.

The rest of the pipeline depends only on these types, never on a concrete OCR
provider (Task 4). Adapters (Tesseract now; Google Vision / Azure / Textract /
LLM-vision later) implement :class:`OcrEngine` and are selected via the registry.

Coordinates are normalised to the 0..1 range relative to the page so the
frontend can overlay bounding boxes regardless of render size (Task 7).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Protocol, runtime_checkable


@dataclass(frozen=True)
class BoundingBox:
    """Normalised (0..1) box: x/y is the top-left corner."""

    x: float
    y: float
    width: float
    height: float
    page: int = 0

    def as_dict(self) -> dict:
        return {"x": self.x, "y": self.y, "width": self.width, "height": self.height, "page": self.page}


@dataclass(frozen=True)
class OcrWord:
    text: str
    confidence: float  # 0..1
    box: BoundingBox


@dataclass
class OcrPage:
    page_number: int
    width: float
    height: float
    words: List[OcrWord] = field(default_factory=list)

    @property
    def text(self) -> str:
        return " ".join(w.text for w in self.words if w.text)


@dataclass
class OcrResult:
    pages: List[OcrPage] = field(default_factory=list)
    engine: str = "unknown"
    # "pdf-text" = born-digital text layer, "ocr" = pixel OCR, "text" = plain text.
    source: str = "ocr"

    @property
    def text(self) -> str:
        return "\n".join(page.text for page in self.pages)

    @property
    def words(self) -> List[OcrWord]:
        return [word for page in self.pages for word in page.words]

    @property
    def mean_confidence(self) -> float:
        confidences = [w.confidence for w in self.words if w.text.strip()]
        return round(sum(confidences) / len(confidences), 4) if confidences else 0.0


@runtime_checkable
class OcrEngine(Protocol):
    name: str

    def supports(self, mime: str) -> bool: ...

    def recognize(self, data: bytes, mime: str) -> OcrResult: ...
