"""Financial statement field extraction (intelligent, non-positional).

Maps free-form statement text to a canonical set of financial fields using a
synonym dictionary rather than fixed coordinates (Task 5). Each result carries a
value, the raw matched text, a confidence score and (when available) the
bounding box of the value for the document viewer overlay (Task 7).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .ocr.base import BoundingBox, OcrResult, OcrWord

# India GSTIN (15 chars): 2-digit state + 10-char PAN ([A-Z]{5}\d{4}[A-Z]) +
# 1 entity char + 'Z' + 1 checksum char.
GSTIN_RE = re.compile(r"\b\d{2}[A-Z]{5}\d{4}[A-Z][A-Z\d]Z[A-Z\d]\b")
YEAR_RE = re.compile(r"\b(?:FY\s?)?(19|20)\d{2}\s?[-/–]\s?(?:\d{2}|\d{4})\b|\b(19|20)\d{2}\b", re.IGNORECASE)
AMOUNT_RE = re.compile(r"\(?-?\s?(?:₹|rs\.?|inr|\$)?\s?\d{1,3}(?:,\d{2,3})*(?:\.\d+)?\)?", re.IGNORECASE)


class FieldType:
    CURRENCY = "currency"
    TEXT = "text"
    YEAR = "year"
    GST = "gst"
    IDENTIFIER = "identifier"


@dataclass(frozen=True)
class FieldSpec:
    key: str
    label: str
    type: str
    synonyms: List[str]


# Order within synonyms doesn't matter; globally the longest synonym wins so
# "cost of revenue" is never captured by "revenue".
FIELD_SPECS: List[FieldSpec] = [
    FieldSpec("company_name", "Company Name", FieldType.TEXT, ["company name", "name of company", "name of the company", "entity name", "business name"]),
    FieldSpec("financial_year", "Financial Year", FieldType.YEAR, ["financial year", "for the year ended", "year ended", "period ended", "for the period", "fy"]),
    FieldSpec("revenue", "Revenue", FieldType.CURRENCY, ["total revenue", "revenue from operations", "annual revenue", "total income", "net sales", "turnover", "revenue", "sales"]),
    FieldSpec("cost_of_goods_sold", "Cost of Goods Sold", FieldType.CURRENCY, ["cost of goods sold", "cost of sales", "cost of revenue", "cogs"]),
    FieldSpec("gross_profit", "Gross Profit", FieldType.CURRENCY, ["gross profit"]),
    FieldSpec("operating_expenses", "Operating Expenses", FieldType.CURRENCY, ["total operating expenses", "operating expenses", "administrative expenses", "opex"]),
    FieldSpec("ebitda", "EBITDA", FieldType.CURRENCY, ["ebitda", "operating profit", "earnings before interest"]),
    FieldSpec("net_profit", "Net Profit", FieldType.CURRENCY, ["profit after tax", "net profit", "net income", "net earnings", "pat"]),
    FieldSpec("cash", "Cash & Equivalents", FieldType.CURRENCY, ["cash and cash equivalents", "cash & cash equivalents", "cash equivalents", "cash"]),
    FieldSpec("current_assets", "Current Assets", FieldType.CURRENCY, ["total current assets", "current assets"]),
    FieldSpec("current_liabilities", "Current Liabilities", FieldType.CURRENCY, ["total current liabilities", "current liabilities"]),
    FieldSpec("inventory", "Inventory", FieldType.CURRENCY, ["inventories", "inventory", "stock in trade"]),
    FieldSpec("accounts_receivable", "Accounts Receivable", FieldType.CURRENCY, ["accounts receivable", "trade receivables", "receivables", "debtors"]),
    FieldSpec("accounts_payable", "Accounts Payable", FieldType.CURRENCY, ["accounts payable", "trade payables", "payables", "creditors"]),
    FieldSpec("short_term_debt", "Short-term Debt", FieldType.CURRENCY, ["short term debt", "short-term borrowings", "current borrowings"]),
    FieldSpec("long_term_debt", "Long-term Debt", FieldType.CURRENCY, ["long term debt", "long-term borrowings", "non-current borrowings"]),
    FieldSpec("operating_cash_flow", "Operating Cash Flow", FieldType.CURRENCY, ["net cash from operating activities", "cash flow from operations", "cash from operating activities", "operating cash flow"]),
    FieldSpec("tax_paid", "Tax Paid", FieldType.CURRENCY, ["provision for tax", "income tax expense", "current tax", "tax paid", "tax expense", "taxes paid"]),
    FieldSpec("gst_number", "GST Number", FieldType.GST, ["gstin", "gst number", "gst no", "gst"]),
    FieldSpec("registration_number", "Registration Number", FieldType.IDENTIFIER, ["registration number", "company registration", "registration no", "cin", "reg no"]),
    FieldSpec("bank_account_name", "Bank Account Name", FieldType.TEXT, ["name of account holder", "bank account name", "account holder", "account name"]),
]

_SPEC_BY_KEY = {spec.key: spec for spec in FIELD_SPECS}

# (synonym, spec) sorted longest-first so the most specific label matches.
_SYNONYM_INDEX = sorted(
    ((syn, spec) for spec in FIELD_SPECS for syn in spec.synonyms),
    key=lambda pair: len(pair[0]),
    reverse=True,
)

_LINE_Y_TOLERANCE = 0.012


@dataclass
class ExtractedField:
    key: str
    label: str
    type: str
    value: Optional[Any]
    raw_text: Optional[str]
    confidence: float
    bbox: Optional[dict] = None

    def as_dict(self) -> dict:
        return {
            "key": self.key,
            "label": self.label,
            "type": self.type,
            "value": self.value,
            "raw_text": self.raw_text,
            "confidence": round(self.confidence, 4),
            "bbox": self.bbox,
        }


@dataclass
class _Line:
    text: str
    words: List[OcrWord] = field(default_factory=list)


def _norm_token(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.lower())


def _parse_amount(text: str) -> Optional[float]:
    if not text:
        return None
    negative = "(" in text and ")" in text
    cleaned = re.sub(r"[^0-9.]", "", text.replace(",", ""))
    if not cleaned or cleaned == ".":
        return None
    try:
        value = float(cleaned)
    except ValueError:
        return None
    return -value if negative else value


def _union_box(words: List[OcrWord]) -> Optional[dict]:
    boxed = [w.box for w in words if w.box.width > 0 or w.box.height > 0]
    if not boxed:
        return None
    x0 = min(b.x for b in boxed)
    y0 = min(b.y for b in boxed)
    x1 = max(b.x + b.width for b in boxed)
    y1 = max(b.y + b.height for b in boxed)
    page = boxed[0].page
    return BoundingBox(x0, y0, x1 - x0, y1 - y0, page).as_dict()


def _group_lines(result: OcrResult) -> List[_Line]:
    lines: List[_Line] = []
    for page in result.pages:
        raw = getattr(page, "_raw_text", None)
        if raw is not None:
            lines.extend(_Line(text=" ".join(l.split())) for l in raw.splitlines() if l.strip())
            continue

        current: List[OcrWord] = []
        current_y: Optional[float] = None
        for word in sorted(page.words, key=lambda w: (w.box.y, w.box.x)):
            yc = word.box.y + word.box.height / 2
            if current_y is None or abs(yc - current_y) <= _LINE_Y_TOLERANCE:
                current.append(word)
                current_y = yc if current_y is None else current_y
            else:
                lines.append(_line_from_words(current))
                current, current_y = [word], yc
        if current:
            lines.append(_line_from_words(current))
    return lines


def _line_from_words(words: List[OcrWord]) -> _Line:
    ordered = sorted(words, key=lambda w: w.box.x)
    return _Line(text=" ".join(w.text for w in ordered), words=ordered)


def _match_label(line: _Line, synonym: str) -> Optional[int]:
    """Return the word index immediately after the label, or None if absent."""
    syn_tokens = [_norm_token(t) for t in synonym.split() if _norm_token(t)]
    if not syn_tokens:
        return None

    if line.words:
        norm = [_norm_token(w.text) for w in line.words]
        for start in range(len(norm) - len(syn_tokens) + 1):
            if norm[start:start + len(syn_tokens)] == syn_tokens:
                return start + len(syn_tokens)
        return None

    # Text-only line (plain-text path): substring match.
    return 0 if " ".join(syn_tokens) in _norm_token(line.text.replace(" ", " ")) or all(
        t in _norm_token(line.text) for t in syn_tokens
    ) else None


def _extract_value(line: _Line, after: int, spec: FieldSpec) -> Optional[ExtractedField]:
    value_words = line.words[after:] if line.words else []
    remainder = " ".join(w.text for w in value_words) if value_words else _strip_label(line.text, spec)
    base_conf = _mean_conf(value_words)

    if spec.type == FieldType.CURRENCY:
        chosen, box = _pick_amount(value_words, remainder)
        if chosen is None:
            return None
        return ExtractedField(spec.key, spec.label, spec.type, chosen, remainder.strip(), base_conf, box)

    if spec.type == FieldType.YEAR:
        match = YEAR_RE.search(remainder)
        if not match:
            return None
        return ExtractedField(spec.key, spec.label, spec.type, match.group(0).strip(), remainder.strip(),
                              min(0.97, base_conf), _union_box(value_words))

    if spec.type == FieldType.GST:
        match = GSTIN_RE.search(remainder.upper().replace(" ", ""))
        if not match:
            return None
        return ExtractedField(spec.key, spec.label, spec.type, match.group(0), remainder.strip(),
                              min(0.98, base_conf + 0.1), _union_box(value_words))

    # TEXT / IDENTIFIER
    text_value = re.sub(r"^[\s:\-–]+", "", remainder).strip()
    if not text_value:
        return None
    return ExtractedField(spec.key, spec.label, spec.type, text_value, remainder.strip(),
                          min(0.95, base_conf), _union_box(value_words))


def _pick_amount(value_words: List[OcrWord], remainder: str):
    for word in value_words:
        amount = _parse_amount(word.text)
        if amount is not None and sum(c.isdigit() for c in word.text) >= 2:
            return amount, _union_box([word])
    match = AMOUNT_RE.search(remainder)
    if match:
        amount = _parse_amount(match.group(0))
        if amount is not None:
            return amount, _union_box(value_words)
    return None, None


def _mean_conf(words: List[OcrWord]) -> float:
    confs = [w.confidence for w in words if w.text.strip()]
    return round(sum(confs) / len(confs), 4) if confs else 0.9


def _strip_label(text: str, spec: FieldSpec) -> str:
    lowered = text.lower()
    for syn in sorted(spec.synonyms, key=len, reverse=True):
        idx = lowered.find(syn)
        if idx != -1:
            return text[idx + len(syn):]
    return text


class FinancialStatementExtractor:
    """Extracts canonical financial fields from an :class:`OcrResult`."""

    def extract(self, result: OcrResult) -> Dict[str, ExtractedField]:
        lines = _group_lines(result)
        found: Dict[str, ExtractedField] = {}

        for line in lines:
            for synonym, spec in _SYNONYM_INDEX:
                if spec.key in found:
                    continue
                after = _match_label(line, synonym)
                if after is None:
                    continue
                extracted = _extract_value(line, after, spec)
                if extracted is not None:
                    found[spec.key] = extracted
                    break  # one field per line

        self._apply_fallbacks(found, lines)
        return found

    def _apply_fallbacks(self, found: Dict[str, ExtractedField], lines: List[_Line]) -> None:
        # Company name: first title-like line near the top if not labelled.
        if "company_name" not in found:
            for line in lines[:5]:
                text = line.text.strip()
                if 2 <= len(text) <= 60 and re.search(r"[A-Za-z]", text) and ":" not in text and not AMOUNT_RE.fullmatch(text):
                    spec = _SPEC_BY_KEY["company_name"]
                    found["company_name"] = ExtractedField(
                        spec.key, spec.label, spec.type, text, text, 0.5, _union_box(line.words)
                    )
                    break

        # Financial year: scan whole document if not labelled.
        if "financial_year" not in found:
            for line in lines:
                match = YEAR_RE.search(line.text)
                if match:
                    spec = _SPEC_BY_KEY["financial_year"]
                    found["financial_year"] = ExtractedField(
                        spec.key, spec.label, spec.type, match.group(0).strip(), line.text.strip(), 0.5,
                        _union_box(line.words),
                    )
                    break
