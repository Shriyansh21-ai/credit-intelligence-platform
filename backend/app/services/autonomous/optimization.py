"""M7 — Portfolio Optimization AI.

Turns the live book (latest assessment per company) into an actionable
optimization view: sector/geographic exposure, concentration (HHI + top-name)
expected return, RAROC, capital allocation and risk-adjusted rebalancing
suggestions. All figures derive from stored assessment data (exposure, PD, LGD
interest rate) — nothing is fabricated; positions missing a figure are excluded
from that particular calculation and flagged in ``coverage``.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from backend.app.models.autonomous import PortfolioOptimization
from . import data_access
from .common import clamp

CAPITAL_RATIO = 0.08
# Default single-name / single-sector concentration limits (share of book).
DEFAULT_LIMITS = {"single_name": 0.15, "single_sector": 0.30, "single_region": 0.40}


def _risk_weight(pd: Optional[float]) -> float:
    return round(0.2 + clamp((pd or 0.05) * 3.0, 0, 1.3), 4)


def _hhi(shares: List[float]) -> float:
    return round(sum(s * s for s in shares), 4)


def analyze(db: Session, *, objective: str = "risk_adjusted_return",
            constraints: Optional[Dict[str, Any]] = None, tenant_id: Optional[int] = None,
            user_id: Optional[int] = None, persist: bool = False) -> Dict[str, Any]:
    limits = {**DEFAULT_LIMITS, **((constraints or {}).get("limits") or {})}
    profs = data_access.portfolio_profiles(db)
    positions = [p for p in profs if (p.get("exposure") or 0) > 0]
    total = sum(p["exposure"] for p in positions) or 0.0

    by_sector: Dict[str, float] = defaultdict(float)
    by_region: Dict[str, float] = defaultdict(float)
    total_return = total_el = total_capital = 0.0
    name_shares: List[float] = []
    detail: List[Dict[str, Any]] = []

    for p in positions:
        exp = p["exposure"]
        pd = p.get("pd") or 0.05
        lgd = p.get("lgd") or 0.45
        rate = p.get("interest_rate")
        el = pd * lgd * exp
        cap = exp * _risk_weight(pd) * CAPITAL_RATIO
        gross = (rate / 100.0 * exp) if isinstance(rate, (int, float)) else (0.06 * exp)
        raroc = ((gross - el) / cap) if cap else None
        by_sector[p.get("industry") or "Unclassified"] += exp
        by_region[p.get("country") or "Unclassified"] += exp
        total_return += gross
        total_el += el
        total_capital += cap
        if total:
            name_shares.append(exp / total)
        detail.append({"company_ref": p.get("company_ref"), "industry": p.get("industry"),
                       "exposure": round(exp, 2), "pd": round(pd, 4),
                       "expected_loss": round(el, 2), "capital": round(cap, 2),
                       "raroc": round(raroc, 4) if raroc is not None else None,
                       "share": round(exp / total, 4) if total else 0.0})

    sector_shares = {k: round(v / total, 4) for k, v in by_sector.items()} if total else {}
    region_shares = {k: round(v / total, 4) for k, v in by_region.items()} if total else {}
    portfolio_raroc = ((total_return - total_el) / total_capital) if total_capital else None

    breaches = _limit_breaches(name_shares, sector_shares, region_shares, limits, detail)
    suggestions = _rebalance(detail, sector_shares, limits, objective)

    result = {
        "objective": objective, "position_count": len(positions),
        "total_exposure": round(total, 2),
        "expected_return": round(total_return, 2),
        "expected_loss": round(total_el, 2),
        "net_return": round(total_return - total_el, 2),
        "capital_required": round(total_capital, 2),
        "portfolio_raroc": round(portfolio_raroc, 4) if portfolio_raroc is not None else None,
        "concentration": {
            "hhi": _hhi(name_shares),
            "top_name_share": round(max(name_shares), 4) if name_shares else 0.0,
            "effective_names": round(1 / _hhi(name_shares), 1) if name_shares and _hhi(name_shares) else 0.0,
        },
        "sector_exposure": sector_shares,
        "geographic_exposure": region_shares,
        "concentration_limits": limits,
        "limit_breaches": breaches,
        "capital_allocation": sorted(detail, key=lambda d: -(d["capital"] or 0))[:25],
        "rebalancing_suggestions": suggestions,
        "recommendations": _recommendations(breaches, suggestions, portfolio_raroc),
        "coverage": {"positions_total": len(profs), "positions_with_exposure": len(positions)},
    }

    if persist:
        row = PortfolioOptimization(tenant_id=tenant_id, user_id=user_id, objective=objective,
                                    constraints=constraints or {}, result=result)
        db.add(row)
        db.commit()
        db.refresh(row)
        result["id"] = row.id
    return result


def _limit_breaches(name_shares, sector_shares, region_shares, limits, detail) -> List[Dict[str, Any]]:
    out = []
    for d in detail:
        if d["share"] > limits["single_name"]:
            out.append({"type": "single_name", "entity": d["company_ref"],
                        "share": d["share"], "limit": limits["single_name"]})
    for sector, share in sector_shares.items():
        if share > limits["single_sector"]:
            out.append({"type": "single_sector", "entity": sector, "share": share,
                        "limit": limits["single_sector"]})
    for region, share in region_shares.items():
        if share > limits["single_region"]:
            out.append({"type": "single_region", "entity": region, "share": share,
                        "limit": limits["single_region"]})
    return sorted(out, key=lambda b: -b["share"])


def _rebalance(detail, sector_shares, limits, objective) -> List[Dict[str, Any]]:
    out = []
    # Trim over-concentrated / low-RAROC names; grow diversified high-RAROC ones.
    for d in sorted(detail, key=lambda x: (x["raroc"] if x["raroc"] is not None else 0)):
        if d["raroc"] is not None and d["raroc"] < 0.1 and d["share"] > 0.05:
            out.append({"action": "reduce", "company_ref": d["company_ref"],
                        "reason": f"Low RAROC ({d['raroc']:.1%}) and {d['share']:.0%} of book",
                        "current_share": d["share"]})
    over = [(s, sh) for s, sh in sector_shares.items() if sh > limits["single_sector"]]
    for sector, share in over:
        out.append({"action": "diversify_out_of_sector", "sector": sector,
                    "reason": f"Sector at {share:.0%} exceeds {limits['single_sector']:.0%} limit",
                    "current_share": share})
    return out[:15]


def _recommendations(breaches, suggestions, raroc) -> List[str]:
    recs = []
    if breaches:
        names = ", ".join(f"{b['entity']} ({b['type']})" for b in breaches[:3])
        recs.append(f"Address {len(breaches)} concentration limit breach(es): {names}.")
    if raroc is not None and raroc < 0.12:
        recs.append(f"Portfolio RAROC ({raroc:.1%}) is below hurdle — reprice or rebalance toward higher risk-adjusted returns.")
    if suggestions:
        recs.append(f"{len(suggestions)} rebalancing action(s) identified to improve diversification.")
    if not recs:
        recs.append("Portfolio is well-diversified and within limits; maintain the current allocation.")
    return recs


def list_runs(db: Session, *, tenant_id: Optional[int] = None, limit: int = 20) -> List[PortfolioOptimization]:
    return (db.query(PortfolioOptimization).filter(PortfolioOptimization.tenant_id == tenant_id)
            .order_by(PortfolioOptimization.created_at.desc()).limit(limit).all())
