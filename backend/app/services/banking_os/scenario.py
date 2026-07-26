"""M5 / M6 — Digital Twin Simulation + Scenario Planning Engine.

Deterministic scenario analysis over a portfolio (or a single company): a named
scenario library (best / base / worst / stress / black-swan / custom), a seeded
**Monte Carlo** expected-loss distribution (VaR / expected-shortfall), and
one-factor **sensitivity** analysis. Positions are ``{exposure, pd, lgd}`` and
are resolved from the platform's assessments when not supplied. Reproducible
(fixed RNG seed) so committee packs and regulatory submissions are stable.
"""

from __future__ import annotations

import random
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from backend.app.models.banking_os import ScenarioPlan
from .common import clamp

# scenario -> multiplicative shocks (pd/lgd/exposure) + rate delta (bps → pp).
SCENARIO_LIBRARY: Dict[str, Dict[str, float]] = {
    "best": {"pd_mult": 0.7, "lgd_mult": 0.9, "exposure_mult": 1.0, "rate_delta": -1.0},
    "base": {"pd_mult": 1.0, "lgd_mult": 1.0, "exposure_mult": 1.0, "rate_delta": 0.0},
    "worst": {"pd_mult": 1.6, "lgd_mult": 1.15, "exposure_mult": 1.0, "rate_delta": 2.0},
    "stress": {"pd_mult": 2.2, "lgd_mult": 1.25, "exposure_mult": 1.05, "rate_delta": 3.5},
    "black_swan": {"pd_mult": 3.5, "lgd_mult": 1.4, "exposure_mult": 1.1, "rate_delta": 5.0},
}
SCENARIOS = list(SCENARIO_LIBRARY.keys()) + ["custom"]


def _shocks(scenario: str, custom: Optional[dict] = None) -> Dict[str, float]:
    if scenario == "custom":
        base = dict(SCENARIO_LIBRARY["base"])
        base.update(custom or {})
        return base
    return dict(SCENARIO_LIBRARY.get(scenario, SCENARIO_LIBRARY["base"]))


# ---------------------------------------------------------------------------
# Portfolio resolution
# ---------------------------------------------------------------------------
def resolve_portfolio(db: Session, *, scope: str = "portfolio", scope_ref: Optional[str] = None,
                      tenant_id: Optional[int] = None) -> List[Dict[str, Any]]:
    """Build ``[{ref, exposure, pd, lgd}]`` positions from the platform assessments."""
    from backend.app.models.enterprise_assessment import EnterpriseAssessment
    q = db.query(EnterpriseAssessment)
    if scope == "company" and scope_ref:
        q = q.filter(EnterpriseAssessment.company_name == scope_ref)
    elif scope == "industry" and scope_ref:
        q = q.filter(EnterpriseAssessment.industry == scope_ref)
    out = []
    for a in q.limit(5000).all():
        exposure = a.recommended_loan_amount or 0
        pd = a.probability_of_default
        lgd = a.loss_given_default if a.loss_given_default is not None else 0.45
        if pd is None or exposure <= 0:
            continue
        out.append({"ref": a.company_name, "exposure": float(exposure), "pd": float(pd),
                    "lgd": float(lgd)})
    return out


# ---------------------------------------------------------------------------
# Core maths
# ---------------------------------------------------------------------------
def expected_loss(positions: List[dict]) -> float:
    return round(sum(p["exposure"] * clamp(p["pd"]) * clamp(p["lgd"]) for p in positions), 2)


def _shocked(positions: List[dict], shocks: Dict[str, float]) -> List[dict]:
    out = []
    for p in positions:
        out.append({
            "ref": p.get("ref"),
            "exposure": p["exposure"] * shocks.get("exposure_mult", 1.0),
            "pd": clamp(p["pd"] * shocks.get("pd_mult", 1.0)),
            "lgd": clamp(p["lgd"] * shocks.get("lgd_mult", 1.0)),
        })
    return out


def apply_scenario(positions: List[dict], scenario: str, *, custom: Optional[dict] = None) -> Dict[str, Any]:
    shocks = _shocks(scenario, custom)
    shocked = _shocked(positions, shocks)
    base_el = expected_loss(positions)
    scn_el = expected_loss(shocked)
    total_exp = sum(p["exposure"] for p in shocked)
    return {
        "scenario": scenario, "shocks": shocks,
        "expected_loss": scn_el, "baseline_expected_loss": base_el,
        "el_change": round(scn_el - base_el, 2),
        "el_change_pct": round((scn_el - base_el) / base_el, 4) if base_el else None,
        "total_exposure": round(total_exp, 2),
        "avg_pd": round(sum(p["pd"] for p in shocked) / len(shocked), 4) if shocked else 0.0,
        "positions": len(shocked),
    }


def monte_carlo(positions: List[dict], *, draws: int = 2000, seed: int = 12345,
                pd_vol: float = 0.4) -> Dict[str, Any]:
    """Seeded Monte Carlo of portfolio expected loss.

    Each draw perturbs every position's PD by a lognormal shock (mean 1, vol
    ``pd_vol``) and recomputes EL. Returns the loss distribution summary incl.
    VaR/ES at 95% and 99%. Deterministic given ``seed``.
    """
    if not positions:
        return {"draws": 0, "mean": 0.0, "p50": 0.0, "var_95": 0.0, "var_99": 0.0,
                "es_97_5": 0.0, "max": 0.0}
    rng = random.Random(seed)
    losses: List[float] = []
    for _ in range(max(1, draws)):
        total = 0.0
        for p in positions:
            shock = rng.lognormvariate(0.0, pd_vol)
            pd = clamp(p["pd"] * shock)
            total += p["exposure"] * pd * clamp(p["lgd"])
        losses.append(total)
    losses.sort()
    n = len(losses)

    def q(pct: float) -> float:
        idx = min(n - 1, int(pct * n))
        return round(losses[idx], 2)

    tail = losses[int(0.975 * n):] or losses[-1:]
    return {
        "draws": n, "mean": round(sum(losses) / n, 2),
        "p50": q(0.50), "p95": q(0.95), "p99": q(0.99),
        "var_95": q(0.95), "var_99": q(0.99),
        "es_97_5": round(sum(tail) / len(tail), 2),
        "min": round(losses[0], 2), "max": round(losses[-1], 2),
    }


def sensitivity(positions: List[dict], *, factor: str = "pd",
                grid: Optional[List[float]] = None) -> Dict[str, Any]:
    """One-factor sensitivity: scale ``factor`` (pd|lgd|exposure) across a grid."""
    grid = grid or [0.5, 0.75, 1.0, 1.25, 1.5, 2.0]
    mult_key = {"pd": "pd_mult", "lgd": "lgd_mult", "exposure": "exposure_mult"}.get(factor)
    if mult_key is None:
        raise ValueError("factor must be pd|lgd|exposure")
    base = expected_loss(positions)
    points = []
    for g in grid:
        shocked = _shocked(positions, {mult_key: g})
        el = expected_loss(shocked)
        points.append({"multiplier": g, "expected_loss": el,
                       "delta_pct": round((el - base) / base, 4) if base else None})
    return {"factor": factor, "baseline_expected_loss": base, "points": points}


# ---------------------------------------------------------------------------
# Orchestration + persistence
# ---------------------------------------------------------------------------
def run_plan(db: Session, *, name: str, scope: str = "portfolio", scope_ref: Optional[str] = None,
             scenarios: Optional[List[str]] = None, positions: Optional[List[dict]] = None,
             custom: Optional[dict] = None, monte_carlo_draws: int = 2000,
             tenant_id: Optional[int] = None, user_id: Optional[int] = None,
             persist: bool = True) -> Dict[str, Any]:
    positions = positions or resolve_portfolio(db, scope=scope, scope_ref=scope_ref, tenant_id=tenant_id)
    if not positions:
        raise ValueError("no positions to analyze")
    scenarios = scenarios or ["best", "base", "worst", "stress", "black_swan"]
    scenario_results = [apply_scenario(positions, s, custom=custom) for s in scenarios]
    mc = monte_carlo(positions, draws=monte_carlo_draws)
    sens = {f: sensitivity(positions, factor=f) for f in ("pd", "lgd")}
    worst = max(scenario_results, key=lambda r: r["expected_loss"])
    result = {
        "scope": scope, "scope_ref": scope_ref, "positions": len(positions),
        "total_exposure": round(sum(p["exposure"] for p in positions), 2),
        "baseline_expected_loss": expected_loss(positions),
        "scenarios": scenario_results, "monte_carlo": mc, "sensitivity": sens,
        "worst_case": {"scenario": worst["scenario"], "expected_loss": worst["expected_loss"]},
        "recommendations": _recommendations(scenario_results, mc),
    }
    if persist:
        row = ScenarioPlan(tenant_id=tenant_id, user_id=user_id, name=name, scope=scope,
                           scope_ref=scope_ref, scenarios=scenarios, result=result)
        db.add(row)
        db.commit()
        db.refresh(row)
        result["plan_id"] = row.id
    return result


def _recommendations(scenario_results: List[dict], mc: Dict[str, Any]) -> List[str]:
    recs = []
    stress = next((r for r in scenario_results if r["scenario"] == "stress"), None)
    if stress and stress.get("el_change_pct") and stress["el_change_pct"] > 1.0:
        recs.append("Stress EL more than doubles baseline — raise provisioning coverage.")
    if mc.get("var_99") and mc.get("mean") and mc["var_99"] > 1.5 * mc["mean"]:
        recs.append("Heavy tail (99% VaR ≫ mean) — hold additional economic capital buffer.")
    if not recs:
        recs.append("Loss distribution within tolerance; maintain current provisioning.")
    return recs


def list_plans(db: Session, *, tenant_id: Optional[int] = None) -> List[ScenarioPlan]:
    return (db.query(ScenarioPlan).filter(ScenarioPlan.tenant_id == tenant_id)
            .order_by(ScenarioPlan.created_at.desc()).all())
