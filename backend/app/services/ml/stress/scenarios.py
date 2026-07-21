"""Named macro stress scenarios.

Each scenario maps the three severity cases (``optimistic`` / ``expected`` /
``worst``) to a bundle of scenario-engine adjustments. Severities are calibrated
so that ``worst`` is a genuinely severe but plausible shock — the standard shape
of a supervisory stress test.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

CASES = ("optimistic", "expected", "worst")


@dataclass(frozen=True)
class StressScenario:
    name: str
    label: str
    description: str
    # case -> list of {"factor", "value"} adjustments
    severities: Dict[str, List[dict]]


def _adj(factor: str, value: float) -> dict:
    return {"factor": factor, "value": value}


STRESS_SCENARIOS: Dict[str, StressScenario] = {
    s.name: s for s in (
        StressScenario(
            "economic_recession", "Economic Recession",
            "Broad demand contraction with tighter credit and higher servicing cost.",
            {
                "optimistic": [_adj("revenue_change", -5), _adj("interest_rate_increase", 0.5)],
                "expected": [_adj("revenue_change", -15), _adj("interest_rate_increase", 1.5)],
                "worst": [_adj("revenue_change", -30), _adj("interest_rate_increase", 3),
                          _adj("debt_change", 10)],
            },
        ),
        StressScenario(
            "high_inflation", "High Inflation",
            "Sustained cost inflation compressing operating margins.",
            {
                "optimistic": [_adj("inflation_increase", 4)],
                "expected": [_adj("inflation_increase", 9)],
                "worst": [_adj("inflation_increase", 18)],
            },
        ),
        StressScenario(
            "interest_rate_shock", "Interest Rate Shock",
            "Sharp rise in the effective borrowing rate.",
            {
                "optimistic": [_adj("interest_rate_increase", 1.5)],
                "expected": [_adj("interest_rate_increase", 3.5)],
                "worst": [_adj("interest_rate_increase", 6.5)],
            },
        ),
        StressScenario(
            "pandemic", "Pandemic",
            "Sudden demand shock, supply disruption and working-capital drain.",
            {
                "optimistic": [_adj("revenue_change", -10), _adj("supply_chain_delay", 15)],
                "expected": [_adj("revenue_change", -25), _adj("supply_chain_delay", 30),
                             _adj("working_capital_reduction", 1_000_000)],
                "worst": [_adj("revenue_change", -45), _adj("supply_chain_delay", 50),
                          _adj("working_capital_reduction", 2_500_000)],
            },
        ),
        StressScenario(
            "supply_chain_collapse", "Supply Chain Collapse",
            "Severe input disruption: inventory build-up and lost sales.",
            {
                "optimistic": [_adj("supply_chain_delay", 15), _adj("commodity_price_change", 8)],
                "expected": [_adj("supply_chain_delay", 35), _adj("commodity_price_change", 18)],
                "worst": [_adj("supply_chain_delay", 60), _adj("commodity_price_change", 35)],
            },
        ),
        StressScenario(
            "commodity_crisis", "Commodity Crisis",
            "Input-cost spike compressing gross margin.",
            {
                "optimistic": [_adj("commodity_price_change", 8)],
                "expected": [_adj("commodity_price_change", 20)],
                "worst": [_adj("commodity_price_change", 40)],
            },
        ),
        StressScenario(
            "sector_slowdown", "Sector Slowdown",
            "Industry-wide revenue softness.",
            {
                "optimistic": [_adj("revenue_change", -5)],
                "expected": [_adj("revenue_change", -12)],
                "worst": [_adj("revenue_change", -25)],
            },
        ),
        StressScenario(
            "currency_crisis", "Currency Crisis",
            "Adverse FX movement hitting revenue-linked earnings.",
            {
                "optimistic": [_adj("currency_fluctuation", -4)],
                "expected": [_adj("currency_fluctuation", -12)],
                "worst": [_adj("currency_fluctuation", -28)],
            },
        ),
        StressScenario(
            "demand_reduction", "Demand Reduction",
            "Loss of customer demand / concentrated accounts.",
            {
                "optimistic": [_adj("customer_loss", 5)],
                "expected": [_adj("customer_loss", 15)],
                "worst": [_adj("customer_loss", 35)],
            },
        ),
    )
}


def available_scenarios() -> List[dict]:
    return [
        {"name": s.name, "label": s.label, "description": s.description}
        for s in STRESS_SCENARIOS.values()
    ]
