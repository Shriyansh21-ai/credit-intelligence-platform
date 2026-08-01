"""M13 — Enterprise Financial Digital Twin.

A digital twin is a driver-based model of a real entity — company, industry
portfolio, economy, bank, treasury, market, supply chain or counterparty — whose
``state`` (named metrics) evolves under ``drivers`` (growth/decay/elasticities).
Simulating a twin projects the state forward under an optional scenario of
driver shocks, producing a period-by-period outcome path. Twins integrate with
the economic scenario engine (M4) and feed strategic intelligence (M14).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from backend.app.models.financial_intelligence import FinTwin, FinTwinSimulation
from . import data_access as da
from .common import checksum, clamp, grounding_block, iso, safe_div, to_float, utcnow

TWIN_TYPES = ["company", "industry", "portfolio", "economy", "bank", "treasury",
              "market", "supply_chain", "counterparty"]


def _default_state(twin_type: str, prof: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    ei = (prof or {}).get("engine_input", {}) if prof else {}
    if twin_type == "company":
        return {"revenue": to_float(ei.get("revenue"), 100.0),
                "net_margin": to_float(ei.get("net_margin"), 0.08),
                "current_ratio": to_float(ei.get("current_ratio"), 1.3),
                "debt_to_equity": to_float(ei.get("debt_to_equity"), 1.6),
                "pd": da.pd_of(prof) if prof else 0.05}
    if twin_type in ("portfolio", "bank"):
        return {"total_ead": 0.0, "expected_loss": 0.0, "car": 0.14, "nim": 0.03}
    if twin_type == "economy":
        return {"gdp_growth": 0.065, "inflation": 0.05, "unemployment": 0.075, "policy_rate": 0.065}
    if twin_type == "treasury":
        return {"lcr": 1.2, "nsfr": 1.15, "funding_cost": 0.065}
    return {"level": 100.0, "growth": 0.05}


def _default_drivers(twin_type: str) -> Dict[str, float]:
    if twin_type == "company":
        return {"revenue": 0.08, "net_margin": 0.0, "current_ratio": 0.0,
                "debt_to_equity": -0.02, "pd": -0.03}
    if twin_type == "economy":
        return {"gdp_growth": 0.0, "inflation": 0.0, "unemployment": 0.0, "policy_rate": 0.0}
    return {k: 0.05 for k in ("level", "growth", "total_ead", "nim")}


def create_twin(db: Session, *, key: str, name: str, twin_type: str,
                subject_ref: Optional[str] = None, state: Optional[Dict[str, Any]] = None,
                drivers: Optional[Dict[str, float]] = None, meta: Optional[dict] = None,
                tenant_id: Optional[int] = None, created_by: Optional[str] = None) -> Dict[str, Any]:
    if twin_type not in TWIN_TYPES:
        raise ValueError(f"unknown twin_type '{twin_type}'")
    if db.query(FinTwin).filter(FinTwin.tenant_id == tenant_id, FinTwin.key == key).first():
        raise ValueError(f"twin '{key}' already exists")
    prof = da.company_or_none(db, company_ref=subject_ref) if subject_ref else None
    state = state or _default_state(twin_type, prof)
    drivers = drivers or _default_drivers(twin_type)
    row = FinTwin(tenant_id=tenant_id, key=key, name=name, twin_type=twin_type,
                  subject_ref=subject_ref, state=state, drivers=drivers, meta=meta or {},
                  created_by=created_by)
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"twin_id": row.id, "key": row.key, "twin_type": twin_type, "state": state,
            "drivers": drivers}


def list_twins(db: Session, *, twin_type: Optional[str] = None, tenant_id: Optional[int] = None) -> List[Dict[str, Any]]:
    q = db.query(FinTwin)
    if tenant_id is not None:
        q = q.filter(FinTwin.tenant_id == tenant_id)
    if twin_type:
        q = q.filter(FinTwin.twin_type == twin_type)
    return [{"twin_id": t.id, "key": t.key, "name": t.name, "twin_type": t.twin_type,
             "subject_ref": t.subject_ref, "updated_at": iso(t.updated_at)}
            for t in q.order_by(FinTwin.id.desc()).all()]


def get_twin(db: Session, twin_id: int) -> Optional[Dict[str, Any]]:
    t = db.query(FinTwin).filter(FinTwin.id == twin_id).first()
    if not t:
        return None
    return {"twin_id": t.id, "key": t.key, "name": t.name, "twin_type": t.twin_type,
            "subject_ref": t.subject_ref, "state": t.state, "drivers": t.drivers,
            "created_at": iso(t.created_at), "updated_at": iso(t.updated_at)}


def update_state(db: Session, *, twin_id: int, state: Dict[str, Any],
                 drivers: Optional[Dict[str, float]] = None) -> Dict[str, Any]:
    t = db.query(FinTwin).filter(FinTwin.id == twin_id).first()
    if not t:
        raise ValueError("twin not found")
    t.state = {**(t.state or {}), **state}
    if drivers:
        t.drivers = {**(t.drivers or {}), **drivers}
    db.commit()
    db.refresh(t)
    return {"twin_id": t.id, "state": t.state, "drivers": t.drivers}


def simulate(db: Session, *, twin_id: int, horizon: int = 8,
             scenario: Optional[Dict[str, float]] = None, scenario_ref: Optional[str] = None,
             tenant_id: Optional[int] = None, created_by: Optional[str] = None) -> Dict[str, Any]:
    """Project the twin's state forward under driver dynamics + a scenario shock.

    ``scenario`` maps a driver/metric name to an additive per-period shock on its
    growth rate. Each metric compounds by (driver + shock) each period.
    """
    t = db.query(FinTwin).filter(FinTwin.id == twin_id).first()
    if not t:
        raise ValueError("twin not found")
    scenario = scenario or {}
    state = dict(t.state or {})
    drivers = dict(t.drivers or {})
    path: List[Dict[str, Any]] = [{"t": 0, **{k: round(v, 5) if isinstance(v, (int, float)) else v
                                              for k, v in state.items()}}]
    cur = dict(state)
    for step in range(1, horizon + 1):
        nxt = {}
        for k, v in cur.items():
            if not isinstance(v, (int, float)):
                nxt[k] = v
                continue
            rate = to_float(drivers.get(k, 0.0)) + to_float(scenario.get(k, 0.0))
            # PD and risk-like metrics are bounded to [0,1].
            new_v = v * (1 + rate)
            if k in ("pd", "car", "lcr", "nsfr", "net_margin"):
                new_v = clamp(new_v, 0.0, 1.5)
            nxt[k] = round(new_v, 6)
        path.append({"t": step, **nxt})
        cur = nxt
    terminal = path[-1]
    deltas = {k: round(to_float(terminal.get(k)) - to_float(state.get(k)), 6)
              for k in state if isinstance(state[k], (int, float))}
    outcomes = {"path": path, "terminal_state": terminal, "deltas": deltas,
                "horizon": horizon, "scenario": scenario}
    g = grounding_block("Twin Simulation", {"terminal": terminal, "deltas": deltas})
    row = FinTwinSimulation(
        tenant_id=tenant_id, twin_id=twin_id, scenario_ref=scenario_ref, horizon=horizon,
        inputs={"scenario": scenario, "initial_state": state}, outcomes={**outcomes, "grounding": g},
        narrative=f"Simulated {t.twin_type} twin '{t.key}' over {horizon} periods.",
        checksum=checksum(outcomes), created_by=created_by)
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"simulation_id": row.id, "twin_id": twin_id, **outcomes}


def list_simulations(db: Session, *, twin_id: Optional[int] = None, limit: int = 50,
                     tenant_id: Optional[int] = None) -> List[Dict[str, Any]]:
    q = db.query(FinTwinSimulation)
    if tenant_id is not None:
        q = q.filter(FinTwinSimulation.tenant_id == tenant_id)
    if twin_id is not None:
        q = q.filter(FinTwinSimulation.twin_id == twin_id)
    return [{"simulation_id": s.id, "twin_id": s.twin_id, "horizon": s.horizon,
             "checksum": s.checksum, "created_at": iso(s.created_at)}
            for s in q.order_by(FinTwinSimulation.id.desc()).limit(limit).all()]
