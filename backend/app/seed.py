"""Seed the database with a demo portfolio.

Idempotent CLI wrapper around the demo-portfolio service. Populates a tenant's
book of companies (profile + financials + credit + exposure) from the active
``DATA_PROVIDER``. Running it repeatedly never creates duplicates.

Usage
-----
    python -m backend.app.seed                 # 50 companies into the default tenant
    python -m backend.app.seed --companies 100 # 100 companies
    python -m backend.app.seed --reset         # wipe the tenant book, then reseed
    python -m backend.app.seed --demo          # explicit: use the demo provider
    python -m backend.app.seed --tenant-slug default --org-slug platform

The schema must already be migrated (``alembic upgrade head``); this never
creates tables (production must not depend on schema auto-creation).
"""

from __future__ import annotations

import argparse
import logging
import sys
from typing import Optional

from sqlalchemy.orm import Session

logger = logging.getLogger("seed")


def _resolve_tenant_id(db: Session, org_slug: str, tenant_slug: str) -> Optional[int]:
    from backend.app.models.tenancy import Organization, Tenant
    from backend.app.services.saas.seeding import ensure_default_tenant

    # Fast path: the platform default tenant.
    if org_slug == "platform" and tenant_slug == "default":
        tenant = ensure_default_tenant(db)
        return tenant.id if tenant else None

    org = db.query(Organization).filter(Organization.slug == org_slug).first()
    if org is None:
        logger.error("organization slug not found: %s", org_slug)
        return None
    tenant = (
        db.query(Tenant)
        .filter(Tenant.organization_id == org.id, Tenant.slug == tenant_slug)
        .first()
    )
    if tenant is None:
        logger.error("tenant slug not found in org %s: %s", org_slug, tenant_slug)
        return None
    return tenant.id


def run(
    *,
    companies: int = 50,
    reset: bool = False,
    provider_name: Optional[str] = None,
    org_slug: str = "platform",
    tenant_slug: str = "default",
) -> dict:
    import backend.app.db.registry  # noqa: F401  (register every ORM mapper)
    from backend.app.db.database import SessionLocal
    from backend.app.services import demo_portfolio
    from backend.app.services.providers import get_data_provider

    db = SessionLocal()
    try:
        tenant_id = _resolve_tenant_id(db, org_slug, tenant_slug)
        if tenant_id is None:
            raise SystemExit(2)

        if reset:
            removed = demo_portfolio.reset_demo_portfolio(db, tenant_id)
            logger.info("Reset: removed %s companies", removed["companies_removed"])

        provider = get_data_provider(provider_name)
        summary = demo_portfolio.load_demo_portfolio(
            db, tenant_id, count=companies, provider=provider
        )

        logger.info("Seed completed (tenant_id=%s, provider=%s):", tenant_id, provider.name)
        logger.info("  Companies:           %s", summary["companies_loaded"])
        logger.info("  Financial statements: %s", summary["financial_records_loaded"])
        logger.info("  Credit profiles:      %s", summary["credit_profiles_loaded"])
        logger.info("  Portfolio records:    %s", summary["portfolio_records_loaded"])
        logger.info("  Skipped existing:     %s", summary["skipped_existing"])
        return summary
    finally:
        db.close()


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(description="Seed a demo portfolio.")
    parser.add_argument("--companies", type=int, default=50,
                        help="number of companies to seed (default 50)")
    parser.add_argument("--reset", action="store_true",
                        help="wipe the tenant's book before seeding")
    parser.add_argument("--demo", action="store_true",
                        help="use the demo (synthetic) provider explicitly")
    parser.add_argument("--provider", type=str, default=None,
                        help="provider name (defaults to DATA_PROVIDER)")
    parser.add_argument("--org-slug", type=str, default="platform")
    parser.add_argument("--tenant-slug", type=str, default="default")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    provider_name = args.provider or ("demo" if args.demo else None)
    run(
        companies=args.companies,
        reset=args.reset,
        provider_name=provider_name,
        org_slug=args.org_slug,
        tenant_slug=args.tenant_slug,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
