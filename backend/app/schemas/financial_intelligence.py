"""Inbound Pydantic schemas for the Advanced Financial Intelligence APIs.

Request bodies only — responses are plain JSON dicts assembled by the services
(mirroring the /10 / convention). Grouped by milestone.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# --- M1 Treasury ----------------------------------------------------------
class FundingSourceCreate(BaseModel):
    name: str
    source_type: str
    amount: float
    rate: float = 0.0
    tenor_days: int = 0
    currency: str = "INR"
    stability_factor: Optional[float] = None
    is_secured: bool = False
    meta: Dict[str, Any] = Field(default_factory=dict)


class CashPositionRequest(BaseModel):
    balances: Dict[str, float] = Field(default_factory=dict)
    as_of: Optional[str] = None


class LiquidityLadderRequest(BaseModel):
    assets: List[Dict[str, Any]] = Field(default_factory=list)
    liabilities: List[Dict[str, Any]] = Field(default_factory=list)
    as_of: Optional[str] = None


class FundingGapRequest(BaseModel):
    funding_need: float


class NIMRequest(BaseModel):
    earning_assets: float
    asset_yield: float


class YieldRequest(BaseModel):
    positions: List[Dict[str, Any]]


class ALMRequest(BaseModel):
    assets: List[Dict[str, Any]] = Field(default_factory=list)
    liabilities: List[Dict[str, Any]] = Field(default_factory=list)
    rate_shock_bps: float = 100.0


class LCRRequest(BaseModel):
    hqla: float
    outflows: Optional[Dict[str, float]] = None
    inflows: float = 0.0
    use_registry: bool = True


class NSFRRequest(BaseModel):
    required_stable_funding: float
    available_stable_funding: Optional[float] = None
    use_registry: bool = True


class CashForecastRequest(BaseModel):
    opening_cash: float
    horizon: int = 12
    monthly_inflow: float = 0.0
    monthly_outflow: float = 0.0
    growth: float = 0.0
    volatility: float = 0.05


class LiquidityScenarioRequest(BaseModel):
    base_hqla: float
    base_outflows: float
    shocks: Optional[List[Dict[str, Any]]] = None


class LiquidityStressRequest(BaseModel):
    hqla: float
    base_outflows: float
    survival_days: int = 30


class FundingOptimizationRequest(BaseModel):
    target_amount: float
    max_cost: Optional[float] = None
    min_stability: float = 0.5


# --- M2 Portfolio ---------------------------------------------------------
class PortfolioCreate(BaseModel):
    key: str
    name: str
    portfolio_type: str = "commercial"
    currency: str = "INR"
    description: Optional[str] = None
    meta: Dict[str, Any] = Field(default_factory=dict)


class PositionCreate(BaseModel):
    portfolio_id: int
    company_ref: str
    ead: float
    pd: float = 0.05
    lgd: float = 0.45
    industry: Optional[str] = None
    country: Optional[str] = None
    region: Optional[str] = None
    rating: Optional[str] = None
    maturity_years: float = 3.0
    spread: float = 0.03
    assessment_id: Optional[int] = None
    meta: Dict[str, Any] = Field(default_factory=dict)


class LossParams(BaseModel):
    confidence: float = 0.999


class RarocParams(BaseModel):
    cost_of_capital: float = 0.12
    opex_rate: float = 0.005
    confidence: float = 0.999


class SimulateParams(BaseModel):
    iterations: int = 5000
    seed: int = 42
    confidence: float = 0.99


class OptimizeParams(BaseModel):
    max_single_exposure_pct: float = 0.10
    max_sector_pct: float = 0.30


# --- M3 Regulatory --------------------------------------------------------
class ECLRequest(BaseModel):
    subject_ref: Optional[str] = None
    assessment_id: Optional[int] = None
    pd: Optional[float] = None
    lgd: Optional[float] = None
    ead: Optional[float] = None
    dpd: int = 0
    original_pd: Optional[float] = None
    lifetime_years: int = 5
    eir: float = 0.10


class RWARequest(BaseModel):
    approach: str = "irb"
    subject_ref: Optional[str] = None
    assessment_id: Optional[int] = None
    pd: Optional[float] = None
    lgd: Optional[float] = None
    ead: Optional[float] = None
    maturity: float = 2.5


class CARRequest(BaseModel):
    cet1: float
    additional_tier1: float = 0.0
    tier2: float = 0.0
    total_rwa: float


class LeverageRequest(BaseModel):
    tier1_capital: float
    total_exposure: float


# --- M4 Economic ----------------------------------------------------------
class IndicatorCreate(BaseModel):
    code: str
    name: str
    value: float
    region: str = "IN"
    unit: Optional[str] = None
    as_of: Optional[str] = None
    meta: Dict[str, Any] = Field(default_factory=dict)


class ScenarioGenerate(BaseModel):
    name: str
    scenario_type: str = "baseline"
    region: str = "IN"
    horizon_years: int = 3
    custom_shocks: Optional[Dict[str, float]] = None
    key: Optional[str] = None


class PropagateRequest(BaseModel):
    scenario_id: Optional[int] = None
    scenario_type: Optional[str] = None
    region: str = "IN"


# --- M5 ESG ---------------------------------------------------------------
class ESGAssessRequest(BaseModel):
    subject_ref: str
    assessment_id: Optional[int] = None
    revenue: Optional[float] = None
    industry: Optional[str] = None
    overrides: Optional[Dict[str, float]] = None


class ClimateStressRequest(BaseModel):
    subject_ref: Optional[str] = None
    carbon_price: float = 3000.0
    price_shock_multiple: float = 3.0
    revenue: Optional[float] = None
    industry: Optional[str] = None


# --- M6 Market ------------------------------------------------------------
class InstrumentCreate(BaseModel):
    symbol: str
    name: str
    asset_class: str
    currency: str = "INR"
    meta: Dict[str, Any] = Field(default_factory=dict)


class QuoteCreate(BaseModel):
    symbol: str
    value: float
    asset_class: Optional[str] = None
    change: Optional[float] = None
    payload: Dict[str, Any] = Field(default_factory=dict)
    as_of: Optional[str] = None
    source: str = "synthetic"


class YieldCurveRequest(BaseModel):
    curve: Optional[Dict[str, float]] = None
    query_tenors: Optional[List[float]] = None


class NewsCreate(BaseModel):
    headline: str
    category: str = "macro"
    body: Optional[str] = None
    subject_ref: Optional[str] = None
    source: str = "synthetic"
    published_at: Optional[str] = None


# --- M7 Alternative Data --------------------------------------------------
class SignalIngest(BaseModel):
    subject_ref: str
    signal_type: str
    raw: Dict[str, Any] = Field(default_factory=dict)
    source: str = "synthetic"
    as_of: Optional[str] = None


class CompositeRequest(BaseModel):
    subject_ref: str


# --- M8 Forecasting -------------------------------------------------------
class ForecastRequest(BaseModel):
    forecast_type: str
    subject_ref: Optional[str] = None
    assessment_id: Optional[int] = None
    horizon: int = 12
    history: Optional[List[float]] = None
    frequency: str = "monthly"
    drift: Optional[float] = None


class MultiHorizonRequest(BaseModel):
    forecast_type: str
    subject_ref: Optional[str] = None
    assessment_id: Optional[int] = None
    horizons: Optional[List[int]] = None
    history: Optional[List[float]] = None


# --- M9 Quant Risk --------------------------------------------------------
class MonteCarloRequest(BaseModel):
    positions: List[Dict[str, Any]]
    iterations: int = 10000
    seed: int = 7
    correlation_matrix: Optional[List[List[float]]] = None
    confidence: float = 0.99
    subject_ref: Optional[str] = None


class VaRRequest(BaseModel):
    returns: Optional[List[float]] = None
    portfolio_value: float = 1_000_000.0
    mean_return: Optional[float] = None
    volatility: Optional[float] = None
    confidence: float = 0.99
    method: str = "parametric"
    horizon_days: int = 1
    subject_ref: Optional[str] = None


class QuantStressRequest(BaseModel):
    base_value: float
    factors: Dict[str, float]
    scenarios: Optional[List[Dict[str, Any]]] = None
    subject_ref: Optional[str] = None


class SensitivityRequest(BaseModel):
    base_value: float
    factors: Dict[str, float]
    shock: float = 0.01
    subject_ref: Optional[str] = None


class ScenarioTreeRequest(BaseModel):
    base_value: float
    stages: int = 3
    up: float = 0.10
    down: float = -0.08
    prob_up: float = 0.55
    subject_ref: Optional[str] = None


class AttributionRequest(BaseModel):
    positions: List[Dict[str, Any]]
    confidence: float = 0.99
    subject_ref: Optional[str] = None


class CorrelationRequest(BaseModel):
    series: Dict[str, List[float]]
    subject_ref: Optional[str] = None


class VolatilityRequest(BaseModel):
    returns: List[float]
    lam: float = 0.94
    subject_ref: Optional[str] = None


class TailRequest(BaseModel):
    returns: List[float]
    threshold: float = 0.95
    subject_ref: Optional[str] = None


# --- M10 Benchmarking -----------------------------------------------------
class BenchmarkRequest(BaseModel):
    subject_ref: str
    assessment_id: Optional[int] = None
    industry: Optional[str] = None


# --- M11 Executive --------------------------------------------------------
class ExecDashboardRequest(BaseModel):
    persona: str


# --- M12 Optimization -----------------------------------------------------
class LoanPricingRequest(BaseModel):
    subject_ref: Optional[str] = None
    assessment_id: Optional[int] = None
    pd: Optional[float] = None
    lgd: Optional[float] = None
    ead: Optional[float] = None
    cost_of_funds: float = 0.065
    opex_rate: float = 0.005
    target_roe: float = 0.15
    capital_ratio: float = 0.12


class CreditLimitRequest(BaseModel):
    subject_ref: Optional[str] = None
    assessment_id: Optional[int] = None
    pd: Optional[float] = None
    single_name_cap: float = 0.10
    total_capital: float = 100_000_000.0
    risk_appetite_el: float = 0.02


class AllocationRequest(BaseModel):
    candidates: List[Dict[str, Any]]
    budget: float
    cost_of_capital: float = 0.12
    max_weight: float = 0.25
    subject_ref: Optional[str] = None


class CapitalAllocationRequest(BaseModel):
    business_units: List[Dict[str, Any]]
    total_capital: float


class CollateralRequest(BaseModel):
    exposure: float
    collateral_options: List[Dict[str, Any]]
    subject_ref: Optional[str] = None


# --- M13 Digital Twin -----------------------------------------------------
class TwinCreate(BaseModel):
    key: str
    name: str
    twin_type: str
    subject_ref: Optional[str] = None
    state: Optional[Dict[str, Any]] = None
    drivers: Optional[Dict[str, float]] = None
    meta: Dict[str, Any] = Field(default_factory=dict)


class TwinSimulateRequest(BaseModel):
    horizon: int = 8
    scenario: Optional[Dict[str, float]] = None
    scenario_ref: Optional[str] = None


class TwinUpdateRequest(BaseModel):
    state: Dict[str, Any]
    drivers: Optional[Dict[str, float]] = None


# --- M14 Strategic --------------------------------------------------------
class StrategicReportRequest(BaseModel):
    report_type: str
    subject_ref: Optional[str] = None
    assessment_id: Optional[int] = None
    title: Optional[str] = None
