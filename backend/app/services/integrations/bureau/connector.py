"""Credit Bureau connector interface + providers.

Supports multiple bureau providers (mock CIBIL-style + Experian-style sandbox)
behind one interface and **normalizes** their differing raw shapes into a single
canonical response via :func:`normalize`, so downstream code never branches on
which bureau answered. Retrieves business score, director credit, defaults, loan
history, outstanding, DPD history, guarantees, utilization, enquiries and
tradelines.
"""

from __future__ import annotations

from datetime import date
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
    "get_business_score", "get_director_credit", "get_defaults", "get_loan_history",
    "get_outstanding", "get_dpd_history", "get_guarantees", "get_utilization",
    "get_enquiries", "get_tradelines", "get_full_report",
]


def normalize(raw: Dict[str, Any], *, bureau: str) -> Dict[str, Any]:
    """Normalize a bureau's raw report into the canonical shape.

    Different bureaus name the same field differently (``score`` vs
    ``creditScore``, ``dpd`` vs ``daysPastDue``). This collapses them so callers
    see one schema regardless of provider.
    """
    score = raw.get("score", raw.get("creditScore", raw.get("credit_score")))
    grade = raw.get("grade") or _grade_for(score)
    return {
        "bureau": bureau,
        "score": score,
        "grade": grade,
        "score_range": raw.get("score_range", raw.get("scoreRange", "300-900")),
        "as_of": raw.get("as_of", raw.get("asOf")),
    }


def _grade_for(score: Any) -> str:
    if score is None:
        return "NA"
    s = int(score)
    if s >= 800:
        return "AAA"
    if s >= 750:
        return "AA"
    if s >= 700:
        return "A"
    if s >= 650:
        return "BBB"
    if s >= 600:
        return "BB"
    return "B"


class BureauConnector(BaseConnector):
    category = ConnectorCategory.CREDIT_BUREAU
    connector_key = "bureau"

    def operations(self) -> List[str]:
        return list(_OPERATIONS)

    def _execute(self, request: ConnectorRequest) -> Any:
        op = request.operation
        if op not in _OPERATIONS:
            raise ProviderError(f"unknown bureau operation '{op}'", provider=self.provider, operation=op)
        entity = (request.params.get("entity_ref") or request.params.get("pan")
                  or request.params.get("gstin"))
        if not entity:
            raise ProviderError("entity_ref/pan is required", provider=self.provider, operation=op)
        return getattr(self, f"fetch_{op}")(str(entity), request.params)


class MockBureauConnector(BureauConnector):
    # Which bureau this mock emulates (drives raw field naming).
    bureau_name = "MockBureau"

    def __init__(self, **kwargs):
        kwargs.setdefault("provider", "mock_bureau")
        super().__init__(**kwargs)

    def _profile(self, entity: str) -> Dict[str, Any]:
        rng = mockdata.rng_for("bureau", self.bureau_name, entity)
        score = rng.randint(560, 840)
        n_loans = rng.randint(1, 6)
        return {"score": score, "n_loans": n_loans, "rng": rng}

    def fetch_get_business_score(self, entity: str, params: Dict[str, Any]) -> Any:
        p = self._profile(entity)
        raw = {"score": p["score"], "as_of": date.today().isoformat()}
        return {"entity_ref": entity, **normalize(raw, bureau=self.bureau_name)}

    def fetch_get_director_credit(self, entity: str, params: Dict[str, Any]) -> Any:
        rng = mockdata.rng_for("bureau-dir", self.bureau_name, entity)
        directors = []
        for i in range(rng.randint(1, 3)):
            directors.append({
                "name": mockdata.person_name(mockdata.rng_for("bd", entity, str(i))),
                "score": rng.randint(600, 830),
                "active_loans": rng.randint(0, 4),
            })
        return {"entity_ref": entity, "directors": directors}

    def fetch_get_defaults(self, entity: str, params: Dict[str, Any]) -> Any:
        p = self._profile(entity)
        rng = p["rng"]
        # Lower score → more likely to have defaults.
        n = 0 if p["score"] > 720 else rng.randint(0, 2)
        defaults = [{
            "lender": rng.choice(["HDFC", "SBI", "Bajaj Finserv", "ICICI"]),
            "amount": round(rng.uniform(50000, 2000000), 2),
            "date": mockdata.iso(date(rng.randint(2019, 2024), rng.randint(1, 12), rng.randint(1, 28))),
            "status": rng.choice(["settled", "written_off", "overdue"]),
        } for _ in range(n)]
        return {"entity_ref": entity, "defaults": defaults, "default_count": n}

    def fetch_get_loan_history(self, entity: str, params: Dict[str, Any]) -> Any:
        return {"entity_ref": entity, "loans": self._loans(entity)}

    def _loans(self, entity: str) -> List[Dict[str, Any]]:
        p = self._profile(entity)
        rng = p["rng"]
        loans = []
        for i in range(p["n_loans"]):
            lrng = mockdata.rng_for("bl", entity, str(i))
            sanctioned = round(lrng.uniform(200000, 10000000), 2)
            outstanding = round(sanctioned * lrng.uniform(0.0, 0.9), 2)
            loans.append({
                "loan_id": f"LN{lrng.randint(10**6, 10**7)}",
                "lender": lrng.choice(["HDFC", "SBI", "Axis", "Kotak", "Bajaj Finserv"]),
                "type": lrng.choice(["term_loan", "working_capital", "od", "equipment"]),
                "sanctioned": sanctioned,
                "outstanding": outstanding,
                "status": "closed" if outstanding == 0 else "active",
                "opened": mockdata.iso(date(lrng.randint(2017, 2023), lrng.randint(1, 12), lrng.randint(1, 28))),
            })
        return loans

    def fetch_get_outstanding(self, entity: str, params: Dict[str, Any]) -> Any:
        loans = self._loans(entity)
        total = round(sum(l["outstanding"] for l in loans), 2)
        return {"entity_ref": entity, "total_outstanding": total,
                "active_loans": sum(1 for l in loans if l["status"] == "active")}

    def fetch_get_dpd_history(self, entity: str, params: Dict[str, Any]) -> Any:
        p = self._profile(entity)
        rng = p["rng"]
        buckets = []
        for m in mockdata.month_starts(12, date.today()):
            # Higher score → mostly 0 DPD.
            if p["score"] > 750:
                dpd = 0 if rng.random() < 0.95 else rng.choice([1, 5])
            elif p["score"] > 680:
                dpd = 0 if rng.random() < 0.8 else rng.choice([1, 15, 30])
            else:
                dpd = rng.choice([0, 0, 15, 30, 60, 90])
            buckets.append({"period": m.strftime("%m-%Y"), "dpd": dpd})
        max_dpd = max(b["dpd"] for b in buckets)
        return {"entity_ref": entity, "dpd_history": buckets, "max_dpd": max_dpd,
                "months_delinquent": sum(1 for b in buckets if b["dpd"] > 0)}

    def fetch_get_guarantees(self, entity: str, params: Dict[str, Any]) -> Any:
        rng = mockdata.rng_for("bureau-g", self.bureau_name, entity)
        n = rng.randint(0, 2)
        gs = [{
            "beneficiary": rng.choice(["Supplier Co", "Group Company", "Associate Ltd"]),
            "amount": round(rng.uniform(500000, 5000000), 2),
            "type": rng.choice(["financial", "performance"]),
        } for _ in range(n)]
        return {"entity_ref": entity, "guarantees": gs,
                "total_guaranteed": round(sum(g["amount"] for g in gs), 2)}

    def fetch_get_utilization(self, entity: str, params: Dict[str, Any]) -> Any:
        rng = mockdata.rng_for("bureau-u", self.bureau_name, entity)
        limit = round(rng.uniform(1000000, 20000000), 2)
        used = round(limit * rng.uniform(0.1, 0.95), 2)
        return {"entity_ref": entity, "credit_limit": limit, "utilized": used,
                "utilization_ratio": round(used / limit, 4) if limit else 0.0}

    def fetch_get_enquiries(self, entity: str, params: Dict[str, Any]) -> Any:
        rng = mockdata.rng_for("bureau-e", self.bureau_name, entity)
        n = rng.randint(0, 8)
        enq = [{
            "lender": rng.choice(["HDFC", "SBI", "Axis", "Fintech Co"]),
            "purpose": rng.choice(["term_loan", "credit_card", "working_capital"]),
            "date": mockdata.iso(date(2024, rng.randint(1, 12), rng.randint(1, 28))),
        } for _ in range(n)]
        return {"entity_ref": entity, "enquiries": enq, "enquiry_count_6m": n}

    def fetch_get_tradelines(self, entity: str, params: Dict[str, Any]) -> Any:
        loans = self._loans(entity)
        return {"entity_ref": entity, "tradelines": [
            {"account": l["loan_id"], "lender": l["lender"], "type": l["type"],
             "balance": l["outstanding"], "status": l["status"]} for l in loans]}

    def fetch_get_full_report(self, entity: str, params: Dict[str, Any]) -> Any:
        return {
            "entity_ref": entity,
            "bureau": self.bureau_name,
            "score": self.fetch_get_business_score(entity, params),
            "defaults": self.fetch_get_defaults(entity, params),
            "outstanding": self.fetch_get_outstanding(entity, params),
            "dpd": self.fetch_get_dpd_history(entity, params),
            "utilization": self.fetch_get_utilization(entity, params),
            "enquiries": self.fetch_get_enquiries(entity, params),
            "tradelines": self.fetch_get_tradelines(entity, params),
            "guarantees": self.fetch_get_guarantees(entity, params),
        }


class SandboxBureauConnector(SandboxProviderMixin, MockBureauConnector):
    """Emulates a *different* bureau to prove normalization works cross-provider."""

    bureau_name = "SandboxBureau"
    sandbox_secret = "bureau.sandbox_token"

    def __init__(self, **kwargs):
        kwargs["provider"] = "sandbox_bureau"
        super().__init__(**kwargs)


class ProductionBureauConnector(ProductionProviderMixin, BureauConnector):
    production_secret = "bureau.api_key"

    def __init__(self, **kwargs):
        kwargs.setdefault("provider", "production_bureau")
        super().__init__(**kwargs)
