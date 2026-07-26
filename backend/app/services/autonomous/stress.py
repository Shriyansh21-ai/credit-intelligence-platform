"""M6 — Banking-grade Stress Testing Framework.

Runs Base / Moderate / Severe / Custom macro scenarios across a chosen scope
(single company, whole portfolio, an industry, or a region), reusing the M5
scenario engine per position. Outputs loss projections, capital impact, PD and
rating migration matrices, expected losses and industry/region heatmaps.

Capital impact uses a transparent Basel-style proxy: RWA ≈ exposure × PD-driven
risk weight, capital = RWA × 8%. The proxy is deterministic and clearly labeled
(not a regulatory calculation) — banks plug their own risk-weight curve later.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from backend.app.models.autonomous import StressTestRun
from . import data_access, simulation
from .common import clamp, pd_from_score, rating_index, RATING_ORDER

# Named scenarios → shock bundles fed to the M5 simulation engine.
STRESS_SCENARIOS: Dict[str, Dict[str, float]] = {
    "base": {"revenue_drop": 0.05, "interest_increase": 0.05},
    "moderate": {"revenue_drop": 0.15, "interest_increase": 0.15, "working_capital_delay": 45},
    "severe": {"revenue_drop": 0.30, "interest_increase": 0.30, "working_capital_delay": 90,
               "market_recession": 0.7, "commodity_price_change": 0.25},
}
CAPITAL_RATIO = 0.08  # 8% capital against risk-weighted assets (proxy)


def _risk_weight(pd: float) -> float:
    """Monotonic PD → risk-weight proxy in [0.2, 1.5]."""
    return round(0.2 + clamp(pd * 3.0, 0, 1.3), 4)


def _capital(exposure: float, pd: float) -> float:
    return round((exposure or 0.0) * _risk_weight(pd) * CAPITAL_RATIO, 2)


def _positions(db: Session, scope: str, scope_ref: Optional[str]) -> List[Dict[str, Any]]:
    profs = data_access.portfolio_profiles(db)
    if scope == "company" and scope_ref:
        ref = scope_ref.strip().lower()
        return [p for p in profs if (p.get("company_ref") or "").strip().lower() == ref]
    if scope == "industry" and scope_ref:
        return [p for p in profs if (p.get("industry") or "").strip().lower() == scope_ref.strip().lower()]
    if scope == "region" and scope_ref:
        return [p for p in profs if (p.get("country") or "").strip().lower() == scope_ref.strip().lower()]
    return profs  # portfolio


def run(db: Session, *, scenario: str = "severe", scope: str = "portfolio",
        scope_ref: Optional[str] = None, custom_shocks: Optional[Dict[str, float]] = None,
        user_id: Optional[int] = None, tenant_id: Optional[int] = None,
        persist: bool = True) -> Dict[str, Any]:
    shocks = custom_shocks if scenario == "custom" else STRESS_SCENARIOS.get(scenario, STRESS_SCENARIOS["severe"])
    positions = _positions(db, scope, scope_ref)

    base_exposure = base_el = stress_el = base_capital = stress_capital = 0.0
    pd_migration: List[Dict[str, Any]] = []
    rating_matrix: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
    heatmap: Dict[str, Dict[str, float]] = defaultdict(lambda: {"exposure": 0.0, "stress_el": 0.0})
    per_name: List[Dict[str, Any]] = []

    for p in positions:
        sim = simulation.simulate(db, shocks, company_ref=p.get("company_ref"),
                                  assessment_id=p.get("assessment_id"), persist=False)
        b, r = sim["baseline"], sim["result"]
        exp = b.get("recommended_limit") or p.get("exposure") or 0.0
        lgd = p.get("lgd") or 0.45
        b_pd = b["pd"] if isinstance(b["pd"], (int, float)) else pd_from_score(b["credit_score"])
        s_pd = r["pd"]
        b_el = b_pd * lgd * exp
        s_el = s_pd * lgd * exp
        base_exposure += exp
        base_el += b_el
        stress_el += s_el
        base_capital += _capital(exp, b_pd)
        stress_capital += _capital(exp, s_pd)

        pd_migration.append({"company_ref": p.get("company_ref"), "pd_before": round(b_pd, 4),
                             "pd_after": round(s_pd, 4), "delta": round(s_pd - b_pd, 4)})
        rating_matrix[b["rating"]][r["rating"]] += 1

        bucket = (p.get("industry") if scope != "industry" else p.get("country")) or "Unclassified"
        heatmap[bucket]["exposure"] += exp
        heatmap[bucket]["stress_el"] += s_el

        per_name.append({"company_ref": p.get("company_ref"), "industry": p.get("industry"),
                         "exposure": round(exp, 2), "rating_before": b["rating"],
                         "rating_after": r["rating"], "stress_el": round(s_el, 2),
                         "score_change": sim["delta"]["score_change"]})

    per_name.sort(key=lambda x: -x["stress_el"])
    result = {
        "scenario": scenario, "scope": scope, "scope_ref": scope_ref,
        "shocks": shocks, "position_count": len(positions),
        "total_exposure": round(base_exposure, 2),
        "expected_loss": {"baseline": round(base_el, 2), "stressed": round(stress_el, 2),
                          "increase": round(stress_el - base_el, 2),
                          "increase_pct": round((stress_el - base_el) / base_el, 4) if base_el else None},
        "capital_impact": {"baseline": round(base_capital, 2), "stressed": round(stress_capital, 2),
                           "additional_required": round(stress_capital - base_capital, 2)},
        "pd_migration": pd_migration[:200],
        "rating_migration": {k: dict(v) for k, v in rating_matrix.items()},
        "rating_migration_summary": _downgrade_summary(rating_matrix),
        "heatmap": [{"bucket": k, "exposure": round(v["exposure"], 2),
                     "stress_el": round(v["stress_el"], 2),
                     "loss_rate": round(v["stress_el"] / v["exposure"], 4) if v["exposure"] else 0.0}
                    for k, v in sorted(heatmap.items(), key=lambda kv: -kv[1]["stress_el"])],
        "top_contributors": per_name[:25],
    }

    if persist:
        row = StressTestRun(tenant_id=tenant_id, user_id=user_id, scope=scope, scope_ref=scope_ref,
                            scenario=scenario, custom_shocks=custom_shocks if scenario == "custom" else None,
                            positions=len(positions), result=result)
        db.add(row)
        db.commit()
        db.refresh(row)
        result["id"] = row.id
    return result


def _downgrade_summary(matrix: Dict[str, Dict[str, int]]) -> Dict[str, int]:
    downgraded = stable = upgraded = 0
    for frm, tos in matrix.items():
        fi = rating_index(frm)
        for to, count in tos.items():
            ti = rating_index(to)
            if fi is None or ti is None:
                stable += count
            elif ti > fi:
                downgraded += count
            elif ti < fi:
                upgraded += count
            else:
                stable += count
    return {"downgraded": downgraded, "stable": stable, "upgraded": upgraded}


def compare_scenarios(db: Session, *, scope: str = "portfolio", scope_ref: Optional[str] = None,
                      tenant_id: Optional[int] = None) -> Dict[str, Any]:
    """Run base/moderate/severe on the same scope for a side-by-side view."""
    out = {}
    for name in ("base", "moderate", "severe"):
        r = run(db, scenario=name, scope=scope, scope_ref=scope_ref, tenant_id=tenant_id, persist=False)
        out[name] = {"expected_loss": r["expected_loss"], "capital_impact": r["capital_impact"],
                     "rating_migration_summary": r["rating_migration_summary"],
                     "position_count": r["position_count"]}
    return {"scope": scope, "scope_ref": scope_ref, "scenarios": out}


def get_run(db: Session, run_id: int) -> Optional[StressTestRun]:
    return db.query(StressTestRun).filter(StressTestRun.id == run_id).first()


def list_runs(db: Session, *, tenant_id: Optional[int] = None, limit: int = 50) -> List[StressTestRun]:
    return (db.query(StressTestRun).filter(StressTestRun.tenant_id == tenant_id)
            .order_by(StressTestRun.created_at.desc()).limit(limit).all())
