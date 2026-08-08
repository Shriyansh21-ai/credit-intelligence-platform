"""Synthetic ("demo") data provider.

Generates realistic-but-clearly-synthetic companies across a broad spread of
industries, with **internally consistent** financials, ratios and risk metrics:

* revenue > EBITDA > EBIT (positive operations)
* total assets == total liabilities + equity (balance sheet reconciles)
* every ratio (D/E, current, quick, interest-coverage, DSCR, leverage) is
  derived from the underlying statement, never hardcoded independently
* expected loss == PD x LGD x exposure

Generation is deterministic (seeded from a stable hash of the company index),
so the same seed run always yields the same book — idempotent seeding and
reproducible tests/demos. Company names are fictional; the accompanying
``is_demo`` flag and ``data_source`` marker keep these plainly distinguishable
from real financial records.
"""

from __future__ import annotations

from datetime import date
from typing import List

from backend.app.services.integrations.mockdata import (
    make_cin,
    make_gstin,
    make_pan,
    rng_for,
)
from backend.app.services.providers.base import (
    CompanyProfile,
    CreditAssessment,
    DataProvider,
    FinancialStatement,
    PortfolioPosition,
)

_CRORE = 10_000_000.0  # 1 crore in rupees


# (industry, sector, rev_lo_cr, rev_hi_cr, ebitda_lo, ebitda_hi, asset_intensity,
#  lev_lo, lev_hi)  — ranges chosen to look plausible per industry.
_INDUSTRIES = [
    ("Banking", "Financials", 400, 6000, 0.30, 0.45, 1.6, 2.5, 5.0),
    ("Financial Services", "Financials", 150, 3000, 0.25, 0.40, 1.4, 2.0, 4.5),
    ("FinTech", "Financials", 40, 1200, 0.10, 0.30, 0.9, 1.0, 3.0),
    ("Information Technology", "Technology", 200, 5000, 0.18, 0.28, 0.8, 0.3, 1.5),
    ("SaaS", "Technology", 30, 1500, 0.12, 0.32, 0.7, 0.4, 2.0),
    ("Manufacturing", "Industrials", 150, 4000, 0.12, 0.20, 1.3, 1.5, 3.5),
    ("Automotive", "Consumer Discretionary", 300, 6000, 0.10, 0.18, 1.4, 1.8, 3.8),
    ("Healthcare", "Health Care", 100, 3000, 0.15, 0.25, 1.2, 1.0, 2.8),
    ("Pharmaceuticals", "Health Care", 150, 4500, 0.18, 0.30, 1.3, 1.0, 3.0),
    ("Retail", "Consumer Staples", 100, 4000, 0.06, 0.14, 1.0, 1.5, 3.5),
    ("E-commerce", "Consumer Discretionary", 80, 3500, 0.05, 0.15, 0.9, 1.2, 3.2),
    ("Logistics", "Industrials", 80, 2500, 0.10, 0.20, 1.5, 1.8, 4.0),
    ("Energy", "Energy", 500, 9000, 0.15, 0.30, 1.8, 2.0, 4.5),
    ("Telecommunications", "Communication Services", 400, 7000, 0.25, 0.40, 2.0, 2.5, 5.5),
    ("Construction", "Industrials", 120, 3500, 0.08, 0.16, 1.3, 2.0, 4.2),
    ("Real Estate", "Real Estate", 100, 4000, 0.20, 0.40, 2.2, 2.5, 5.5),
    ("FMCG", "Consumer Staples", 200, 5000, 0.12, 0.22, 0.9, 0.8, 2.5),
    ("Agriculture", "Consumer Staples", 50, 1800, 0.08, 0.18, 1.2, 1.5, 3.5),
    ("Infrastructure", "Industrials", 300, 8000, 0.15, 0.28, 2.0, 2.5, 5.0),
]

_NAME_A = ["North", "South", "Peak", "Blue", "Ever", "Prime", "Vertex",
           "Zenith", "Apex", "Meridian"]
_NAME_B = ["wind", "field", "stone", "bridge", "gate", "haven", "crest",
           "forge", "spring", "ridge"]
_INDUSTRY_WORD = {
    "Banking": "Financial", "Financial Services": "Capital", "FinTech": "Pay",
    "Information Technology": "Systems", "SaaS": "Cloud",
    "Manufacturing": "Industries", "Automotive": "Motors", "Healthcare": "Health",
    "Pharmaceuticals": "Pharma", "Retail": "Retail", "E-commerce": "Commerce",
    "Logistics": "Logistics", "Energy": "Energy", "Telecommunications": "Telecom",
    "Construction": "Infra", "Real Estate": "Estates", "FMCG": "Consumer",
    "Agriculture": "Agro", "Infrastructure": "Infra",
}
_SUFFIXES = ["Ltd", "Pvt Ltd", "Corp", "Group", "Holdings"]
_REGIONS = ["Maharashtra", "Karnataka", "Delhi NCR", "Tamil Nadu", "Gujarat",
            "Telangana", "West Bengal", "Uttar Pradesh"]

# Credit-score band -> (grade, LGD). Higher score = safer.
_GRADE_BANDS = [
    (820, "AAA", 0.20), (780, "AA", 0.25), (740, "A", 0.30),
    (700, "BBB", 0.35), (660, "BB", 0.40), (620, "B", 0.45),
    (560, "CCC", 0.55), (0, "D", 0.65),
]


def _grade_and_lgd(score: int):
    for threshold, grade, lgd in _GRADE_BANDS:
        if score >= threshold:
            return grade, lgd
    return "D", 0.65


class DemoDataProvider(DataProvider):
    """Deterministic synthetic provider (the default)."""

    name = "demo"
    is_synthetic = True

    # ------------------------------------------------------------------ companies
    def list_companies(self, count: int) -> List[CompanyProfile]:
        count = max(1, min(int(count), 200))
        out: List[CompanyProfile] = []
        for i in range(count):
            out.append(self._profile(i))
        return out

    def _profile(self, i: int) -> CompanyProfile:
        rng = rng_for("demo-company", str(i))
        industry, sector, rev_lo, rev_hi, *_ = _INDUSTRIES[i % len(_INDUSTRIES)]
        revenue = round(rng.uniform(rev_lo, rev_hi) * _CRORE, 2)

        base = _NAME_A[(i // len(_NAME_B)) % len(_NAME_A)] + _NAME_B[i % len(_NAME_B)]
        name = f"{base} {_INDUSTRY_WORD[industry]} {rng.choice(_SUFFIXES)}"
        # Employee count scales with revenue but varies by labour intensity.
        emp = int(max(25, revenue / _CRORE * rng.uniform(3, 12)))
        return CompanyProfile(
            external_id=f"DEMO-{i:04d}",
            name=name,
            legal_name=f"{name}.",
            industry=industry,
            sector=sector,
            country="India",
            region=rng.choice(_REGIONS),
            incorporation_year=rng.randint(1985, 2020),
            employee_count=emp,
            annual_revenue=revenue,
            business_status="Active",
            gstin=make_gstin(rng),
            pan=make_pan(rng),
            cin=make_cin(rng),
        )

    # ---------------------------------------------------------------- financials
    def financials_for(
        self, profile: CompanyProfile, *, years: int = 3
    ) -> List[FinancialStatement]:
        rng = rng_for("demo-fin", profile.external_id)
        _, _, _, _, eb_lo, eb_hi, asset_intensity, lev_lo, lev_hi = _INDUSTRIES[
            self._industry_index(profile.industry)
        ]
        ebitda_margin = rng.uniform(eb_lo, eb_hi)
        leverage = rng.uniform(lev_lo, lev_hi)  # debt / EBITDA
        growth = rng.uniform(0.04, 0.18)  # YoY growth (latest highest)

        end_year = date.today().year - 1
        statements: List[FinancialStatement] = []
        for offset in range(years - 1, -1, -1):
            fy = end_year - offset
            # Scale earlier years down by compounding growth.
            scale = (1 + growth) ** (-offset)
            revenue = round(profile.annual_revenue * scale, 2)
            statements.append(
                self._statement(fy, revenue, ebitda_margin, leverage, asset_intensity, rng)
            )
        return statements

    def _statement(
        self,
        fy: int,
        revenue: float,
        ebitda_margin: float,
        leverage: float,
        asset_intensity: float,
        rng,
    ) -> FinancialStatement:
        ebitda = revenue * ebitda_margin
        depreciation = ebitda * rng.uniform(0.15, 0.30)
        ebit = ebitda - depreciation  # ebitda > ebit

        total_assets = revenue * asset_intensity
        debt = min(ebitda * leverage, total_assets * 0.7)
        interest = debt * rng.uniform(0.08, 0.12)

        pretax = ebit - interest
        tax = max(0.0, pretax) * 0.25
        net_income = pretax - tax

        current_ratio_target = rng.uniform(1.1, 2.4)
        current_liabilities = total_assets * rng.uniform(0.18, 0.32)
        current_assets = current_liabilities * current_ratio_target
        # Keep current assets within total assets.
        current_assets = min(current_assets, total_assets * 0.85)
        cash = current_assets * rng.uniform(0.12, 0.30)
        working_capital = current_assets - current_liabilities

        # Non-current liabilities = long-term portion of debt; total liabilities
        # combine current liabilities and long-term debt, then equity balances.
        long_term_debt = max(0.0, debt - current_liabilities * 0.3)
        total_liabilities = current_liabilities + long_term_debt
        total_liabilities = min(total_liabilities, total_assets * 0.9)
        equity = total_assets - total_liabilities  # balance sheet reconciles

        operating_cash_flow = ebitda * rng.uniform(0.6, 0.9) - tax
        capex = revenue * rng.uniform(0.03, 0.09)
        free_cash_flow = operating_cash_flow - capex

        return FinancialStatement(
            fiscal_year=fy,
            revenue=round(revenue, 2),
            ebitda=round(ebitda, 2),
            ebit=round(ebit, 2),
            net_income=round(net_income, 2),
            operating_margin=round(ebit / revenue, 4) if revenue else 0.0,
            net_margin=round(net_income / revenue, 4) if revenue else 0.0,
            total_assets=round(total_assets, 2),
            total_liabilities=round(total_liabilities, 2),
            equity=round(equity, 2),
            current_assets=round(current_assets, 2),
            current_liabilities=round(current_liabilities, 2),
            cash=round(cash, 2),
            debt=round(debt, 2),
            working_capital=round(working_capital, 2),
            operating_cash_flow=round(operating_cash_flow, 2),
            free_cash_flow=round(free_cash_flow, 2),
        )

    # -------------------------------------------------------------------- credit
    def credit_for(
        self, profile: CompanyProfile, financials: List[FinancialStatement]
    ) -> CreditAssessment:
        rng = rng_for("demo-credit", profile.external_id)
        latest = financials[-1]

        equity = latest.equity if latest.equity > 0 else max(1.0, latest.total_assets * 0.05)
        debt_to_equity = latest.debt / equity
        current_ratio = (
            latest.current_assets / latest.current_liabilities
            if latest.current_liabilities
            else 0.0
        )
        quick_ratio = (
            (latest.current_assets - (latest.current_assets - latest.cash) * 0.4)
            / latest.current_liabilities
            if latest.current_liabilities
            else 0.0
        )
        interest = latest.debt * 0.10
        interest_coverage = latest.ebit / interest if interest else 20.0
        # Debt service = interest + a modest principal amortization slice.
        debt_service = interest + latest.debt * 0.05
        dscr = latest.operating_cash_flow / debt_service if debt_service else 2.0
        leverage = latest.debt / latest.ebitda if latest.ebitda else 8.0
        liquidity_score = round(max(0.0, min(100.0, (current_ratio - 0.5) * 45)), 1)

        def clamp(x, lo, hi):
            return max(lo, min(hi, x))

        # Composite credit score (300-900): a weighted blend of normalized
        # sub-signals so a healthy firm lands investment-grade and a stressed
        # one lands speculative — producing a realistic, favourably-skewed book.
        profitability = clamp(latest.net_margin / 0.12, 0.0, 1.0)
        solvency = clamp((4.0 - debt_to_equity) / 3.0, 0.0, 1.0)
        liquidity = clamp((current_ratio - 1.0) / 1.0, 0.0, 1.0)
        coverage = clamp((interest_coverage - 1.0) / 5.0, 0.0, 1.0)
        service = clamp((dscr - 0.8) / 0.7, 0.0, 1.0)
        health = (
            0.25 * profitability
            + 0.20 * solvency
            + 0.20 * liquidity
            + 0.175 * coverage
            + 0.175 * service
        )
        # A mild convex curve widens the spread so the book spans investment
        # grade down to a speculative tail (a few rejections), rather than
        # clustering in the middle.
        score = 315 + (health ** 1.25) * 585
        credit_score = int(clamp(round(score + rng.uniform(-35, 35)), 300, 900))
        grade, lgd = _grade_and_lgd(credit_score)

        # PD falls as score rises (roughly 0.5% .. 30%).
        pd = round(clamp(0.32 - (credit_score - 300) / 600 * 0.31, 0.004, 0.35), 4)

        requested = round(latest.revenue * rng.uniform(0.15, 0.45), 2)
        # Risk-adjusted sizing: safer names get closer to their ask.
        approval_factor = clamp((credit_score - 560) / 340, 0.0, 1.0)
        recommended = round(requested * (0.35 + 0.6 * approval_factor), 2)
        exposure = recommended
        expected_loss = round(pd * lgd * exposure, 2)
        interest_rate = round(9.0 + (1 - approval_factor) * 9.0 + rng.uniform(-0.5, 0.5), 2)
        collateral = round(recommended * rng.uniform(0.8, 1.6), 2)
        tenure = rng.choice([12, 24, 36, 48, 60, 84])

        if credit_score >= 700:
            status, repayment = "approved", "excellent"
        elif credit_score >= 620:
            status, repayment = "approved", "good"
        elif credit_score >= 560:
            status, repayment = "under_review", "fair"
        else:
            status, repayment = "rejected", "poor"

        return CreditAssessment(
            credit_score=credit_score,
            probability_of_default=pd,
            risk_grade=grade,
            expected_loss=expected_loss,
            debt_to_equity=round(debt_to_equity, 3),
            current_ratio=round(current_ratio, 3),
            quick_ratio=round(quick_ratio, 3),
            interest_coverage=round(interest_coverage, 3),
            dscr=round(dscr, 3),
            leverage=round(leverage, 3),
            liquidity_score=liquidity_score,
            requested_loan_amount=requested,
            recommended_loan_amount=recommended,
            interest_rate=interest_rate,
            collateral_value=collateral,
            loan_tenure_months=tenure,
            repayment_history=repayment,
            approval_status=status,
        )

    # ----------------------------------------------------------------- portfolio
    def portfolio_for(
        self, profile: CompanyProfile, credit: CreditAssessment
    ) -> PortfolioPosition:
        rng = rng_for("demo-portfolio", profile.external_id)
        exposure = credit.recommended_loan_amount
        utilization = round(rng.uniform(0.35, 0.95), 3)
        outstanding = round(exposure * utilization, 2)
        # Weaker credits are likelier to be delinquent.
        risk = 1.0 - max(0.0, min(1.0, (credit.credit_score - 300) / 600))
        delinquency_days = int(rng.uniform(0, 120) * risk)
        is_delinquent = delinquency_days > 30
        repayment_performance = round(max(0.0, 100.0 - risk * 100 - rng.uniform(0, 10)), 1)
        return PortfolioPosition(
            exposure=exposure,
            outstanding_amount=outstanding,
            utilization=utilization,
            repayment_performance=repayment_performance,
            delinquency_days=delinquency_days,
            is_delinquent=is_delinquent,
            sector_classification=profile.sector,
        )

    # ------------------------------------------------------------------ helpers
    @staticmethod
    def _industry_index(industry: str) -> int:
        for idx, row in enumerate(_INDUSTRIES):
            if row[0] == industry:
                return idx
        return 0
