"""Collateral type catalog — pure data.

Regulatory-style default haircuts per collateral type. Kept dependency-free so it
can be imported anywhere. Haircuts are the fraction of market value discounted
when computing realizable (security) value.
"""

from __future__ import annotations

from typing import Dict, List, Tuple

# (type, display, default_haircut, liquidity)
COLLATERAL_TYPES: List[Tuple[str, str, float, str]] = [
    ("real_estate", "Real Estate", 0.25, "low"),
    ("machinery", "Plant & Machinery", 0.40, "low"),
    ("vehicle", "Vehicles", 0.35, "medium"),
    ("inventory", "Inventory / Stock", 0.50, "medium"),
    ("receivables", "Book Debts / Receivables", 0.30, "medium"),
    ("fixed_deposit", "Fixed Deposits", 0.10, "high"),
    ("guarantee", "Guarantees", 0.60, "low"),
    ("insurance", "Insurance Policies", 0.20, "high"),
]

_HAIRCUTS: Dict[str, float] = {t[0]: t[2] for t in COLLATERAL_TYPES}
_DISPLAY: Dict[str, str] = {t[0]: t[1] for t in COLLATERAL_TYPES}
VALID_TYPES = set(_HAIRCUTS.keys())


def default_haircut(collateral_type: str) -> float:
    return _HAIRCUTS.get(collateral_type, 0.5)


def display_name(collateral_type: str) -> str:
    return _DISPLAY.get(collateral_type, collateral_type)


def catalog() -> List[Dict[str, object]]:
    return [{"type": t, "display": d, "default_haircut": h, "liquidity": lq}
            for (t, d, h, lq) in COLLATERAL_TYPES]
