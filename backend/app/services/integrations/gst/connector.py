"""GST connector interface + mock/sandbox/production providers (Milestone 2).

The abstract :class:`GSTConnector` defines the GST operation surface and
dispatches each operation to a ``fetch_*`` method the concrete provider
implements. Because the mock derives every operation from a single coherent
synthetic GST record (seeded by GSTIN), the profile, returns, sales history and
compliance signals are always mutually consistent.
"""

from __future__ import annotations

import random
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
    "get_profile", "get_returns", "get_sales_history", "get_filing_status",
    "validate", "get_business_status", "get_filing_delays", "get_tax_trends",
]


class GSTConnector(BaseConnector):
    category = ConnectorCategory.GOVERNMENT
    connector_key = "gst"

    def operations(self) -> List[str]:
        return list(_OPERATIONS)

    def _execute(self, request: ConnectorRequest) -> Any:
        op = request.operation
        if op not in _OPERATIONS:
            raise ProviderError(f"unknown GST operation '{op}'", provider=self.provider, operation=op)
        gstin = request.params.get("gstin") or request.params.get("entity_ref")
        if not gstin:
            raise ProviderError("gstin is required", provider=self.provider, operation=op)
        return getattr(self, f"fetch_{op}")(str(gstin), request.params)

    # -- provider contract (implemented by mock; sandbox reuses it) --------
    def fetch_get_profile(self, gstin: str, params: Dict[str, Any]) -> Any:  # pragma: no cover - abstract
        raise NotImplementedError

    def fetch_get_returns(self, gstin: str, params: Dict[str, Any]) -> Any:  # pragma: no cover
        raise NotImplementedError

    def fetch_get_sales_history(self, gstin: str, params: Dict[str, Any]) -> Any:  # pragma: no cover
        raise NotImplementedError

    def fetch_get_filing_status(self, gstin: str, params: Dict[str, Any]) -> Any:  # pragma: no cover
        raise NotImplementedError

    def fetch_validate(self, gstin: str, params: Dict[str, Any]) -> Any:  # pragma: no cover
        raise NotImplementedError

    def fetch_get_business_status(self, gstin: str, params: Dict[str, Any]) -> Any:  # pragma: no cover
        raise NotImplementedError

    def fetch_get_filing_delays(self, gstin: str, params: Dict[str, Any]) -> Any:  # pragma: no cover
        raise NotImplementedError

    def fetch_get_tax_trends(self, gstin: str, params: Dict[str, Any]) -> Any:  # pragma: no cover
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Mock provider — deterministic, offline
# ---------------------------------------------------------------------------
_GSTIN_RE = __import__("re").compile(r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][0-9A-Z]{3}$")


class MockGSTConnector(GSTConnector):
    def __init__(self, **kwargs):
        kwargs.setdefault("provider", "mock_gst")
        super().__init__(**kwargs)

    # -- the single source record everything derives from -----------------
    def _record(self, gstin: str) -> Dict[str, Any]:
        rng = mockdata.rng_for("gst", gstin)
        sc, state = mockdata.state_code(rng)
        reg_year = rng.randint(2017, 2022)
        legal = mockdata.company_name(rng) + " Pvt Ltd"
        statuses = ["Active", "Active", "Active", "Suspended", "Cancelled"]
        status = rng.choice(statuses)
        base_turnover = rng.choice([8, 15, 30, 60, 120]) * 100000.0  # monthly, INR
        growth = rng.uniform(-0.03, 0.06)
        return {
            "gstin": gstin,
            "legal_name": legal,
            "trade_name": legal.replace(" Pvt Ltd", ""),
            "state_code": sc,
            "state": state,
            "registration_date": mockdata.iso(date(reg_year, rng.randint(1, 12), rng.randint(1, 28))),
            "constitution": rng.choice(["Private Limited", "Proprietorship", "Partnership", "LLP"]),
            "taxpayer_type": rng.choice(["Regular", "Composition"]),
            "status": status,
            "base_monthly_turnover": base_turnover,
            "growth": growth,
            "_rng_state": rng.random(),
        }

    def fetch_get_profile(self, gstin: str, params: Dict[str, Any]) -> Any:
        r = self._record(gstin)
        return {
            "gstin": r["gstin"], "legal_name": r["legal_name"], "trade_name": r["trade_name"],
            "state": r["state"], "state_code": r["state_code"],
            "registration_date": r["registration_date"], "constitution": r["constitution"],
            "taxpayer_type": r["taxpayer_type"], "status": r["status"],
        }

    def _returns(self, gstin: str, months: int = 12) -> List[Dict[str, Any]]:
        r = self._record(gstin)
        rng = mockdata.rng_for("gst-returns", gstin)
        periods = mockdata.month_starts(months, date.today())
        turnover = r["base_monthly_turnover"]
        out: List[Dict[str, Any]] = []
        for i, p in enumerate(periods):
            turnover *= (1 + r["growth"] + rng.uniform(-0.05, 0.05))
            due = date(p.year + (1 if p.month == 12 else 0), 1 if p.month == 12 else p.month + 1, 20)
            # Filing behaviour: mostly on-time, occasional delay.
            late = rng.random() < (0.15 if r["status"] == "Active" else 0.4)
            pending = (r["status"] != "Active" and i >= months - 3 and rng.random() < 0.5)
            delay_days = rng.randint(1, 45) if late and not pending else 0
            out.append({
                "period": p.strftime("%m-%Y"),
                "return_type": "GSTR-3B",
                "turnover": round(turnover, 2),
                "tax_paid": round(turnover * rng.uniform(0.03, 0.09), 2),
                "due_date": mockdata.iso(due),
                "status": "pending" if pending else ("filed_late" if late else "filed"),
                "delay_days": delay_days,
            })
        return out

    def fetch_get_returns(self, gstin: str, params: Dict[str, Any]) -> Any:
        months = int(params.get("months", 12))
        return {"gstin": gstin, "returns": self._returns(gstin, months)}

    def fetch_get_sales_history(self, gstin: str, params: Dict[str, Any]) -> Any:
        months = int(params.get("months", 12))
        rows = self._returns(gstin, months)
        return {
            "gstin": gstin,
            "monthly_sales": [{"period": r["period"], "turnover": r["turnover"]} for r in rows],
            "annual_turnover": round(sum(r["turnover"] for r in rows), 2),
        }

    def fetch_get_filing_status(self, gstin: str, params: Dict[str, Any]) -> Any:
        rows = self._returns(gstin, 12)
        last = rows[-1]
        pending = [r for r in rows if r["status"] == "pending"]
        return {
            "gstin": gstin,
            "last_return_period": last["period"],
            "last_return_status": last["status"],
            "pending_returns": len(pending),
            "compliant": len(pending) == 0 and last["status"] != "pending",
        }

    def fetch_validate(self, gstin: str, params: Dict[str, Any]) -> Any:
        valid_format = bool(_GSTIN_RE.match(gstin))
        r = self._record(gstin) if valid_format else None
        return {
            "gstin": gstin,
            "valid_format": valid_format,
            "exists": valid_format,
            "active": bool(r and r["status"] == "Active"),
            "status": r["status"] if r else "invalid",
        }

    def fetch_get_business_status(self, gstin: str, params: Dict[str, Any]) -> Any:
        r = self._record(gstin)
        return {
            "gstin": gstin,
            "status": r["status"],
            "active": r["status"] == "Active",
            "registration_date": r["registration_date"],
        }

    def fetch_get_filing_delays(self, gstin: str, params: Dict[str, Any]) -> Any:
        rows = self._returns(gstin, 12)
        late = [r for r in rows if r["status"] == "filed_late"]
        delays = [r["delay_days"] for r in late]
        return {
            "gstin": gstin,
            "total_returns": len(rows),
            "late_filings": len(late),
            "late_ratio": round(len(late) / len(rows), 4) if rows else 0.0,
            "avg_delay_days": round(sum(delays) / len(delays), 2) if delays else 0.0,
            "max_delay_days": max(delays) if delays else 0,
        }

    def fetch_get_tax_trends(self, gstin: str, params: Dict[str, Any]) -> Any:
        rows = self._returns(gstin, 12)
        taxes = [r["tax_paid"] for r in rows]
        first_half = sum(taxes[: len(taxes) // 2]) or 1.0
        second_half = sum(taxes[len(taxes) // 2:])
        trend = "rising" if second_half > first_half * 1.05 else (
            "declining" if second_half < first_half * 0.95 else "stable")
        return {
            "gstin": gstin,
            "monthly_tax": [{"period": r["period"], "tax_paid": r["tax_paid"]} for r in rows],
            "total_tax_paid": round(sum(taxes), 2),
            "trend": trend,
        }


# ---------------------------------------------------------------------------
# Sandbox + production
# ---------------------------------------------------------------------------
class SandboxGSTConnector(SandboxProviderMixin, MockGSTConnector):
    sandbox_secret = "gst.sandbox_token"

    def __init__(self, **kwargs):
        kwargs["provider"] = "sandbox_gst"
        super().__init__(**kwargs)


class ProductionGSTConnector(ProductionProviderMixin, GSTConnector):
    production_secret = "gst.api_key"

    def __init__(self, **kwargs):
        kwargs.setdefault("provider", "production_gst")
        super().__init__(**kwargs)
