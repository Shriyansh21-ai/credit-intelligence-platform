"""Demo-portfolio domain service.

Persists a coherent, tenant-scoped book of companies (profile + financials +
credit + exposure) sourced from the active :class:`DataProvider`, and exposes
tenant-scoped read models for the dashboard. All writes and reads are filtered
by ``tenant_id`` so organizations are isolated.
"""

from backend.app.services.demo_portfolio.service import (
    DEFAULT_COMPANY_COUNT,
    MAX_COMPANY_COUNT,
    list_companies,
    load_demo_portfolio,
    portfolio_status,
    portfolio_summary,
    reset_demo_portfolio,
)

__all__ = [
    "DEFAULT_COMPANY_COUNT",
    "MAX_COMPANY_COUNT",
    "load_demo_portfolio",
    "reset_demo_portfolio",
    "portfolio_summary",
    "portfolio_status",
    "list_companies",
]
