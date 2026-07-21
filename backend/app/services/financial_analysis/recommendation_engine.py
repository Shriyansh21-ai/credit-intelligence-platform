"""Recommendation Engine (Task 6).

Turns weak ratios and health dimensions into structured, deterministic actions.
Each recommendation carries a ``priority`` and ``category`` so the frontend can
group and rank them. Recommendations are triggered by concrete conditions, and
a healthy business receives a single "maintain" recommendation rather than an
empty list.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Mapping

from .health_engine import (
    CASH_FLOW, EFFICIENCY, LEVERAGE, LIQUIDITY, PROFITABILITY, HealthScore,
)
from .ratio_engine import Ratio

HIGH = "high"
MEDIUM = "medium"
LOW = "low"

_PRIORITY_RANK = {HIGH: 0, MEDIUM: 1, LOW: 2}
_WEAK = ("weak", "critical")


@dataclass
class Recommendation:
    key: str
    title: str
    detail: str
    priority: str
    category: str

    def as_dict(self) -> dict:
        return {
            "key": self.key,
            "title": self.title,
            "detail": self.detail,
            "priority": self.priority,
            "category": self.category,
        }


def generate_recommendations(
    ratios: Mapping[str, Ratio],
    health: Mapping[str, HealthScore],
) -> List[Recommendation]:
    recs: List[Recommendation] = []

    def status(key: str) -> str:
        r = ratios.get(key)
        return r.status if r else "unavailable"

    def health_status(key: str) -> str:
        hs = health.get(key)
        return hs.status if hs else "unavailable"

    def add(key, title, detail, priority, category):
        recs.append(Recommendation(key, title, detail, priority, category))

    # Liquidity
    if health_status(LIQUIDITY) in _WEAK or status("current_ratio") in _WEAK:
        add("strengthen_liquidity", "Strengthen liquidity before lending",
            "Short-term assets do not comfortably cover short-term obligations. "
            "Build a cash/liquidity buffer to reduce refinancing risk.", HIGH, LIQUIDITY)

    # Working capital
    if status("working_capital") in _WEAK:
        add("improve_working_capital", "Improve working capital",
            "Free up working capital by tightening the cash conversion cycle — "
            "faster collections, leaner inventory and better-negotiated payables.", HIGH, LIQUIDITY)

    # Leverage / debt
    if (health_status(LEVERAGE) in _WEAK or status("debt_to_equity") in _WEAK
            or status("debt_ratio") in _WEAK):
        add("reduce_debt", "Reduce debt exposure",
            "Leverage is elevated relative to equity and assets. Prioritise "
            "deleveraging or an equity injection before adding new facilities.", HIGH, LEVERAGE)

    if status("interest_coverage") in _WEAK or status("dscr") in _WEAK:
        add("improve_coverage", "Improve debt-service coverage",
            "Earnings provide only a thin cushion over interest and debt service. "
            "Grow operating earnings or extend tenor to lower annual service.", HIGH, LEVERAGE)

    # Cash flow
    if health_status(CASH_FLOW) in _WEAK or status("operating_cash_flow_ratio") in _WEAK:
        add("increase_operating_cash_flow", "Increase operating cash flow",
            "Operations are not generating enough cash to cover near-term liabilities. "
            "Focus on cash-based profitability and the working-capital cycle.", HIGH, CASH_FLOW)

    # Efficiency
    if status("receivable_turnover") in _WEAK:
        add("improve_collections", "Improve receivable collection",
            "Receivables are turning over slowly, tying up cash. Tighten credit terms "
            "and collections follow-up to accelerate inflows.", MEDIUM, EFFICIENCY)

    if status("inventory_turnover") in _WEAK:
        add("reduce_inventory", "Reduce inventory holding",
            "Inventory is turning over slowly, locking up capital and raising carrying cost. "
            "Rationalise slow-moving stock and improve demand planning.", MEDIUM, EFFICIENCY)

    # Profitability
    if health_status(PROFITABILITY) in _WEAK or status("net_margin") in _WEAK:
        add("improve_profitability", "Improve profitability",
            "Margins are thin, leaving little buffer to absorb shocks or service debt. "
            "Address pricing, cost structure and product mix.", MEDIUM, PROFITABILITY)

    if not recs:
        add("maintain", "Maintain current financial discipline",
            "No material weaknesses were detected. Sustain the current liquidity, "
            "leverage and profitability posture and monitor quarterly.", LOW, "general")

    recs.sort(key=lambda r: _PRIORITY_RANK.get(r.priority, 9))
    return recs
