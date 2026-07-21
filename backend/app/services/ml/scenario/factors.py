"""Scenario factors — transparent elasticity models.

Each factor is a pure function that mutates a *copy* of an assessment
``engine_input`` to reflect a business shock. The models are deliberately
simple, deterministic and monotonic first-order elasticities (documented per
factor), not black boxes: an analyst can always reason about what a factor did.

Value semantics are per-factor and described in each :class:`ScenarioFactor`
(percent, percentage-points or an absolute currency amount).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, List

# P&L lines that scale (approximately) with revenue at constant margins.
_REVENUE_LINKED = (
    "annual_revenue", "gross_profit", "ebitda", "net_profit",
    "operating_cash_flow", "free_cash_flow",
)


def _num(ei: Dict, key: str, default: float = 0.0) -> float:
    value = ei.get(key)
    try:
        return float(value) if value is not None else default
    except (TypeError, ValueError):
        return default


def _scale(ei: Dict, fields, factor: float) -> None:
    for field in fields:
        if ei.get(field) is not None:
            ei[field] = _num(ei, field) * factor


def _add(ei: Dict, field: str, delta: float) -> None:
    ei[field] = _num(ei, field) + delta


def _total_debt(ei: Dict) -> float:
    return _num(ei, "long_term_debt") + _num(ei, "short_term_debt")


def _cogs(ei: Dict) -> float:
    """Cost of goods sold, inferred from revenue and gross profit."""
    return max(0.0, _num(ei, "annual_revenue") - _num(ei, "gross_profit"))


# ---------------------------------------------------------------------------
# Factor handlers
# ---------------------------------------------------------------------------

def _revenue_change(ei: Dict, value: float) -> None:
    _scale(ei, _REVENUE_LINKED, 1.0 + value / 100.0)


def _customer_loss(ei: Dict, value: float) -> None:
    # `value` = % of revenue lost.
    _scale(ei, _REVENUE_LINKED, max(0.0, 1.0 - value / 100.0))


def _debt_change(ei: Dict, value: float) -> None:
    factor = 1.0 + value / 100.0
    _scale(ei, ("long_term_debt", "short_term_debt", "interest_expense", "existing_emi"), factor)


def _add_collateral(ei: Dict, value: float) -> None:
    # `value` = absolute currency added to the recoverable base.
    _add(ei, "net_worth", value)
    _add(ei, "current_assets", value)


def _ebitda_change(ei: Dict, value: float) -> None:
    delta = _num(ei, "ebitda") * (value / 100.0)
    _add(ei, "ebitda", delta)
    _add(ei, "net_profit", delta)
    _add(ei, "operating_cash_flow", delta)


def _interest_rate_increase(ei: Dict, value: float) -> None:
    # `value` = percentage points added to the effective borrowing rate.
    extra_annual_interest = _total_debt(ei) * (value / 100.0)
    _add(ei, "interest_expense", extra_annual_interest)
    _add(ei, "existing_emi", extra_annual_interest / 12.0)
    _add(ei, "net_profit", -extra_annual_interest)


def _inflation_increase(ei: Dict, value: float) -> None:
    delta_opex = _num(ei, "operating_expenses") * (value / 100.0)
    _add(ei, "operating_expenses", delta_opex)
    _add(ei, "ebitda", -delta_opex)
    _add(ei, "net_profit", -delta_opex)
    _add(ei, "operating_cash_flow", -delta_opex)


def _working_capital_reduction(ei: Dict, value: float) -> None:
    # `value` = absolute currency of working capital withdrawn.
    _add(ei, "current_assets", -value)
    _add(ei, "cash_and_cash_equivalents", -value)
    _add(ei, "working_capital", -value)


def _currency_fluctuation(ei: Dict, value: float) -> None:
    # Net first-order impact on revenue-linked earnings (signed %).
    _scale(ei, _REVENUE_LINKED, 1.0 + value / 100.0)


def _commodity_price_change(ei: Dict, value: float) -> None:
    # `value` = % increase in input (COGS) cost; margin compresses by the delta.
    delta = _cogs(ei) * (value / 100.0)
    _add(ei, "gross_profit", -delta)
    _add(ei, "ebitda", -delta)
    _add(ei, "net_profit", -delta)
    _add(ei, "operating_cash_flow", -delta)


def _supply_chain_delay(ei: Dict, value: float) -> None:
    # Inventory builds up (`value` %) and revenue softens by half that.
    _add(ei, "inventory", _num(ei, "inventory") * (value / 100.0))
    _scale(ei, _REVENUE_LINKED, max(0.0, 1.0 - (value / 200.0)))


@dataclass(frozen=True)
class ScenarioFactor:
    name: str
    label: str
    description: str
    value_unit: str          # "percent" | "percentage_points" | "currency"
    apply: Callable[[Dict, float], None]


FACTORS: Dict[str, ScenarioFactor] = {
    f.name: f for f in (
        ScenarioFactor("revenue_change", "Revenue Change",
                       "Scale revenue and revenue-linked earnings by a signed percent.",
                       "percent", _revenue_change),
        ScenarioFactor("customer_loss", "Customer Loss",
                       "Lose a percentage of revenue (e.g. a concentrated customer).",
                       "percent", _customer_loss),
        ScenarioFactor("debt_change", "Debt Change",
                       "Increase or decrease total debt (and its servicing cost).",
                       "percent", _debt_change),
        ScenarioFactor("add_collateral", "Add Collateral",
                       "Add collateral / equity to the recoverable base.",
                       "currency", _add_collateral),
        ScenarioFactor("ebitda_change", "EBITDA Change",
                       "Change EBITDA by a signed percent, cascading to profit and cash.",
                       "percent", _ebitda_change),
        ScenarioFactor("interest_rate_increase", "Interest Rate Increase",
                       "Add percentage points to the effective borrowing rate.",
                       "percentage_points", _interest_rate_increase),
        ScenarioFactor("inflation_increase", "Inflation Increase",
                       "Raise operating costs by a percent, compressing margins.",
                       "percent", _inflation_increase),
        ScenarioFactor("working_capital_reduction", "Working Capital Reduction",
                       "Withdraw an absolute amount of working capital.",
                       "currency", _working_capital_reduction),
        ScenarioFactor("currency_fluctuation", "Currency Fluctuation",
                       "Signed net FX impact on revenue-linked earnings.",
                       "percent", _currency_fluctuation),
        ScenarioFactor("commodity_price_change", "Commodity Price Change",
                       "Raise input (COGS) costs by a percent, compressing gross margin.",
                       "percent", _commodity_price_change),
        ScenarioFactor("supply_chain_delay", "Supply Chain Delay",
                       "Inventory builds up and revenue softens.",
                       "percent", _supply_chain_delay),
    )
}


def apply_adjustments(engine_input: Dict, adjustments: List[Dict]) -> Dict:
    """Return a new ``engine_input`` with every adjustment applied in order.

    Each adjustment is ``{"factor": <name>, "value": <number>}``. Unknown
    factors are ignored (validated at the API layer). The input is never
    mutated — a deep-enough copy of the numeric fields is made.
    """
    adjusted = dict(engine_input)
    for adj in adjustments or []:
        factor = FACTORS.get(str(adj.get("factor")))
        if factor is None:
            continue
        try:
            value = float(adj.get("value", 0.0))
        except (TypeError, ValueError):
            continue
        factor.apply(adjusted, value)
    return adjusted
