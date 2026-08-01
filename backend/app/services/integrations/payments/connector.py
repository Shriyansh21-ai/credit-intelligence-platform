"""Payments connector interface + providers.

Abstracts payment/transaction rails (UPI, NEFT, RTGS, IMPS, SWIFT, card
merchant) behind the common interface and exposes analytics over payment
behaviour, settlement delays, transaction health, counterparty risk and the
payment network.
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

PAYMENT_RAILS = ["upi", "neft", "rtgs", "imps", "swift", "card", "merchant"]

_OPERATIONS = [
    "get_payment_behaviour", "get_settlement_delays", "get_transaction_health",
    "get_counterparty_risk", "get_payment_network",
]


class PaymentsConnector(BaseConnector):
    category = ConnectorCategory.PAYMENT
    connector_key = "payments"

    def operations(self) -> List[str]:
        return list(_OPERATIONS)

    def _execute(self, request: ConnectorRequest) -> Any:
        op = request.operation
        if op not in _OPERATIONS:
            raise ProviderError(f"unknown payments operation '{op}'", provider=self.provider, operation=op)
        entity = request.params.get("entity_ref") or request.params.get("merchant_id")
        if not entity:
            raise ProviderError("entity_ref is required", provider=self.provider, operation=op)
        return getattr(self, f"fetch_{op}")(str(entity), request.params)


class MockPaymentsConnector(PaymentsConnector):
    def __init__(self, **kwargs):
        kwargs.setdefault("provider", "mock_payments")
        super().__init__(**kwargs)

    def _profile(self, entity: str) -> Dict[str, Any]:
        rng = mockdata.rng_for("pay", entity)
        monthly_volume = rng.choice([2, 8, 20, 60]) * 100000.0
        reliability = rng.uniform(0.7, 0.99)
        return {"rng": rng, "monthly_volume": monthly_volume, "reliability": reliability}

    def fetch_get_payment_behaviour(self, entity: str, params: Dict[str, Any]) -> Any:
        p = self._profile(entity)
        rng = p["rng"]
        rail_mix = {}
        remaining = 1.0
        for rail in PAYMENT_RAILS[:-1]:
            share = round(remaining * rng.uniform(0.05, 0.4), 3)
            rail_mix[rail] = share
            remaining = max(0.0, remaining - share)
        rail_mix[PAYMENT_RAILS[-1]] = round(remaining, 3)
        return {
            "entity_ref": entity,
            "monthly_volume": round(p["monthly_volume"], 2),
            "avg_ticket_size": round(p["monthly_volume"] / rng.randint(50, 400), 2),
            "on_time_ratio": round(p["reliability"], 4),
            "rail_mix": rail_mix,
        }

    def fetch_get_settlement_delays(self, entity: str, params: Dict[str, Any]) -> Any:
        p = self._profile(entity)
        rng = p["rng"]
        rows = []
        for m in mockdata.month_starts(6, date.today()):
            avg_delay = round((1 - p["reliability"]) * rng.uniform(1, 8), 2)
            rows.append({"period": m.strftime("%m-%Y"), "avg_settlement_days": avg_delay,
                         "delayed_ratio": round((1 - p["reliability"]) * rng.uniform(0.5, 1.5), 4)})
        return {"entity_ref": entity, "settlement_delays": rows,
                "avg_settlement_days": round(sum(r["avg_settlement_days"] for r in rows) / len(rows), 2)}

    def fetch_get_transaction_health(self, entity: str, params: Dict[str, Any]) -> Any:
        p = self._profile(entity)
        rng = p["rng"]
        success = round(p["reliability"], 4)
        failure = round(1 - success, 4)
        score = round(min(100, max(0, success * 100 - failure * 40)), 1)
        return {"entity_ref": entity, "success_rate": success, "failure_rate": failure,
                "chargeback_ratio": round(rng.uniform(0, 0.03), 4), "health_score": score}

    def fetch_get_counterparty_risk(self, entity: str, params: Dict[str, Any]) -> Any:
        p = self._profile(entity)
        rng = p["rng"]
        counterparties = []
        for i in range(rng.randint(3, 8)):
            crng = mockdata.rng_for("pay-cp", entity, str(i))
            risk = crng.choice(["low", "low", "medium", "high"])
            counterparties.append({
                "name": f"Counterparty {crng.randint(1, 99)}",
                "share": round(crng.uniform(0.02, 0.3), 3),
                "risk": risk,
            })
        concentration = round(max(c["share"] for c in counterparties), 3)
        return {"entity_ref": entity, "counterparties": counterparties,
                "concentration": concentration,
                "high_risk_count": sum(1 for c in counterparties if c["risk"] == "high")}

    def fetch_get_payment_network(self, entity: str, params: Dict[str, Any]) -> Any:
        p = self._profile(entity)
        rng = p["rng"]
        nodes = rng.randint(5, 15)
        edges = []
        for i in range(nodes):
            nrng = mockdata.rng_for("pay-net", entity, str(i))
            edges.append({
                "counterparty": f"Node {i+1}",
                "direction": nrng.choice(["inbound", "outbound", "both"]),
                "volume": round(p["monthly_volume"] * nrng.uniform(0.01, 0.2), 2),
                "txn_count": nrng.randint(1, 100),
            })
        return {"entity_ref": entity, "node_count": nodes, "edges": edges,
                "total_network_volume": round(sum(e["volume"] for e in edges), 2)}


class SandboxPaymentsConnector(SandboxProviderMixin, MockPaymentsConnector):
    sandbox_secret = "payments.sandbox_token"

    def __init__(self, **kwargs):
        kwargs["provider"] = "sandbox_payments"
        super().__init__(**kwargs)


class ProductionPaymentsConnector(ProductionProviderMixin, PaymentsConnector):
    production_secret = "payments.api_key"

    def __init__(self, **kwargs):
        kwargs.setdefault("provider", "production_payments")
        super().__init__(**kwargs)
