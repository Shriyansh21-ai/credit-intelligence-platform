"""MCA connector interface + providers.

Retrieves company master data, directors, charges, capital, annual filings
financial statements and the director/company relationship network from the
Ministry of Corporate Affairs. Everything derives from one seeded company record
keyed by CIN, so directors, charges and relationships stay consistent.
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
    "get_company_master", "get_directors", "get_charges", "get_registered_office",
    "get_incorporation", "get_capital", "get_annual_filings", "get_financial_statements",
    "get_director_network", "get_company_relationships",
]


class MCAConnector(BaseConnector):
    category = ConnectorCategory.GOVERNMENT
    connector_key = "mca"

    def operations(self) -> List[str]:
        return list(_OPERATIONS)

    def _execute(self, request: ConnectorRequest) -> Any:
        op = request.operation
        if op not in _OPERATIONS:
            raise ProviderError(f"unknown MCA operation '{op}'", provider=self.provider, operation=op)
        cin = request.params.get("cin") or request.params.get("entity_ref")
        if not cin:
            raise ProviderError("cin is required", provider=self.provider, operation=op)
        return getattr(self, f"fetch_{op}")(str(cin), request.params)


class MockMCAConnector(MCAConnector):
    def __init__(self, **kwargs):
        kwargs.setdefault("provider", "mock_mca")
        super().__init__(**kwargs)

    def _record(self, cin: str) -> Dict[str, Any]:
        rng = mockdata.rng_for("mca", cin)
        inc_year = rng.randint(1998, 2021)
        name = mockdata.company_name(rng) + rng.choice([" Pvt Ltd", " Ltd", " LLP"])
        auth_capital = rng.choice([1, 5, 10, 25, 50]) * 1_000_000.0
        paid_up = auth_capital * rng.uniform(0.4, 1.0)
        n_directors = rng.randint(2, 5)
        directors = []
        for i in range(n_directors):
            drng = mockdata.rng_for("mca-dir", cin, str(i))
            directors.append({
                "din": f"{drng.randint(10000000, 99999999)}",
                "name": mockdata.person_name(drng),
                "designation": "Managing Director" if i == 0 else rng.choice(
                    ["Director", "Whole-time Director", "Independent Director"]),
                "appointment_date": mockdata.iso(date(inc_year + i % 3, drng.randint(1, 12), drng.randint(1, 28))),
                "other_directorships": drng.randint(0, 4),
            })
        _, state = mockdata.state_code(rng)
        return {
            "cin": cin,
            "company_name": name,
            "incorporation_date": mockdata.iso(date(inc_year, rng.randint(1, 12), rng.randint(1, 28))),
            "status": rng.choice(["Active", "Active", "Active", "Under Strike Off", "Dormant"]),
            "class": rng.choice(["Private", "Public"]),
            "category": "Company limited by shares",
            "authorized_capital": round(auth_capital, 2),
            "paid_up_capital": round(paid_up, 2),
            "state": state,
            "city": mockdata.city(rng),
            "roc": f"RoC-{mockdata.city(rng)}",
            "directors": directors,
        }

    def fetch_get_company_master(self, cin: str, params: Dict[str, Any]) -> Any:
        r = self._record(cin)
        return {k: r[k] for k in (
            "cin", "company_name", "incorporation_date", "status", "class",
            "category", "authorized_capital", "paid_up_capital", "roc")}

    def fetch_get_directors(self, cin: str, params: Dict[str, Any]) -> Any:
        return {"cin": cin, "directors": self._record(cin)["directors"]}

    def fetch_get_charges(self, cin: str, params: Dict[str, Any]) -> Any:
        rng = mockdata.rng_for("mca-charges", cin)
        n = rng.randint(0, 4)
        banks = ["HDFC Bank", "SBI", "ICICI Bank", "Axis Bank", "Kotak Mahindra Bank"]
        charges = []
        for i in range(n):
            amt = rng.choice([2, 5, 10, 20]) * 1_000_000.0
            charges.append({
                "charge_id": f"CH{rng.randint(10000, 99999)}",
                "holder": rng.choice(banks),
                "amount": round(amt, 2),
                "status": rng.choice(["Open", "Open", "Satisfied"]),
                "creation_date": mockdata.iso(date(rng.randint(2018, 2024), rng.randint(1, 12), rng.randint(1, 28))),
            })
        open_amt = sum(c["amount"] for c in charges if c["status"] == "Open")
        return {"cin": cin, "charges": charges, "open_charges": sum(1 for c in charges if c["status"] == "Open"),
                "total_open_amount": round(open_amt, 2)}

    def fetch_get_registered_office(self, cin: str, params: Dict[str, Any]) -> Any:
        r = self._record(cin)
        rng = mockdata.rng_for("mca-office", cin)
        return {
            "cin": cin,
            "address": f"{rng.randint(1, 999)}, {rng.choice(['MG Road','Industrial Area','Tech Park','Main Street'])}",
            "city": r["city"], "state": r["state"],
            "pincode": f"{rng.randint(110000, 799999)}",
            "email": f"contact@{r['company_name'].split()[0].lower()}.com",
        }

    def fetch_get_incorporation(self, cin: str, params: Dict[str, Any]) -> Any:
        r = self._record(cin)
        return {"cin": cin, "incorporation_date": r["incorporation_date"], "roc": r["roc"], "class": r["class"]}

    def fetch_get_capital(self, cin: str, params: Dict[str, Any]) -> Any:
        r = self._record(cin)
        return {
            "cin": cin,
            "authorized_capital": r["authorized_capital"],
            "paid_up_capital": r["paid_up_capital"],
            "utilization_ratio": round(r["paid_up_capital"] / r["authorized_capital"], 4)
            if r["authorized_capital"] else 0.0,
        }

    def fetch_get_annual_filings(self, cin: str, params: Dict[str, Any]) -> Any:
        rng = mockdata.rng_for("mca-filings", cin)
        this_year = date.today().year
        filings = []
        compliant = True
        for y in range(this_year - 4, this_year):
            aoc_late = rng.random() < 0.2
            mgt_filed = rng.random() < 0.9
            if aoc_late or not mgt_filed:
                compliant = False
            filings.append({
                "financial_year": f"{y}-{y+1}",
                "aoc4_filed": True, "aoc4_late": aoc_late,
                "mgt7_filed": mgt_filed,
            })
        return {"cin": cin, "filings": filings, "compliant": compliant}

    def fetch_get_financial_statements(self, cin: str, params: Dict[str, Any]) -> Any:
        r = self._record(cin)
        rng = mockdata.rng_for("mca-fin", cin)
        this_year = date.today().year
        revenue = r["paid_up_capital"] * rng.uniform(1.5, 4.0)
        statements = []
        for y in range(this_year - 3, this_year):
            revenue *= (1 + rng.uniform(-0.1, 0.25))
            pat = revenue * rng.uniform(0.02, 0.12)
            statements.append({
                "financial_year": f"{y}-{y+1}",
                "revenue": round(revenue, 2),
                "profit_after_tax": round(pat, 2),
                "net_worth": round(r["paid_up_capital"] + pat * rng.uniform(1, 3), 2),
                "total_assets": round(revenue * rng.uniform(0.8, 1.5), 2),
            })
        return {"cin": cin, "statements": statements}

    def fetch_get_director_network(self, cin: str, params: Dict[str, Any]) -> Any:
        directors = self._record(cin)["directors"]
        network = []
        for d in directors:
            drng = mockdata.rng_for("mca-net", d["din"])
            others = [{"cin": mockdata.make_cin(drng), "role": "Director"}
                      for _ in range(d["other_directorships"])]
            network.append({"din": d["din"], "name": d["name"], "linked_companies": others})
        return {"cin": cin, "network": network,
                "total_linked_companies": sum(len(n["linked_companies"]) for n in network)}

    def fetch_get_company_relationships(self, cin: str, params: Dict[str, Any]) -> Any:
        rng = mockdata.rng_for("mca-rel", cin)
        n = rng.randint(0, 3)
        rels = []
        for _ in range(n):
            rels.append({
                "related_cin": mockdata.make_cin(rng),
                "relationship": rng.choice(["Subsidiary", "Holding", "Associate", "Common Director"]),
            })
        return {"cin": cin, "relationships": rels}


class SandboxMCAConnector(SandboxProviderMixin, MockMCAConnector):
    sandbox_secret = "mca.sandbox_token"

    def __init__(self, **kwargs):
        kwargs["provider"] = "sandbox_mca"
        super().__init__(**kwargs)


class ProductionMCAConnector(ProductionProviderMixin, MCAConnector):
    production_secret = "mca.api_key"

    def __init__(self, **kwargs):
        kwargs.setdefault("provider", "production_mca")
        super().__init__(**kwargs)
