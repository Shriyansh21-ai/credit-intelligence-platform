"""Enterprise Credit Assessment domain schemas.

These models describe the *enterprise* (commercial / B2B) lending workflow and
replace the legacy consumer-credit request. They are organised into the four
business sections that the assessment form collects:

    1. BusinessProfile        - who the borrower is
    2. FinancialInformation   - P&L / balance-sheet / cash-flow figures
    3. BankingInformation     - banking behaviour & credit conduct
    4. BusinessRiskProfile    - qualitative risk indicators

The composed :class:`EnterpriseAssessmentRequest` is the wire contract for
``POST /predict/enterprise-assessment``. The scoring engine consumes a *flat*
dictionary (for backward compatibility with other callers), so the request
exposes :meth:`EnterpriseAssessmentRequest.to_engine_input`.

Validation (Task 7) is enforced here with Pydantic v2 field constraints:
monetary values that cannot be negative use ``ge=0``, percentages are bounded
to ``0..100`` and business age is capped to a realistic range.
"""

from __future__ import annotations

from enum import Enum
from typing import Annotated, Optional

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Reusable constrained types
# ---------------------------------------------------------------------------

# Money that cannot logically be negative (revenue, assets, balances...).
NonNegativeMoney = Annotated[float, Field(ge=0)]
# Money that may be negative (profit, cash flow, working capital, net worth).
SignedMoney = Annotated[float, Field()]
Percentage = Annotated[float, Field(ge=0, le=100)]


# ---------------------------------------------------------------------------
# Categorical enums (drive strong validation + frontend selects)
# ---------------------------------------------------------------------------

class RiskBand(str, Enum):
    low = "low"
    moderate = "moderate"
    high = "high"


class ConcentrationLevel(str, Enum):
    diversified = "diversified"
    balanced = "balanced"
    concentrated = "concentrated"


class ComplianceStatus(str, Enum):
    compliant = "compliant"
    partial = "partial"
    non_compliant = "non_compliant"


class ExpansionStage(str, Enum):
    startup = "startup"
    growth = "growth"
    mature = "mature"
    expansion = "expansion"
    decline = "decline"


class PriorDefaults(str, Enum):
    none = "none"
    present = "present"


# ---------------------------------------------------------------------------
# Section 1 — Business Profile
# ---------------------------------------------------------------------------

class BusinessProfile(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    company_name: str = Field(min_length=1, max_length=200)
    industry: str = Field(min_length=1, max_length=120)
    business_type: str = Field(min_length=1, max_length=120)
    years_in_business: int = Field(ge=0, le=200)
    employee_count: int = Field(ge=1, le=5_000_000)
    head_office: str = Field(min_length=1, max_length=200)
    country: str = Field(min_length=1, max_length=100)
    registration_number: Optional[str] = Field(default=None, max_length=120)
    gst_number: Optional[str] = Field(default=None, max_length=120)
    website: Optional[str] = Field(default=None, max_length=200)


# ---------------------------------------------------------------------------
# Section 2 — Financial Information
# ---------------------------------------------------------------------------

class FinancialInformation(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    annual_revenue: NonNegativeMoney
    gross_profit: SignedMoney
    net_profit: SignedMoney
    ebitda: SignedMoney
    operating_expenses: NonNegativeMoney
    cash_and_cash_equivalents: NonNegativeMoney
    current_assets: NonNegativeMoney
    current_liabilities: NonNegativeMoney
    inventory: NonNegativeMoney
    accounts_receivable: NonNegativeMoney
    accounts_payable: NonNegativeMoney
    long_term_debt: NonNegativeMoney
    short_term_debt: NonNegativeMoney
    operating_cash_flow: SignedMoney

    # Supplementary figures used by the ratio engine. Optional so the form can
    # stay lean; sensible defaults keep scoring well-defined.
    working_capital: Optional[SignedMoney] = Field(
        default=None,
        description="Overridden by (current_assets - current_liabilities) when omitted.",
    )
    interest_expense: NonNegativeMoney = 0.0
    free_cash_flow: SignedMoney = 0.0
    net_worth: SignedMoney = 0.0


# ---------------------------------------------------------------------------
# Section 3 — Banking & Credit
# ---------------------------------------------------------------------------

class BankingInformation(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    average_monthly_balance: NonNegativeMoney
    average_monthly_inflow: NonNegativeMoney
    average_monthly_outflow: NonNegativeMoney
    existing_loans: int = Field(ge=0, le=100_000)
    existing_emi: NonNegativeMoney = 0.0
    credit_utilization: Percentage
    tax_compliance: ComplianceStatus = ComplianceStatus.compliant
    gst_compliance: ComplianceStatus = ComplianceStatus.compliant
    cheque_bounce_count: int = Field(ge=0, le=100_000)
    previous_defaults: PriorDefaults = PriorDefaults.none


# ---------------------------------------------------------------------------
# Section 4 — Business Risk
# ---------------------------------------------------------------------------

class BusinessRiskProfile(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    industry_risk: RiskBand = RiskBand.moderate
    geographical_risk: RiskBand = RiskBand.low
    supplier_concentration: ConcentrationLevel = ConcentrationLevel.balanced
    customer_concentration: ConcentrationLevel = ConcentrationLevel.balanced
    business_expansion_stage: ExpansionStage = ExpansionStage.growth


# ---------------------------------------------------------------------------
# Composed request
# ---------------------------------------------------------------------------

class EnterpriseAssessmentRequest(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    business_profile: BusinessProfile
    financials: FinancialInformation
    banking: BankingInformation
    risk_profile: BusinessRiskProfile

    def to_engine_input(self) -> dict:
        """Flatten the sectioned request into the dict the scoring engine reads."""
        bp = self.business_profile
        fin = self.financials
        bank = self.banking
        risk = self.risk_profile

        working_capital = fin.working_capital
        if working_capital is None:
            working_capital = fin.current_assets - fin.current_liabilities

        return {
            # Business profile
            "company_name": bp.company_name,
            "industry": bp.industry,
            "business_type": bp.business_type,
            "years_in_business": bp.years_in_business,
            "employee_count": bp.employee_count,
            "head_office": bp.head_office,
            "country": bp.country,
            "registration_number": bp.registration_number,
            "gst_number": bp.gst_number,
            "website": bp.website,
            # Financials
            "annual_revenue": fin.annual_revenue,
            "gross_profit": fin.gross_profit,
            "net_profit": fin.net_profit,
            "ebitda": fin.ebitda,
            "operating_expenses": fin.operating_expenses,
            "cash_and_cash_equivalents": fin.cash_and_cash_equivalents,
            "current_assets": fin.current_assets,
            "current_liabilities": fin.current_liabilities,
            "inventory": fin.inventory,
            "accounts_receivable": fin.accounts_receivable,
            "accounts_payable": fin.accounts_payable,
            "long_term_debt": fin.long_term_debt,
            "short_term_debt": fin.short_term_debt,
            "operating_cash_flow": fin.operating_cash_flow,
            "working_capital": working_capital,
            "interest_expense": fin.interest_expense,
            "free_cash_flow": fin.free_cash_flow,
            "net_worth": fin.net_worth,
            # Banking
            "average_monthly_balance": bank.average_monthly_balance,
            "average_monthly_inflow": bank.average_monthly_inflow,
            "average_monthly_outflow": bank.average_monthly_outflow,
            "existing_bank_loans": bank.existing_loans,
            "existing_emi": bank.existing_emi,
            "credit_utilization": bank.credit_utilization,
            "tax_compliance": bank.tax_compliance,
            "gst_compliance": bank.gst_compliance,
            "cheque_bounce_count": bank.cheque_bounce_count,
            "previous_defaults": bank.previous_defaults,
            # Risk
            "industry_risk": risk.industry_risk,
            "geographical_risk": risk.geographical_risk,
            "supplier_concentration": risk.supplier_concentration,
            "customer_concentration": risk.customer_concentration,
            "business_expansion_stage": risk.business_expansion_stage,
        }


# ---------------------------------------------------------------------------
# Result models
# ---------------------------------------------------------------------------

class HealthScore(BaseModel):
    """A 0-100 dimension score with a human label and one-line rationale."""

    score: int = Field(ge=0, le=100)
    label: str
    rationale: str


class HealthMetrics(BaseModel):
    liquidity_health: HealthScore
    debt_health: HealthScore
    working_capital_health: HealthScore
    business_stability: HealthScore


class RiskMetrics(BaseModel):
    probability_of_default: float
    loss_given_default: float
    expected_loss: float


class Recommendation(BaseModel):
    decision: str
    loan_recommendation: str
    interest_rate_recommendation: str
    loan_tenure_recommendation: str
    collateral_recommendation: str
    monitoring: str


class PredictionSummary(BaseModel):
    enterprise_credit_score: int
    risk_grade: str
    probability_of_default: float
    recommended_loan_amount: float
    recommended_interest_rate: float


class EnterpriseAssessmentResult(BaseModel):
    summary: PredictionSummary
    risk_metrics: RiskMetrics
    health_metrics: HealthMetrics
    recommendation: Recommendation
    key_ratios: dict[str, float]
    narrative: str

    # --- Backward-compatible flat fields (consumed by legacy callers) ---
    enterprise_credit_score: int
    probability_of_default: float
    loss_given_default: float
    expected_loss: float
    risk_rating: str
    loan_recommendation: str
    interest_rate_recommendation: str
    loan_tenure_recommendation: str
    collateral_recommendation: str
    ai_analysis: str
    explanations: dict[str, float]
