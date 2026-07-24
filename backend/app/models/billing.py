"""Subscription & billing persistence (Phase 8, Milestone 4).

Additive tables. The plan *catalog* is code-driven (see
``services/saas/billing/catalog.py``) and seeded into ``billing_plans`` on
startup; subscriptions, metered usage, and invoices are per-organization data.

Payment-provider integration (Stripe / Razorpay) is deliberately abstracted:
:class:`Subscription` carries ``provider`` + ``provider_ref`` columns and the
service layer talks to a ``PaymentGateway`` interface, so wiring a real gateway
never touches the schema.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean, Column, DateTime, Float, ForeignKey, Integer, JSON, String, Text,
)

from backend.app.db.database import Base


class BillingPlan(Base):
    """A subscription tier. Seeded from the code catalog; admins may add custom
    plans per organization (``organization_id`` set)."""

    __tablename__ = "billing_plans"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String, nullable=False, index=True)  # free|professional|enterprise|custom-<n>
    name = Column(String, nullable=False)
    tier = Column(String, nullable=False, default="free")  # free|professional|enterprise|custom
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=True)  # null = global plan
    # Recurring price + billing period.
    base_price = Column(Float, nullable=False, default=0.0)
    currency = Column(String, nullable=False, default="INR")
    billing_interval = Column(String, nullable=False, default="monthly")  # monthly|annual
    # Quotas / entitlements (seats, storage_gb, api_calls, ml_predictions, ocr_pages,
    # connector_calls, …). Absent key = unlimited.
    limits = Column(JSON, nullable=False, default=dict)
    # Per-unit prices for usage-based / overage billing, keyed by meter.
    unit_prices = Column(JSON, nullable=False, default=dict)
    features = Column(JSON, nullable=False, default=list)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    plan_id = Column(Integer, ForeignKey("billing_plans.id"), nullable=False)
    status = Column(String, nullable=False, default="active", index=True)  # trialing|active|past_due|canceled
    seats = Column(Integer, nullable=False, default=1)
    current_period_start = Column(DateTime, nullable=True)
    current_period_end = Column(DateTime, nullable=True)
    cancel_at_period_end = Column(Boolean, nullable=False, default=False)
    # Payment provider abstraction — no schema change to wire Stripe/Razorpay.
    provider = Column(String, nullable=False, default="internal")  # internal|stripe|razorpay
    provider_ref = Column(String, nullable=True)
    trial_end = Column(DateTime, nullable=True)
    metadata_json = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class SubscriptionEvent(Base):
    """Append-only subscription history (created, upgraded, downgraded, canceled)."""

    __tablename__ = "subscription_events"

    id = Column(Integer, primary_key=True, index=True)
    subscription_id = Column(Integer, ForeignKey("subscriptions.id"), nullable=False, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    event_type = Column(String, nullable=False)  # created|upgraded|downgraded|renewed|canceled|reactivated
    from_plan = Column(String, nullable=True)
    to_plan = Column(String, nullable=True)
    actor = Column(String, nullable=True)
    detail = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class UsageRecord(Base):
    """One metered usage row. Aggregated into invoices and analytics.

    ``meter`` ∈ {seats, storage_gb, api_calls, ml_predictions, ocr_pages,
    connector_calls, …}. ``period`` is a ``YYYY-MM`` billing month for cheap
    grouping.
    """

    __tablename__ = "usage_records"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    meter = Column(String, nullable=False, index=True)
    quantity = Column(Float, nullable=False, default=0.0)
    period = Column(String, nullable=False, index=True)  # YYYY-MM
    metadata_json = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class Invoice(Base):
    __tablename__ = "invoices"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    subscription_id = Column(Integer, ForeignKey("subscriptions.id"), nullable=True)
    number = Column(String, nullable=False, unique=True, index=True)
    period = Column(String, nullable=False, index=True)  # YYYY-MM
    status = Column(String, nullable=False, default="draft")  # draft|open|paid|void
    currency = Column(String, nullable=False, default="INR")
    subtotal = Column(Float, nullable=False, default=0.0)
    tax = Column(Float, nullable=False, default=0.0)
    total = Column(Float, nullable=False, default=0.0)
    provider = Column(String, nullable=False, default="internal")
    provider_ref = Column(String, nullable=True)
    issued_at = Column(DateTime, nullable=True)
    paid_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class InvoiceLineItem(Base):
    __tablename__ = "invoice_line_items"

    id = Column(Integer, primary_key=True, index=True)
    invoice_id = Column(Integer, ForeignKey("invoices.id"), nullable=False, index=True)
    kind = Column(String, nullable=False, default="usage")  # base|seat|usage|overage|discount
    meter = Column(String, nullable=True)
    description = Column(String, nullable=False)
    quantity = Column(Float, nullable=False, default=1.0)
    unit_price = Column(Float, nullable=False, default=0.0)
    amount = Column(Float, nullable=False, default=0.0)
