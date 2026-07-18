import re
from typing import Dict, Optional
from io import BytesIO
import base64

try:
    from PIL import Image
except Exception:  # pragma: no cover
    Image = None

try:
    import pytesseract
except Exception:  # pragma: no cover
    pytesseract = None


LABEL_ALIASES = {
    "annual revenue": "annual_revenue",
    "revenue": "annual_revenue",
    "gross profit": "gross_profit",
    "net profit": "net_profit",
    "operating expenses": "operating_expenses",
    "cash": "cash_and_cash_equivalents",
    "cash and cash equivalents": "cash_and_cash_equivalents",
    "accounts receivable": "accounts_receivable",
    "accounts payable": "accounts_payable",
    "inventory": "inventory",
    "current assets": "current_assets",
    "current liabilities": "current_liabilities",
    "long term debt": "long_term_debt",
    "short term debt": "short_term_debt",
}


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _extract_amount(text: str) -> Optional[float]:
    if not text:
        return None
    cleaned = re.sub(r"[^0-9.-]", "", text.replace(",", ""))
    if not cleaned:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def _extract_text_from_image_bytes(data: bytes) -> Optional[str]:
    if Image is None or pytesseract is None:
        return None
    try:
        image = Image.open(BytesIO(data))
        image.load()
        return pytesseract.image_to_string(image)
    except Exception:
        return None


def extract_financial_summary(text: str) -> Dict[str, float]:
    normalized = _normalize_text(text)
    if not normalized:
        return {}

    summary: Dict[str, float] = {}
    for label, key in LABEL_ALIASES.items():
        pattern = re.compile(rf"{re.escape(label)}\s*[:\-]?\s*([0-9,\.]+)", re.IGNORECASE)
        match = pattern.search(normalized)
        if match:
            amount = _extract_amount(match.group(1))
            if amount is not None:
                summary[key] = amount

    if not summary:
        for sentence in re.split(r"(?<!\w)\.(?!\w)", normalized):
            if not sentence:
                continue
            for label, key in LABEL_ALIASES.items():
                if label.lower() in sentence.lower():
                    value = re.search(r"([0-9,\.]+)", sentence)
                    if value:
                        amount = _extract_amount(value.group(1))
                        if amount is not None:
                            summary[key] = amount
                            break

    return summary


def extract_financial_statement_from_bytes(data: bytes, filename: str) -> Dict[str, object]:
    text = ""
    ocr_used = False
    source = "text"

    if filename.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
        extracted_text = _extract_text_from_image_bytes(data)
        if extracted_text:
            text = extracted_text
            ocr_used = True
            source = "ocr"
    elif filename.lower().endswith(".pdf"):
        try:
            import fitz  # PyMuPDF
        except Exception:
            fitz = None

        if fitz is not None:
            try:
                with fitz.open(stream=data, filetype="pdf") as doc:
                    text = "\n".join(page.get_text() for page in doc)
                    source = "pdf"
            except Exception:
                text = ""
        else:
            text = ""
    else:
        try:
            text = data.decode("utf-8")
            source = "text"
        except Exception:
            text = data.decode("latin-1", errors="ignore")
            source = "text"

    metrics = extract_financial_summary(text)
    if not metrics and not text:
        message = "No readable financial data was found in the uploaded file."
    elif metrics:
        message = "Financial statement metrics extracted successfully."
    else:
        message = "The file was received, but no structured financial metrics could be confidently parsed."

    return {
        "metrics": metrics,
        "message": message,
        "source": source,
        "extracted_text": text[:4000],
        "ocr_used": ocr_used,
    }
