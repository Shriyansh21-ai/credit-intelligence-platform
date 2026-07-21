"""Normalised financial statement + adapters.

:class:`FinancialStatement` is the single input contract for every engine in
this package. It is deliberately source-agnostic: adapters build it from either
the enterprise assessment ``engine_input`` (Phase 1) or from reviewed document
extraction fields (Phase 2). Each numeric field is ``Optional`` so a genuine
``0`` is distinguishable from a *missing* figure — the engines return
"unavailable" for ratios whose inputs are absent instead of inventing values.

A ``period`` (label + type + fiscal year) is carried on every statement so the
same object powers both single-period analysis today and multi-period trend
analysis later, with no schema change.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Mapping, Optional

from .primitives import Number, as_float


@dataclass
class Period:
    """The reporting period a statement covers."""

    label: Optional[str] = None          # e.g. "FY2024", "Q2 2024"
    period_type: str = "annual"          # "annual" | "quarter"
    fiscal_year: Optional[int] = None
    sequence: Optional[int] = None       # monotonic order key for trends

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass
class FinancialStatement:
    """A single period of normalised financials (all monetary, same currency)."""

    # --- Income statement ---
    revenue: Number = None
    cogs: Number = None
    gross_profit: Number = None
    operating_expenses: Number = None
    operating_income: Number = None          # EBIT
    ebitda: Number = None
    depreciation_amortization: Number = None
    interest_expense: Number = None
    tax: Number = None
    net_profit: Number = None

    # --- Balance sheet ---
    cash: Number = None
    inventory: Number = None
    accounts_receivable: Number = None
    accounts_payable: Number = None
    current_assets: Number = None
    current_liabilities: Number = None
    short_term_debt: Number = None
    long_term_debt: Number = None
    total_assets: Number = None
    total_equity: Number = None              # a.k.a. net worth

    # --- Cash flow ---
    operating_cash_flow: Number = None
    free_cash_flow: Number = None
    capital_expenditure: Number = None

    # --- Debt service (for coverage ratios) ---
    annual_debt_principal: Number = None     # scheduled principal repayment / yr
    existing_emi: Number = None              # monthly EMI (annualised below)

    period: Period = field(default_factory=Period)

    # -- Derived accounting relationships --------------------------------

    @property
    def total_debt(self) -> Number:
        parts = [self.short_term_debt, self.long_term_debt]
        present = [p for p in parts if p is not None]
        return sum(present) if present else None

    @property
    def working_capital(self) -> Number:
        if self.current_assets is None or self.current_liabilities is None:
            return None
        return self.current_assets - self.current_liabilities

    @property
    def cost_of_goods_sold(self) -> Number:
        """Explicit COGS, else revenue - gross_profit when both are known."""
        if self.cogs is not None:
            return self.cogs
        if self.revenue is not None and self.gross_profit is not None:
            return self.revenue - self.gross_profit
        return None

    @property
    def gross_profit_value(self) -> Number:
        if self.gross_profit is not None:
            return self.gross_profit
        if self.revenue is not None and self.cogs is not None:
            return self.revenue - self.cogs
        return None

    @property
    def ebit(self) -> Number:
        """Operating income; approximated from EBITDA - D&A when absent."""
        if self.operating_income is not None:
            return self.operating_income
        if self.ebitda is not None and self.depreciation_amortization is not None:
            return self.ebitda - self.depreciation_amortization
        return self.ebitda  # last resort: EBITDA (may be None)

    @property
    def effective_total_assets(self) -> Number:
        """Reported total assets, else the accounting-identity estimate
        (equity + total liabilities). Marked as estimated by callers."""
        if self.total_assets is not None:
            return self.total_assets
        return self.estimated_total_assets

    @property
    def estimated_total_assets(self) -> Number:
        """Assets ≈ equity + current liabilities + long-term debt.

        A transparent proxy for datasets (like the assessment form) that omit a
        full balance sheet. Returns ``None`` unless enough components exist.
        """
        components = [self.total_equity, self.current_liabilities, self.long_term_debt]
        present = [c for c in components if c is not None]
        if not present or self.total_equity is None:
            return None
        return sum(present)

    @property
    def total_assets_is_estimated(self) -> bool:
        return self.total_assets is None and self.estimated_total_assets is not None

    @property
    def annual_debt_service(self) -> Number:
        """Interest + annualised EMI + scheduled principal. ``None`` only when
        no component is known."""
        emi_annual = None if self.existing_emi is None else self.existing_emi * 12.0
        parts = [self.interest_expense, emi_annual, self.annual_debt_principal]
        present = [p for p in parts if p is not None]
        return sum(present) if present else None

    @property
    def free_cash_flow_value(self) -> Number:
        """Reported FCF, else operating cash flow - capex."""
        if self.free_cash_flow is not None:
            return self.free_cash_flow
        if self.operating_cash_flow is not None and self.capital_expenditure is not None:
            return self.operating_cash_flow - self.capital_expenditure
        return None

    def as_dict(self) -> dict:
        """Snapshot including derived fields, for persistence and the API."""
        data = asdict(self)
        data["period"] = self.period.as_dict()
        data["derived"] = {
            "total_debt": self.total_debt,
            "working_capital": self.working_capital,
            "cost_of_goods_sold": self.cost_of_goods_sold,
            "gross_profit": self.gross_profit_value,
            "ebit": self.ebit,
            "effective_total_assets": self.effective_total_assets,
            "total_assets_is_estimated": self.total_assets_is_estimated,
            "annual_debt_service": self.annual_debt_service,
            "free_cash_flow": self.free_cash_flow_value,
        }
        return data


# ---------------------------------------------------------------------------
# Adapters
# ---------------------------------------------------------------------------

def from_engine_input(data: Mapping[str, Any]) -> FinancialStatement:
    """Build a statement from the enterprise assessment ``engine_input`` dict
    (see ``schemas/enterprise.EnterpriseAssessmentRequest.to_engine_input``)."""

    def g(*keys: str) -> Number:
        for key in keys:
            if key in data and data[key] is not None:
                return as_float(data[key])
        return None

    fiscal_year = None
    fy = data.get("financial_year")
    if fy is not None:
        fiscal_year = int(as_float(fy)) if as_float(fy) is not None else None

    return FinancialStatement(
        revenue=g("annual_revenue", "annual_turnover", "revenue"),
        gross_profit=g("gross_profit"),
        operating_expenses=g("operating_expenses"),
        ebitda=g("ebitda"),
        net_profit=g("net_profit"),
        interest_expense=g("interest_expense"),
        cash=g("cash_and_cash_equivalents", "cash"),
        inventory=g("inventory"),
        accounts_receivable=g("accounts_receivable"),
        accounts_payable=g("accounts_payable"),
        current_assets=g("current_assets"),
        current_liabilities=g("current_liabilities"),
        short_term_debt=g("short_term_debt"),
        long_term_debt=g("long_term_debt"),
        total_equity=g("net_worth", "total_equity"),
        operating_cash_flow=g("operating_cash_flow"),
        free_cash_flow=g("free_cash_flow"),
        existing_emi=g("existing_emi"),
        period=Period(
            label=(f"FY{fiscal_year}" if fiscal_year else None),
            period_type="annual",
            fiscal_year=fiscal_year,
        ),
    )


# Map document extraction field keys -> FinancialStatement fields.
_DOCUMENT_FIELD_MAP = {
    "revenue": "revenue",
    "cost_of_goods_sold": "cogs",
    "gross_profit": "gross_profit",
    "operating_expenses": "operating_expenses",
    "ebitda": "ebitda",
    "net_profit": "net_profit",
    "cash": "cash",
    "inventory": "inventory",
    "accounts_receivable": "accounts_receivable",
    "accounts_payable": "accounts_payable",
    "current_assets": "current_assets",
    "current_liabilities": "current_liabilities",
    "short_term_debt": "short_term_debt",
    "long_term_debt": "long_term_debt",
    "operating_cash_flow": "operating_cash_flow",
    "tax_paid": "tax",
}


def from_document_fields(fields: Any) -> FinancialStatement:
    """Build a statement from a ``DocumentExtraction.fields`` payload.

    Accepts either the persisted list of ``{key, value, ...}`` dicts or a plain
    ``{key: value}`` mapping. Values are coerced with :func:`as_float`.
    """
    values: Dict[str, Any] = {}
    if isinstance(fields, Mapping):
        values = dict(fields)
    else:
        for item in fields or []:
            if isinstance(item, Mapping) and "key" in item:
                values[item["key"]] = item.get("value")

    kwargs: Dict[str, Number] = {}
    for src_key, dst_attr in _DOCUMENT_FIELD_MAP.items():
        if src_key in values:
            kwargs[dst_attr] = as_float(values[src_key])

    fiscal_year = None
    raw_year = values.get("financial_year")
    if raw_year is not None:
        import re

        match = re.search(r"(19|20)\d{2}", str(raw_year))
        if match:
            fiscal_year = int(match.group(0))

    statement = FinancialStatement(**kwargs)
    statement.period = Period(
        label=(str(raw_year) if raw_year else (f"FY{fiscal_year}" if fiscal_year else None)),
        period_type="annual",
        fiscal_year=fiscal_year,
    )
    return statement


def from_mapping(data: Mapping[str, Any]) -> FinancialStatement:
    """Build a statement from an arbitrary mapping whose keys already match
    :class:`FinancialStatement` field names (used by ``POST /analysis/compute``)."""
    valid = {f for f in FinancialStatement.__dataclass_fields__ if f != "period"}
    kwargs = {k: as_float(v) for k, v in data.items() if k in valid}
    statement = FinancialStatement(**kwargs)
    period = data.get("period")
    if isinstance(period, Mapping):
        statement.period = Period(
            label=period.get("label"),
            period_type=period.get("period_type", "annual"),
            fiscal_year=period.get("fiscal_year"),
            sequence=period.get("sequence"),
        )
    return statement


def build_statements(periods: List[Mapping[str, Any]]) -> List[FinancialStatement]:
    """Build an ordered list of statements for trend analysis."""
    statements = [from_mapping(p) for p in periods]
    statements.sort(
        key=lambda s: (
            s.period.sequence if s.period.sequence is not None else (s.period.fiscal_year or 0)
        )
    )
    return statements
