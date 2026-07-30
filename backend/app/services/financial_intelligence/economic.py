"""M4 — Economic Scenario Engine.

Macroeconomic intelligence: a registry of indicators (GDP, inflation, interest
& policy rates, FX, commodities, unemployment, sector growth, country/political
risk) and a scenario generator producing optimistic / baseline / adverse /
severely-adverse / custom paths. Scenarios *propagate* through the platform's
live exposures — macro shocks translate into stressed PD/LGD, expected loss and
RWA — so a single scenario feeds every downstream assessment engine.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from backend.app.models.financial_intelligence import (
    FinEconomicIndicator, FinEconomicScenario,
)
from . import data_access as da
from .common import (
    checksum, clamp, expected_loss, grounding_block, iso, pct, safe_div, to_float, utcnow,
)

INDICATOR_CODES = [
    "gdp_growth", "inflation", "policy_rate", "interest_rate", "unemployment",
    "fx_usd", "commodity_index", "oil_price", "sector_growth", "country_risk",
    "political_risk", "credit_spread",
]
SCENARIO_TYPES = ["optimistic", "baseline", "adverse", "severely_adverse", "custom"]

# Baseline indicator levels (India-centric defaults) used when no data seeded.
BASELINE_LEVELS = {
    "gdp_growth": 0.065, "inflation": 0.05, "policy_rate": 0.065, "interest_rate": 0.09,
    "unemployment": 0.075, "fx_usd": 83.0, "commodity_index": 100.0, "oil_price": 80.0,
    "sector_growth": 0.06, "country_risk": 0.30, "political_risk": 0.25, "credit_spread": 0.03,
}

# Preset shock deltas per scenario (added to baseline unless multiplicative noted).
SCENARIO_SHOCKS: Dict[str, Dict[str, float]] = {
    "optimistic": {"gdp_growth": +0.02, "inflation": -0.01, "policy_rate": -0.01,
                   "unemployment": -0.015, "credit_spread": -0.01, "country_risk": -0.10},
    "baseline": {},
    "adverse": {"gdp_growth": -0.03, "inflation": +0.02, "policy_rate": +0.015,
                "unemployment": +0.02, "credit_spread": +0.02, "country_risk": +0.15,
                "fx_usd": +5.0, "oil_price": +20.0},
    "severely_adverse": {"gdp_growth": -0.06, "inflation": +0.04, "policy_rate": +0.03,
                         "unemployment": +0.045, "credit_spread": +0.05, "country_risk": +0.30,
                         "fx_usd": +12.0, "oil_price": +40.0},
}

# Sensitivity of default risk to macro shocks (elasticities on log-PD).
PD_BETAS = {"gdp_growth": -6.0, "unemployment": +5.0, "policy_rate": +3.0,
            "credit_spread": +4.0, "inflation": +1.5, "country_risk": +1.0}


def upsert_indicator(db: Session, *, code: str, name: str, value: float, region: str = "IN",
                     unit: Optional[str] = None, as_of: Optional[str] = None,
                     meta: Optional[dict] = None, tenant_id: Optional[int] = None) -> FinEconomicIndicator:
    row = FinEconomicIndicator(tenant_id=tenant_id, code=code, name=name, region=region,
                               value=to_float(value), unit=unit, as_of=as_of or iso(utcnow())[:10],
                               meta=meta or {})
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def seed_defaults(db: Session, *, region: str = "IN", tenant_id: Optional[int] = None) -> Dict[str, Any]:
    seeded = 0
    for code, val in BASELINE_LEVELS.items():
        exists = (db.query(FinEconomicIndicator)
                  .filter(FinEconomicIndicator.code == code,
                          FinEconomicIndicator.region == region,
                          FinEconomicIndicator.tenant_id == tenant_id).first())
        if not exists:
            upsert_indicator(db, code=code, name=code.replace("_", " ").title(), value=val,
                             region=region, tenant_id=tenant_id)
            seeded += 1
    return {"seeded": seeded, "region": region}


def list_indicators(db: Session, *, region: Optional[str] = None,
                    tenant_id: Optional[int] = None) -> List[Dict[str, Any]]:
    q = db.query(FinEconomicIndicator)
    if tenant_id is not None:
        q = q.filter(FinEconomicIndicator.tenant_id == tenant_id)
    if region:
        q = q.filter(FinEconomicIndicator.region == region)
    return [{"id": i.id, "code": i.code, "name": i.name, "region": i.region,
             "value": i.value, "unit": i.unit, "as_of": i.as_of}
            for i in q.order_by(FinEconomicIndicator.id.desc()).all()]


def _current_levels(db: Session, region: str, tenant_id: Optional[int]) -> Dict[str, float]:
    levels = dict(BASELINE_LEVELS)
    for i in list_indicators(db, region=region, tenant_id=tenant_id):
        if i["code"] in levels:
            levels[i["code"]] = i["value"]
    return levels


def generate_scenario(db: Session, *, name: str, scenario_type: str = "baseline",
                      region: str = "IN", horizon_years: int = 3,
                      custom_shocks: Optional[Dict[str, float]] = None, key: Optional[str] = None,
                      tenant_id: Optional[int] = None, created_by: Optional[str] = None) -> Dict[str, Any]:
    """Build a macro scenario: shocked indicator levels + multi-year paths."""
    if scenario_type not in SCENARIO_TYPES:
        raise ValueError(f"unknown scenario_type '{scenario_type}'")
    base = _current_levels(db, region, tenant_id)
    shocks = dict(SCENARIO_SHOCKS.get(scenario_type, {}))
    if scenario_type == "custom" and custom_shocks:
        shocks = dict(custom_shocks)
    elif custom_shocks:
        shocks.update(custom_shocks)

    shocked = {k: v + shocks.get(k, 0.0) for k, v in base.items()}
    # Multi-year paths: shock phases in over year 1, mean-reverts halfway by horizon.
    paths: Dict[str, List[float]] = {}
    for code in base:
        path = []
        for y in range(1, horizon_years + 1):
            phase = 1.0 if y == 1 else max(0.5, 1.0 - 0.15 * (y - 1))
            path.append(round(base[code] + shocks.get(code, 0.0) * phase, 5))
        paths[code] = path
    results = {
        "scenario_type": scenario_type, "region": region, "horizon_years": horizon_years,
        "baseline_levels": {k: round(v, 5) for k, v in base.items()},
        "shocked_levels": {k: round(v, 5) for k, v in shocked.items()},
        "shocks": shocks, "paths": paths,
    }
    g = grounding_block("Economic Scenario", results)
    row = FinEconomicScenario(
        tenant_id=tenant_id, key=key or f"{scenario_type}-{region}-{horizon_years}y",
        name=name, scenario_type=scenario_type, region=region, horizon_years=horizon_years,
        shocks=shocks, results={**results, "grounding": g},
        narrative=f"{scenario_type.replace('_', ' ').title()} scenario for {region} over {horizon_years}y.",
        checksum=checksum(results), created_by=created_by)
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"scenario_id": row.id, "key": row.key, "scenario_type": scenario_type, **results}


def propagate(db: Session, *, scenario_id: Optional[int] = None,
              scenario_type: Optional[str] = None, region: str = "IN",
              tenant_id: Optional[int] = None, created_by: Optional[str] = None) -> Dict[str, Any]:
    """Propagate a scenario's macro shocks through the live exposure set.

    PD is stressed multiplicatively via macro elasticities; LGD is nudged by the
    downturn signal. Reports baseline vs stressed EL and the implied uplift.
    """
    if scenario_id is not None:
        sc = db.query(FinEconomicScenario).filter(FinEconomicScenario.id == scenario_id).first()
        if not sc:
            raise ValueError("scenario not found")
        shocks = sc.shocks or {}
        scenario_type = sc.scenario_type
    else:
        shocks = SCENARIO_SHOCKS.get(scenario_type or "adverse", {})

    # Log-PD shift from macro shocks.
    log_shift = sum(PD_BETAS.get(code, 0.0) * shocks.get(code, 0.0) for code in PD_BETAS)
    pd_multiplier = math.exp(log_shift)
    lgd_uplift = clamp(0.5 * max(shocks.get("credit_spread", 0.0), 0.0) +
                       0.3 * max(-shocks.get("gdp_growth", 0.0), 0.0), 0.0, 0.25)

    exposures = da.portfolio_exposures(db)
    base_el = stressed_el = 0.0
    detail = []
    for e in exposures:
        s_pd = clamp(e["pd"] * pd_multiplier, 0.0, 1.0)
        s_lgd = clamp(e["lgd"] * (1 + lgd_uplift), 0.0, 1.0)
        b = expected_loss(e["pd"], e["lgd"], e["ead"])
        s = expected_loss(s_pd, s_lgd, e["ead"])
        base_el += b
        stressed_el += s
        detail.append({"company_ref": e["company_ref"], "base_pd_pct": pct(e["pd"]),
                       "stressed_pd_pct": pct(s_pd), "base_el": round(b, 2),
                       "stressed_el": round(s, 2)})
    results = {
        "scenario_type": scenario_type,
        "pd_multiplier": round(pd_multiplier, 4),
        "lgd_uplift_pct": pct(lgd_uplift),
        "baseline_expected_loss": round(base_el, 2),
        "stressed_expected_loss": round(stressed_el, 2),
        "el_uplift": round(stressed_el - base_el, 2),
        "el_uplift_pct": pct(safe_div(stressed_el - base_el, base_el, 0.0)),
        "exposures": len(exposures),
        "top_impacts": sorted(detail, key=lambda d: d["stressed_el"] - d["base_el"], reverse=True)[:10],
    }
    g = grounding_block("Scenario Propagation", results)
    row = FinEconomicScenario(
        tenant_id=tenant_id, key=f"propagation-{scenario_type}", name="Scenario Propagation",
        scenario_type=scenario_type or "custom", region=region, horizon_years=1,
        shocks=shocks, results={**results, "grounding": g},
        narrative=(f"{scenario_type} scenario lifts expected loss by "
                   f"{results['el_uplift_pct']}% (×{results['pd_multiplier']} on PD)."),
        checksum=checksum(results), created_by=created_by)
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"propagation_id": row.id, **results}


def list_scenarios(db: Session, *, scenario_type: Optional[str] = None, limit: int = 50,
                   tenant_id: Optional[int] = None) -> List[Dict[str, Any]]:
    q = db.query(FinEconomicScenario)
    if tenant_id is not None:
        q = q.filter(FinEconomicScenario.tenant_id == tenant_id)
    if scenario_type:
        q = q.filter(FinEconomicScenario.scenario_type == scenario_type)
    return [{"scenario_id": s.id, "key": s.key, "name": s.name,
             "scenario_type": s.scenario_type, "region": s.region,
             "checksum": s.checksum, "created_at": iso(s.created_at)}
            for s in q.order_by(FinEconomicScenario.id.desc()).limit(limit).all()]


def get_scenario(db: Session, scenario_id: int) -> Optional[Dict[str, Any]]:
    s = db.query(FinEconomicScenario).filter(FinEconomicScenario.id == scenario_id).first()
    if not s:
        return None
    return {"scenario_id": s.id, "key": s.key, "name": s.name, "scenario_type": s.scenario_type,
            "region": s.region, "horizon_years": s.horizon_years, "shocks": s.shocks,
            "results": s.results, "narrative": s.narrative, "created_at": iso(s.created_at)}
