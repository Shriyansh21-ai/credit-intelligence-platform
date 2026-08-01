"""M2 — Enterprise Portfolio Intelligence.

A portfolio construction, analytics and optimization engine over commercial
SME and corporate loan books. Positions can be added explicitly or pulled from
the platform's live assessment set (``data_access.portfolio_exposures``). Every
analytic is deterministic and grounded: sector/geo/industry/borrower
concentration (HHI + Gini), expected & unexpected loss (single-factor Vasicek)
RAROC, Monte-Carlo loss distribution (VaR/ES), rating migration, and early-
warning signals. Results persist to ``fin_portfolio_analyses``.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from backend.app.models.financial_intelligence import (
    FinPortfolio, FinPortfolioAnalysis, FinPortfolioPosition,
)
from . import data_access as da
from .common import (
    DeterministicRNG, checksum, clamp, expected_loss, gini, grounding_block,
    herfindahl, iso, norm_cdf, norm_ppf, pct, percentile, safe_div, to_float,
    unexpected_loss, utcnow,
)

PORTFOLIO_TYPES = ["commercial", "sme", "corporate", "retail", "mixed"]
ANALYSIS_TYPES = ["summary", "concentration", "loss", "raroc", "optimization",
                  "simulation", "migration", "ews", "insights"]


# ---------------------------------------------------------------------------
# Portfolio & position CRUD
# ---------------------------------------------------------------------------

def create_portfolio(db: Session, *, key: str, name: str, portfolio_type: str = "commercial",
                     currency: str = "INR", description: Optional[str] = None,
                     meta: Optional[dict] = None, tenant_id: Optional[int] = None,
                     created_by: Optional[str] = None) -> FinPortfolio:
    if portfolio_type not in PORTFOLIO_TYPES:
        raise ValueError(f"unknown portfolio_type '{portfolio_type}'")
    existing = (db.query(FinPortfolio)
                .filter(FinPortfolio.tenant_id == tenant_id, FinPortfolio.key == key).first())
    if existing:
        raise ValueError(f"portfolio '{key}' already exists")
    row = FinPortfolio(tenant_id=tenant_id, key=key, name=name, portfolio_type=portfolio_type,
                       currency=currency, description=description, meta=meta or {},
                       created_by=created_by)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def list_portfolios(db: Session, *, tenant_id: Optional[int] = None) -> List[FinPortfolio]:
    q = db.query(FinPortfolio)
    if tenant_id is not None:
        q = q.filter(FinPortfolio.tenant_id == tenant_id)
    return q.order_by(FinPortfolio.id.desc()).all()


def get_portfolio(db: Session, portfolio_id: int) -> Optional[FinPortfolio]:
    return db.query(FinPortfolio).filter(FinPortfolio.id == portfolio_id).first()


def add_position(db: Session, *, portfolio_id: int, company_ref: str, ead: float,
                 pd: float = 0.05, lgd: float = 0.45, industry: Optional[str] = None,
                 country: Optional[str] = None, region: Optional[str] = None,
                 rating: Optional[str] = None, maturity_years: float = 3.0,
                 spread: float = 0.03, assessment_id: Optional[int] = None,
                 meta: Optional[dict] = None, tenant_id: Optional[int] = None) -> FinPortfolioPosition:
    if not get_portfolio(db, portfolio_id):
        raise ValueError("portfolio not found")
    row = FinPortfolioPosition(
        tenant_id=tenant_id, portfolio_id=portfolio_id, company_ref=company_ref,
        assessment_id=assessment_id, industry=industry, country=country, region=region,
        rating=rating, ead=to_float(ead), pd=clamp(to_float(pd), 0.0, 1.0),
        lgd=clamp(to_float(lgd), 0.0, 1.0), maturity_years=to_float(maturity_years, 3.0),
        spread=to_float(spread, 0.03), meta=meta or {})
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def sync_from_platform(db: Session, *, portfolio_id: int,
                       tenant_id: Optional[int] = None) -> Dict[str, Any]:
    """Populate a portfolio from the live per-company exposure set."""
    if not get_portfolio(db, portfolio_id):
        raise ValueError("portfolio not found")
    added = 0
    for e in da.portfolio_exposures(db):
        if not e.get("company_ref"):
            continue
        add_position(db, portfolio_id=portfolio_id, company_ref=e["company_ref"],
                     ead=e["ead"], pd=e["pd"], lgd=e["lgd"], industry=e.get("industry"),
                     country=e.get("country"), rating=e.get("rating"), tenant_id=tenant_id)
        added += 1
    return {"portfolio_id": portfolio_id, "positions_added": added}


def list_positions(db: Session, *, portfolio_id: int) -> List[FinPortfolioPosition]:
    return (db.query(FinPortfolioPosition)
            .filter(FinPortfolioPosition.portfolio_id == portfolio_id)
            .order_by(FinPortfolioPosition.ead.desc()).all())


def _pos_rows(db: Session, portfolio_id: int) -> List[Dict[str, Any]]:
    return [{"company_ref": p.company_ref, "industry": p.industry or "general",
             "country": p.country or "IN", "region": p.region or (p.country or "IN"),
             "rating": p.rating, "ead": p.ead, "pd": p.pd, "lgd": p.lgd,
             "maturity_years": p.maturity_years, "spread": p.spread}
            for p in list_positions(db, portfolio_id=portfolio_id)]


def _save(db: Session, *, portfolio_id: Optional[int], analysis_type: str, inputs: dict,
          results: dict, narrative: Optional[str], tenant_id: Optional[int],
          created_by: Optional[str]) -> Dict[str, Any]:
    row = FinPortfolioAnalysis(
        tenant_id=tenant_id, portfolio_id=portfolio_id, analysis_type=analysis_type,
        inputs=inputs, results=results, narrative=narrative, checksum=checksum(results),
        created_by=created_by)
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"analysis_id": row.id, "analysis_type": analysis_type,
            "checksum": row.checksum, **results, "narrative": narrative}


# ---------------------------------------------------------------------------
# Loss analytics — single-factor Vasicek portfolio model.
# ---------------------------------------------------------------------------

def _asset_correlation(pd: float) -> float:
    """Basel IRB asset-correlation formula (corporate) as a function of PD."""
    w = (1 - math.exp(-50 * pd)) / (1 - math.exp(-50))
    return 0.12 * w + 0.24 * (1 - w)


def _portfolio_loss_stats(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    total_ead = sum(r["ead"] for r in rows) or 0.0
    el = sum(expected_loss(r["pd"], r["lgd"], r["ead"]) for r in rows)
    # Diversified UL: sqrt of sum of pairwise contributions via avg correlation proxy.
    ul_names = [unexpected_loss(r["pd"], r["lgd"], r["ead"]) for r in rows]
    avg_corr = safe_div(sum(_asset_correlation(r["pd"]) for r in rows), len(rows) or 1, 0.15)
    sum_ul_sq = sum(u * u for u in ul_names)
    cross = sum(ul_names[i] * ul_names[j] for i in range(len(ul_names))
                for j in range(len(ul_names)) if i != j)
    ul = (sum_ul_sq + avg_corr * cross) ** 0.5
    return {"total_ead": round(total_ead, 2), "expected_loss": round(el, 2),
            "unexpected_loss": round(ul, 2),
            "el_rate_pct": pct(safe_div(el, total_ead, 0.0)),
            "avg_asset_correlation": round(avg_corr or 0, 4)}


def summary(db: Session, *, portfolio_id: int, tenant_id: Optional[int] = None,
            created_by: Optional[str] = None) -> Dict[str, Any]:
    rows = _pos_rows(db, portfolio_id)
    if not rows:
        raise ValueError("portfolio has no positions")
    stats = _portfolio_loss_stats(rows)
    ratings: Dict[str, int] = {}
    for r in rows:
        ratings[r["rating"] or "NR"] = ratings.get(r["rating"] or "NR", 0) + 1
    wavg_pd = safe_div(sum(r["ead"] * r["pd"] for r in rows), stats["total_ead"], 0.0)
    results = {**stats, "position_count": len(rows),
               "weighted_avg_pd_pct": pct(wavg_pd),
               "weighted_avg_maturity": round(safe_div(
                   sum(r["ead"] * r["maturity_years"] for r in rows), stats["total_ead"], 0.0) or 0, 2),
               "rating_distribution": ratings}
    g = grounding_block("Portfolio Summary", results)
    return _save(db, portfolio_id=portfolio_id, analysis_type="summary", inputs={},
                 results={**results, "grounding": g},
                 narrative=(f"Portfolio of {len(rows)} names, EAD {stats['total_ead']:,.0f}, "
                            f"expected loss {stats['expected_loss']:,.0f} ({stats['el_rate_pct']}%)."),
                 tenant_id=tenant_id, created_by=created_by)


def concentration(db: Session, *, portfolio_id: int, top_n: int = 10,
                  tenant_id: Optional[int] = None, created_by: Optional[str] = None) -> Dict[str, Any]:
    rows = _pos_rows(db, portfolio_id)
    if not rows:
        raise ValueError("portfolio has no positions")
    total = sum(r["ead"] for r in rows) or 1.0

    def agg(field: str) -> Dict[str, float]:
        out: Dict[str, float] = {}
        for r in rows:
            out[r[field]] = out.get(r[field], 0.0) + r["ead"]
        return out

    def dim(field: str) -> Dict[str, Any]:
        a = agg(field)
        shares = {k: round(v / total, 4) for k, v in a.items()}
        return {"exposure": {k: round(v, 2) for k, v in a.items()},
                "shares": shares, "hhi": round(herfindahl(list(a.values())), 4),
                "gini": round(gini(list(a.values())), 4)}

    borrowers = sorted(rows, key=lambda r: r["ead"], reverse=True)
    single_largest = borrowers[0]["ead"] / total if borrowers else 0.0
    top = [{"company_ref": r["company_ref"], "ead": round(r["ead"], 2),
            "share_pct": pct(r["ead"] / total)} for r in borrowers[:top_n]]
    # Heatmap: industry × region exposure grid.
    heat: Dict[str, Dict[str, float]] = {}
    for r in rows:
        heat.setdefault(r["industry"], {}).setdefault(r["region"], 0.0)
        heat[r["industry"]][r["region"]] += r["ead"]
    results = {
        "sector": dim("industry"),
        "geography": dim("country"),
        "region": dim("region"),
        "borrower_hhi": round(herfindahl([r["ead"] for r in rows]), 4),
        "single_largest_exposure_pct": pct(single_largest),
        "top_exposures": top,
        "heatmap": {k: {rk: round(rv, 2) for rk, rv in v.items()} for k, v in heat.items()},
        "diversification_score": round(1 - herfindahl([r["ead"] for r in rows]), 4),
    }
    g = grounding_block("Concentration", results)
    return _save(db, portfolio_id=portfolio_id, analysis_type="concentration", inputs={"top_n": top_n},
                 results={**results, "grounding": g},
                 narrative=(f"Single largest exposure is {pct(single_largest)}% of EAD; "
                            f"borrower HHI {results['borrower_hhi']}."),
                 tenant_id=tenant_id, created_by=created_by)


def loss_analysis(db: Session, *, portfolio_id: int, confidence: float = 0.999,
                  tenant_id: Optional[int] = None, created_by: Optional[str] = None) -> Dict[str, Any]:
    rows = _pos_rows(db, portfolio_id)
    if not rows:
        raise ValueError("portfolio has no positions")
    stats = _portfolio_loss_stats(rows)
    # Vasicek analytic tail loss per name at the given confidence.
    z = norm_ppf(confidence)
    tail = 0.0
    for r in rows:
        rho = _asset_correlation(r["pd"])
        cond_pd = norm_cdf((norm_ppf(clamp(r["pd"], 1e-6, 1 - 1e-6)) + (rho ** 0.5) * z) / ((1 - rho) ** 0.5))
        tail += cond_pd * r["lgd"] * r["ead"]
    econ_capital = max(tail - stats["expected_loss"], 0.0)
    results = {**stats, "confidence": confidence,
               "credit_var": round(tail, 2),
               "economic_capital": round(econ_capital, 2)}
    g = grounding_block("Portfolio Loss", results)
    return _save(db, portfolio_id=portfolio_id, analysis_type="loss", inputs={"confidence": confidence},
                 results={**results, "grounding": g},
                 narrative=(f"Credit VaR at {pct(confidence)}% is {tail:,.0f}; "
                            f"economic capital {econ_capital:,.0f}."),
                 tenant_id=tenant_id, created_by=created_by)


def raroc(db: Session, *, portfolio_id: int, cost_of_capital: float = 0.12,
          opex_rate: float = 0.005, confidence: float = 0.999,
          tenant_id: Optional[int] = None, created_by: Optional[str] = None) -> Dict[str, Any]:
    """Risk-Adjusted Return On Capital = (revenue − EL − opex) / economic capital."""
    rows = _pos_rows(db, portfolio_id)
    if not rows:
        raise ValueError("portfolio has no positions")
    stats = _portfolio_loss_stats(rows)
    z = norm_ppf(confidence)
    tail = 0.0
    for r in rows:
        rho = _asset_correlation(r["pd"])
        cond_pd = norm_cdf((norm_ppf(clamp(r["pd"], 1e-6, 1 - 1e-6)) + (rho ** 0.5) * z) / ((1 - rho) ** 0.5))
        tail += cond_pd * r["lgd"] * r["ead"]
    econ_capital = max(tail - stats["expected_loss"], 1.0)
    revenue = sum(r["ead"] * r["spread"] for r in rows)
    opex = sum(r["ead"] * opex_rate for r in rows)
    net = revenue - stats["expected_loss"] - opex
    raroc_val = safe_div(net, econ_capital, 0.0)
    results = {
        "gross_revenue": round(revenue, 2),
        "expected_loss": stats["expected_loss"],
        "opex": round(opex, 2),
        "net_income": round(net, 2),
        "economic_capital": round(econ_capital, 2),
        "raroc_pct": pct(raroc_val),
        "cost_of_capital_pct": pct(cost_of_capital),
        "eva": round(net - econ_capital * cost_of_capital, 2),
        "creates_value": (raroc_val or 0) > cost_of_capital,
    }
    g = grounding_block("RAROC", results)
    return _save(db, portfolio_id=portfolio_id, analysis_type="raroc",
                 inputs={"cost_of_capital": cost_of_capital, "opex_rate": opex_rate},
                 results={**results, "grounding": g},
                 narrative=(f"RAROC is {pct(raroc_val)}% vs a {pct(cost_of_capital)}% hurdle "
                            f"({'value-creating' if (raroc_val or 0) > cost_of_capital else 'value-destroying'})."),
                 tenant_id=tenant_id, created_by=created_by)


def simulate(db: Session, *, portfolio_id: int, iterations: int = 5000, seed: int = 42,
             confidence: float = 0.99, tenant_id: Optional[int] = None,
             created_by: Optional[str] = None) -> Dict[str, Any]:
    """Monte-Carlo single-factor default simulation → loss distribution."""
    rows = _pos_rows(db, portfolio_id)
    if not rows:
        raise ValueError("portfolio has no positions")
    rng = DeterministicRNG(seed)
    losses: List[float] = []
    thresholds = [(norm_ppf(clamp(r["pd"], 1e-6, 1 - 1e-6)), _asset_correlation(r["pd"]) ** 0.5,
                   r["lgd"], r["ead"]) for r in rows]
    for _ in range(max(iterations, 100)):
        m = rng.normal()  # systematic factor
        loss = 0.0
        for thr, sqrt_rho, lgd, ead in thresholds:
            idio = rng.normal()
            a = sqrt_rho * m + ((1 - sqrt_rho ** 2) ** 0.5) * idio
            if a < thr:
                loss += lgd * ead
        losses.append(loss)
    el = sum(losses) / len(losses)
    var = percentile(losses, confidence * 100)
    tail = [x for x in losses if x >= var]
    es = sum(tail) / len(tail) if tail else var
    results = {
        "iterations": len(losses), "seed": seed, "confidence": confidence,
        "mean_loss": round(el, 2),
        "loss_var": round(var, 2),
        "expected_shortfall": round(es, 2),
        "max_loss": round(max(losses), 2),
        "p50": round(percentile(losses, 50), 2),
        "p95": round(percentile(losses, 95), 2),
        "p99": round(percentile(losses, 99), 2),
    }
    g = grounding_block("Portfolio Simulation", results)
    return _save(db, portfolio_id=portfolio_id, analysis_type="simulation",
                 inputs={"iterations": iterations, "seed": seed, "confidence": confidence},
                 results={**results, "grounding": g},
                 narrative=(f"Simulated loss VaR at {pct(confidence)}% is {var:,.0f}; "
                            f"expected shortfall {es:,.0f}."),
                 tenant_id=tenant_id, created_by=created_by)


def optimize(db: Session, *, portfolio_id: int, max_single_exposure_pct: float = 0.10,
             max_sector_pct: float = 0.30, tenant_id: Optional[int] = None,
             created_by: Optional[str] = None) -> Dict[str, Any]:
    """Explainable concentration-reduction: trim names/sectors above limits."""
    rows = _pos_rows(db, portfolio_id)
    if not rows:
        raise ValueError("portfolio has no positions")
    total = sum(r["ead"] for r in rows) or 1.0
    actions = []
    new_ead = {r["company_ref"]: r["ead"] for r in rows}
    # Single-name limit.
    for r in rows:
        cap = max_single_exposure_pct * total
        if r["ead"] > cap:
            actions.append({"type": "trim_single_name", "company_ref": r["company_ref"],
                            "from": round(r["ead"], 2), "to": round(cap, 2),
                            "reason": f"exceeds {pct(max_single_exposure_pct)}% single-name limit"})
            new_ead[r["company_ref"]] = cap
    # Sector limit.
    sector: Dict[str, float] = {}
    for r in rows:
        sector[r["industry"]] = sector.get(r["industry"], 0.0) + new_ead[r["company_ref"]]
    for sec, exp in sector.items():
        cap = max_sector_pct * total
        if exp > cap:
            scale = cap / exp
            for r in rows:
                if r["industry"] == sec:
                    new_ead[r["company_ref"]] *= scale
            actions.append({"type": "trim_sector", "sector": sec, "from": round(exp, 2),
                            "to": round(cap, 2), "reason": f"exceeds {pct(max_sector_pct)}% sector limit"})
    freed = round(total - sum(new_ead.values()), 2)
    before_hhi = herfindahl([r["ead"] for r in rows])
    after_hhi = herfindahl(list(new_ead.values()))
    results = {
        "actions": actions,
        "capital_freed": freed,
        "hhi_before": round(before_hhi, 4),
        "hhi_after": round(after_hhi, 4),
        "diversification_improvement_pct": pct(safe_div(before_hhi - after_hhi, before_hhi, 0.0)),
        "target_weights": {k: round(v / total, 4) for k, v in new_ead.items()},
    }
    g = grounding_block("Portfolio Optimization", results)
    return _save(db, portfolio_id=portfolio_id, analysis_type="optimization",
                 inputs={"max_single_exposure_pct": max_single_exposure_pct,
                         "max_sector_pct": max_sector_pct},
                 results={**results, "grounding": g},
                 narrative=(f"{len(actions)} rebalancing actions free {freed:,.0f} of EAD and "
                            f"cut HHI from {round(before_hhi,4)} to {round(after_hhi,4)}."),
                 tenant_id=tenant_id, created_by=created_by)


# Rating transition matrix (annual, %), simplified S&P-style.
TRANSITION = {
    "AAA": {"AAA": 0.90, "AA": 0.09, "A": 0.006, "BBB": 0.003, "D": 0.001},
    "AA": {"AAA": 0.02, "AA": 0.90, "A": 0.07, "BBB": 0.008, "D": 0.002},
    "A": {"AA": 0.03, "A": 0.90, "BBB": 0.06, "BB": 0.007, "D": 0.003},
    "BBB": {"A": 0.05, "BBB": 0.86, "BB": 0.07, "B": 0.015, "D": 0.005},
    "BB": {"BBB": 0.06, "BB": 0.80, "B": 0.11, "CCC": 0.02, "D": 0.01},
    "B": {"BB": 0.05, "B": 0.78, "CCC": 0.12, "D": 0.05},
    "CCC": {"B": 0.10, "CCC": 0.60, "D": 0.30},
}


def migration_analysis(db: Session, *, portfolio_id: int, tenant_id: Optional[int] = None,
                       created_by: Optional[str] = None) -> Dict[str, Any]:
    """Apply the annual transition matrix to project rating drift & default flow."""
    rows = _pos_rows(db, portfolio_id)
    if not rows:
        raise ValueError("portfolio has no positions")
    projected_default_ead = 0.0
    drift = {"upgrades": 0.0, "stable": 0.0, "downgrades": 0.0, "defaults": 0.0}
    order = ["AAA", "AA", "A", "BBB", "BB", "B", "CCC", "D"]
    for r in rows:
        rating = r["rating"] if r["rating"] in TRANSITION else "BBB"
        trans = TRANSITION.get(rating, {})
        cur_idx = order.index(rating) if rating in order else 3
        for to, prob in trans.items():
            ead_flow = r["ead"] * prob
            if to == "D":
                drift["defaults"] += ead_flow
                projected_default_ead += ead_flow
            else:
                to_idx = order.index(to)
                if to_idx < cur_idx:
                    drift["upgrades"] += ead_flow
                elif to_idx > cur_idx:
                    drift["downgrades"] += ead_flow
                else:
                    drift["stable"] += ead_flow
    total = sum(r["ead"] for r in rows) or 1.0
    results = {"drift": {k: round(v, 2) for k, v in drift.items()},
               "projected_default_ead": round(projected_default_ead, 2),
               "projected_default_rate_pct": pct(projected_default_ead / total),
               "downgrade_ratio_pct": pct(drift["downgrades"] / total)}
    g = grounding_block("Migration Analysis", results)
    return _save(db, portfolio_id=portfolio_id, analysis_type="migration", inputs={},
                 results={**results, "grounding": g},
                 narrative=(f"Projected 1y default EAD {projected_default_ead:,.0f} "
                            f"({pct(projected_default_ead/total)}%)."),
                 tenant_id=tenant_id, created_by=created_by)


def early_warning(db: Session, *, portfolio_id: int, pd_threshold: float = 0.10,
                  tenant_id: Optional[int] = None, created_by: Optional[str] = None) -> Dict[str, Any]:
    """Flag positions on watch by PD, rating and concentration contribution."""
    rows = _pos_rows(db, portfolio_id)
    if not rows:
        raise ValueError("portfolio has no positions")
    total = sum(r["ead"] for r in rows) or 1.0
    signals = []
    for r in rows:
        flags = []
        if r["pd"] >= pd_threshold:
            flags.append(f"elevated PD {pct(r['pd'])}%")
        if r["rating"] in ("CCC", "CC", "C", "B"):
            flags.append(f"speculative rating {r['rating']}")
        if r["ead"] / total > 0.10:
            flags.append(f"single-name concentration {pct(r['ead']/total)}%")
        if flags:
            severity = "high" if r["pd"] >= pd_threshold and r["rating"] in ("CCC", "CC", "C") else "medium"
            signals.append({"company_ref": r["company_ref"], "ead": round(r["ead"], 2),
                            "pd_pct": pct(r["pd"]), "rating": r["rating"],
                            "severity": severity, "flags": flags})
    signals.sort(key=lambda s: s["ead"], reverse=True)
    results = {"watchlist_count": len(signals),
               "watchlist_ead": round(sum(s["ead"] for s in signals), 2),
               "watchlist_ead_pct": pct(sum(s["ead"] for s in signals) / total),
               "signals": signals}
    g = grounding_block("Early Warning Signals", results)
    return _save(db, portfolio_id=portfolio_id, analysis_type="ews", inputs={"pd_threshold": pd_threshold},
                 results={**results, "grounding": g},
                 narrative=f"{len(signals)} positions on the watchlist ({results['watchlist_ead_pct']}% of EAD).",
                 tenant_id=tenant_id, created_by=created_by)


def ai_insights(db: Session, *, portfolio_id: int, tenant_id: Optional[int] = None,
                created_by: Optional[str] = None) -> Dict[str, Any]:
    """Composite grounded insight combining summary, concentration and EWS."""
    s = summary(db, portfolio_id=portfolio_id, tenant_id=tenant_id, created_by=created_by)
    c = concentration(db, portfolio_id=portfolio_id, tenant_id=tenant_id, created_by=created_by)
    e = early_warning(db, portfolio_id=portfolio_id, tenant_id=tenant_id, created_by=created_by)
    insights = []
    if (c.get("single_largest_exposure_pct") or 0) > 10:
        insights.append("Single-name concentration exceeds the 10% guideline — consider trimming top exposures.")
    if (e.get("watchlist_ead_pct") or 0) > 15:
        insights.append("Watchlist exposure is elevated — prioritise remediation on high-severity names.")
    if (s.get("el_rate_pct") or 0) > 2:
        insights.append("Expected-loss rate is above 2% — reprice or de-risk the weakest cohorts.")
    if not insights:
        insights.append("Portfolio is well-diversified with contained expected loss.")
    results = {"summary": {k: s[k] for k in ("total_ead", "expected_loss", "el_rate_pct")},
               "single_largest_exposure_pct": c.get("single_largest_exposure_pct"),
               "watchlist_ead_pct": e.get("watchlist_ead_pct"),
               "insights": insights}
    g = grounding_block("Portfolio AI Insights", results)
    return _save(db, portfolio_id=portfolio_id, analysis_type="insights", inputs={},
                 results={**results, "grounding": g},
                 narrative=" ".join(insights), tenant_id=tenant_id, created_by=created_by)


def list_analyses(db: Session, *, portfolio_id: Optional[int] = None,
                  analysis_type: Optional[str] = None, limit: int = 50,
                  tenant_id: Optional[int] = None) -> List[Dict[str, Any]]:
    q = db.query(FinPortfolioAnalysis)
    if tenant_id is not None:
        q = q.filter(FinPortfolioAnalysis.tenant_id == tenant_id)
    if portfolio_id is not None:
        q = q.filter(FinPortfolioAnalysis.portfolio_id == portfolio_id)
    if analysis_type:
        q = q.filter(FinPortfolioAnalysis.analysis_type == analysis_type)
    return [{"analysis_id": a.id, "analysis_type": a.analysis_type,
             "portfolio_id": a.portfolio_id, "checksum": a.checksum,
             "created_at": iso(a.created_at)}
            for a in q.order_by(FinPortfolioAnalysis.id.desc()).limit(limit).all()]
