"""Billing engine service (Phase 8, Milestone 4).

Subscriptions, metered usage, quota enforcement, invoice generation and billing
analytics. Plans come from the code catalog and are synced into ``billing_plans``
on startup. Invoicing rolls up ``usage_records`` for a period against the plan's
``unit_prices`` (base fee + seat + usage/overage lines) and charges through the
:mod:`gateway` abstraction.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.app.models.billing import (
    BillingPlan, Invoice, InvoiceLineItem, Subscription, SubscriptionEvent,
    UsageRecord,
)
from backend.app.services.saas.billing import catalog
from backend.app.services.saas.billing.gateway import get_gateway


def current_period() -> str:
    return datetime.utcnow().strftime("%Y-%m")


# ===========================================================================
# Plan catalog sync
# ===========================================================================
def sync_plans(db: Session) -> int:
    """Idempotently upsert the global plan catalog. Returns rows touched."""
    touched = 0
    for spec in catalog.PLANS:
        row = (
            db.query(BillingPlan)
            .filter(BillingPlan.code == spec["code"],
                    BillingPlan.organization_id.is_(None))
            .first()
        )
        if row is None:
            row = BillingPlan(code=spec["code"], organization_id=None)
            db.add(row)
        row.name = spec["name"]
        row.tier = spec["tier"]
        row.base_price = spec["base_price"]
        row.limits = spec["limits"]
        row.unit_prices = spec["unit_prices"]
        row.features = spec["features"]
        row.is_active = True
        touched += 1
    db.commit()
    return touched


def list_plans(db: Session, organization_id: Optional[int] = None) -> List[BillingPlan]:
    q = db.query(BillingPlan).filter(
        (BillingPlan.organization_id.is_(None)) |
        (BillingPlan.organization_id == organization_id)
    )
    return q.filter(BillingPlan.is_active.is_(True)).all()


def get_plan(db: Session, code: str, organization_id: Optional[int] = None) -> Optional[BillingPlan]:
    return (
        db.query(BillingPlan)
        .filter(BillingPlan.code == code,
                (BillingPlan.organization_id.is_(None)) |
                (BillingPlan.organization_id == organization_id))
        .order_by(BillingPlan.organization_id.isnot(None).desc())
        .first()
    )


def create_custom_plan(db: Session, organization_id: int, *, code: str, name: str,
                       base_price: float, limits: Dict[str, Any],
                       unit_prices: Dict[str, Any], features: List[str]) -> BillingPlan:
    plan = BillingPlan(code=code, name=name, tier="custom",
                       organization_id=organization_id, base_price=base_price,
                       limits=limits, unit_prices=unit_prices, features=features)
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return plan


# ===========================================================================
# Subscriptions
# ===========================================================================
def _log_event(db: Session, sub: Subscription, event_type: str, *,
               from_plan: Optional[str] = None, to_plan: Optional[str] = None,
               actor: Optional[str] = None, detail: Optional[Dict] = None) -> None:
    db.add(SubscriptionEvent(
        subscription_id=sub.id, organization_id=sub.organization_id,
        event_type=event_type, from_plan=from_plan, to_plan=to_plan,
        actor=actor, detail=detail or {},
    ))


def subscribe(db: Session, organization_id: int, plan_code: str, *,
              seats: int = 1, trial_days: int = 0, actor: Optional[str] = None) -> Subscription:
    plan = get_plan(db, plan_code, organization_id)
    if plan is None:
        raise ValueError(f"unknown plan: {plan_code}")
    now = datetime.utcnow()
    existing = active_subscription(db, organization_id)
    if existing:
        return change_plan(db, organization_id, plan_code, actor=actor)
    sub = Subscription(
        organization_id=organization_id, plan_id=plan.id, seats=seats,
        status="trialing" if trial_days else "active",
        current_period_start=now,
        current_period_end=now + timedelta(days=30),
        trial_end=(now + timedelta(days=trial_days)) if trial_days else None,
    )
    db.add(sub)
    db.flush()
    _log_event(db, sub, "created", to_plan=plan_code, actor=actor)
    db.commit()
    db.refresh(sub)
    return sub


def active_subscription(db: Session, organization_id: int) -> Optional[Subscription]:
    return (
        db.query(Subscription)
        .filter(Subscription.organization_id == organization_id,
                Subscription.status.in_(["trialing", "active", "past_due"]))
        .order_by(Subscription.id.desc())
        .first()
    )


def change_plan(db: Session, organization_id: int, new_plan_code: str, *,
                actor: Optional[str] = None) -> Subscription:
    sub = active_subscription(db, organization_id)
    if sub is None:
        return subscribe(db, organization_id, new_plan_code, actor=actor)
    old_plan = db.query(BillingPlan).get(sub.plan_id)
    new_plan = get_plan(db, new_plan_code, organization_id)
    if new_plan is None:
        raise ValueError(f"unknown plan: {new_plan_code}")
    old_tier_rank = _tier_rank(old_plan.tier if old_plan else "free")
    event = "upgraded" if _tier_rank(new_plan.tier) >= old_tier_rank else "downgraded"
    sub.plan_id = new_plan.id
    sub.status = "active"
    _log_event(db, sub, event, from_plan=old_plan.code if old_plan else None,
               to_plan=new_plan_code, actor=actor)
    db.commit()
    db.refresh(sub)
    return sub


def _tier_rank(tier: str) -> int:
    return {"free": 0, "professional": 1, "enterprise": 2, "custom": 3}.get(tier, 0)


def cancel_subscription(db: Session, organization_id: int, *, at_period_end: bool = True,
                        actor: Optional[str] = None) -> Subscription:
    sub = active_subscription(db, organization_id)
    if sub is None:
        raise ValueError("no active subscription")
    if at_period_end:
        sub.cancel_at_period_end = True
    else:
        sub.status = "canceled"
    _log_event(db, sub, "canceled", actor=actor)
    db.commit()
    db.refresh(sub)
    return sub


def subscription_history(db: Session, organization_id: int) -> List[SubscriptionEvent]:
    return (
        db.query(SubscriptionEvent)
        .filter(SubscriptionEvent.organization_id == organization_id)
        .order_by(SubscriptionEvent.created_at.desc())
        .all()
    )


# ===========================================================================
# Metered usage + quota enforcement
# ===========================================================================
def record_usage(db: Session, organization_id: int, meter: str, quantity: float, *,
                 tenant_id: Optional[int] = None, period: Optional[str] = None,
                 metadata: Optional[Dict] = None) -> UsageRecord:
    rec = UsageRecord(
        organization_id=organization_id, tenant_id=tenant_id, meter=meter,
        quantity=quantity, period=period or current_period(),
        metadata_json=metadata or {},
    )
    db.add(rec)
    db.commit()
    db.refresh(rec)
    return rec


def usage_total(db: Session, organization_id: int, meter: str, *,
                period: Optional[str] = None) -> float:
    q = db.query(func.coalesce(func.sum(UsageRecord.quantity), 0.0)).filter(
        UsageRecord.organization_id == organization_id,
        UsageRecord.meter == meter,
        UsageRecord.period == (period or current_period()),
    )
    return float(q.scalar() or 0.0)


def usage_summary(db: Session, organization_id: int, *,
                  period: Optional[str] = None) -> Dict[str, float]:
    period = period or current_period()
    rows = (
        db.query(UsageRecord.meter, func.sum(UsageRecord.quantity))
        .filter(UsageRecord.organization_id == organization_id,
                UsageRecord.period == period)
        .group_by(UsageRecord.meter)
        .all()
    )
    return {meter: float(total) for meter, total in rows}


def check_quota(db: Session, organization_id: int, meter: str, *,
                additional: float = 0.0) -> Dict[str, Any]:
    """Whether ``additional`` usage of ``meter`` is within the plan limit.

    Missing limit key = unlimited (enterprise). Returns allowance details rather
    than raising, so callers decide whether to hard-block or soft-meter.
    """
    sub = active_subscription(db, organization_id)
    plan = db.query(BillingPlan).get(sub.plan_id) if sub else None
    limits = (plan.limits if plan else {}) or {}
    limit = limits.get(meter)
    used = usage_total(db, organization_id, meter)
    projected = used + additional
    allowed = limit is None or projected <= limit
    return {
        "meter": meter, "limit": limit, "used": used,
        "projected": projected, "allowed": allowed,
        "remaining": (None if limit is None else max(0.0, limit - used)),
    }


def has_feature(db: Session, organization_id: int, feature: str) -> bool:
    sub = active_subscription(db, organization_id)
    plan = db.query(BillingPlan).get(sub.plan_id) if sub else None
    return bool(plan and feature in (plan.features or []))


# ===========================================================================
# Invoicing
# ===========================================================================
def _next_invoice_number(db: Session) -> str:
    count = db.query(func.count(Invoice.id)).scalar() or 0
    return f"INV-{datetime.utcnow().strftime('%Y%m')}-{count + 1:05d}"


def generate_invoice(db: Session, organization_id: int, *,
                     period: Optional[str] = None) -> Invoice:
    period = period or current_period()
    sub = active_subscription(db, organization_id)
    if sub is None:
        raise ValueError("no active subscription")
    plan = db.query(BillingPlan).get(sub.plan_id)
    unit_prices = (plan.unit_prices if plan else {}) or {}
    limits = (plan.limits if plan else {}) or {}

    invoice = Invoice(
        organization_id=organization_id, subscription_id=sub.id,
        number=_next_invoice_number(db), period=period, status="open",
        currency=plan.currency if plan else "INR",
    )
    db.add(invoice)
    db.flush()

    lines: List[InvoiceLineItem] = []
    # Base subscription fee.
    if plan and plan.base_price:
        lines.append(InvoiceLineItem(
            invoice_id=invoice.id, kind="base", description=f"{plan.name} plan",
            quantity=1, unit_price=plan.base_price, amount=plan.base_price,
        ))
    # Seat + metered usage / overage lines.
    usage = usage_summary(db, organization_id, period=period)
    for meter, qty in sorted(usage.items()):
        price = unit_prices.get(meter)
        if not price:
            continue
        limit = limits.get(meter)
        billable = qty if limit is None else max(0.0, qty - limit)
        if billable <= 0:
            continue
        # api/ml/ocr/connector priced per 1,000 units.
        divisor = 1000.0 if meter in ("api_calls", "ml_predictions", "ocr_pages",
                                      "connector_calls") else 1.0
        units = billable / divisor
        amount = round(units * price, 2)
        kind = "overage" if limit is not None else "usage"
        lines.append(InvoiceLineItem(
            invoice_id=invoice.id, kind=kind, meter=meter,
            description=f"{meter} ({'overage' if limit is not None else 'usage'})",
            quantity=round(units, 3), unit_price=price, amount=amount,
        ))

    db.add_all(lines)
    subtotal = round(sum(l.amount for l in lines), 2)
    tax = round(subtotal * catalog.DEFAULT_TAX_RATE, 2)
    invoice.subtotal = subtotal
    invoice.tax = tax
    invoice.total = round(subtotal + tax, 2)
    invoice.issued_at = datetime.utcnow()
    db.commit()
    db.refresh(invoice)
    return invoice


def pay_invoice(db: Session, invoice_id: int) -> Invoice:
    invoice = db.query(Invoice).get(invoice_id)
    if invoice is None:
        raise ValueError("invoice not found")
    if invoice.status == "paid":
        return invoice
    result = get_gateway().charge_invoice(invoice.number, invoice.total, invoice.currency)
    if result.success:
        invoice.status = "paid"
        invoice.provider = result.provider
        invoice.provider_ref = result.provider_ref
        invoice.paid_at = datetime.utcnow()
    db.commit()
    db.refresh(invoice)
    return invoice


def list_invoices(db: Session, organization_id: int) -> List[Invoice]:
    return (
        db.query(Invoice)
        .filter(Invoice.organization_id == organization_id)
        .order_by(Invoice.created_at.desc())
        .all()
    )


def invoice_lines(db: Session, invoice_id: int) -> List[InvoiceLineItem]:
    return db.query(InvoiceLineItem).filter(
        InvoiceLineItem.invoice_id == invoice_id).all()


# ===========================================================================
# Billing analytics
# ===========================================================================
def billing_analytics(db: Session, organization_id: int) -> Dict[str, Any]:
    invoices = list_invoices(db, organization_id)
    paid = [i for i in invoices if i.status == "paid"]
    sub = active_subscription(db, organization_id)
    plan = db.query(BillingPlan).get(sub.plan_id) if sub else None
    return {
        "organization_id": organization_id,
        "current_plan": plan.code if plan else None,
        "mrr": plan.base_price if plan else 0.0,
        "invoice_count": len(invoices),
        "total_billed": round(sum(i.total for i in invoices), 2),
        "total_paid": round(sum(i.total for i in paid), 2),
        "outstanding": round(sum(i.total for i in invoices if i.status == "open"), 2),
        "usage_current_period": usage_summary(db, organization_id),
    }
