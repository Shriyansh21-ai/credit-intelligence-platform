"""Durable connector call logging (Milestones 1, 13, 14).

Persists one :class:`ConnectorCallLog` row per connector call. Request params are
PII-masked before storage (:func:`..base.security.mask_pii`). Best-effort by
design — :meth:`BaseConnector._log` already guards this, but we commit here so a
logging failure is contained to its own transaction.
"""

from __future__ import annotations

from typing import Any, Optional

from sqlalchemy.orm import Session

from backend.app.models.integrations import ConnectorCallLog
from backend.app.services.integrations.base.exceptions import ConnectorError
from backend.app.services.integrations.base.security import mask_pii
from backend.app.services.integrations.base.types import ConnectorRequest, ConnectorResponse


def record_call(
    db: Session,
    *,
    connector: Any,
    request: ConnectorRequest,
    response: ConnectorResponse,
    circuit_state: str,
    error: Optional[ConnectorError] = None,
) -> Optional[ConnectorCallLog]:
    entity_ref = None
    try:
        params = request.params or {}
        entity_ref = (
            params.get("entity_ref")
            or params.get("gstin")
            or params.get("cin")
            or params.get("pan")
            or params.get("account_ref")
        )
    except Exception:  # noqa: BLE001
        entity_ref = None

    row = ConnectorCallLog(
        connector_key=getattr(connector, "connector_key", connector.provider),
        category=connector.category.value,
        provider=connector.provider,
        mode=connector.mode.value,
        operation=request.operation,
        success=response.success,
        from_cache=response.from_cache,
        latency_ms=response.latency_ms,
        attempts=response.attempts,
        circuit_state=circuit_state,
        error=response.error,
        request_summary=mask_pii(request.params or {}),
        entity_ref=str(entity_ref) if entity_ref is not None else None,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def recent_calls(
    db: Session,
    *,
    connector_key: Optional[str] = None,
    category: Optional[str] = None,
    provider: Optional[str] = None,
    success: Optional[bool] = None,
    limit: int = 100,
) -> list[ConnectorCallLog]:
    q = db.query(ConnectorCallLog)
    if connector_key:
        q = q.filter(ConnectorCallLog.connector_key == connector_key)
    if category:
        q = q.filter(ConnectorCallLog.category == category)
    if provider:
        q = q.filter(ConnectorCallLog.provider == provider)
    if success is not None:
        q = q.filter(ConnectorCallLog.success == success)
    return q.order_by(ConnectorCallLog.id.desc()).limit(min(limit, 1000)).all()
