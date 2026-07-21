"""Default system configuration catalog (pure data).

Each entry: key -> {value, value_type, category, description}. Seeded into the
``system_config`` table; admins may override any value at runtime.
"""

from __future__ import annotations

from typing import Any, Dict

CONFIG_DEFAULTS: Dict[str, Dict[str, Any]] = {
    "risk_thresholds": {
        "value": {"low": 0.02, "medium": 0.05, "high": 0.10, "severe": 0.20},
        "value_type": "json",
        "category": "Risk",
        "description": "Probability-of-default bands used to classify risk.",
    },
    "rating_scale": {
        "value": [
            {"grade": "AAA", "min_score": 850, "max_score": 900},
            {"grade": "AA", "min_score": 800, "max_score": 849},
            {"grade": "A", "min_score": 750, "max_score": 799},
            {"grade": "BBB", "min_score": 700, "max_score": 749},
            {"grade": "BB", "min_score": 650, "max_score": 699},
            {"grade": "B", "min_score": 600, "max_score": 649},
            {"grade": "CCC", "min_score": 500, "max_score": 599},
            {"grade": "D", "min_score": 300, "max_score": 499},
        ],
        "value_type": "list",
        "category": "Risk",
        "description": "Score-to-grade mapping.",
    },
    "approval_matrix": {
        "value": [
            {"max_amount": 5_000_000, "stages": ["junior_analyst", "senior_analyst"]},
            {"max_amount": 25_000_000, "stages": ["junior_analyst", "senior_analyst", "risk_manager"]},
            {"max_amount": None, "stages": ["junior_analyst", "senior_analyst", "risk_manager", "credit_committee"]},
        ],
        "value_type": "list",
        "category": "Approvals",
        "description": "Required approval stages by loan amount band.",
    },
    "interest_rules": {
        "value": {"base_rate": 9.5, "spread_by_rating": {"AAA": 0.0, "A": 1.0, "BBB": 2.0, "BB": 3.5, "B": 5.0, "CCC": 7.5}},
        "value_type": "json",
        "category": "Pricing",
        "description": "Base rate and risk spreads (percent).",
    },
    "loan_limits": {
        "value": {"min": 100_000, "max": 500_000_000},
        "value_type": "json",
        "category": "Limits",
        "description": "Minimum and maximum sanctionable loan amount.",
    },
    "industries": {
        "value": [
            "Manufacturing", "Retail", "Services", "Technology", "Healthcare",
            "Construction", "Agriculture", "Textiles", "Logistics", "Hospitality",
        ],
        "value_type": "list",
        "category": "Reference",
        "description": "Supported industry sectors.",
    },
    "currencies": {
        "value": ["INR", "USD", "EUR", "GBP", "AED", "SGD"],
        "value_type": "list",
        "category": "Reference",
        "description": "Supported currencies.",
    },
    "notification_rules": {
        "value": {"digest_enabled": False, "escalate_after_hours": 48},
        "value_type": "json",
        "category": "Notifications",
        "description": "Global notification behaviour.",
    },
    "stress_scenarios": {
        "value": ["baseline", "mild_recession", "severe_recession", "rate_shock", "liquidity_crunch"],
        "value_type": "list",
        "category": "Stress",
        "description": "Named macro stress scenarios.",
    },
}
