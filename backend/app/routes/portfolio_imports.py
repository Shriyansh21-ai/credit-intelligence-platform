"""Authenticated, tenant-scoped customer portfolio import API."""

from __future__ import annotations

import csv
import io
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.app.core.dependencies import get_current_tenant_id
from backend.app.core.settings import get_settings
from backend.app.db.database import get_db
from backend.app.models.portfolio_import import PortfolioImport
from backend.app.models.user import User
from backend.app.services import audit, portfolio_imports
from backend.app.services.rbac import require_permission

logger = logging.getLogger("app.portfolio_imports")
router = APIRouter(prefix="/api/portfolio-imports", tags=["Portfolio Imports"])


class MappingRequest(BaseModel):
    worksheet: str | None = None
    mapping: dict[str, str | None]


def _owned_import(db: Session, import_id: int, tenant_id: int) -> PortfolioImport:
    record = db.query(PortfolioImport).filter(
        PortfolioImport.id == import_id,
        PortfolioImport.tenant_id == tenant_id,
    ).first()
    if record is None:
        raise HTTPException(status_code=404, detail="Import not found.")
    return record


def _audit(db: Session, user: User, request, action: str, record: PortfolioImport) -> None:
    audit.record_safe(
        db,
        action=action,
        actor=user,
        entity_type="portfolio_import",
        entity_id=record.id,
        request=request,
        meta={"tenant_id": record.tenant_id, "status": record.status},
    )


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_import(
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    user: User = Depends(require_permission("portfolio.manage")),
):
    settings = get_settings()
    content = await file.read(settings.max_upload_bytes + 1)
    if len(content) > settings.max_upload_bytes:
        raise HTTPException(status_code=413, detail="The uploaded file exceeds the configured size limit.")
    try:
        file_format, staged = portfolio_imports.inspect_upload(file.filename or "upload", content)
    except portfolio_imports.ImportFileError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    record = PortfolioImport(
        tenant_id=tenant_id,
        uploaded_by=user.id,
        filename=portfolio_imports.safe_filename(file.filename or "upload"),
        file_format=file_format,
        file_size=len(content),
        status="awaiting_mapping",
        worksheet=next(iter(staged)),
        total_rows=len(staged[next(iter(staged))]["rows"]),
        staged_data=staged,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    _audit(db, user, request, "portfolio_import.created", record)
    return {**portfolio_imports.public_import(record), **portfolio_imports.mapping_suggestions(record)}


@router.get("")
def list_imports(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    _user: User = Depends(require_permission("portfolio.view")),
):
    query = db.query(PortfolioImport).filter(PortfolioImport.tenant_id == tenant_id)
    total = query.count()
    items = query.order_by(PortfolioImport.created_at.desc(), PortfolioImport.id.desc())\
        .offset(offset).limit(limit).all()
    return {"total": total, "items": [portfolio_imports.public_import(item) for item in items]}


@router.get("/{import_id}")
def get_import(
    import_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    _user: User = Depends(require_permission("portfolio.view")),
):
    return {**portfolio_imports.public_import(_owned_import(db, import_id, tenant_id)), "findings": _owned_import(db, import_id, tenant_id).findings}


@router.get("/{import_id}/mapping")
def get_mapping_suggestions(
    import_id: int,
    worksheet: str | None = None,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    _user: User = Depends(require_permission("portfolio.view")),
):
    record = _owned_import(db, import_id, tenant_id)
    try:
        return portfolio_imports.mapping_suggestions(record, worksheet)
    except portfolio_imports.ImportStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except portfolio_imports.ImportFileError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/{import_id}/mapping")
def update_mapping(
    import_id: int,
    body: MappingRequest,
    request: Request,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    user: User = Depends(require_permission("portfolio.manage")),
):
    record = _owned_import(db, import_id, tenant_id)
    try:
        suggestion_data = portfolio_imports.mapping_suggestions(record, body.worksheet)
        portfolio_imports.validate_mapping(record, body.mapping, suggestion_data["worksheet"])
    except portfolio_imports.ImportStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except portfolio_imports.ImportFileError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    db.refresh(record)
    _audit(db, user, request, "portfolio_import.validated", record)
    return {**portfolio_imports.public_import(record), "findings": record.findings}


@router.get("/{import_id}/preview")
def preview_import(
    import_id: int,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    _user: User = Depends(require_permission("portfolio.view")),
):
    record = _owned_import(db, import_id, tenant_id)
    try:
        return portfolio_imports.preview_import(record, limit=limit, offset=offset)
    except portfolio_imports.ImportStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/{import_id}/confirm")
def confirm_import(
    import_id: int,
    request: Request,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    user: User = Depends(require_permission("portfolio.manage")),
):
    record = _owned_import(db, import_id, tenant_id)
    before_status = record.status
    try:
        result = portfolio_imports.confirm_import(db, record, tenant_id)
    except portfolio_imports.ImportStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        db.rollback()
        logger.exception("Portfolio import %s failed", import_id)
        failed = _owned_import(db, import_id, tenant_id)
        failed.status = "failed"
        failed.failed_rows = failed.valid_rows
        failed.error_summary = "Persistence failed; no records were imported."
        failed.staged_data = None
        failed.completed_at = datetime.now(timezone.utc)
        db.commit()
        _audit(db, user, request, "portfolio_import.failed", failed)
        raise HTTPException(status_code=500, detail="Portfolio import failed; no records were imported.") from exc
    if before_status != "completed":
        _audit(db, user, request, "portfolio_import.completed", record)
    return result


@router.post("/{import_id}/cancel")
def cancel_import(
    import_id: int,
    request: Request,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    user: User = Depends(require_permission("portfolio.manage")),
):
    record = _owned_import(db, import_id, tenant_id)
    if record.status not in {"awaiting_mapping", "awaiting_confirmation"}:
        raise HTTPException(status_code=409, detail="This import can no longer be cancelled.")
    record.status = "cancelled"
    record.staged_data = None
    record.completed_at = datetime.now(timezone.utc)
    db.commit()
    _audit(db, user, request, "portfolio_import.cancelled", record)
    return portfolio_imports.public_import(record)


@router.get("/{import_id}/validation-report.csv")
def validation_report(
    import_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    _user: User = Depends(require_permission("portfolio.view")),
):
    record = _owned_import(db, import_id, tenant_id)
    stream = io.StringIO(newline="")
    writer = csv.writer(stream)
    writer.writerow(["row_number", "field", "code", "severity", "message"])
    for finding in record.findings:
        writer.writerow([finding["row_number"], finding["field"], finding["code"], finding["severity"], finding["message"]])
    stream.seek(0)
    return StreamingResponse(
        iter([stream.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="portfolio-import-{record.id}-validation.csv"'},
    )