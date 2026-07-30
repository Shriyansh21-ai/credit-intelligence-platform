"""M12 — Decision Optimization Engine.

Explainable optimization for the core lending decisions: loan pricing, credit
limits, collateral, portfolio allocation, capital allocation, liquidity,
recovery, risk appetite and relationship optimization. Every optimizer returns a
``solution`` plus an ``explanation`` naming the objective, the binding
constraints and the trade-off — no black-box output. Deterministic closed-form
or greedy/marginal methods (no external solver dependency).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from backend.app.models.financial_intelligence import FinOptimization
from . import data_access as da
from .common import (
    checksum, clamp, expected_loss, grounding_block, iso, normalize, pct, safe_div, to_float, utcnow,
)

OPT_TYPES = ["loan_pricing", "credit_limit", "collateral", "portfolio_allocation",
             "capital", "liquidity", "recovery", "risk_appetite", "relationship"]


def _save(db: Session, *, opt_type: str, subject_ref: Optional[str], objective: str,
          inputs: dict, constraints: dict, solution: dict, explanation: dict,
          objective_value: Optional[float], narrative: str, tenant_id: Optional[int],
          created_by: Optional[str]) -> Dict[str, Any]:
    row = FinOptimization(
        tenant_id=tenant_id, opt_type=opt_type, subject_ref=subject_ref, objective=objective,
        inputs=inputs, constraints=constraints, solution=solution, explanation=explanation,
        objective_value=objective_value, narrative=narrative, created_by=created_by)
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"optimization_id": row.id, "opt_type": opt_type, "objective": objective,
            "solution": solution, "explanation": explanation,
            "objective_value": objective_value, "narrative": narrative}


def loan_pricing(db: Session, *, subject_ref: Optional[str] = None, assessment_id: Optional[int] = None,
                 pd: Optional[float] = None, lgd: Optional[float] = None, ead: Optional[float] = None,
                 cost_of_funds: float = 0.065, opex_rate: float = 0.005, target_roe: float = 0.15,
                 capital_ratio: float = 0.12, tenant_id: Optional[int] = None,
                 created_by: Optional[str] = None) -> Dict[str, Any]:
    """Risk-based loan price = CoF + expected-loss rate + opex + capital charge."""
    prof = da.company_or_none(db, assessment_id=assessment_id, company_ref=subject_ref)
    pd = da.pd_of(prof) if (pd is None and prof) else (pd if pd is not None else 0.05)
    lgd = da.lgd_of(prof) if (lgd is None and prof) else (lgd if lgd is not None else 0.45)
    ead = da.exposure_of(prof) if (ead is None and prof) else (ead if ead is not None else 1_000_000.0)
    el_rate = pd * lgd
    capital_charge = capital_ratio * target_roe
    breakeven = cost_of_funds + el_rate + opex_rate
    price = breakeven + capital_charge
    solution = {"recommended_rate_pct": pct(price), "breakeven_rate_pct": pct(breakeven),
                "expected_loss_rate_pct": pct(el_rate), "capital_charge_pct": pct(capital_charge)}
    explanation = {"objective": "achieve target RoE while covering risk",
                   "formula": "rate = cost_of_funds + PD×LGD + opex + capital_ratio×target_RoE",
                   "components": {"cost_of_funds": cost_of_funds, "el_rate": round(el_rate, 5),
                                  "opex": opex_rate, "capital_charge": round(capital_charge, 5)},
                   "binding_constraint": f"target RoE {pct(target_roe)}%"}
    g = grounding_block("Loan Pricing", {**solution, "grounding_inputs": {"pd": pd, "lgd": lgd}})
    return _save(db, opt_type="loan_pricing", subject_ref=subject_ref, objective="target_roe",
                 inputs={"pd": pd, "lgd": lgd, "ead": ead, "cost_of_funds": cost_of_funds},
                 constraints={"target_roe": target_roe}, solution={**solution, "grounding": g},
                 explanation=explanation, objective_value=price,
                 narrative=f"Risk-based price of {pct(price)}% (breakeven {pct(breakeven)}%).",
                 tenant_id=tenant_id, created_by=created_by)


def credit_limit(db: Session, *, subject_ref: Optional[str] = None, assessment_id: Optional[int] = None,
                 pd: Optional[float] = None, single_name_cap: float = 0.10,
                 total_capital: float = 100_000_000.0, risk_appetite_el: float = 0.02,
                 tenant_id: Optional[int] = None, created_by: Optional[str] = None) -> Dict[str, Any]:
    """Optimal credit limit from single-name cap and EL risk-appetite budget."""
    prof = da.company_or_none(db, assessment_id=assessment_id, company_ref=subject_ref)
    pd = da.pd_of(prof) if (pd is None and prof) else (pd if pd is not None else 0.05)
    lgd = da.lgd_of(prof) if prof else 0.45
    cap_limit = single_name_cap * total_capital
    el_budget = risk_appetite_el * total_capital
    el_limit = safe_div(el_budget, max(pd * lgd, 1e-6), cap_limit)
    limit = min(cap_limit, el_limit)
    binding = "single-name cap" if limit == cap_limit else "expected-loss budget"
    solution = {"recommended_limit": round(limit, 2), "single_name_cap": round(cap_limit, 2),
                "el_budget_limit": round(el_limit, 2), "binding_constraint": binding}
    explanation = {"objective": "maximise limit within risk appetite",
                   "constraints": {"single_name_cap_pct": pct(single_name_cap),
                                   "risk_appetite_el_pct": pct(risk_appetite_el)},
                   "formula": "limit = min(cap×capital, el_budget / (PD×LGD))"}
    g = grounding_block("Credit Limit", solution)
    return _save(db, opt_type="credit_limit", subject_ref=subject_ref, objective="maximise_limit",
                 inputs={"pd": pd, "lgd": lgd, "total_capital": total_capital},
                 constraints={"single_name_cap": single_name_cap, "risk_appetite_el": risk_appetite_el},
                 solution={**solution, "grounding": g}, explanation=explanation, objective_value=limit,
                 narrative=f"Recommended limit {limit:,.0f} (bound by {binding}).",
                 tenant_id=tenant_id, created_by=created_by)


def portfolio_allocation(db: Session, *, candidates: List[Dict[str, Any]], budget: float,
                         cost_of_capital: float = 0.12, max_weight: float = 0.25,
                         subject_ref: Optional[str] = None, tenant_id: Optional[int] = None,
                         created_by: Optional[str] = None) -> Dict[str, Any]:
    """Allocate a budget across candidates to maximise risk-adjusted return (RAROC).

    Greedy on RAROC per unit, respecting a per-name max weight — explainable and
    deterministic. Each candidate: {name, spread, pd, lgd}.
    """
    if not candidates:
        raise ValueError("candidates required")
    scored = []
    for c in candidates:
        pd = to_float(c.get("pd"), 0.05)
        lgd = to_float(c.get("lgd"), 0.45)
        spread = to_float(c.get("spread"), 0.03)
        el_rate = pd * lgd
        raroc = safe_div(spread - el_rate, max(cost_of_capital * 0.1, 1e-6), 0.0)
        scored.append({"name": c.get("name"), "raroc": raroc, "net_spread": spread - el_rate})
    scored.sort(key=lambda s: s["raroc"], reverse=True)
    cap = max_weight * budget
    remaining = budget
    allocation = {}
    for s in scored:
        if remaining <= 0:
            break
        alloc = min(cap, remaining) if s["net_spread"] > 0 else 0.0
        if alloc > 0:
            allocation[s["name"]] = round(alloc, 2)
            remaining -= alloc
    total_alloc = sum(allocation.values()) or 1.0
    exp_return = sum(allocation.get(s["name"], 0) * s["net_spread"] for s in scored)
    solution = {"allocation": allocation, "weights": {k: round(v / budget, 4) for k, v in allocation.items()},
                "deployed": round(budget - max(remaining, 0), 2), "undeployed": round(max(remaining, 0), 2),
                "expected_net_return": round(exp_return, 2),
                "portfolio_raroc_pct": pct(safe_div(exp_return, total_alloc, 0.0))}
    explanation = {"objective": "maximise risk-adjusted return",
                   "method": "greedy on RAROC with per-name max weight",
                   "max_weight_pct": pct(max_weight)}
    g = grounding_block("Portfolio Allocation", solution)
    return _save(db, opt_type="portfolio_allocation", subject_ref=subject_ref,
                 objective="maximise_raroc", inputs={"budget": budget, "candidates": candidates},
                 constraints={"max_weight": max_weight}, solution={**solution, "grounding": g},
                 explanation=explanation, objective_value=exp_return,
                 narrative=f"Deployed {solution['deployed']:,.0f} at {solution['portfolio_raroc_pct']}% RAROC.",
                 tenant_id=tenant_id, created_by=created_by)


def capital_allocation(db: Session, *, business_units: List[Dict[str, Any]], total_capital: float,
                       tenant_id: Optional[int] = None, created_by: Optional[str] = None) -> Dict[str, Any]:
    """Allocate capital across units to equalise marginal RAROC (water-filling)."""
    if not business_units:
        raise ValueError("business_units required")
    # Allocate proportional to RAROC × demand, capped at stated demand.
    scored = [{"name": b.get("name"), "raroc": to_float(b.get("raroc"), 0.12),
               "demand": to_float(b.get("capital_demand"), total_capital / len(business_units))}
              for b in business_units]
    weights = normalize([s["raroc"] * s["demand"] for s in scored])
    allocation = {}
    for s, w in zip(scored, weights):
        allocation[s["name"]] = round(min(w * total_capital, s["demand"]), 2)
    blended = safe_div(sum(allocation[s["name"]] * s["raroc"] for s in scored),
                       sum(allocation.values()) or 1.0, 0.0)
    solution = {"allocation": allocation, "blended_raroc_pct": pct(blended),
                "allocated": round(sum(allocation.values()), 2)}
    explanation = {"objective": "maximise blended RAROC",
                   "method": "RAROC×demand weighting capped at stated demand"}
    g = grounding_block("Capital Allocation", solution)
    return _save(db, opt_type="capital", subject_ref=None, objective="maximise_blended_raroc",
                 inputs={"total_capital": total_capital, "business_units": business_units},
                 constraints={}, solution={**solution, "grounding": g}, explanation=explanation,
                 objective_value=blended, narrative=f"Blended RAROC {pct(blended)}% across {len(scored)} units.",
                 tenant_id=tenant_id, created_by=created_by)


def collateral_optimization(db: Session, *, exposure: float, collateral_options: List[Dict[str, Any]],
                            subject_ref: Optional[str] = None, tenant_id: Optional[int] = None,
                            created_by: Optional[str] = None) -> Dict[str, Any]:
    """Select the cheapest collateral mix (after haircuts) to fully secure exposure."""
    opts = sorted(collateral_options, key=lambda c: to_float(c.get("cost", 0)))
    remaining = exposure
    selected = []
    for c in opts:
        if remaining <= 0:
            break
        haircut = to_float(c.get("haircut"), 0.2)
        effective = to_float(c.get("value")) * (1 - haircut)
        use = min(effective, remaining)
        if use > 0:
            selected.append({"type": c.get("type"), "pledged_value": round(use / (1 - haircut), 2),
                             "effective_cover": round(use, 2), "haircut_pct": pct(haircut)})
            remaining -= use
    covered = exposure - max(remaining, 0)
    solution = {"selected": selected, "coverage": round(covered, 2),
                "coverage_ratio_pct": pct(safe_div(covered, exposure, 0.0)),
                "shortfall": round(max(remaining, 0), 2), "fully_secured": remaining <= 0}
    explanation = {"objective": "minimise collateral cost while covering exposure",
                   "method": "cheapest-first after haircuts"}
    g = grounding_block("Collateral Optimization", solution)
    return _save(db, opt_type="collateral", subject_ref=subject_ref, objective="minimise_cost",
                 inputs={"exposure": exposure, "options": collateral_options}, constraints={},
                 solution={**solution, "grounding": g}, explanation=explanation, objective_value=covered,
                 narrative=f"Secured {solution['coverage_ratio_pct']}% of exposure.",
                 tenant_id=tenant_id, created_by=created_by)


def list_optimizations(db: Session, *, opt_type: Optional[str] = None, limit: int = 50,
                       tenant_id: Optional[int] = None) -> List[Dict[str, Any]]:
    q = db.query(FinOptimization)
    if tenant_id is not None:
        q = q.filter(FinOptimization.tenant_id == tenant_id)
    if opt_type:
        q = q.filter(FinOptimization.opt_type == opt_type)
    return [{"optimization_id": o.id, "opt_type": o.opt_type, "objective": o.objective,
             "objective_value": o.objective_value, "created_at": iso(o.created_at)}
            for o in q.order_by(FinOptimization.id.desc()).limit(limit).all()]
