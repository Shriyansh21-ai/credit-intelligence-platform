"""Report service — orchestrates builders + renderers.

``generate_report`` builds the normalised document for a report type then either
returns it as JSON (``format="json"``) or renders it to a downloadable file.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from backend.app.services.reports import builders
from backend.app.services.reports.renderers import RENDERERS, available_formats

REPORT_TYPES = (
    "credit_memo",
    "executive_summary",
    "financial_report",
    "risk_report",
    "committee_pack",
    "portfolio_report",
    "compliance_report",
    "audit_report",
)

SUPPORTED_FORMATS = ("json", "html", "pdf", "csv", "rtf")

# Report types that require an application_id.
_APP_SCOPED = {
    "credit_memo", "executive_summary", "financial_report",
    "risk_report", "committee_pack",
}


class ReportError(ValueError):
    pass


def _build(db: Session, report_type: str, *, application_id: Optional[int],
           entity_type: Optional[str], entity_id: Optional[int]) -> Dict[str, Any]:
    if report_type in _APP_SCOPED:
        if application_id is None:
            raise ReportError(f"{report_type} requires application_id")
        builder = getattr(builders, f"build_{report_type}")
        return builder(db, application_id)
    if report_type == "portfolio_report":
        return builders.build_portfolio_report(db)
    if report_type == "compliance_report":
        return builders.build_compliance_report(db, application_id=application_id)
    if report_type == "audit_report":
        return builders.build_audit_report(db, entity_type=entity_type, entity_id=entity_id)
    raise ReportError(f"Unknown report type: {report_type}")


def generate_report(
    db: Session,
    *,
    report_type: str,
    fmt: str = "json",
    application_id: Optional[int] = None,
    entity_type: Optional[str] = None,
    entity_id: Optional[int] = None,
) -> Dict[str, Any]:
    """Return ``{format, document|content, content_type, filename}``.

    For ``format="json"`` the ``document`` key holds the report dict. For file
    formats, ``content`` holds raw bytes plus ``content_type`` and ``filename``.
    """
    if report_type not in REPORT_TYPES:
        raise ReportError(f"Unknown report type: {report_type}")
    if fmt not in SUPPORTED_FORMATS:
        raise ReportError(f"Unsupported format: {fmt}")

    document = _build(
        db, report_type,
        application_id=application_id, entity_type=entity_type, entity_id=entity_id,
    )

    if fmt == "json":
        return {"format": "json", "document": document}

    renderer = RENDERERS[fmt]
    content, content_type, ext = renderer(document)
    filename = f"{report_type}"
    if application_id:
        filename += f"_{application_id}"
    filename += f".{ext}"
    return {
        "format": fmt,
        "content": content,
        "content_type": content_type,
        "filename": filename,
        "available_formats": available_formats(),
    }
