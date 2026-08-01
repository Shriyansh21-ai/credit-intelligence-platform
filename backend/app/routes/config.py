"""System configuration API.

    GET /api/config all config (optional ?category=)
    GET /api/config/categories distinct categories
    GET /api/config/{key} one value
    PUT /api/config/{key} update a value (config.manage)

Reading requires ``config.view``; writing requires ``config.manage``.
"""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status as http_status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.app.db.database import get_db
from backend.app.models.system_config import SystemConfig
from backend.app.models.user import User
from backend.app.services import config as config_service
from backend.app.services.rbac import require_permission

router = APIRouter(prefix="/api/config", tags=["System Config"])


class ConfigUpdate(BaseModel):
    value: Any


@router.get("")
def get_all(
    category: Optional[str] = None,
    db: Session = Depends(get_db),
    _user: User = Depends(require_permission("config.view")),
):
    return {"config": config_service.get_all_config(db, category=category)}


@router.get("/categories")
def categories(
    db: Session = Depends(get_db),
    _user: User = Depends(require_permission("config.view")),
):
    return {"categories": config_service.list_categories(db)}


@router.get("/{key}")
def get_one(
    key: str,
    db: Session = Depends(get_db),
    _user: User = Depends(require_permission("config.view")),
):
    row = db.query(SystemConfig).filter(SystemConfig.key == key).first()
    if row is None:
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="Config key not found")
    return config_service.serialize(row)


@router.put("/{key}")
def update_one(
    key: str,
    payload: ConfigUpdate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("config.manage")),
):
    return config_service.set_config(db, key, payload.value, actor=actor)
