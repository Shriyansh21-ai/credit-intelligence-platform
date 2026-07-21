"""Canonical covenant metric definitions (pure data).

Each metric declares its default comparison direction and unit. Definitions are
used to pre-fill covenant names/units and to evaluate breaches consistently.
"""

from __future__ import annotations

from typing import Dict

# metric_key -> {label, operator, unit, help}
COVENANT_METRICS: Dict[str, Dict[str, str]] = {
    "dscr": {
        "label": "Minimum DSCR",
        "operator": "min",
        "unit": "x",
        "help": "Debt Service Coverage Ratio must stay at or above the threshold.",
    },
    "debt_ratio": {
        "label": "Maximum Debt Ratio",
        "operator": "max",
        "unit": "x",
        "help": "Total debt to assets must stay at or below the threshold.",
    },
    "current_ratio": {
        "label": "Minimum Current Ratio",
        "operator": "min",
        "unit": "x",
        "help": "Current assets to current liabilities must stay above the threshold.",
    },
    "interest_coverage": {
        "label": "Minimum Interest Coverage",
        "operator": "min",
        "unit": "x",
        "help": "EBIT to interest expense must stay above the threshold.",
    },
    "net_worth": {
        "label": "Minimum Net Worth",
        "operator": "min",
        "unit": "currency",
        "help": "Tangible net worth must stay above the threshold.",
    },
    "ebitda": {
        "label": "Minimum EBITDA",
        "operator": "min",
        "unit": "currency",
        "help": "EBITDA must stay above the threshold.",
    },
    "leverage": {
        "label": "Maximum Leverage (Debt/EBITDA)",
        "operator": "max",
        "unit": "x",
        "help": "Total debt to EBITDA must stay at or below the threshold.",
    },
}


def metric_definition(metric_key: str) -> Dict[str, str]:
    return COVENANT_METRICS.get(
        metric_key, {"label": metric_key, "operator": "min", "unit": "", "help": ""}
    )
