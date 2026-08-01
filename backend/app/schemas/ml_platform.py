"""Request/response schemas for the ML platform APIs."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

Features = Dict[str, Any]


class TrainRequest(BaseModel):
    algorithm: str = Field(..., description="logistic_regression | random_forest | gradient_boosting | xgboost | lightgbm | catboost | neural_network")
    dataset_seed: int = 42
    n_rows: int = 4000
    label_noise: float = 0.03
    tune: bool = False
    hyperparameters: Optional[Dict[str, Any]] = None
    model_key: Optional[str] = None
    name: Optional[str] = None
    register: bool = True


class PredictRequest(BaseModel):
    features: Features
    model_id: Optional[int] = None
    model_key: Optional[str] = None
    entity_type: Optional[str] = None
    entity_id: Optional[int] = None
    use_cache: bool = True


class BatchItem(BaseModel):
    features: Features
    entity_id: Optional[int] = None


class BatchPredictRequest(BaseModel):
    items: List[BatchItem]
    model_id: Optional[int] = None
    model_key: Optional[str] = None


class ExplainRequest(BaseModel):
    features: Features
    model_id: Optional[int] = None
    model_key: Optional[str] = None
    entity_type: Optional[str] = None
    entity_id: Optional[int] = None
    persist: bool = True


class ApprovalAction(BaseModel):
    note: Optional[str] = None


class DriftRequest(BaseModel):
    current_rows: List[Features]
    model_id: int
    report_type: str = "overall"
    psi_threshold: float = 0.25


class TargetDriftRequest(BaseModel):
    current_pds: List[float]
    model_id: int


class RetrainRequest(BaseModel):
    model_key: str
    algorithm: Optional[str] = None
    trigger: str = "manual"
    dataset_seed: int = 4242
    n_rows: int = 4000
    drift_shift: Optional[Dict[str, float]] = None
    auto_promote: bool = False
    tune: bool = False


class FraudScoreRequest(BaseModel):
    features: Features
    entity_type: Optional[str] = None
    entity_id: Optional[int] = None


class FraudBatchRequest(BaseModel):
    items: List[BatchItem]


class Position(BaseModel):
    features: Features
    entity_id: Optional[int] = None
    sector: Optional[str] = None
    exposure: Optional[float] = None
    lgd: Optional[float] = None


class PortfolioRequest(BaseModel):
    positions: List[Position]
    model_id: Optional[int] = None
    model_key: Optional[str] = None


class StressRequest(BaseModel):
    positions: List[Position]
    scenario: str
    severities: Optional[List[str]] = None
    model_id: Optional[int] = None
    model_key: Optional[str] = None


class StressAllRequest(BaseModel):
    positions: List[Position]
    severity: str = "worst"
    model_id: Optional[int] = None
    model_key: Optional[str] = None
