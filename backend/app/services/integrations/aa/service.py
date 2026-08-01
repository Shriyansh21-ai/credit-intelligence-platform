"""Account Aggregator service — consent lifecycle + statement import (M4).

Wraps the AA connector with durable persistence

* Consent lifecycle: request → activate → (expire | revoke), stored as
  :class:`ConsentArtifact`. :func:`sync_consent_status` reconciles state with the
  provider and enforces expiry.
* Account discovery and statement import: a fetched statement is persisted as a
  :class:`BankStatement` header plus :class:`BankTransaction` rows, ready for the
  analytics engine.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from backend.app.models.integrations import (
    BankStatement,
    BankTransaction,
    ConsentArtifact,
)
from backend.app.services.integrations.factory import get_connector


def _parse_dt(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
    except Exception:
        try:
            return datetime.strptime(value[:10], "%Y-%m-%d")
        except Exception:
            return None


# ---------------------------------------------------------------------------
# Consent
# ---------------------------------------------------------------------------
def create_consent(
    db: Session,
    *,
    entity_ref: str,
    purpose: str = "Credit assessment",
    months: int = 12,
    application_id: Optional[int] = None,
    fi_types: Optional[List[str]] = None,
    mode: Optional[str] = None,
) -> ConsentArtifact:
    conn = get_connector(db, "account_aggregator", mode=mode)
    resp = conn.call("create_consent", {
        "entity_ref": entity_ref, "purpose": purpose, "months": months,
        "fi_types": fi_types or ["DEPOSIT"],
    }, db=db)
    if not resp.success:
        raise ValueError(resp.error or "consent creation failed")
    data = resp.data
    consent = ConsentArtifact(
        handle=data["consent_handle"],
        entity_ref=entity_ref,
        application_id=application_id,
        status="pending",
        purpose=purpose,
        scope={"fi_types": data.get("fi_types"), "months": months,
               "frequency": data.get("frequency")},
        accounts=[],
        provider=conn.provider,
        expires_at=_parse_dt(data.get("expires_at")),
    )
    db.add(consent)
    db.commit()
    db.refresh(consent)
    return consent


def sync_consent_status(db: Session, consent_id: int, *, mode: Optional[str] = None) -> ConsentArtifact:
    consent = db.query(ConsentArtifact).get(consent_id)
    if consent is None:
        raise ValueError("consent not found")
    # Expiry takes precedence over provider status.
    if consent.expires_at and consent.expires_at <= datetime.utcnow() and consent.status not in ("revoked", "expired"):
        consent.status = "expired"
        db.commit()
        db.refresh(consent)
        return consent
    if consent.status in ("revoked", "expired"):
        return consent
    conn = get_connector(db, "account_aggregator", mode=mode)
    resp = conn.call("get_consent_status", {"consent_handle": consent.handle}, db=db)
    if resp.success:
        upstream = (resp.data.get("status") or "").upper()
        if upstream == "ACTIVE":
            consent.status = "active"
            consent.activated_at = consent.activated_at or datetime.utcnow()
        elif upstream == "REJECTED":
            consent.status = "rejected"
        elif upstream == "REVOKED":
            consent.status = "revoked"
            consent.revoked_at = datetime.utcnow()
        db.commit()
        db.refresh(consent)
    return consent


def revoke_consent(db: Session, consent_id: int, *, mode: Optional[str] = None) -> ConsentArtifact:
    consent = db.query(ConsentArtifact).get(consent_id)
    if consent is None:
        raise ValueError("consent not found")
    conn = get_connector(db, "account_aggregator", mode=mode)
    conn.call("revoke_consent", {"consent_handle": consent.handle}, db=db)
    consent.status = "revoked"
    consent.revoked_at = datetime.utcnow()
    db.commit()
    db.refresh(consent)
    return consent


def discover_accounts(db: Session, consent_id: int, *, mode: Optional[str] = None) -> List[Dict[str, Any]]:
    consent = db.query(ConsentArtifact).get(consent_id)
    if consent is None:
        raise ValueError("consent not found")
    if consent.status != "active":
        raise ValueError(f"consent is not active (status={consent.status})")
    conn = get_connector(db, "account_aggregator", mode=mode)
    resp = conn.call("discover_accounts", {"entity_ref": consent.entity_ref}, db=db)
    if not resp.success:
        raise ValueError(resp.error or "account discovery failed")
    accounts = resp.data.get("accounts", [])
    consent.accounts = accounts
    db.commit()
    return accounts


# ---------------------------------------------------------------------------
# Statement import
# ---------------------------------------------------------------------------
def import_statement(
    db: Session,
    *,
    entity_ref: str,
    account_ref: str,
    months: int = 12,
    consent_id: Optional[int] = None,
    application_id: Optional[int] = None,
    account_type: Optional[str] = None,
    bank_name: Optional[str] = None,
    mode: Optional[str] = None,
) -> BankStatement:
    """Fetch and persist a bank statement (header + transactions)."""
    if consent_id is not None:
        consent = db.query(ConsentArtifact).get(consent_id)
        if consent is None or consent.status != "active":
            raise ValueError("a valid active consent is required to import statements")

    conn = get_connector(db, "account_aggregator", mode=mode)
    resp = conn.call("fetch_statement", {
        "entity_ref": entity_ref, "account_ref": account_ref, "months": months,
        "account_type": account_type, "bank_name": bank_name,
    }, db=db)
    if not resp.success:
        raise ValueError(resp.error or "statement fetch failed")
    data = resp.data

    stmt = BankStatement(
        entity_ref=entity_ref,
        application_id=application_id,
        consent_id=consent_id,
        account_ref=account_ref,
        account_type=data.get("account_type"),
        bank_name=data.get("bank_name"),
        currency=data.get("currency", "INR"),
        from_date=_parse_dt(data.get("from_date")),
        to_date=_parse_dt(data.get("to_date")),
        opening_balance=data.get("opening_balance"),
        closing_balance=data.get("closing_balance"),
        source="account_aggregator",
        provider=conn.provider,
        txn_count=len(data.get("transactions", [])),
    )
    db.add(stmt)
    db.flush()  # assign stmt.id

    for t in data.get("transactions", []):
        db.add(BankTransaction(
            statement_id=stmt.id,
            txn_date=_parse_dt(t.get("txn_date")) or datetime.utcnow(),
            amount=t.get("amount", 0.0),
            direction=t.get("direction", "debit"),
            balance=t.get("balance"),
            narration=t.get("narration"),
            category=t.get("category"),
            counterparty=t.get("counterparty"),
            mode=t.get("mode"),
            reference=t.get("reference"),
            is_recurring=bool(t.get("is_recurring", False)),
        ))
    db.commit()
    db.refresh(stmt)
    return stmt


def statement_to_dict(stmt: BankStatement, *, with_transactions: bool = False, db: Optional[Session] = None) -> Dict[str, Any]:
    out = {
        "id": stmt.id,
        "entity_ref": stmt.entity_ref,
        "application_id": stmt.application_id,
        "consent_id": stmt.consent_id,
        "account_ref": stmt.account_ref,
        "account_type": stmt.account_type,
        "bank_name": stmt.bank_name,
        "currency": stmt.currency,
        "from_date": stmt.from_date.isoformat() if stmt.from_date else None,
        "to_date": stmt.to_date.isoformat() if stmt.to_date else None,
        "opening_balance": stmt.opening_balance,
        "closing_balance": stmt.closing_balance,
        "txn_count": stmt.txn_count,
        "provider": stmt.provider,
    }
    if with_transactions and db is not None:
        rows = db.query(BankTransaction).filter(BankTransaction.statement_id == stmt.id).order_by(BankTransaction.txn_date).all()
        out["transactions"] = [{
            "txn_date": r.txn_date.isoformat() if r.txn_date else None,
            "amount": r.amount, "direction": r.direction, "balance": r.balance,
            "category": r.category, "counterparty": r.counterparty, "mode": r.mode,
            "narration": r.narration, "is_recurring": r.is_recurring,
        } for r in rows]
    return out


def consent_to_dict(c: ConsentArtifact) -> Dict[str, Any]:
    return {
        "id": c.id, "handle": c.handle, "entity_ref": c.entity_ref,
        "application_id": c.application_id, "status": c.status, "purpose": c.purpose,
        "scope": c.scope, "accounts": c.accounts, "provider": c.provider,
        "created_at": c.created_at.isoformat() if c.created_at else None,
        "activated_at": c.activated_at.isoformat() if c.activated_at else None,
        "expires_at": c.expires_at.isoformat() if c.expires_at else None,
        "revoked_at": c.revoked_at.isoformat() if c.revoked_at else None,
    }
