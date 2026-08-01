"""Financial Ratio Engine (Task 1).

Computes 20 commercial-lending ratios from a :class:`FinancialStatement`. Every
ratio is returned as a :class:`Ratio` carrying ``value``, ``formula``
``interpretation``, ``ideal_range`` and a five-tier ``status`` — the exact
contract the phase brief specifies.

Design notes
------------
* Missing or undefined ratios (e.g. division by a zero/absent denominator)
  surface ``value=None`` and ``status="unavailable"`` rather than a fabricated
  number (Task 12).
* A handful of ratios have finance-specific edge cases handled explicitly
  zero interest expense / zero debt service means *no* obligation to cover
  (excellent, not "unavailable"), and equity-based ratios are suppressed when
  equity is non-positive (the negative-equity condition is raised separately by
  the risk-flag engine).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Sequence, Tuple

from .primitives import (
    EXCELLENT,
    UNAVAILABLE,
    Number,
    divide,
    status_from_thresholds,
)
from .statement import FinancialStatement

# Ratio categories (align with the health engine's dimensions).
LIQUIDITY = "liquidity"
LEVERAGE = "leverage"
PROFITABILITY = "profitability"
EFFICIENCY = "efficiency"
CASH_FLOW = "cash_flow"

# Units drive frontend formatting.
UNIT_RATIO = "ratio"        # e.g. 1.85x
UNIT_PERCENT = "percent"    # value stored as a fraction (0.18 -> 18%)
UNIT_CURRENCY = "currency"
UNIT_DAYS = "days"


@dataclass
class Ratio:
    key: str
    label: str
    category: str
    unit: str
    value: Number
    formula: str
    ideal_range: str
    status: str
    interpretation: str

    def as_dict(self) -> dict:
        return {
            "key": self.key,
            "label": self.label,
            "category": self.category,
            "unit": self.unit,
            "value": None if self.value is None else round(self.value, 4),
            "formula": self.formula,
            "ideal_range": self.ideal_range,
            "status": self.status,
            "interpretation": self.interpretation,
        }


@dataclass(frozen=True)
class RatioSpec:
    key: str
    label: str
    category: str
    unit: str
    formula: str
    ideal_range: str
    meaning: str
    compute: Callable[[FinancialStatement], Number]
    # Either threshold-based grading, or a custom status function.
    thresholds: Optional[Sequence[Tuple[float, str]]] = None
    higher_is_better: bool = True
    status_fn: Optional[Callable[[Number, FinancialStatement], str]] = None


def _fmt(value: Number, unit: str) -> str:
    if value is None:
        return "unavailable"
    if unit == UNIT_RATIO:
        return f"{value:.2f}x"
    if unit == UNIT_PERCENT:
        return f"{value * 100:.1f}%"
    if unit == UNIT_DAYS:
        return f"{value:.0f} days"
    return f"{value:,.0f}"


_STATUS_CLAUSE = {
    EXCELLENT: "This is excellent and well within a healthy range",
    "good": "This is healthy",
    "moderate": "This is moderate and worth monitoring",
    "weak": "This is weak and a potential concern",
    "critical": "This is critical and a clear red flag",
    UNAVAILABLE: "There is not enough data to assess this metric",
}


def _sign_status(value: Number, _s: FinancialStatement) -> str:
    if value is None:
        return UNAVAILABLE
    if value > 0:
        return "good"
    if value == 0:
        return "weak"
    return "critical"


def _coverage_status(
    coverage: Number,
    obligation: Number,
    earnings: Number,
    thresholds: Sequence[Tuple[float, str]],
) -> str:
    # No obligation to service + positive earnings => nothing to cover.
    if (obligation == 0 or obligation is None) and earnings is not None and earnings > 0:
        return EXCELLENT
    return status_from_thresholds(coverage, thresholds, higher_is_better=True)


def _equity_guarded(numerator: Number, equity: Number) -> Number:
    """Equity-based ratio; undefined (None) when equity is non-positive so a
    negative denominator can't masquerade as a strong score."""
    if equity is None or equity <= 0:
        return None
    return divide(numerator, equity)


# ---------------------------------------------------------------------------
# Ratio catalogue
# ---------------------------------------------------------------------------

def _catalogue() -> List[RatioSpec]:
    return [
        # -- Liquidity ---------------------------------------------------
        RatioSpec(
            "current_ratio", "Current Ratio", LIQUIDITY, UNIT_RATIO,
            "Current Assets / Current Liabilities", "1.5x – 3.0x",
            "Measures the ability to cover short-term obligations with short-term assets.",
            lambda s: divide(s.current_assets, s.current_liabilities),
            [(2.0, EXCELLENT), (1.5, "good"), (1.0, "moderate"), (0.8, "weak"), (0, "critical")],
        ),
        RatioSpec(
            "quick_ratio", "Quick Ratio", LIQUIDITY, UNIT_RATIO,
            "(Current Assets − Inventory) / Current Liabilities", "≥ 1.0x",
            "Liquidity excluding inventory — the acid test of short-term solvency.",
            lambda s: divide(
                None if s.current_assets is None else s.current_assets - (s.inventory or 0),
                s.current_liabilities,
            ),
            [(1.5, EXCELLENT), (1.0, "good"), (0.8, "moderate"), (0.5, "weak"), (0, "critical")],
        ),
        RatioSpec(
            "cash_ratio", "Cash Ratio", LIQUIDITY, UNIT_RATIO,
            "Cash & Equivalents / Current Liabilities", "0.2x – 0.5x",
            "The most conservative liquidity test — coverage from cash alone.",
            lambda s: divide(s.cash, s.current_liabilities),
            [(0.5, EXCELLENT), (0.2, "good"), (0.1, "moderate"), (0.05, "weak"), (0, "critical")],
        ),
        RatioSpec(
            "working_capital", "Working Capital", LIQUIDITY, UNIT_CURRENCY,
            "Current Assets − Current Liabilities", "Positive and growing",
            "The absolute short-term liquidity cushion funding day-to-day operations.",
            lambda s: s.working_capital,
            status_fn=_sign_status,
        ),
        # -- Leverage ----------------------------------------------------
        RatioSpec(
            "debt_to_equity", "Debt-to-Equity", LEVERAGE, UNIT_RATIO,
            "Total Debt / Total Equity", "< 1.0x (≤ 2.0x acceptable)",
            "How much the business is financed by debt versus owners' capital.",
            lambda s: _equity_guarded(s.total_debt, s.total_equity),
            [(0.5, EXCELLENT), (1.0, "good"), (2.0, "moderate"), (3.0, "weak"), (0, "critical")],
            higher_is_better=False,
        ),
        RatioSpec(
            "debt_ratio", "Debt Ratio", LEVERAGE, UNIT_RATIO,
            "Total Debt / Total Assets", "< 0.5x",
            "The share of assets funded by debt — overall balance-sheet leverage.",
            lambda s: divide(s.total_debt, s.effective_total_assets),
            [(0.3, EXCELLENT), (0.5, "good"), (0.6, "moderate"), (0.8, "weak"), (0, "critical")],
            higher_is_better=False,
        ),
        RatioSpec(
            "interest_coverage", "Interest Coverage", LEVERAGE, UNIT_RATIO,
            "EBIT / Interest Expense", "≥ 3.0x",
            "How comfortably operating earnings cover interest costs.",
            lambda s: divide(s.ebit, s.interest_expense),
            [(8.0, EXCELLENT), (4.0, "good"), (2.0, "moderate"), (1.0, "weak"), (0, "critical")],
            status_fn=lambda v, s: _coverage_status(
                v, s.interest_expense, s.ebit,
                [(8.0, EXCELLENT), (4.0, "good"), (2.0, "moderate"), (1.0, "weak"), (0, "critical")],
            ),
        ),
        RatioSpec(
            "dscr", "Debt Service Coverage (DSCR)", LEVERAGE, UNIT_RATIO,
            "EBITDA / Annual Debt Service", "≥ 1.25x",
            "The single most important lending metric — cash earnings against total debt service.",
            lambda s: divide(s.ebitda, s.annual_debt_service),
            [(2.0, EXCELLENT), (1.5, "good"), (1.25, "moderate"), (1.0, "weak"), (0, "critical")],
            status_fn=lambda v, s: _coverage_status(
                v, s.annual_debt_service, s.ebitda,
                [(2.0, EXCELLENT), (1.5, "good"), (1.25, "moderate"), (1.0, "weak"), (0, "critical")],
            ),
        ),
        # -- Profitability ----------------------------------------------
        RatioSpec(
            "gross_margin", "Gross Profit Margin", PROFITABILITY, UNIT_PERCENT,
            "Gross Profit / Revenue", "Industry-dependent; higher is better",
            "Profit left after direct cost of goods, before overheads.",
            lambda s: divide(s.gross_profit_value, s.revenue),
            [(0.40, EXCELLENT), (0.25, "good"), (0.15, "moderate"), (0.05, "weak"), (0, "critical")],
        ),
        RatioSpec(
            "operating_margin", "Operating Margin", PROFITABILITY, UNIT_PERCENT,
            "Operating Income (EBIT) / Revenue", "≥ 10%",
            "Core operating profitability before financing and tax.",
            lambda s: divide(s.ebit, s.revenue),
            [(0.20, EXCELLENT), (0.12, "good"), (0.06, "moderate"), (0.0, "weak"), (-1, "critical")],
        ),
        RatioSpec(
            "ebitda_margin", "EBITDA Margin", PROFITABILITY, UNIT_PERCENT,
            "EBITDA / Revenue", "≥ 15%",
            "Cash operating profitability, independent of capital structure.",
            lambda s: divide(s.ebitda, s.revenue),
            [(0.25, EXCELLENT), (0.15, "good"), (0.08, "moderate"), (0.0, "weak"), (-1, "critical")],
        ),
        RatioSpec(
            "net_margin", "Net Profit Margin", PROFITABILITY, UNIT_PERCENT,
            "Net Profit / Revenue", "≥ 8%",
            "Bottom-line profit retained from every unit of revenue.",
            lambda s: divide(s.net_profit, s.revenue),
            [(0.15, EXCELLENT), (0.08, "good"), (0.03, "moderate"), (0.0, "weak"), (-1, "critical")],
        ),
        RatioSpec(
            "return_on_assets", "Return on Assets (ROA)", PROFITABILITY, UNIT_PERCENT,
            "Net Profit / Total Assets", "≥ 5%",
            "How efficiently the asset base generates profit.",
            lambda s: divide(s.net_profit, s.effective_total_assets),
            [(0.10, EXCELLENT), (0.05, "good"), (0.02, "moderate"), (0.0, "weak"), (-1, "critical")],
        ),
        RatioSpec(
            "return_on_equity", "Return on Equity (ROE)", PROFITABILITY, UNIT_PERCENT,
            "Net Profit / Total Equity", "≥ 12%",
            "The return generated on owners' capital.",
            lambda s: _equity_guarded(s.net_profit, s.total_equity),
            [(0.18, EXCELLENT), (0.12, "good"), (0.06, "moderate"), (0.0, "weak"), (-1, "critical")],
        ),
        # -- Efficiency --------------------------------------------------
        RatioSpec(
            "asset_turnover", "Asset Turnover", EFFICIENCY, UNIT_RATIO,
            "Revenue / Total Assets", "≥ 1.0x",
            "Revenue generated per unit of assets — asset productivity.",
            lambda s: divide(s.revenue, s.effective_total_assets),
            [(1.5, EXCELLENT), (1.0, "good"), (0.6, "moderate"), (0.3, "weak"), (0, "critical")],
        ),
        RatioSpec(
            "inventory_turnover", "Inventory Turnover", EFFICIENCY, UNIT_RATIO,
            "COGS / Inventory", "≥ 5x (industry-dependent)",
            "How many times inventory is sold and replaced in the period.",
            lambda s: divide(s.cost_of_goods_sold, s.inventory),
            [(8.0, EXCELLENT), (5.0, "good"), (3.0, "moderate"), (1.0, "weak"), (0, "critical")],
        ),
        RatioSpec(
            "receivable_turnover", "Receivable Turnover", EFFICIENCY, UNIT_RATIO,
            "Revenue / Accounts Receivable", "≥ 8x",
            "How efficiently the business collects on credit sales.",
            lambda s: divide(s.revenue, s.accounts_receivable),
            [(12.0, EXCELLENT), (8.0, "good"), (5.0, "moderate"), (3.0, "weak"), (0, "critical")],
        ),
        RatioSpec(
            "payable_turnover", "Payable Turnover", EFFICIENCY, UNIT_RATIO,
            "COGS / Accounts Payable", "4x – 12x",
            "How quickly the business pays its suppliers.",
            lambda s: divide(s.cost_of_goods_sold, s.accounts_payable),
            [(12.0, EXCELLENT), (8.0, "good"), (5.0, "moderate"), (3.0, "weak"), (0, "critical")],
        ),
        # -- Cash flow ---------------------------------------------------
        RatioSpec(
            "operating_cash_flow_ratio", "Operating Cash Flow Ratio", CASH_FLOW, UNIT_RATIO,
            "Operating Cash Flow / Current Liabilities", "≥ 1.0x",
            "Whether operations alone generate enough cash to cover short-term liabilities.",
            lambda s: divide(s.operating_cash_flow, s.current_liabilities),
            [(1.0, EXCELLENT), (0.6, "good"), (0.4, "moderate"), (0.2, "weak"), (-1, "critical")],
        ),
        RatioSpec(
            "free_cash_flow", "Free Cash Flow", CASH_FLOW, UNIT_CURRENCY,
            "Operating Cash Flow − Capital Expenditure", "Positive",
            "Cash left after reinvestment — the true capacity to service and repay debt.",
            lambda s: s.free_cash_flow_value,
            status_fn=_sign_status,
        ),
    ]


_CATALOGUE = _catalogue()


def _grade(spec: RatioSpec, value: Number, statement: FinancialStatement) -> str:
    if spec.status_fn is not None:
        return spec.status_fn(value, statement)
    if spec.thresholds is not None:
        return status_from_thresholds(value, spec.thresholds, spec.higher_is_better)
    return UNAVAILABLE


def _interpret(spec: RatioSpec, value: Number, status: str, unit: str) -> str:
    return (
        f"{spec.meaning} At {_fmt(value, unit)}, {_STATUS_CLAUSE[status].lower()} "
        f"(ideal: {spec.ideal_range})."
    )


def compute_ratio(spec: RatioSpec, statement: FinancialStatement) -> Ratio:
    value = spec.compute(statement)
    status = _grade(spec, value, statement)
    return Ratio(
        key=spec.key,
        label=spec.label,
        category=spec.category,
        unit=spec.unit,
        value=value,
        formula=spec.formula,
        ideal_range=spec.ideal_range,
        status=status,
        interpretation=_interpret(spec, value, status, spec.unit),
    )


def compute_ratios(statement: FinancialStatement) -> List[Ratio]:
    """Compute all 20 ratios, preserving catalogue order."""
    return [compute_ratio(spec, statement) for spec in _CATALOGUE]


def ratios_by_key(statement: FinancialStatement) -> Dict[str, Ratio]:
    return {r.key: r for r in compute_ratios(statement)}


def ratios_by_category(ratios: Sequence[Ratio]) -> Dict[str, List[Ratio]]:
    grouped: Dict[str, List[Ratio]] = {}
    for ratio in ratios:
        grouped.setdefault(ratio.category, []).append(ratio)
    return grouped
