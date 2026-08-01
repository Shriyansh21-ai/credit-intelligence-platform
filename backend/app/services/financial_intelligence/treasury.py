"""M1 — Treasury Intelligence Platform.

A complete, deterministic treasury analytics engine: cash position, liquidity
management, funding-gap analysis, cash forecasting, net interest margin, ALM
gapping, Basel LCR / NSFR, funding optimization, liquidity stress and treasury
KPIs. Everything is grounded in either explicit balance-sheet inputs or the
platform's funding-source registry — no numbers are invented by the (optional)
LLM narrator, which only phrases the computed grounding block.

Snapshots are persisted to ``fin_treasury_snapshots`` for historical/projected
treasury reporting.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from backend.app.models.financial_intelligence import (
    FinFundingSource, FinTreasurySnapshot,
)
from . import data_access as da
from .common import (
    checksum, clamp, grounding_block, iso, mean, pct, safe_div, to_float, utcnow,
)

FUNDING_SOURCE_TYPES = [
    "deposit", "wholesale", "repo", "bond", "equity", "central_bank",
    "interbank", "securitization",
]

# Standard maturity buckets (days) for ALM gapping and liquidity laddering.
LIQUIDITY_BUCKETS: List[Dict[str, Any]] = [
    {"key": "0-7d", "lo": 0, "hi": 7},
    {"key": "8-30d", "lo": 8, "hi": 30},
    {"key": "31-90d", "lo": 31, "hi": 90},
    {"key": "91-180d", "lo": 91, "hi": 180},
    {"key": "181-365d", "lo": 181, "hi": 365},
    {"key": "1-3y", "lo": 366, "hi": 1095},
    {"key": "3-5y", "lo": 1096, "hi": 1825},
    {"key": "5y+", "lo": 1826, "hi": 10 ** 9},
]

# Basel LCR run-off factors by funding type (fraction assumed to leave in 30d).
LCR_RUNOFF = {
    "deposit": 0.10, "wholesale": 0.75, "repo": 0.25, "interbank": 1.0,
    "bond": 0.0, "equity": 0.0, "central_bank": 0.0, "securitization": 1.0,
}
# NSFR Available Stable Funding factors by funding type.
NSFR_ASF = {
    "deposit": 0.90, "wholesale": 0.50, "repo": 0.0, "interbank": 0.0,
    "bond": 1.0, "equity": 1.0, "central_bank": 0.0, "securitization": 0.0,
}


# ---------------------------------------------------------------------------
# Funding-source registry
# ---------------------------------------------------------------------------

def register_funding_source(db: Session, *, name: str, source_type: str,
                            amount: float, rate: float, tenor_days: int = 0,
                            currency: str = "INR", stability_factor: Optional[float] = None,
                            is_secured: bool = False, meta: Optional[dict] = None,
                            tenant_id: Optional[int] = None,
                            created_by: Optional[str] = None) -> FinFundingSource:
    if source_type not in FUNDING_SOURCE_TYPES:
        raise ValueError(f"unknown source_type '{source_type}'")
    if stability_factor is None:
        stability_factor = NSFR_ASF.get(source_type, 0.5)
    row = FinFundingSource(
        tenant_id=tenant_id, name=name, source_type=source_type,
        amount=to_float(amount), rate=to_float(rate), tenor_days=int(tenor_days or 0),
        currency=currency, stability_factor=clamp(stability_factor, 0.0, 1.0),
        is_secured=bool(is_secured), meta=meta or {}, created_by=created_by)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def list_funding_sources(db: Session, *, tenant_id: Optional[int] = None) -> List[FinFundingSource]:
    q = db.query(FinFundingSource)
    if tenant_id is not None:
        q = q.filter(FinFundingSource.tenant_id == tenant_id)
    return q.order_by(FinFundingSource.id.desc()).all()


def _funding_rows(db: Session, tenant_id: Optional[int]) -> List[Dict[str, Any]]:
    out = []
    for s in list_funding_sources(db, tenant_id=tenant_id):
        out.append({"name": s.name, "source_type": s.source_type, "amount": s.amount,
                    "rate": s.rate, "tenor_days": s.tenor_days, "is_secured": s.is_secured,
                    "stability_factor": s.stability_factor})
    return out


# ---------------------------------------------------------------------------
# Snapshot persistence
# ---------------------------------------------------------------------------

def _save(db: Session, *, kind: str, inputs: dict, results: dict,
          narrative: Optional[str], label: Optional[str], as_of: Optional[str],
          tenant_id: Optional[int], created_by: Optional[str]) -> Dict[str, Any]:
    row = FinTreasurySnapshot(
        tenant_id=tenant_id, kind=kind, label=label, as_of=as_of or iso(utcnow())[:10],
        inputs=inputs, results=results, narrative=narrative,
        checksum=checksum(results), created_by=created_by)
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"snapshot_id": row.id, "kind": kind, "as_of": row.as_of,
            "checksum": row.checksum, **results, "narrative": narrative}


# ---------------------------------------------------------------------------
# Cash position & liquidity
# ---------------------------------------------------------------------------

def cash_position(db: Session, *, balances: Optional[Dict[str, float]] = None,
                  tenant_id: Optional[int] = None, as_of: Optional[str] = None,
                  created_by: Optional[str] = None) -> Dict[str, Any]:
    """Aggregate cash & equivalents across accounts/instruments."""
    balances = balances or {}
    cash = to_float(balances.get("cash", 0))
    nostro = to_float(balances.get("nostro", 0))
    central_bank = to_float(balances.get("central_bank_reserves", 0))
    money_market = to_float(balances.get("money_market", 0))
    hqla_securities = to_float(balances.get("hqla_securities", 0))
    total_cash = cash + nostro + central_bank + money_market
    total_liquid = total_cash + hqla_securities
    results = {
        "components": {"cash": cash, "nostro": nostro,
                       "central_bank_reserves": central_bank,
                       "money_market": money_market,
                       "hqla_securities": hqla_securities},
        "total_cash": round(total_cash, 2),
        "total_liquid_assets": round(total_liquid, 2),
    }
    g = grounding_block("Cash Position", results)
    return _save(db, kind="cash", inputs={"balances": balances}, results={**results, "grounding": g},
                 narrative=f"Total cash of {total_cash:,.0f} and liquid assets of {total_liquid:,.0f}.",
                 label="Cash Position", as_of=as_of, tenant_id=tenant_id, created_by=created_by)


def liquidity_buckets(db: Session, *, assets: List[Dict[str, Any]],
                      liabilities: List[Dict[str, Any]], tenant_id: Optional[int] = None,
                      as_of: Optional[str] = None, created_by: Optional[str] = None) -> Dict[str, Any]:
    """Ladder assets & liabilities into maturity buckets and compute gaps."""
    def bucket_of(days: float) -> str:
        for b in LIQUIDITY_BUCKETS:
            if b["lo"] <= days <= b["hi"]:
                return b["key"]
        return LIQUIDITY_BUCKETS[-1]["key"]

    rows = {b["key"]: {"assets": 0.0, "liabilities": 0.0} for b in LIQUIDITY_BUCKETS}
    for a in assets:
        rows[bucket_of(to_float(a.get("tenor_days", 0)))]["assets"] += to_float(a.get("amount", 0))
    for l in liabilities:
        rows[bucket_of(to_float(l.get("tenor_days", 0)))]["liabilities"] += to_float(l.get("amount", 0))

    cumulative = 0.0
    buckets = []
    for b in LIQUIDITY_BUCKETS:
        r = rows[b["key"]]
        gap = r["assets"] - r["liabilities"]
        cumulative += gap
        buckets.append({"bucket": b["key"], "assets": round(r["assets"], 2),
                        "liabilities": round(r["liabilities"], 2),
                        "gap": round(gap, 2), "cumulative_gap": round(cumulative, 2)})
    results = {"buckets": buckets, "cumulative_gap": round(cumulative, 2)}
    g = grounding_block("Liquidity Buckets", results)
    return _save(db, kind="liquidity", inputs={"assets": assets, "liabilities": liabilities},
                 results={**results, "grounding": g},
                 narrative=f"Cumulative liquidity gap across the ladder is {cumulative:,.0f}.",
                 label="Liquidity Buckets", as_of=as_of, tenant_id=tenant_id, created_by=created_by)


def funding_gap_analysis(db: Session, *, funding_need: float,
                         tenant_id: Optional[int] = None, as_of: Optional[str] = None,
                         created_by: Optional[str] = None) -> Dict[str, Any]:
    """Compare available stable funding against a target funding need."""
    rows = _funding_rows(db, tenant_id)
    total_funding = sum(r["amount"] for r in rows)
    stable_funding = sum(r["amount"] * r["stability_factor"] for r in rows)
    gap = funding_need - total_funding
    stable_gap = funding_need - stable_funding
    by_type: Dict[str, float] = {}
    for r in rows:
        by_type[r["source_type"]] = by_type.get(r["source_type"], 0.0) + r["amount"]
    results = {
        "funding_need": round(funding_need, 2),
        "total_available_funding": round(total_funding, 2),
        "stable_funding": round(stable_funding, 2),
        "funding_gap": round(gap, 2),
        "stable_funding_gap": round(stable_gap, 2),
        "by_type": {k: round(v, 2) for k, v in by_type.items()},
        "status": "surplus" if gap <= 0 else "shortfall",
    }
    g = grounding_block("Funding Gap", results)
    return _save(db, kind="cash", inputs={"funding_need": funding_need},
                 results={**results, "grounding": g},
                 narrative=(f"Funding {'surplus' if gap <= 0 else 'shortfall'} of "
                            f"{abs(gap):,.0f} against a need of {funding_need:,.0f}."),
                 label="Funding Gap", as_of=as_of, tenant_id=tenant_id, created_by=created_by)


# ---------------------------------------------------------------------------
# Net interest margin & yield
# ---------------------------------------------------------------------------

def net_interest_margin(db: Session, *, earning_assets: float, asset_yield: float,
                        tenant_id: Optional[int] = None, as_of: Optional[str] = None,
                        created_by: Optional[str] = None) -> Dict[str, Any]:
    """NIM from earning-asset yield vs blended funding cost (from the registry)."""
    rows = _funding_rows(db, tenant_id)
    total_funding = sum(r["amount"] for r in rows)
    funding_cost = safe_div(sum(r["amount"] * r["rate"] for r in rows), total_funding, 0.0)
    interest_income = earning_assets * asset_yield
    interest_expense = total_funding * funding_cost
    nim = safe_div(interest_income - interest_expense, earning_assets, 0.0)
    results = {
        "earning_assets": round(earning_assets, 2),
        "asset_yield_pct": pct(asset_yield),
        "blended_funding_cost_pct": pct(funding_cost),
        "interest_income": round(interest_income, 2),
        "interest_expense": round(interest_expense, 2),
        "net_interest_income": round(interest_income - interest_expense, 2),
        "net_interest_margin_pct": pct(nim),
        "spread_pct": pct(asset_yield - (funding_cost or 0.0)),
    }
    g = grounding_block("Net Interest Margin", results)
    return _save(db, kind="kpis", inputs={"earning_assets": earning_assets, "asset_yield": asset_yield},
                 results={**results, "grounding": g},
                 narrative=f"Net interest margin is {pct(nim)}% on {earning_assets:,.0f} of earning assets.",
                 label="Net Interest Margin", as_of=as_of, tenant_id=tenant_id, created_by=created_by)


def yield_analysis(db: Session, *, positions: List[Dict[str, Any]],
                   tenant_id: Optional[int] = None, as_of: Optional[str] = None,
                   created_by: Optional[str] = None) -> Dict[str, Any]:
    """Weighted-average yield and duration across earning positions."""
    total = sum(to_float(p.get("amount", 0)) for p in positions) or 1.0
    wavg_yield = sum(to_float(p.get("amount", 0)) * to_float(p.get("yield", 0)) for p in positions) / total
    wavg_duration = sum(to_float(p.get("amount", 0)) * to_float(p.get("duration", 0)) for p in positions) / total
    results = {
        "total_earning_assets": round(total, 2),
        "weighted_avg_yield_pct": pct(wavg_yield),
        "weighted_avg_duration_years": round(wavg_duration, 3),
        "positions": len(positions),
    }
    g = grounding_block("Yield Analysis", results)
    return _save(db, kind="yield", inputs={"positions": positions},
                 results={**results, "grounding": g},
                 narrative=f"Weighted average yield {pct(wavg_yield)}% at duration {wavg_duration:.2f}y.",
                 label="Yield Analysis", as_of=as_of, tenant_id=tenant_id, created_by=created_by)


# ---------------------------------------------------------------------------
# ALM / LCR / NSFR
# ---------------------------------------------------------------------------

def alm_report(db: Session, *, assets: List[Dict[str, Any]], liabilities: List[Dict[str, Any]],
               rate_shock_bps: float = 100.0, tenant_id: Optional[int] = None,
               as_of: Optional[str] = None, created_by: Optional[str] = None) -> Dict[str, Any]:
    """Asset-Liability Management gap report with rate-sensitivity (EVE) impact."""
    # Ladder into buckets inline (avoid persisting an extra snapshot).
    def bucket_of(days: float) -> str:
        for b in LIQUIDITY_BUCKETS:
            if b["lo"] <= days <= b["hi"]:
                return b["key"]
        return LIQUIDITY_BUCKETS[-1]["key"]

    rows = {b["key"]: {"assets": 0.0, "liabilities": 0.0} for b in LIQUIDITY_BUCKETS}
    for a in assets:
        rows[bucket_of(to_float(a.get("tenor_days", 0)))]["assets"] += to_float(a.get("amount", 0))
    for l in liabilities:
        rows[bucket_of(to_float(l.get("tenor_days", 0)))]["liabilities"] += to_float(l.get("amount", 0))

    shock = rate_shock_bps / 10000.0
    cumulative = 0.0
    eve_impact = 0.0
    buckets = []
    for i, b in enumerate(LIQUIDITY_BUCKETS):
        r = rows[b["key"]]
        gap = r["assets"] - r["liabilities"]
        cumulative += gap
        mid_years = ((b["lo"] + min(b["hi"], 3650)) / 2.0) / 365.0
        eve_impact += -gap * shock * mid_years  # duration-approx EVE sensitivity
        buckets.append({"bucket": b["key"], "rate_sensitive_gap": round(gap, 2),
                        "cumulative_gap": round(cumulative, 2)})
    results = {
        "buckets": buckets,
        "cumulative_gap": round(cumulative, 2),
        "rate_shock_bps": rate_shock_bps,
        "eve_impact": round(eve_impact, 2),
        "interpretation": "asset_sensitive" if cumulative > 0 else "liability_sensitive",
    }
    g = grounding_block("ALM Report", results)
    return _save(db, kind="alm", inputs={"assets": assets, "liabilities": liabilities,
                                          "rate_shock_bps": rate_shock_bps},
                 results={**results, "grounding": g},
                 narrative=(f"Balance sheet is {'asset' if cumulative > 0 else 'liability'}-sensitive; "
                            f"a {rate_shock_bps:.0f}bps shock moves EVE by {eve_impact:,.0f}."),
                 label="ALM Report", as_of=as_of, tenant_id=tenant_id, created_by=created_by)


def lcr(db: Session, *, hqla: float, outflows: Optional[Dict[str, float]] = None,
        inflows: float = 0.0, use_registry: bool = True, tenant_id: Optional[int] = None,
        as_of: Optional[str] = None, created_by: Optional[str] = None) -> Dict[str, Any]:
    """Liquidity Coverage Ratio = HQLA / net 30-day cash outflows (≥100%)."""
    outflows = outflows or {}
    gross_outflows = 0.0
    if outflows:
        gross_outflows = sum(to_float(v) for v in outflows.values())
    elif use_registry:
        for r in _funding_rows(db, tenant_id):
            gross_outflows += r["amount"] * LCR_RUNOFF.get(r["source_type"], 0.5)
    capped_inflows = min(inflows, 0.75 * gross_outflows)  # Basel 75% inflow cap
    net_outflows = max(gross_outflows - capped_inflows, 0.25 * gross_outflows, 1.0)
    ratio = safe_div(hqla, net_outflows, 0.0)
    results = {
        "hqla": round(hqla, 2),
        "gross_outflows": round(gross_outflows, 2),
        "capped_inflows": round(capped_inflows, 2),
        "net_cash_outflows": round(net_outflows, 2),
        "lcr_ratio_pct": pct(ratio),
        "compliant": ratio >= 1.0,
        "buffer_or_shortfall": round(hqla - net_outflows, 2),
    }
    g = grounding_block("LCR", results)
    return _save(db, kind="lcr", inputs={"hqla": hqla, "outflows": outflows, "inflows": inflows},
                 results={**results, "grounding": g},
                 narrative=f"LCR is {pct(ratio)}% ({'compliant' if ratio >= 1 else 'below 100% minimum'}).",
                 label="LCR", as_of=as_of, tenant_id=tenant_id, created_by=created_by)


def nsfr(db: Session, *, required_stable_funding: float, use_registry: bool = True,
         available_stable_funding: Optional[float] = None, tenant_id: Optional[int] = None,
         as_of: Optional[str] = None, created_by: Optional[str] = None) -> Dict[str, Any]:
    """Net Stable Funding Ratio = ASF / RSF (≥100%)."""
    if available_stable_funding is None and use_registry:
        available_stable_funding = sum(r["amount"] * NSFR_ASF.get(r["source_type"], r["stability_factor"])
                                       for r in _funding_rows(db, tenant_id))
    asf = to_float(available_stable_funding)
    rsf = max(to_float(required_stable_funding), 1.0)
    ratio = safe_div(asf, rsf, 0.0)
    results = {
        "available_stable_funding": round(asf, 2),
        "required_stable_funding": round(rsf, 2),
        "nsfr_ratio_pct": pct(ratio),
        "compliant": ratio >= 1.0,
        "surplus_or_deficit": round(asf - rsf, 2),
    }
    g = grounding_block("NSFR", results)
    return _save(db, kind="nsfr", inputs={"required_stable_funding": required_stable_funding},
                 results={**results, "grounding": g},
                 narrative=f"NSFR is {pct(ratio)}% ({'compliant' if ratio >= 1 else 'below minimum'}).",
                 label="NSFR", as_of=as_of, tenant_id=tenant_id, created_by=created_by)


# ---------------------------------------------------------------------------
# Cash forecasting, scenario & optimization
# ---------------------------------------------------------------------------

def cash_forecast(db: Session, *, opening_cash: float, horizon: int = 12,
                  monthly_inflow: float = 0.0, monthly_outflow: float = 0.0,
                  growth: float = 0.0, volatility: float = 0.05,
                  tenant_id: Optional[int] = None, as_of: Optional[str] = None,
                  created_by: Optional[str] = None) -> Dict[str, Any]:
    """Deterministic projected cash path with ± confidence bands."""
    series = []
    cash = opening_cash
    for t in range(1, horizon + 1):
        inflow = monthly_inflow * ((1 + growth) ** (t - 1))
        outflow = monthly_outflow * ((1 + growth) ** (t - 1))
        cash += inflow - outflow
        band = abs(cash) * volatility * (t ** 0.5)
        series.append({"t": t, "point": round(cash, 2),
                       "lower": round(cash - band, 2), "upper": round(cash + band, 2)})
    min_cash = min((p["lower"] for p in series), default=opening_cash)
    results = {"opening_cash": round(opening_cash, 2), "horizon": horizon,
               "series": series, "min_projected_cash": round(min_cash, 2),
               "liquidity_at_risk": min_cash < 0}
    g = grounding_block("Cash Forecast", results)
    return _save(db, kind="forecast", inputs={"opening_cash": opening_cash, "horizon": horizon},
                 results={**results, "grounding": g},
                 narrative=f"Projected minimum cash over {horizon}m is {min_cash:,.0f}.",
                 label="Cash Forecast", as_of=as_of, tenant_id=tenant_id, created_by=created_by)


def scenario_analysis(db: Session, *, base_hqla: float, base_outflows: float,
                      shocks: Optional[List[Dict[str, Any]]] = None,
                      tenant_id: Optional[int] = None, as_of: Optional[str] = None,
                      created_by: Optional[str] = None) -> Dict[str, Any]:
    """Apply named liquidity shocks and report LCR under each."""
    shocks = shocks or [
        {"name": "baseline", "hqla_haircut": 0.0, "outflow_uplift": 0.0},
        {"name": "deposit_runoff", "hqla_haircut": 0.05, "outflow_uplift": 0.25},
        {"name": "market_freeze", "hqla_haircut": 0.15, "outflow_uplift": 0.50},
        {"name": "combined_stress", "hqla_haircut": 0.25, "outflow_uplift": 0.75},
    ]
    scenarios = []
    for sh in shocks:
        hqla = base_hqla * (1 - to_float(sh.get("hqla_haircut", 0)))
        out = base_outflows * (1 + to_float(sh.get("outflow_uplift", 0)))
        ratio = safe_div(hqla, max(out, 1.0), 0.0)
        scenarios.append({"name": sh.get("name"), "hqla": round(hqla, 2),
                          "net_outflows": round(out, 2), "lcr_pct": pct(ratio),
                          "compliant": ratio >= 1.0})
    worst = min(scenarios, key=lambda s: s["lcr_pct"] or 0)
    results = {"scenarios": scenarios, "worst_case": worst}
    g = grounding_block("Liquidity Scenarios", results)
    return _save(db, kind="scenario", inputs={"base_hqla": base_hqla, "base_outflows": base_outflows},
                 results={**results, "grounding": g},
                 narrative=f"Worst-case scenario '{worst['name']}' yields LCR of {worst['lcr_pct']}%.",
                 label="Liquidity Scenarios", as_of=as_of, tenant_id=tenant_id, created_by=created_by)


def stress_liquidity(db: Session, *, hqla: float, base_outflows: float,
                     survival_days: int = 30, tenant_id: Optional[int] = None,
                     as_of: Optional[str] = None, created_by: Optional[str] = None) -> Dict[str, Any]:
    """Liquidity survival horizon under sustained stressed outflows."""
    daily_outflow = base_outflows / max(survival_days, 1) * 1.5  # 50% stress uplift
    survival = safe_div(hqla, daily_outflow, 0.0) or 0.0
    results = {"hqla": round(hqla, 2), "stressed_daily_outflow": round(daily_outflow, 2),
               "survival_horizon_days": round(survival, 1),
               "meets_30d": survival >= 30}
    g = grounding_block("Liquidity Stress", results)
    return _save(db, kind="scenario", inputs={"hqla": hqla, "base_outflows": base_outflows},
                 results={**results, "grounding": g},
                 narrative=f"Under stress the bank survives {survival:.0f} days on current HQLA.",
                 label="Liquidity Stress", as_of=as_of, tenant_id=tenant_id, created_by=created_by)


def funding_optimization(db: Session, *, target_amount: float, max_cost: Optional[float] = None,
                         min_stability: float = 0.5, tenant_id: Optional[int] = None,
                         as_of: Optional[str] = None, created_by: Optional[str] = None) -> Dict[str, Any]:
    """Greedy cost-minimizing funding mix meeting a stability floor.

    Sort available sources by rate ascending and draw until the target is met
    then report blended cost and stability. Explainable and deterministic.
    """
    rows = sorted(_funding_rows(db, tenant_id), key=lambda r: r["rate"])
    remaining = target_amount
    plan = []
    for r in rows:
        if remaining <= 0:
            break
        draw = min(r["amount"], remaining)
        if draw <= 0:
            continue
        plan.append({"name": r["name"], "source_type": r["source_type"],
                     "amount": round(draw, 2), "rate_pct": pct(r["rate"]),
                     "stability_factor": r["stability_factor"]})
        remaining -= draw
    drawn = target_amount - max(remaining, 0)
    blended_cost = safe_div(sum(p["amount"] * (p["rate_pct"] / 100.0) for p in plan), drawn, 0.0)
    blended_stability = safe_div(sum(p["amount"] * p["stability_factor"] for p in plan), drawn, 0.0)
    feasible = remaining <= 0 and blended_stability >= min_stability and \
        (max_cost is None or (blended_cost or 0) <= max_cost)
    results = {
        "target_amount": round(target_amount, 2),
        "drawn": round(drawn, 2),
        "unmet": round(max(remaining, 0), 2),
        "blended_cost_pct": pct(blended_cost),
        "blended_stability": round(blended_stability or 0, 3),
        "plan": plan,
        "feasible": feasible,
    }
    g = grounding_block("Funding Optimization", results)
    return _save(db, kind="scenario", inputs={"target_amount": target_amount, "min_stability": min_stability},
                 results={**results, "grounding": g},
                 narrative=(f"Lowest-cost mix funds {drawn:,.0f} at a blended {pct(blended_cost)}% "
                            f"(stability {blended_stability or 0:.2f})."),
                 label="Funding Optimization", as_of=as_of, tenant_id=tenant_id, created_by=created_by)


# ---------------------------------------------------------------------------
# KPIs & dashboard
# ---------------------------------------------------------------------------

def treasury_kpis(db: Session, *, tenant_id: Optional[int] = None) -> Dict[str, Any]:
    rows = _funding_rows(db, tenant_id)
    total_funding = sum(r["amount"] for r in rows)
    blended_cost = safe_div(sum(r["amount"] * r["rate"] for r in rows), total_funding, 0.0)
    stable = sum(r["amount"] * r["stability_factor"] for r in rows)
    concentration = 0.0
    if total_funding:
        by_type: Dict[str, float] = {}
        for r in rows:
            by_type[r["source_type"]] = by_type.get(r["source_type"], 0.0) + r["amount"]
        concentration = max(by_type.values()) / total_funding
    return {
        "total_funding": round(total_funding, 2),
        "source_count": len(rows),
        "blended_funding_cost_pct": pct(blended_cost),
        "stable_funding_ratio_pct": pct(safe_div(stable, total_funding, 0.0)),
        "funding_concentration_pct": pct(concentration),
        "wholesale_reliance_pct": pct(safe_div(
            sum(r["amount"] for r in rows if r["source_type"] in ("wholesale", "interbank", "repo")),
            total_funding, 0.0)),
    }


def dashboard(db: Session, *, tenant_id: Optional[int] = None) -> Dict[str, Any]:
    """Treasury command view: KPIs + latest snapshot per kind."""
    latest: Dict[str, Any] = {}
    q = db.query(FinTreasurySnapshot)
    if tenant_id is not None:
        q = q.filter(FinTreasurySnapshot.tenant_id == tenant_id)
    for s in q.order_by(FinTreasurySnapshot.id.desc()).limit(200).all():
        if s.kind not in latest:
            latest[s.kind] = {"snapshot_id": s.id, "label": s.label, "as_of": s.as_of,
                              "created_at": iso(s.created_at)}
    return {"kpis": treasury_kpis(db, tenant_id=tenant_id), "latest_snapshots": latest,
            "generated_at": iso(utcnow())}


def list_snapshots(db: Session, *, kind: Optional[str] = None, limit: int = 50,
                   tenant_id: Optional[int] = None) -> List[Dict[str, Any]]:
    q = db.query(FinTreasurySnapshot)
    if tenant_id is not None:
        q = q.filter(FinTreasurySnapshot.tenant_id == tenant_id)
    if kind:
        q = q.filter(FinTreasurySnapshot.kind == kind)
    return [{"snapshot_id": s.id, "kind": s.kind, "label": s.label, "as_of": s.as_of,
             "checksum": s.checksum, "created_at": iso(s.created_at)}
            for s in q.order_by(FinTreasurySnapshot.id.desc()).limit(limit).all()]
