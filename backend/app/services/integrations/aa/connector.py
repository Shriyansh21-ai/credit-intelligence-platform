"""Account Aggregator connector interface + providers.

Implements the AA flow — consent request, account discovery, and financial
information (bank statement) fetch — behind the common connector interface. The
mock produces a realistic, seeded transaction stream (salary credits, vendor
payments, EMIs, tax, collections, occasional cheque bounces, recurring debits)
that the statement-analytics engine consumes.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Dict, List

from backend.app.services.integrations import mockdata
from backend.app.services.integrations.base.connector import BaseConnector
from backend.app.services.integrations.base.exceptions import ProviderError
from backend.app.services.integrations.base.providers import (
    ProductionProviderMixin,
    SandboxProviderMixin,
)
from backend.app.services.integrations.base.types import ConnectorCategory, ConnectorRequest

_OPERATIONS = [
    "create_consent", "get_consent_status", "revoke_consent",
    "discover_accounts", "fetch_statement",
]

_BANKS = ["HDFC Bank", "SBI", "ICICI Bank", "Axis Bank", "Kotak Mahindra Bank"]


class AAConnector(BaseConnector):
    category = ConnectorCategory.ACCOUNT_AGGREGATOR
    connector_key = "account_aggregator"

    def operations(self) -> List[str]:
        return list(_OPERATIONS)

    def _execute(self, request: ConnectorRequest) -> Any:
        op = request.operation
        if op not in _OPERATIONS:
            raise ProviderError(f"unknown AA operation '{op}'", provider=self.provider, operation=op)
        return getattr(self, f"fetch_{op}")(request.params)


class MockAAConnector(AAConnector):
    def __init__(self, **kwargs):
        kwargs.setdefault("provider", "mock_aa")
        super().__init__(**kwargs)

    # -- consent -----------------------------------------------------------
    def fetch_create_consent(self, params: Dict[str, Any]) -> Any:
        entity_ref = params.get("entity_ref") or params.get("customer_id") or "unknown"
        rng = mockdata.rng_for("aa-consent", entity_ref, str(params.get("purpose", "lending")))
        handle = f"CONSENT-{rng.randint(10**9, 10**10 - 1)}"
        fetch_months = int(params.get("months", 12))
        return {
            "consent_handle": handle,
            "entity_ref": entity_ref,
            "status": "PENDING",
            "purpose": params.get("purpose", "Credit assessment"),
            "fi_types": params.get("fi_types", ["DEPOSIT"]),
            "fetch_window_months": fetch_months,
            "frequency": params.get("frequency", "ONE_TIME"),
            "created_at": mockdata.now_utc().isoformat(),
            "expires_at": (mockdata.now_utc() + timedelta(days=int(params.get("validity_days", 365)))).isoformat(),
        }

    def fetch_get_consent_status(self, params: Dict[str, Any]) -> Any:
        handle = params.get("consent_handle") or params.get("entity_ref")
        if not handle:
            raise ProviderError("consent_handle is required", provider=self.provider, operation="get_consent_status")
        rng = mockdata.rng_for("aa-status", str(handle))
        # Mock: consent activates deterministically for most handles.
        status = "ACTIVE" if rng.random() < 0.9 else "REJECTED"
        return {"consent_handle": handle, "status": status}

    def fetch_revoke_consent(self, params: Dict[str, Any]) -> Any:
        handle = params.get("consent_handle")
        if not handle:
            raise ProviderError("consent_handle is required", provider=self.provider, operation="revoke_consent")
        return {"consent_handle": handle, "status": "REVOKED", "revoked_at": mockdata.now_utc().isoformat()}

    # -- discovery ---------------------------------------------------------
    def fetch_discover_accounts(self, params: Dict[str, Any]) -> Any:
        entity_ref = params.get("entity_ref") or "unknown"
        rng = mockdata.rng_for("aa-discover", entity_ref)
        n = rng.randint(1, 3)
        accounts = []
        for i in range(n):
            arng = mockdata.rng_for("aa-acct", entity_ref, str(i))
            accounts.append({
                "account_ref": f"XXXX{arng.randint(1000, 9999)}",
                "bank_name": arng.choice(_BANKS),
                "account_type": arng.choice(["current", "savings", "od", "cc"]),
                "ifsc": f"{''.join(arng.choice('ABCDEFGHIJK') for _ in range(4))}0{arng.randint(100000, 999999)}",
                "masked_number": f"XXXXXX{arng.randint(1000, 9999)}",
            })
        return {"entity_ref": entity_ref, "accounts": accounts}

    # -- financial information (statement) ---------------------------------
    def fetch_fetch_statement(self, params: Dict[str, Any]) -> Any:
        account_ref = params.get("account_ref")
        entity_ref = params.get("entity_ref") or "unknown"
        if not account_ref:
            raise ProviderError("account_ref is required", provider=self.provider, operation="fetch_statement")
        months = int(params.get("months", 12))
        return self._statement(entity_ref, str(account_ref), months, params)

    def _statement(self, entity_ref: str, account_ref: str, months: int, params: Dict[str, Any]) -> Dict[str, Any]:
        rng = mockdata.rng_for("aa-stmt", entity_ref, account_ref)
        bank = params.get("bank_name") or rng.choice(_BANKS)
        acct_type = params.get("account_type") or rng.choice(["current", "savings"])

        # Business profile drives the transaction stream.
        monthly_inflow = rng.choice([5, 12, 25, 50, 90]) * 100000.0
        salary_run = rng.random() < 0.6              # pays salaries?
        n_employees = rng.randint(3, 25) if salary_run else 0
        has_emi = rng.random() < 0.7
        emi_amount = round(monthly_inflow * rng.uniform(0.03, 0.12), 2) if has_emi else 0.0

        end = date.today().replace(day=1) - timedelta(days=1)
        start = mockdata.month_starts(months, end)[0]
        balance = round(monthly_inflow * rng.uniform(0.3, 1.2), 2)
        opening_balance = balance
        txns: List[Dict[str, Any]] = []

        cur = start
        while cur <= end:
            month_seed = mockdata.rng_for("aa-month", entity_ref, account_ref, cur.strftime("%Y%m"))
            # Inflows: collections from customers across the month.
            inflow = monthly_inflow * (1 + month_seed.uniform(-0.2, 0.25))
            n_collections = month_seed.randint(4, 12)
            for _ in range(n_collections):
                day = month_seed.randint(1, 28)
                amt = round(inflow / n_collections * month_seed.uniform(0.5, 1.5), 2)
                balance += amt
                txns.append(self._txn(cur, day, amt, "credit", balance, "collection",
                                      month_seed, counterparty=f"Customer {month_seed.randint(1,999)}"))
            # Salary payouts (25th-ish).
            if salary_run:
                for e in range(n_employees):
                    sal = round(month_seed.uniform(18000, 60000), 2)
                    balance -= sal
                    txns.append(self._txn(cur, month_seed.randint(28, 28), sal, "debit", balance,
                                          "salary", month_seed, counterparty=f"Employee {e+1}", mode="neft"))
            # Vendor payments.
            for _ in range(month_seed.randint(3, 8)):
                amt = round(inflow * month_seed.uniform(0.03, 0.12), 2)
                balance -= amt
                txns.append(self._txn(cur, month_seed.randint(1, 28), amt, "debit", balance,
                                      "vendor", month_seed, counterparty=f"Vendor {month_seed.randint(1,50)}"))
            # EMI (recurring).
            if has_emi:
                balance -= emi_amount
                txns.append(self._txn(cur, 5, emi_amount, "debit", balance, "emi", month_seed,
                                      counterparty="Loan EMI", mode="neft", recurring=True))
            # GST / tax payment (quarterly-ish).
            if cur.month % 3 == 0:
                tax = round(inflow * month_seed.uniform(0.02, 0.06), 2)
                balance -= tax
                txns.append(self._txn(cur, 20, tax, "debit", balance, "tax", month_seed,
                                      counterparty="GST Payment", mode="neft"))
            # Occasional cheque bounce (return) — a risk signal.
            if month_seed.random() < 0.12:
                bounce = round(inflow * month_seed.uniform(0.02, 0.08), 2)
                balance -= 0  # bounce itself is a returned inward; represent as flagged debit reversal
                txns.append(self._txn(cur, month_seed.randint(1, 28), bounce, "debit", balance,
                                      "cheque_bounce", month_seed, counterparty="Cheque Return Charges", mode="cheque"))
            # advance month
            y, m = cur.year, cur.month + 1
            if m > 12:
                y, m = y + 1, 1
            cur = date(y, m, 1)

        txns.sort(key=lambda t: t["txn_date"])
        return {
            "entity_ref": entity_ref,
            "account_ref": account_ref,
            "bank_name": bank,
            "account_type": acct_type,
            "currency": "INR",
            "from_date": mockdata.iso(start),
            "to_date": mockdata.iso(end),
            "opening_balance": round(opening_balance, 2),
            "closing_balance": round(balance, 2),
            "transactions": txns,
        }

    @staticmethod
    def _txn(month: date, day: int, amount: float, direction: str, balance: float,
             category: str, rng, *, counterparty: str = "", mode: str = "", recurring: bool = False) -> Dict[str, Any]:
        day = min(day, 28)
        modes = ["upi", "neft", "imps", "rtgs", "cheque", "cash"]
        return {
            "txn_date": date(month.year, month.month, day).isoformat(),
            "amount": round(amount, 2),
            "direction": direction,
            "balance": round(balance, 2),
            "category": category,
            "counterparty": counterparty,
            "mode": mode or rng.choice(modes),
            "reference": f"REF{rng.randint(10**6, 10**7 - 1)}",
            "narration": f"{category.upper()} {counterparty}".strip(),
            "is_recurring": recurring,
        }


class SandboxAAConnector(SandboxProviderMixin, MockAAConnector):
    sandbox_secret = "aa.sandbox_token"

    def __init__(self, **kwargs):
        kwargs["provider"] = "sandbox_aa"
        super().__init__(**kwargs)


class ProductionAAConnector(ProductionProviderMixin, AAConnector):
    production_secret = "aa.api_key"

    def __init__(self, **kwargs):
        kwargs.setdefault("provider", "production_aa")
        super().__init__(**kwargs)
