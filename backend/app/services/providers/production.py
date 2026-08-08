"""Placeholder real-data providers.

These document the extension point without shipping live integrations. When a
real financial-data source is wired, implement the four capability hooks here
(delegating, for example, to the existing connector platform under
``services/integrations`` — GST / MCA / Account Aggregator / bureau / ERP /
payments) and register the class in :mod:`backend.app.services.providers.registry`.
Selecting it is then purely a matter of setting ``DATA_PROVIDER=production``.

They raise :class:`NotImplementedError` on use so a misconfiguration fails loudly
rather than silently returning demo data.
"""

from __future__ import annotations

from typing import List

from backend.app.services.providers.base import (
    CompanyProfile,
    CreditAssessment,
    DataProvider,
    FinancialStatement,
    PortfolioPosition,
)


class _UnimplementedProvider(DataProvider):
    is_synthetic = False
    _detail = "provider not yet wired"

    def list_companies(self, count: int) -> List[CompanyProfile]:
        raise NotImplementedError(self._detail)

    def financials_for(self, profile, *, years: int = 3) -> List[FinancialStatement]:
        raise NotImplementedError(self._detail)

    def credit_for(self, profile, financials) -> CreditAssessment:
        raise NotImplementedError(self._detail)

    def portfolio_for(self, profile, credit) -> PortfolioPosition:
        raise NotImplementedError(self._detail)


class PublicDataProvider(_UnimplementedProvider):
    """Adapter for public sources (filings, registries, open data)."""

    name = "public"
    _detail = (
        "PublicDataProvider is not implemented; set DATA_PROVIDER=demo or wire a "
        "public-data adapter."
    )


class ProductionDataProvider(_UnimplementedProvider):
    """Adapter backed by live bank / bureau / GST / ERP connectors."""

    name = "production"
    _detail = (
        "ProductionDataProvider is not implemented; set DATA_PROVIDER=demo or wire "
        "the connector-backed provider."
    )
