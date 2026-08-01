"""Report generation API.

    GET /api/reports/types report types + available formats
    GET /api/reports/{report_type} generate a report

Query params: format (json|html|pdf|csv|rtf), application_id, entity_type, entity_id.
JSON returns the structured document; file formats stream a download. Viewing
requires ``reports.view``; non-JSON exports require ``reports.export``.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Response, status as http_status
from sqlalchemy.orm import Session

from backend.app.db.database import get_db
from backend.app.models.user import User
from backend.app.services import audit, reports
from backend.app.services.reports.renderers import available_formats
from backend.app.services.reports.service import ReportError
from backend.app.services.rbac import has_permission
from backend.app.core.dependencies import get_current_user

router = APIRouter(prefix="/api/reports", tags=["Reports"])


@router.get("/types")
def report_types(_user: User = Depends(get_current_user)):
    return {
        "report_types": list(reports.REPORT_TYPES),
        "formats": reports.SUPPORTED_FORMATS,
        "available_formats": available_formats(),
    }


@router.get("/{report_type}")
def generate(
    report_type: str,
    format: str = "json",
    application_id: Optional[int] = None,
    entity_type: Optional[str] = None,
    entity_id: Optional[int] = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    # Viewing needs reports.view; exporting to a file needs reports.export.
    needed = "reports.view" if format == "json" else "reports.export"
    if not has_permission(db, user, needed):
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail=f"Missing required permission: {needed}",
        )

    try:
        result = reports.generate_report(
            db,
            report_type=report_type,
            fmt=format,
            application_id=application_id,
            entity_type=entity_type,
            entity_id=entity_id,
        )
    except ReportError as exc:
        raise HTTPException(status_code=http_status.HTTP_400_BAD_REQUEST, detail=str(exc))

    audit.record_safe(
        db, action="report.generate", actor=user,
        entity_type="report", entity_id=application_id,
        meta={"report_type": report_type, "format": format},
    )

    if result["format"] == "json":
        return result["document"]

    return Response(
        content=result["content"],
        media_type=result["content_type"],
        headers={"Content-Disposition": f'attachment; filename="{result["filename"]}"'},
    )
