"""Data-provider layer.

A thin abstraction between the credit-intelligence platform and the *source* of
company / financial / credit / portfolio data. The seed system and the "Load
Demo Portfolio" feature depend only on the :class:`DataProvider` interface, so
the synthetic :class:`DemoDataProvider` can later be swapped for real financial
data providers (public filings, bank / bureau / GST connectors) purely through
configuration (``DATA_PROVIDER``), without touching the persistence, API,
dashboard or risk-engine code.

    Credit Intelligence Platform
              |
      Data Provider Interface   <-- this package
              |
    +---------+-----------+-----------------+
    |                     |                 |
 DemoProvider     PublicDataProvider   ProductionProvider
    |                     |                 |
 Synthetic DB       Public APIs        Bank / AA / GST / Bureau / ERP
"""

from __future__ import annotations

from backend.app.services.providers.base import (
    CompanyDataProvider,
    CompanyRecord,
    CreditAssessment,
    CreditDataProvider,
    DataProvider,
    FinancialDataProvider,
    FinancialStatement,
    PortfolioDataProvider,
    PortfolioPosition,
    CompanyProfile,
)
from backend.app.services.providers.registry import (
    available_providers,
    get_data_provider,
    register_provider,
)

__all__ = [
    "CompanyProfile",
    "FinancialStatement",
    "CreditAssessment",
    "PortfolioPosition",
    "CompanyRecord",
    "CompanyDataProvider",
    "FinancialDataProvider",
    "CreditDataProvider",
    "PortfolioDataProvider",
    "DataProvider",
    "get_data_provider",
    "register_provider",
    "available_providers",
]
