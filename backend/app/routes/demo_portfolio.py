"""Demo-portfolio API.

Persists and reads a coherent, tenant-isolated demo portfolio for the
authenticated user's organization. The tenant is resolved from the JWT (via
:func:`get_current_tenant_id`), never from a client-supplied header, so a user
can only ever load into / read from their own organization's book.

All endpoints require authentication. Reads and writes are filtered by
``tenant_id`` — a user from one organization can neither see nor modify
another's data.
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.app.core.dependencies import get_current_tenant_id, get_current_user
from backend.app.db.database import get_db
from backend.app.models.user import User
from backend.app.services import demo_portfolio

logger = logging.getLogger("app.demo_portfolio")

router = APIRouter(prefix="/api/demo-portfolio", tags=["Demo Portfolio"])


class LoadRequest(BaseModel):
    count: int = Field(default=demo_portfolio.DEFAULT_COMPANY_COUNT, ge=1, le=150)


@router.post("/load")
def load_portfolio(
    request: Optional[LoadRequest] = None,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    _user: User = Depends(get_current_user),
):
    """Load (idempotently) a demo portfolio into the caller's tenant.

    Safe to call repeatedly: companies already present for the tenant are
    skipped. The response reflects the actual database operation.
    """
    count = request.count if request else demo_portfolio.DEFAULT_COMPANY_COUNT
    try:
        return demo_portfolio.load_demo_portfolio(db, tenant_id, count=count)
    except Exception:  # surface a clean error; never a fake success
        db.rollback()
        # Log the full detail server-side; return a generic message so no
        # exception text (which may reference internals) reaches the client.
        logger.exception("demo portfolio load failed for tenant %s", tenant_id)
        raise HTTPException(status_code=500, detail="Failed to load demo portfolio.")


@router.get("/status")
def portfolio_status(
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    _user: User = Depends(get_current_user),
):
    return demo_portfolio.portfolio_status(db, tenant_id)


@router.get("/summary")
def portfolio_summary(
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    _user: User = Depends(get_current_user),
):
    """Tenant-scoped roll-up for dashboards (counts, exposure, distributions)."""
    return demo_portfolio.portfolio_summary(db, tenant_id)


@router.get("/companies")
def list_companies(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    _user: User = Depends(get_current_user),
):
    return demo_portfolio.list_companies(db, tenant_id, limit=limit, offset=offset)


@router.delete("/reset")
def reset_portfolio(
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    _user: User = Depends(get_current_user),
):
    """Remove the caller's demo portfolio (companies + dependent records)."""
    try:
        return demo_portfolio.reset_demo_portfolio(db, tenant_id)
    except Exception:
        db.rollback()
        logger.exception("demo portfolio reset failed for tenant %s", tenant_id)
        raise HTTPException(status_code=500, detail="Failed to reset demo portfolio.")
