"""Provider interface + neutral transfer objects.

The dataclasses below are the contract between a provider and the persistence
layer. They are intentionally plain (no ORM coupling) so a provider can be a
synthetic generator, a public-data adapter, or a bank/bureau connector without
any of them knowing how the data is stored.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional


# ---------------------------------------------------------------------------
# Transfer objects
# ---------------------------------------------------------------------------
@dataclass
class CompanyProfile:
    """Identity + firmographics for one company."""

    external_id: str
    name: str
    legal_name: str
    industry: str
    sector: str
    country: str
    region: str
    incorporation_year: int
    employee_count: int
    annual_revenue: float
    business_status: str
    gstin: Optional[str] = None
    pan: Optional[str] = None
    cin: Optional[str] = None


@dataclass
class FinancialStatement:
    """One fiscal-year statement. Values are internally consistent."""

    fiscal_year: int
    revenue: float
    ebitda: float
    ebit: float
    net_income: float
    operating_margin: float
    net_margin: float
    total_assets: float
    total_liabilities: float
    equity: float
    current_assets: float
    current_liabilities: float
    cash: float
    debt: float
    working_capital: float
    operating_cash_flow: float
    free_cash_flow: float


@dataclass
class CreditAssessment:
    """Risk metrics + recommended credit terms for a company."""

    credit_score: int
    probability_of_default: float
    risk_grade: str
    expected_loss: float
    debt_to_equity: float
    current_ratio: float
    quick_ratio: float
    interest_coverage: float
    dscr: float
    leverage: float
    liquidity_score: float
    requested_loan_amount: float
    recommended_loan_amount: float
    interest_rate: float
    collateral_value: float
    loan_tenure_months: int
    repayment_history: str
    approval_status: str


@dataclass
class PortfolioPosition:
    """A company's exposure within the portfolio book."""

    exposure: float
    outstanding_amount: float
    utilization: float
    repayment_performance: float
    delinquency_days: int
    is_delinquent: bool
    sector_classification: str


@dataclass
class CompanyRecord:
    """Everything a provider yields for a single company."""

    profile: CompanyProfile
    financials: List[FinancialStatement] = field(default_factory=list)
    credit: Optional[CreditAssessment] = None
    portfolio: Optional[PortfolioPosition] = None


# ---------------------------------------------------------------------------
# Interfaces
# ---------------------------------------------------------------------------
class CompanyDataProvider(ABC):
    """Yields company identity + firmographics."""

    @abstractmethod
    def list_companies(self, count: int) -> List[CompanyProfile]:
        ...


class FinancialDataProvider(ABC):
    """Yields financial statements for a company (time-series)."""

    @abstractmethod
    def financials_for(self, profile: CompanyProfile, *, years: int = 3) -> List[FinancialStatement]:
        ...


class CreditDataProvider(ABC):
    """Yields risk metrics + credit terms derived from a company's financials."""

    @abstractmethod
    def credit_for(
        self, profile: CompanyProfile, financials: List[FinancialStatement]
    ) -> CreditAssessment:
        ...


class PortfolioDataProvider(ABC):
    """Yields the company's exposure/position in the book."""

    @abstractmethod
    def portfolio_for(
        self, profile: CompanyProfile, credit: CreditAssessment
    ) -> PortfolioPosition:
        ...


class DataProvider(
    CompanyDataProvider,
    FinancialDataProvider,
    CreditDataProvider,
    PortfolioDataProvider,
    ABC,
):
    """A complete source of portfolio data.

    Composes the four capability interfaces. :meth:`generate` is a provided
    convenience that stitches them into whole :class:`CompanyRecord` objects;
    subclasses only implement the four ``@abstractmethod`` hooks above.
    """

    #: Stable provider name, matched against the ``DATA_PROVIDER`` setting.
    name: str = "base"

    #: True when the data is synthetic/sample data (drives UI "Demo Data"
    #: labelling and the ``companies.is_demo`` column).
    is_synthetic: bool = True

    def generate(self, count: int, *, years: int = 3) -> List[CompanyRecord]:
        records: List[CompanyRecord] = []
        for profile in self.list_companies(count):
            financials = self.financials_for(profile, years=years)
            credit = self.credit_for(profile, financials)
            portfolio = self.portfolio_for(profile, credit)
            records.append(
                CompanyRecord(
                    profile=profile,
                    financials=financials,
                    credit=credit,
                    portfolio=portfolio,
                )
            )
        return records
