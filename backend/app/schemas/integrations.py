"""Request/response schemas for the Integration Platform APIs."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# --- Connector configuration ------------------------------------------------
class ConnectorModeUpdate(BaseModel):
    provider_mode: str = Field(..., pattern="^(mock|sandbox|production)$")


class ConnectorConfigUpdate(BaseModel):
    enabled: Optional[bool] = None
    config: Optional[Dict[str, Any]] = None
    credentials: Optional[Dict[str, Any]] = None
    rate_limit_per_sec: Optional[float] = None
    timeout_seconds: Optional[float] = None


# --- Generic import ---------------------------------------------------------
class ImportRequest(BaseModel):
    entity_ref: str
    operation: Optional[str] = None
    operations: Optional[List[str]] = None
    params: Dict[str, Any] = Field(default_factory=dict)
    application_id: Optional[int] = None
    mode: Optional[str] = None
    refresh_after_days: Optional[int] = 30


# --- Account Aggregator -----------------------------------------------------
class ConsentCreate(BaseModel):
    entity_ref: str
    purpose: str = "Credit assessment"
    months: int = 12
    application_id: Optional[int] = None
    fi_types: Optional[List[str]] = None


class StatementImport(BaseModel):
    entity_ref: str
    account_ref: str
    months: int = 12
    consent_id: Optional[int] = None
    application_id: Optional[int] = None
    account_type: Optional[str] = None
    bank_name: Optional[str] = None


# --- Collateral -------------------------------------------------------------
class CollateralCreate(BaseModel):
    collateral_type: str
    description: str
    market_value: float
    entity_ref: Optional[str] = None
    application_id: Optional[int] = None
    owner: Optional[str] = None
    haircut_pct: Optional[float] = None
    loan_amount: Optional[float] = None
    charge_type: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


class CollateralRevalue(BaseModel):
    market_value: float
    haircut_pct: Optional[float] = None
    method: str = "market"
    valuer: Optional[str] = None
    notes: Optional[str] = None


class CollateralInspect(BaseModel):
    inspector: Optional[str] = None
    outcome: str = "satisfactory"
    condition: Optional[str] = None
    notes: Optional[str] = None


# --- Synchronization --------------------------------------------------------
class SyncRequest(BaseModel):
    sync_type: str = Field("incremental", pattern="^(full|incremental)$")
    connectors: Optional[List[str]] = None
    entity_refs: List[str]
    max_retries: int = 2
    conflict_strategy: str = "latest_wins"


# --- Open API platform ------------------------------------------------------
class ApiKeyCreate(BaseModel):
    name: str
    scopes: Optional[List[str]] = None
    owner: Optional[str] = None
    rate_limit_per_min: int = 600


class WebhookCreate(BaseModel):
    url: str
    events: List[str]
    secret: Optional[str] = None
    description: Optional[str] = None


class WebhookEmit(BaseModel):
    event: str
    payload: Dict[str, Any] = Field(default_factory=dict)
