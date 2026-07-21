"""Document field validation (Task 9).

Validates extracted or user-edited financial fields and returns structured
issues with severity so the frontend can render a validation panel. Duplicate
upload detection lives in the document service (it needs the DB); this service
covers field-level rules.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .field_extraction import GSTIN_RE

REQUIRED_FIELDS = {"company_name": "Company name", "revenue": "Revenue"}

# Currency fields that must never be negative (profit / cash-flow may be).
NON_NEGATIVE_CURRENCY = {
    "revenue", "cost_of_goods_sold", "operating_expenses", "cash", "current_assets",
    "current_liabilities", "inventory", "accounts_receivable", "accounts_payable",
    "short_term_debt", "long_term_debt", "tax_paid",
}

SEVERITY_ERROR = "error"
SEVERITY_WARNING = "warning"


@dataclass
class ValidationIssue:
    field: Optional[str]
    severity: str
    message: str

    def as_dict(self) -> dict:
        return {"field": self.field, "severity": self.severity, "message": self.message}


def _as_number(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


class DocumentValidationService:
    def validate(self, fields: Dict[str, Any]) -> List[ValidationIssue]:
        issues: List[ValidationIssue] = []

        # Required fields present and non-empty.
        for key, label in REQUIRED_FIELDS.items():
            value = fields.get(key)
            if value is None or (isinstance(value, str) and not value.strip()):
                issues.append(ValidationIssue(key, SEVERITY_ERROR, f"{label} is required."))

        # Non-negative currency fields.
        for key in NON_NEGATIVE_CURRENCY:
            number = _as_number(fields.get(key))
            if number is not None and number < 0:
                label = key.replace("_", " ").title()
                issues.append(ValidationIssue(key, SEVERITY_ERROR, f"{label} cannot be negative."))

        # Cross-field sanity checks.
        revenue = _as_number(fields.get("revenue"))
        gross_profit = _as_number(fields.get("gross_profit"))
        net_profit = _as_number(fields.get("net_profit"))
        if revenue is not None and gross_profit is not None and gross_profit > revenue:
            issues.append(ValidationIssue("gross_profit", SEVERITY_WARNING, "Gross profit exceeds revenue — please verify."))
        if revenue is not None and net_profit is not None and net_profit > revenue:
            issues.append(ValidationIssue("net_profit", SEVERITY_WARNING, "Net profit exceeds revenue — please verify."))

        current_assets = _as_number(fields.get("current_assets"))
        current_liabilities = _as_number(fields.get("current_liabilities"))
        if current_assets is not None and current_liabilities is not None and current_liabilities > current_assets * 5:
            issues.append(ValidationIssue("current_liabilities", SEVERITY_WARNING, "Current liabilities are unusually high relative to current assets."))

        # GST format.
        gst = fields.get("gst_number")
        if gst:
            normalized = str(gst).upper().replace(" ", "")
            if not GSTIN_RE.fullmatch(normalized):
                issues.append(ValidationIssue("gst_number", SEVERITY_ERROR, "Invalid GSTIN format (expected 15-character GST number)."))

        return issues

    def is_blocking(self, issues: List[ValidationIssue]) -> bool:
        return any(issue.severity == SEVERITY_ERROR for issue in issues)
