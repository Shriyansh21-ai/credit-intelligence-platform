"""Collateral management service.

Stores collateral items with valuation, haircut, ownership, expiry and inspection
history; derives realizable value, LTV and coverage; supports revaluation
(append-only valuation history) and portfolio-level coverage roll-ups.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from backend.app.models.integrations import (
    CollateralInspection,
    CollateralItem,
    CollateralValuation,
)
from backend.app.services.integrations.collateral import catalog


def _derive(market_value: float, haircut_pct: float, loan_amount: Optional[float]) -> Dict[str, Optional[float]]:
    haircut_pct = max(0.0, min(1.0, haircut_pct))
    realizable = round(market_value * (1 - haircut_pct), 2)
    ltv = round(loan_amount / market_value, 4) if (loan_amount and market_value) else None
    coverage = round(realizable / loan_amount, 4) if (loan_amount and loan_amount > 0) else None
    return {"realizable_value": realizable, "ltv": ltv, "coverage_ratio": coverage}


def create_collateral(
    db: Session,
    *,
    collateral_type: str,
    description: str,
    market_value: float,
    entity_ref: Optional[str] = None,
    application_id: Optional[int] = None,
    owner: Optional[str] = None,
    haircut_pct: Optional[float] = None,
    loan_amount: Optional[float] = None,
    charge_type: Optional[str] = None,
    expiry_date: Optional[datetime] = None,
    details: Optional[Dict[str, Any]] = None,
) -> CollateralItem:
    if collateral_type not in catalog.VALID_TYPES:
        raise ValueError(f"invalid collateral_type '{collateral_type}'")
    hc = catalog.default_haircut(collateral_type) if haircut_pct is None else haircut_pct
    derived = _derive(market_value, hc, loan_amount)
    item = CollateralItem(
        entity_ref=entity_ref, application_id=application_id,
        collateral_type=collateral_type, description=description, owner=owner,
        market_value=market_value, haircut_pct=hc,
        realizable_value=derived["realizable_value"],
        loan_amount=loan_amount, ltv=derived["ltv"], coverage_ratio=derived["coverage_ratio"],
        status="active", charge_type=charge_type, expiry_date=expiry_date,
        details=details or {},
    )
    db.add(item)
    db.flush()
    # Seed the valuation history.
    db.add(CollateralValuation(
        collateral_id=item.id, market_value=market_value, haircut_pct=hc,
        realizable_value=derived["realizable_value"], method="initial", is_current=True,
    ))
    db.commit()
    db.refresh(item)
    return item


def revalue(
    db: Session,
    collateral_id: int,
    *,
    market_value: float,
    haircut_pct: Optional[float] = None,
    method: str = "market",
    valuer: Optional[str] = None,
    notes: Optional[str] = None,
) -> CollateralItem:
    item = db.query(CollateralItem).get(collateral_id)
    if item is None:
        raise ValueError("collateral not found")
    hc = item.haircut_pct if haircut_pct is None else haircut_pct
    derived = _derive(market_value, hc, item.loan_amount)
    # Mark previous valuations non-current.
    db.query(CollateralValuation).filter(
        CollateralValuation.collateral_id == collateral_id,
        CollateralValuation.is_current.is_(True),
    ).update({CollateralValuation.is_current: False})
    db.add(CollateralValuation(
        collateral_id=collateral_id, market_value=market_value, haircut_pct=hc,
        realizable_value=derived["realizable_value"], method=method, valuer=valuer,
        is_current=True, notes=notes,
    ))
    item.market_value = market_value
    item.haircut_pct = hc
    item.realizable_value = derived["realizable_value"]
    item.ltv = derived["ltv"]
    item.coverage_ratio = derived["coverage_ratio"]
    db.commit()
    db.refresh(item)
    return item


def add_inspection(
    db: Session,
    collateral_id: int,
    *,
    inspector: Optional[str] = None,
    outcome: str = "satisfactory",
    condition: Optional[str] = None,
    notes: Optional[str] = None,
) -> CollateralInspection:
    item = db.query(CollateralItem).get(collateral_id)
    if item is None:
        raise ValueError("collateral not found")
    insp = CollateralInspection(
        collateral_id=collateral_id, inspector=inspector, outcome=outcome,
        condition=condition, notes=notes,
    )
    if outcome == "not_found":
        item.status = "impaired"
    db.add(insp)
    db.commit()
    db.refresh(insp)
    return insp


def set_status(db: Session, collateral_id: int, status: str) -> CollateralItem:
    item = db.query(CollateralItem).get(collateral_id)
    if item is None:
        raise ValueError("collateral not found")
    item.status = status
    db.commit()
    db.refresh(item)
    return item


def list_for_application(db: Session, application_id: int) -> List[CollateralItem]:
    return (db.query(CollateralItem)
            .filter(CollateralItem.application_id == application_id)
            .order_by(CollateralItem.id).all())


def list_for_entity(db: Session, entity_ref: str) -> List[CollateralItem]:
    return (db.query(CollateralItem)
            .filter(CollateralItem.entity_ref == entity_ref)
            .order_by(CollateralItem.id).all())


def coverage_summary(db: Session, *, application_id: Optional[int] = None,
                     entity_ref: Optional[str] = None) -> Dict[str, Any]:
    """Aggregate collateral coverage for an application or entity."""
    q = db.query(CollateralItem).filter(CollateralItem.status == "active")
    if application_id is not None:
        q = q.filter(CollateralItem.application_id == application_id)
    if entity_ref is not None:
        q = q.filter(CollateralItem.entity_ref == entity_ref)
    items = q.all()
    total_market = round(sum(i.market_value or 0.0 for i in items), 2)
    total_realizable = round(sum(i.realizable_value or 0.0 for i in items), 2)
    total_exposure = round(sum(i.loan_amount or 0.0 for i in items), 2)
    by_type: Dict[str, float] = {}
    for i in items:
        by_type[i.collateral_type] = round(by_type.get(i.collateral_type, 0.0) + (i.realizable_value or 0.0), 2)
    coverage = round(total_realizable / total_exposure, 4) if total_exposure > 0 else None
    return {
        "item_count": len(items),
        "total_market_value": total_market,
        "total_realizable_value": total_realizable,
        "total_exposure": total_exposure,
        "coverage_ratio": coverage,
        "secured": coverage is not None and coverage >= 1.0,
        "by_type": by_type,
    }


def to_dict(item: CollateralItem, *, db: Optional[Session] = None) -> Dict[str, Any]:
    out = {
        "id": item.id, "entity_ref": item.entity_ref, "application_id": item.application_id,
        "collateral_type": item.collateral_type, "display": catalog.display_name(item.collateral_type),
        "description": item.description, "owner": item.owner, "currency": item.currency,
        "market_value": item.market_value, "haircut_pct": item.haircut_pct,
        "realizable_value": item.realizable_value, "loan_amount": item.loan_amount,
        "ltv": item.ltv, "coverage_ratio": item.coverage_ratio, "status": item.status,
        "charge_type": item.charge_type,
        "expiry_date": item.expiry_date.isoformat() if item.expiry_date else None,
        "details": item.details,
    }
    if db is not None:
        insp = (db.query(CollateralInspection)
                .filter(CollateralInspection.collateral_id == item.id)
                .order_by(CollateralInspection.inspected_at.desc()).all())
        out["inspections"] = [{
            "inspected_at": i.inspected_at.isoformat() if i.inspected_at else None,
            "inspector": i.inspector, "outcome": i.outcome, "condition": i.condition, "notes": i.notes,
        } for i in insp]
        vals = (db.query(CollateralValuation)
                .filter(CollateralValuation.collateral_id == item.id)
                .order_by(CollateralValuation.valued_at.desc()).all())
        out["valuations"] = [{
            "market_value": v.market_value, "haircut_pct": v.haircut_pct,
            "realizable_value": v.realizable_value, "method": v.method, "valuer": v.valuer,
            "is_current": v.is_current,
            "valued_at": v.valued_at.isoformat() if v.valued_at else None,
        } for v in vals]
    return out
