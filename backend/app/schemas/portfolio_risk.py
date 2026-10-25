"""Request validation for tenant-scoped portfolio risk configuration."""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field


class ExposureLimitCreate(BaseModel):
    scope: Literal["portfolio", "company", "sector"]
    company_id: int | None = Field(default=None, gt=0)
    sector: str | None = Field(default=None, min_length=1, max_length=200)
    currency: str = Field(min_length=3, max_length=3, pattern=r"^[A-Z]{3}$")
    threshold: float = Field(gt=0, allow_inf_nan=False)
    approaching_ratio: float | None = Field(default=None, gt=0, lt=1, allow_inf_nan=False)


class ExposureLimitUpdate(BaseModel):
    threshold: float | None = Field(default=None, gt=0, allow_inf_nan=False)
    approaching_ratio: float | None = Field(default=None, gt=0, lt=1, allow_inf_nan=False)
    clear_approaching_ratio: bool = False
    is_active: bool | None = None
    reason: str = Field(min_length=1, max_length=1000)


class BreachAcknowledge(BaseModel):
    reason: str = Field(min_length=1, max_length=1000)


class CovenantEvaluationAcknowledge(BaseModel):
    reason: str = Field(min_length=1, max_length=1000)


class CompanyCovenantCreate(BaseModel):
    metric_key: Literal[
        "current_ratio_min",
        "debt_to_equity_max",
        "debt_to_ebitda_max",
    ]
    name: str = Field(min_length=1, max_length=200)
    threshold: float = Field(gt=0, allow_inf_nan=False)
    effective_date: date | None = None
    review_frequency_months: int | None = Field(default=None, ge=1, le=60)


class CompanyCovenantUpdate(BaseModel):
    threshold: float | None = Field(default=None, gt=0, allow_inf_nan=False)
    is_active: Literal["active", "inactive"] | None = None
    reason: str = Field(min_length=1, max_length=1000)
