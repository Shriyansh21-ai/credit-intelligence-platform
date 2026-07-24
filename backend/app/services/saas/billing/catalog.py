"""Plan catalog — the code-driven source of truth for billing tiers (M4).

Pure data (no ORM imports) so it can be imported by migrations, seeding and
tests. ``limits`` are hard entitlements (None/absent = unlimited). ``unit_prices``
drive usage-based / overage billing per meter. Seeded into ``billing_plans`` by
:func:`services.saas.billing.service.sync_plans`.

Metered units (meters)::

    seats            per active seat / month
    storage_gb       per GB stored / month
    api_calls        per 1,000 Open-API calls
    ml_predictions   per 1,000 ML inferences
    ocr_pages        per 1,000 OCR pages
    connector_calls  per 1,000 external connector calls
"""

from __future__ import annotations

from typing import Any, Dict, List

METERS: List[str] = [
    "seats", "storage_gb", "api_calls", "ml_predictions", "ocr_pages",
    "connector_calls",
]

# (code, name, tier, base_price, limits, unit_prices, features)
PLANS: List[Dict[str, Any]] = [
    {
        "code": "free",
        "name": "Free",
        "tier": "free",
        "base_price": 0.0,
        "limits": {
            "seats": 3, "storage_gb": 5, "api_calls": 5_000,
            "ml_predictions": 1_000, "ocr_pages": 500, "connector_calls": 1_000,
        },
        "unit_prices": {},  # no overage — hard caps on free tier
        "features": ["core_credit", "dashboards", "basic_reports"],
    },
    {
        "code": "professional",
        "name": "Professional",
        "tier": "professional",
        "base_price": 49_999.0,
        "limits": {
            "seats": 25, "storage_gb": 250, "api_calls": 500_000,
            "ml_predictions": 100_000, "ocr_pages": 50_000, "connector_calls": 100_000,
        },
        "unit_prices": {
            "seats": 1_499.0, "storage_gb": 25.0, "api_calls": 40.0,
            "ml_predictions": 60.0, "ocr_pages": 120.0, "connector_calls": 80.0,
        },
        "features": ["core_credit", "dashboards", "advanced_reports", "ml_platform",
                     "integrations", "white_label"],
    },
    {
        "code": "enterprise",
        "name": "Enterprise",
        "tier": "enterprise",
        "base_price": 249_999.0,
        "limits": {
            # Enterprise: unlimited (no keys) — soft-metered for analytics only.
        },
        "unit_prices": {
            "seats": 999.0, "storage_gb": 15.0, "api_calls": 25.0,
            "ml_predictions": 40.0, "ocr_pages": 80.0, "connector_calls": 50.0,
        },
        "features": ["core_credit", "dashboards", "advanced_reports", "ml_platform",
                     "integrations", "white_label", "custom_domains", "sso",
                     "priority_support", "admin_console", "analytics_platform"],
    },
]

# tax rate applied to invoices (GST 18%). Configurable per-org in real deployments.
DEFAULT_TAX_RATE = 0.18


def plan_by_code(code: str) -> Dict[str, Any]:
    for p in PLANS:
        if p["code"] == code:
            return p
    raise KeyError(f"unknown plan: {code}")
