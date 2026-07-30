"""M9 — Quantitative Risk Platform.

Advanced, deterministic quantitative models: Monte-Carlo simulation (correlated
factors via Cholesky), Value-at-Risk (parametric / historical / Monte-Carlo),
Expected Shortfall, stress testing, sensitivity analysis, scenario trees, risk
attribution (component VaR), correlation matrices, volatility models (EWMA) and
tail-risk metrics. Uses only the stdlib-backed math in :mod:`common` and the
seedable RNG for exact reproducibility. Results persist to
``fin_risk_simulations``.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence

from sqlalchemy.orm import Session

from backend.app.models.financial_intelligence import FinRiskSimulation
from . import data_access as da
from .common import (
    DeterministicRNG, checksum, clamp, correlation, grounding_block, iso, mean,
    norm_pdf, norm_ppf, percentile, safe_div, stdev, to_float, utcnow,
)

SIM_TYPES = ["montecarlo", "var", "es", "stress", "sensitivity", "scenario_tree",
             "attribution", "correlation", "volatility", "tail"]


def _cholesky(matrix: List[List[float]]) -> List[List[float]]:
    """Lower-triangular Cholesky factor (PSD-safe with tiny jitter)."""
    n = len(matrix)
    L = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1):
            s = sum(L[i][k] * L[j][k] for k in range(j))
            if i == j:
                L[i][j] = math.sqrt(max(matrix[i][i] - s, 1e-12))
            else:
                L[i][j] = safe_div(matrix[i][j] - s, L[j][j], 0.0) or 0.0
    return L


def _save(db: Session, *, sim_type: str, subject_ref: Optional[str], seed: Optional[int],
          iterations: int, inputs: dict, results: dict, narrative: Optional[str],
          portfolio_id: Optional[int], tenant_id: Optional[int],
          created_by: Optional[str]) -> Dict[str, Any]:
    row = FinRiskSimulation(
        tenant_id=tenant_id, sim_type=sim_type, subject_ref=subject_ref,
        portfolio_id=portfolio_id, seed=seed, iterations=iterations, inputs=inputs,
        results=results, narrative=narrative, checksum=checksum(results), created_by=created_by)
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"simulation_id": row.id, "sim_type": sim_type, "checksum": row.checksum,
            **results, "narrative": narrative}


# ---------------------------------------------------------------------------
# Monte Carlo (correlated factors)
# ---------------------------------------------------------------------------

def monte_carlo(db: Session, *, positions: List[Dict[str, Any]], iterations: int = 10000,
                seed: int = 7, correlation_matrix: Optional[List[List[float]]] = None,
                confidence: float = 0.99, subject_ref: Optional[str] = None,
                tenant_id: Optional[int] = None, created_by: Optional[str] = None) -> Dict[str, Any]:
    """Simulate portfolio P&L from position (mean, vol, exposure) with correlations."""
    if not positions:
        raise ValueError("positions required")
    n = len(positions)
    mus = [to_float(p.get("mean", 0.0)) for p in positions]
    vols = [to_float(p.get("vol", 0.1)) for p in positions]
    weights = [to_float(p.get("exposure", p.get("weight", 1.0))) for p in positions]
    if correlation_matrix is None:
        correlation_matrix = [[1.0 if i == j else 0.2 for j in range(n)] for i in range(n)]
    L = _cholesky(correlation_matrix)
    rng = DeterministicRNG(seed)
    pnl: List[float] = []
    for _ in range(max(iterations, 100)):
        z = [rng.normal() for _ in range(n)]
        corr_z = [sum(L[i][k] * z[k] for k in range(i + 1)) for i in range(n)]
        total = sum(weights[i] * (mus[i] + vols[i] * corr_z[i]) for i in range(n))
        pnl.append(total)
    losses = [-x for x in pnl]
    var = percentile(losses, confidence * 100)
    tail = [x for x in losses if x >= var]
    es = mean(tail) if tail else var
    results = {
        "iterations": len(pnl), "seed": seed, "confidence": confidence,
        "mean_pnl": round(mean(pnl), 4), "pnl_vol": round(stdev(pnl), 4),
        "var": round(var, 4), "expected_shortfall": round(es, 4),
        "worst_loss": round(max(losses), 4),
        "percentiles": {"p50": round(percentile(pnl, 50), 4),
                        "p5": round(percentile(pnl, 5), 4),
                        "p1": round(percentile(pnl, 1), 4)},
    }
    g = grounding_block("Monte Carlo", results)
    return _save(db, sim_type="montecarlo", subject_ref=subject_ref, seed=seed,
                 iterations=len(pnl), inputs={"positions": positions, "confidence": confidence},
                 results={**results, "grounding": g},
                 narrative=f"Monte-Carlo VaR at {round(confidence*100,1)}% is {var:,.2f}; ES {es:,.2f}.",
                 portfolio_id=None, tenant_id=tenant_id, created_by=created_by)


# ---------------------------------------------------------------------------
# VaR / ES
# ---------------------------------------------------------------------------

def value_at_risk(db: Session, *, returns: Optional[List[float]] = None,
                  portfolio_value: float = 1_000_000.0, mean_return: Optional[float] = None,
                  volatility: Optional[float] = None, confidence: float = 0.99,
                  method: str = "parametric", horizon_days: int = 1,
                  subject_ref: Optional[str] = None, tenant_id: Optional[int] = None,
                  created_by: Optional[str] = None) -> Dict[str, Any]:
    """VaR & ES by parametric (normal), historical, or supplied-returns method."""
    z = norm_ppf(confidence)
    scale = math.sqrt(max(horizon_days, 1))
    if method == "historical" and returns:
        losses = sorted(-r for r in returns)
        var_ret = percentile(losses, confidence * 100)
        tail = [x for x in losses if x >= var_ret]
        es_ret = mean(tail) if tail else var_ret
    else:
        mu = mean(returns) if returns else to_float(mean_return, 0.0)
        sigma = stdev(returns) if returns and len(returns) > 1 else to_float(volatility, 0.02)
        var_ret = (-mu + z * sigma) * scale
        # Closed-form normal ES = -mu + sigma * phi(z) / (1 - confidence).
        es_ret = (-mu + sigma * safe_div(norm_pdf(z), 1 - confidence, 0.0)) * scale
    results = {
        "method": method, "confidence": confidence, "horizon_days": horizon_days,
        "portfolio_value": round(portfolio_value, 2),
        "var_return_pct": round(var_ret * 100, 4),
        "var_amount": round(var_ret * portfolio_value, 2),
        "es_return_pct": round(es_ret * 100, 4),
        "es_amount": round(es_ret * portfolio_value, 2),
    }
    g = grounding_block("Value at Risk", results)
    return _save(db, sim_type="var", subject_ref=subject_ref, seed=None, iterations=len(returns or []),
                 inputs={"method": method, "confidence": confidence, "horizon_days": horizon_days},
                 results={**results, "grounding": g},
                 narrative=f"{method.title()} {round(confidence*100,1)}% VaR is {results['var_amount']:,.0f}.",
                 portfolio_id=None, tenant_id=tenant_id, created_by=created_by)


# ---------------------------------------------------------------------------
# Stress & sensitivity
# ---------------------------------------------------------------------------

def stress_test(db: Session, *, base_value: float, factors: Dict[str, float],
                scenarios: Optional[List[Dict[str, Any]]] = None,
                subject_ref: Optional[str] = None, tenant_id: Optional[int] = None,
                created_by: Optional[str] = None) -> Dict[str, Any]:
    """Apply named factor shocks (sensitivity × shock) to a base value."""
    scenarios = scenarios or [
        {"name": "rates_+200bps", "shocks": {"rates": 0.02}},
        {"name": "equity_-20pct", "shocks": {"equity": -0.20}},
        {"name": "credit_+150bps", "shocks": {"credit": 0.015}},
        {"name": "fx_-10pct", "shocks": {"fx": -0.10}},
        {"name": "combined", "shocks": {"rates": 0.02, "equity": -0.20, "credit": 0.015}},
    ]
    out = []
    for sc in scenarios:
        impact = sum(to_float(factors.get(f, 0.0)) * to_float(v)
                     for f, v in sc.get("shocks", {}).items())
        out.append({"name": sc["name"], "pnl_impact": round(impact, 2),
                    "stressed_value": round(base_value + impact, 2),
                    "impact_pct": round(safe_div(impact, base_value, 0.0) * 100, 3)})
    worst = min(out, key=lambda s: s["pnl_impact"])
    results = {"base_value": round(base_value, 2), "scenarios": out, "worst_case": worst}
    g = grounding_block("Stress Test", results)
    return _save(db, sim_type="stress", subject_ref=subject_ref, seed=None, iterations=len(scenarios),
                 inputs={"factors": factors}, results={**results, "grounding": g},
                 narrative=f"Worst scenario '{worst['name']}' impacts P&L by {worst['pnl_impact']:,.0f}.",
                 portfolio_id=None, tenant_id=tenant_id, created_by=created_by)


def sensitivity(db: Session, *, base_value: float, factors: Dict[str, float],
                shock: float = 0.01, subject_ref: Optional[str] = None,
                tenant_id: Optional[int] = None, created_by: Optional[str] = None) -> Dict[str, Any]:
    """Per-factor deltas: change in value for a unit shock to each factor."""
    deltas = {}
    for f, sensitivity_val in factors.items():
        deltas[f] = {"delta_per_unit": round(to_float(sensitivity_val), 4),
                     "impact_at_shock": round(to_float(sensitivity_val) * shock, 4)}
    dominant = max(deltas.items(), key=lambda kv: abs(kv[1]["impact_at_shock"]), default=(None, None))
    results = {"base_value": round(base_value, 2), "shock": shock, "deltas": deltas,
               "dominant_factor": dominant[0]}
    g = grounding_block("Sensitivity", results)
    return _save(db, sim_type="sensitivity", subject_ref=subject_ref, seed=None, iterations=0,
                 inputs={"factors": factors, "shock": shock}, results={**results, "grounding": g},
                 narrative=f"Dominant sensitivity is to '{dominant[0]}'.",
                 portfolio_id=None, tenant_id=tenant_id, created_by=created_by)


def scenario_tree(db: Session, *, base_value: float, stages: int = 3, up: float = 0.1,
                  down: float = -0.08, prob_up: float = 0.55, subject_ref: Optional[str] = None,
                  tenant_id: Optional[int] = None, created_by: Optional[str] = None) -> Dict[str, Any]:
    """Recombining binomial scenario tree with terminal distribution & expectation."""
    nodes = {0: {0: {"value": base_value, "prob": 1.0}}}
    for s in range(1, stages + 1):
        nodes[s] = {}
        for up_moves in range(s + 1):
            val = base_value * ((1 + up) ** up_moves) * ((1 + down) ** (s - up_moves))
            from math import comb
            prob = comb(s, up_moves) * (prob_up ** up_moves) * ((1 - prob_up) ** (s - up_moves))
            nodes[s][up_moves] = {"value": round(val, 2), "prob": round(prob, 6)}
    terminal = nodes[stages]
    exp_val = sum(nd["value"] * nd["prob"] for nd in terminal.values())
    results = {"stages": stages, "expected_terminal_value": round(exp_val, 2),
               "terminal_nodes": [{"up_moves": k, **v} for k, v in terminal.items()],
               "best": max(terminal.values(), key=lambda n: n["value"]),
               "worst": min(terminal.values(), key=lambda n: n["value"])}
    g = grounding_block("Scenario Tree", results)
    return _save(db, sim_type="scenario_tree", subject_ref=subject_ref, seed=None, iterations=stages,
                 inputs={"up": up, "down": down, "prob_up": prob_up},
                 results={**results, "grounding": g},
                 narrative=f"Expected terminal value over {stages} stages is {exp_val:,.0f}.",
                 portfolio_id=None, tenant_id=tenant_id, created_by=created_by)


def risk_attribution(db: Session, *, positions: List[Dict[str, Any]], confidence: float = 0.99,
                     subject_ref: Optional[str] = None, tenant_id: Optional[int] = None,
                     created_by: Optional[str] = None) -> Dict[str, Any]:
    """Component VaR: attribute total VaR to each position (parametric)."""
    if not positions:
        raise ValueError("positions required")
    n = len(positions)
    w = [to_float(p.get("exposure", p.get("weight", 1.0))) for p in positions]
    vol = [to_float(p.get("vol", 0.1)) for p in positions]
    corr = [[1.0 if i == j else to_float(positions[i].get("corr", 0.2)) for j in range(n)] for i in range(n)]
    cov = [[corr[i][j] * vol[i] * vol[j] for j in range(n)] for i in range(n)]
    port_var = sum(w[i] * w[j] * cov[i][j] for i in range(n) for j in range(n))
    port_vol = math.sqrt(max(port_var, 1e-12))
    z = norm_ppf(confidence)
    total_var = z * port_vol
    comps = []
    for i in range(n):
        marginal = safe_div(z * sum(w[j] * cov[i][j] for j in range(n)), port_vol, 0.0) or 0.0
        component = marginal * w[i]
        comps.append({"name": positions[i].get("name", f"pos{i}"),
                      "component_var": round(component, 4),
                      "contribution_pct": round(safe_div(component, total_var, 0.0) * 100, 2)})
    results = {"portfolio_var": round(total_var, 4), "portfolio_vol": round(port_vol, 4),
               "components": sorted(comps, key=lambda c: c["component_var"], reverse=True)}
    g = grounding_block("Risk Attribution", results)
    return _save(db, sim_type="attribution", subject_ref=subject_ref, seed=None, iterations=0,
                 inputs={"positions": positions, "confidence": confidence},
                 results={**results, "grounding": g},
                 narrative=f"Total VaR {total_var:,.2f} attributed across {n} positions.",
                 portfolio_id=None, tenant_id=tenant_id, created_by=created_by)


def correlation_matrix(db: Session, *, series: Dict[str, List[float]],
                       subject_ref: Optional[str] = None, tenant_id: Optional[int] = None,
                       created_by: Optional[str] = None) -> Dict[str, Any]:
    keys = list(series.keys())
    matrix = {}
    for a in keys:
        matrix[a] = {b: round(correlation(series[a], series[b]), 4) for b in keys}
    # Highest off-diagonal pair.
    pairs = [(a, b, matrix[a][b]) for i, a in enumerate(keys) for b in keys[i + 1:]]
    strongest = max(pairs, key=lambda p: abs(p[2]), default=(None, None, 0.0))
    results = {"keys": keys, "matrix": matrix,
               "strongest_pair": {"a": strongest[0], "b": strongest[1], "corr": strongest[2]}}
    g = grounding_block("Correlation Matrix", results)
    return _save(db, sim_type="correlation", subject_ref=subject_ref, seed=None, iterations=0,
                 inputs={"n_series": len(keys)}, results={**results, "grounding": g},
                 narrative=f"Strongest correlation is {strongest[0]}~{strongest[1]} at {strongest[2]}.",
                 portfolio_id=None, tenant_id=tenant_id, created_by=created_by)


def volatility(db: Session, *, returns: List[float], lam: float = 0.94,
               subject_ref: Optional[str] = None, tenant_id: Optional[int] = None,
               created_by: Optional[str] = None) -> Dict[str, Any]:
    """EWMA (RiskMetrics) and sample volatility, annualized."""
    if not returns:
        raise ValueError("returns required")
    var_ewma = returns[0] ** 2
    for r in returns[1:]:
        var_ewma = lam * var_ewma + (1 - lam) * (r ** 2)
    ewma_vol = math.sqrt(var_ewma)
    sample_vol = stdev(returns)
    results = {"ewma_vol": round(ewma_vol, 6), "sample_vol": round(sample_vol, 6),
               "annualized_ewma_pct": round(ewma_vol * math.sqrt(252) * 100, 3),
               "annualized_sample_pct": round(sample_vol * math.sqrt(252) * 100, 3),
               "lambda": lam, "observations": len(returns)}
    g = grounding_block("Volatility", results)
    return _save(db, sim_type="volatility", subject_ref=subject_ref, seed=None, iterations=len(returns),
                 inputs={"lambda": lam}, results={**results, "grounding": g},
                 narrative=f"Annualized EWMA volatility is {results['annualized_ewma_pct']}%.",
                 portfolio_id=None, tenant_id=tenant_id, created_by=created_by)


def tail_risk(db: Session, *, returns: List[float], threshold: float = 0.95,
              subject_ref: Optional[str] = None, tenant_id: Optional[int] = None,
              created_by: Optional[str] = None) -> Dict[str, Any]:
    """Tail metrics: VaR/ES at threshold, tail ratio, and skew/kurtosis proxies."""
    if not returns:
        raise ValueError("returns required")
    losses = sorted(-r for r in returns)
    var = percentile(losses, threshold * 100)
    tail = [x for x in losses if x >= var]
    es = mean(tail) if tail else var
    m = mean(returns)
    sd = stdev(returns) or 1e-9
    skew = mean([((r - m) / sd) ** 3 for r in returns])
    kurt = mean([((r - m) / sd) ** 4 for r in returns])
    results = {"threshold": threshold, "tail_var": round(var, 6), "tail_es": round(es, 6),
               "tail_ratio": round(safe_div(es, var, 0.0) or 0, 3),
               "skewness": round(skew, 4), "excess_kurtosis": round(kurt - 3.0, 4),
               "fat_tailed": (kurt - 3.0) > 1.0}
    g = grounding_block("Tail Risk", results)
    return _save(db, sim_type="tail", subject_ref=subject_ref, seed=None, iterations=len(returns),
                 inputs={"threshold": threshold}, results={**results, "grounding": g},
                 narrative=f"Tail ES at {round(threshold*100)}% is {es:.4f} ({'fat' if results['fat_tailed'] else 'normal'}-tailed).",
                 portfolio_id=None, tenant_id=tenant_id, created_by=created_by)


def list_simulations(db: Session, *, sim_type: Optional[str] = None, limit: int = 50,
                     tenant_id: Optional[int] = None) -> List[Dict[str, Any]]:
    q = db.query(FinRiskSimulation)
    if tenant_id is not None:
        q = q.filter(FinRiskSimulation.tenant_id == tenant_id)
    if sim_type:
        q = q.filter(FinRiskSimulation.sim_type == sim_type)
    return [{"simulation_id": s.id, "sim_type": s.sim_type, "subject_ref": s.subject_ref,
             "checksum": s.checksum, "created_at": iso(s.created_at)}
            for s in q.order_by(FinRiskSimulation.id.desc()).limit(limit).all()]


def get_simulation(db: Session, simulation_id: int) -> Optional[Dict[str, Any]]:
    s = db.query(FinRiskSimulation).filter(FinRiskSimulation.id == simulation_id).first()
    if not s:
        return None
    return {"simulation_id": s.id, "sim_type": s.sim_type, "subject_ref": s.subject_ref,
            "inputs": s.inputs, "results": s.results, "narrative": s.narrative,
            "created_at": iso(s.created_at)}
