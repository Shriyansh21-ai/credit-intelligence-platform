"""ERP connector interface + providers (Milestone 7).

One connector, many ERP/accounting systems (SAP, Oracle ERP, Microsoft Dynamics,
Zoho Books, QuickBooks, Tally) selected by the ``system`` param/config. Imports
financial statements, invoices, purchase orders, inventory, receivables,
payables, the general ledger and the trial balance — all normalized to a common
shape so the platform is ERP-agnostic.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Dict, List

from backend.app.services.integrations import mockdata
from backend.app.services.integrations.base.connector import BaseConnector
from backend.app.services.integrations.base.exceptions import ProviderError
from backend.app.services.integrations.base.providers import (
    ProductionProviderMixin,
    SandboxProviderMixin,
)
from backend.app.services.integrations.base.types import ConnectorCategory, ConnectorRequest

SUPPORTED_SYSTEMS = ["sap", "oracle", "dynamics", "zoho", "quickbooks", "tally"]

_OPERATIONS = [
    "get_financial_statements", "get_invoices", "get_purchase_orders", "get_inventory",
    "get_receivables", "get_payables", "get_general_ledger", "get_trial_balance",
]


class ERPConnector(BaseConnector):
    category = ConnectorCategory.ERP
    connector_key = "erp"

    def __init__(self, **kwargs):
        self.system = str(kwargs.pop("system", None) or (kwargs.get("config") or {}).get("system") or "tally").lower()
        super().__init__(**kwargs)

    def operations(self) -> List[str]:
        return list(_OPERATIONS)

    def _execute(self, request: ConnectorRequest) -> Any:
        op = request.operation
        if op not in _OPERATIONS:
            raise ProviderError(f"unknown ERP operation '{op}'", provider=self.provider, operation=op)
        system = str(request.params.get("system") or self.system).lower()
        if system not in SUPPORTED_SYSTEMS:
            raise ProviderError(f"unsupported ERP system '{system}'", provider=self.provider, operation=op)
        entity = request.params.get("entity_ref") or request.params.get("company_id")
        if not entity:
            raise ProviderError("entity_ref is required", provider=self.provider, operation=op)
        return getattr(self, f"fetch_{op}")(str(entity), system, request.params)


class MockERPConnector(ERPConnector):
    def __init__(self, **kwargs):
        kwargs.setdefault("provider", "mock_erp")
        super().__init__(**kwargs)

    def _scale(self, entity: str, system: str) -> Dict[str, Any]:
        rng = mockdata.rng_for("erp", system, entity)
        revenue = rng.choice([20, 50, 120, 300]) * 1_000_000.0
        return {"rng": rng, "revenue": revenue}

    def fetch_get_financial_statements(self, entity: str, system: str, params: Dict[str, Any]) -> Any:
        s = self._scale(entity, system)
        rng = s["rng"]
        revenue = s["revenue"]
        years = []
        this_year = date.today().year
        for y in range(this_year - 3, this_year):
            revenue *= (1 + rng.uniform(-0.08, 0.22))
            cogs = revenue * rng.uniform(0.55, 0.78)
            opex = revenue * rng.uniform(0.1, 0.2)
            ebitda = revenue - cogs - opex
            pat = ebitda * rng.uniform(0.4, 0.75)
            years.append({
                "financial_year": f"{y}-{y+1}",
                "revenue": round(revenue, 2), "cogs": round(cogs, 2),
                "ebitda": round(ebitda, 2), "pat": round(pat, 2),
                "total_assets": round(revenue * rng.uniform(0.9, 1.6), 2),
                "total_liabilities": round(revenue * rng.uniform(0.4, 1.0), 2),
            })
        return {"entity_ref": entity, "system": system, "statements": years}

    def fetch_get_invoices(self, entity: str, system: str, params: Dict[str, Any]) -> Any:
        s = self._scale(entity, system)
        rng = s["rng"]
        n = rng.randint(15, 40)
        invoices = []
        for i in range(n):
            irng = mockdata.rng_for("erp-inv", system, entity, str(i))
            amt = round(s["revenue"] / 200 * irng.uniform(0.3, 3.0), 2)
            issued = date.today() - timedelta(days=irng.randint(1, 180))
            paid = irng.random() < 0.7
            invoices.append({
                "invoice_no": f"INV-{irng.randint(1000, 9999)}",
                "customer": f"Customer {irng.randint(1, 60)}",
                "amount": amt,
                "issued_date": issued.isoformat(),
                "due_date": (issued + timedelta(days=irng.choice([30, 45, 60]))).isoformat(),
                "status": "paid" if paid else "outstanding",
            })
        return {"entity_ref": entity, "system": system, "invoices": invoices,
                "total_value": round(sum(i["amount"] for i in invoices), 2)}

    def fetch_get_purchase_orders(self, entity: str, system: str, params: Dict[str, Any]) -> Any:
        s = self._scale(entity, system)
        rng = s["rng"]
        n = rng.randint(8, 25)
        pos = []
        for i in range(n):
            prng = mockdata.rng_for("erp-po", system, entity, str(i))
            pos.append({
                "po_no": f"PO-{prng.randint(1000, 9999)}",
                "vendor": f"Vendor {prng.randint(1, 40)}",
                "amount": round(s["revenue"] / 300 * prng.uniform(0.2, 2.5), 2),
                "status": prng.choice(["open", "received", "closed"]),
                "date": (date.today() - timedelta(days=prng.randint(1, 200))).isoformat(),
            })
        return {"entity_ref": entity, "system": system, "purchase_orders": pos}

    def fetch_get_inventory(self, entity: str, system: str, params: Dict[str, Any]) -> Any:
        s = self._scale(entity, system)
        rng = s["rng"]
        value = round(s["revenue"] * rng.uniform(0.08, 0.25), 2)
        return {"entity_ref": entity, "system": system, "inventory_value": value,
                "sku_count": rng.randint(20, 500),
                "inventory_days": round(rng.uniform(25, 120), 1)}

    def fetch_get_receivables(self, entity: str, system: str, params: Dict[str, Any]) -> Any:
        s = self._scale(entity, system)
        rng = s["rng"]
        total = round(s["revenue"] * rng.uniform(0.1, 0.3), 2)
        aging = {"0-30": 0.5, "31-60": 0.25, "61-90": 0.15, "90+": 0.10}
        buckets = {k: round(total * v * rng.uniform(0.7, 1.3), 2) for k, v in aging.items()}
        return {"entity_ref": entity, "system": system, "total_receivables": total,
                "aging": buckets, "dso_days": round(rng.uniform(30, 110), 1)}

    def fetch_get_payables(self, entity: str, system: str, params: Dict[str, Any]) -> Any:
        s = self._scale(entity, system)
        rng = s["rng"]
        total = round(s["revenue"] * rng.uniform(0.08, 0.22), 2)
        return {"entity_ref": entity, "system": system, "total_payables": total,
                "dpo_days": round(rng.uniform(25, 90), 1)}

    def fetch_get_general_ledger(self, entity: str, system: str, params: Dict[str, Any]) -> Any:
        s = self._scale(entity, system)
        rng = s["rng"]
        accounts = ["Cash", "Bank", "Sales", "Purchases", "Salaries", "Rent", "Interest", "Tax"]
        entries = []
        for i in range(rng.randint(20, 40)):
            grng = mockdata.rng_for("erp-gl", system, entity, str(i))
            entries.append({
                "date": (date.today() - timedelta(days=grng.randint(1, 365))).isoformat(),
                "account": grng.choice(accounts),
                "debit": round(grng.uniform(0, 500000), 2) if grng.random() < 0.5 else 0.0,
                "credit": round(grng.uniform(0, 500000), 2) if grng.random() < 0.5 else 0.0,
            })
        return {"entity_ref": entity, "system": system, "entries": entries}

    def fetch_get_trial_balance(self, entity: str, system: str, params: Dict[str, Any]) -> Any:
        s = self._scale(entity, system)
        rng = s["rng"]
        rows = []
        total_debit = total_credit = 0.0
        for acct in ["Cash", "Bank", "Receivables", "Inventory", "Payables", "Loans", "Capital", "Sales"]:
            debit = round(rng.uniform(0, s["revenue"] * 0.2), 2) if rng.random() < 0.5 else 0.0
            credit = round(rng.uniform(0, s["revenue"] * 0.2), 2) if debit == 0 else 0.0
            total_debit += debit
            total_credit += credit
            rows.append({"account": acct, "debit": debit, "credit": credit})
        # Force balance by adjusting the last row.
        diff = round(total_debit - total_credit, 2)
        if diff > 0:
            rows[-1]["credit"] = round(rows[-1]["credit"] + diff, 2)
        else:
            rows[-1]["debit"] = round(rows[-1]["debit"] - diff, 2)
        return {"entity_ref": entity, "system": system, "rows": rows,
                "total_debit": round(sum(r["debit"] for r in rows), 2),
                "total_credit": round(sum(r["credit"] for r in rows), 2)}


class SandboxERPConnector(SandboxProviderMixin, MockERPConnector):
    sandbox_secret = "erp.sandbox_token"

    def __init__(self, **kwargs):
        kwargs["provider"] = "sandbox_erp"
        super().__init__(**kwargs)


class ProductionERPConnector(ProductionProviderMixin, ERPConnector):
    production_secret = "erp.api_key"

    def __init__(self, **kwargs):
        kwargs.setdefault("provider", "production_erp")
        super().__init__(**kwargs)
