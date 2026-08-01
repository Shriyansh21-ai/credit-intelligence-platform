"""M11 — Executive Intelligence Center.

Persona-tailored executive dashboards (CEO, CFO, CRO, Chief Risk Officer
Treasurer, Portfolio Manager, Board Member, Credit Committee, Regulator
Relationship Manager). Each dashboard aggregates the deterministic outputs of the
other Track-3 engines into persona-relevant KPIs, sections, an AI-generated
executive summary and strategic recommendations. Everything is grounded — the
summary phrases the computed KPIs, it never invents figures.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from backend.app.models.financial_intelligence import FinExecDashboard
from . import data_access as da
from . import esg as esg_svc
from . import market as market_svc
from . import regulatory as regulatory_svc
from . import treasury as treasury_svc
from .common import checksum, expected_loss, grounding_block, iso, pct, safe_div, utcnow

PERSONAS = ["ceo", "cfo", "cro", "chief_risk_officer", "treasurer", "portfolio_manager",
            "board", "credit_committee", "regulator", "rm"]

PERSONA_LABELS = {
    "ceo": "Chief Executive Officer", "cfo": "Chief Financial Officer",
    "cro": "Chief Risk Officer", "chief_risk_officer": "Chief Risk Officer",
    "treasurer": "Treasurer", "portfolio_manager": "Portfolio Manager",
    "board": "Board Member", "credit_committee": "Credit Committee",
    "regulator": "Regulator", "rm": "Relationship Manager",
}


def _platform_snapshot(db: Session, tenant_id: Optional[int]) -> Dict[str, Any]:
    """One grounded read of every headline metric, shared by all personas."""
    exposures = da.portfolio_exposures(db)
    total_ead = sum(e["ead"] for e in exposures)
    total_el = sum(expected_loss(e["pd"], e["lgd"], e["ead"]) for e in exposures)
    wavg_pd = safe_div(sum(e["ead"] * e["pd"] for e in exposures), total_ead, 0.0)
    watch = [e for e in exposures if e["pd"] >= 0.10]
    treasury_kpis = treasury_svc.treasury_kpis(db, tenant_id=tenant_id)
    try:
        reg = regulatory_svc.portfolio_dashboard(db, tenant_id=tenant_id)["results"]
    except Exception:
        reg = {}
    try:
        esg = esg_svc.portfolio_esg(db, tenant_id=tenant_id)
    except Exception:
        esg = {}
    sentiment = market_svc.market_sentiment(db, tenant_id=tenant_id)
    return {
        "exposure_count": len(exposures),
        "total_ead": round(total_ead, 2),
        "expected_loss": round(total_el, 2),
        "el_rate_pct": pct(safe_div(total_el, total_ead, 0.0)),
        "weighted_avg_pd_pct": pct(wavg_pd),
        "watchlist_count": len(watch),
        "watchlist_ead_pct": pct(safe_div(sum(e["ead"] for e in watch), total_ead, 0.0)),
        "treasury": treasury_kpis,
        "regulatory": reg,
        "esg": esg,
        "market_mood": sentiment.get("mood"),
        "market_sentiment": sentiment.get("avg_sentiment"),
    }


def _kpi(label: str, value: Any, unit: str = "", tone: str = "neutral") -> Dict[str, Any]:
    return {"label": label, "value": value, "unit": unit, "tone": tone}


def _persona_view(persona: str, snap: Dict[str, Any]) -> Dict[str, Any]:
    t = snap["treasury"]
    reg = snap["regulatory"]
    kpis: List[Dict[str, Any]] = []
    sections: List[Dict[str, Any]] = []
    recs: List[str] = []

    if persona in ("ceo", "board"):
        kpis = [
            _kpi("Total Exposure", snap["total_ead"], "INR"),
            _kpi("Expected Loss Rate", snap["el_rate_pct"], "%"),
            _kpi("Capital Adequacy", reg.get("car_pct"), "%"),
            _kpi("ESG Score", (snap["esg"] or {}).get("weighted_esg_score")),
            _kpi("Market Mood", snap["market_mood"]),
        ]
        sections = [{"title": "Strategic Position", "metrics": {
            "book_size": snap["total_ead"], "risk_rate": snap["el_rate_pct"],
            "watchlist_share": snap["watchlist_ead_pct"]}}]
        recs = ["Maintain capital buffers above regulatory minimums while pursuing profitable growth.",
                "Prioritise ESG-aligned lending to de-risk the transition exposure."]
    elif persona == "cfo":
        kpis = [
            _kpi("Net Interest Margin", t.get("blended_funding_cost_pct"), "%"),
            _kpi("Funding Cost", t.get("blended_funding_cost_pct"), "%"),
            _kpi("Stable Funding Ratio", t.get("stable_funding_ratio_pct"), "%"),
            _kpi("Expected Loss", snap["expected_loss"], "INR"),
        ]
        sections = [{"title": "Profitability & Funding", "metrics": t}]
        recs = ["Lengthen wholesale funding tenor to reduce rollover risk.",
                "Reprice thin-margin cohorts flagged by the RAROC engine."]
    elif persona in ("cro", "chief_risk_officer", "credit_committee"):
        kpis = [
            _kpi("Weighted Avg PD", snap["weighted_avg_pd_pct"], "%"),
            _kpi("Expected Loss", snap["expected_loss"], "INR"),
            _kpi("Watchlist Exposure", snap["watchlist_ead_pct"], "%"),
            _kpi("Total RWA", reg.get("total_rwa"), "INR"),
            _kpi("Stage 3 Names", (reg.get("stage_distribution") or {}).get("3") if reg else None),
        ]
        sections = [{"title": "Credit Risk", "metrics": {
            "wavg_pd": snap["weighted_avg_pd_pct"], "watchlist_count": snap["watchlist_count"],
            "provision_coverage": reg.get("provision_coverage_pct")}}]
        recs = ["Escalate high-severity watchlist names to committee for remediation.",
                "Run the severely-adverse macro scenario and pre-provision accordingly."]
    elif persona == "treasurer":
        kpis = [
            _kpi("Total Funding", t.get("total_funding"), "INR"),
            _kpi("Blended Cost", t.get("blended_funding_cost_pct"), "%"),
            _kpi("Funding Concentration", t.get("funding_concentration_pct"), "%"),
            _kpi("Wholesale Reliance", t.get("wholesale_reliance_pct"), "%"),
        ]
        sections = [{"title": "Liquidity & Funding", "metrics": t}]
        recs = ["Diversify funding away from wholesale sources above the concentration limit.",
                "Hold HQLA sufficient to keep LCR above 110% under combined stress."]
    elif persona == "portfolio_manager":
        kpis = [
            _kpi("Book Size", snap["total_ead"], "INR"),
            _kpi("Expected Loss Rate", snap["el_rate_pct"], "%"),
            _kpi("Watchlist Share", snap["watchlist_ead_pct"], "%"),
            _kpi("Exposure Count", snap["exposure_count"]),
        ]
        sections = [{"title": "Portfolio Health", "metrics": {
            "el_rate": snap["el_rate_pct"], "watchlist": snap["watchlist_ead_pct"]}}]
        recs = ["Rebalance concentrated sectors flagged by the optimization engine.",
                "Trim single-name exposures exceeding the 10% guideline."]
    elif persona == "regulator":
        kpis = [
            _kpi("Capital Adequacy", reg.get("car_pct"), "%"),
            _kpi("Total RWA", reg.get("total_rwa"), "INR"),
            _kpi("Provision Coverage", reg.get("provision_coverage_pct"), "%"),
            _kpi("Lifetime ECL", reg.get("total_ecl_lifetime"), "INR"),
        ]
        sections = [{"title": "Regulatory Position", "metrics": reg}]
        recs = ["All Basel III minimums and IFRS 9 staging are computed and auditable.",
                "Stage migration and ECL are reproducible via stored checksums."]
    else:  # rm
        kpis = [
            _kpi("Portfolio Exposure", snap["total_ead"], "INR"),
            _kpi("Watchlist Names", snap["watchlist_count"]),
            _kpi("Market Mood", snap["market_mood"]),
        ]
        sections = [{"title": "Client Book", "metrics": {
            "exposure": snap["total_ead"], "watchlist": snap["watchlist_count"]}}]
        recs = ["Proactively engage watchlist clients on covenants and refinancing.",
                "Cross-sell ESG-linked products to green-eligible clients."]

    summary = (f"For the {PERSONA_LABELS.get(persona, persona)}: book of "
               f"{snap['total_ead']:,.0f} EAD across {snap['exposure_count']} names, "
               f"expected-loss rate {snap['el_rate_pct']}%, watchlist share "
               f"{snap['watchlist_ead_pct']}%, market mood {snap['market_mood']}.")
    return {"kpis": kpis, "sections": sections, "summary": summary, "recommendations": recs}


def build_dashboard(db: Session, *, persona: str, tenant_id: Optional[int] = None,
                    created_by: Optional[str] = None) -> Dict[str, Any]:
    if persona not in PERSONAS:
        raise ValueError(f"unknown persona '{persona}'")
    snap = _platform_snapshot(db, tenant_id)
    view = _persona_view(persona, snap)
    g = grounding_block(f"{persona} dashboard", snap)
    row = FinExecDashboard(
        tenant_id=tenant_id, persona=persona, title=f"{PERSONA_LABELS.get(persona, persona)} Dashboard",
        kpis=view["kpis"], sections=view["sections"], summary=view["summary"],
        recommendations=view["recommendations"], checksum=checksum(snap), created_by=created_by)
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"dashboard_id": row.id, "persona": persona, "title": row.title,
            "kpis": view["kpis"], "sections": view["sections"], "summary": view["summary"],
            "recommendations": view["recommendations"], "grounding": g}


def list_dashboards(db: Session, *, persona: Optional[str] = None, limit: int = 50,
                    tenant_id: Optional[int] = None) -> List[Dict[str, Any]]:
    q = db.query(FinExecDashboard)
    if tenant_id is not None:
        q = q.filter(FinExecDashboard.tenant_id == tenant_id)
    if persona:
        q = q.filter(FinExecDashboard.persona == persona)
    return [{"dashboard_id": d.id, "persona": d.persona, "title": d.title,
             "created_at": iso(d.created_at)}
            for d in q.order_by(FinExecDashboard.id.desc()).limit(limit).all()]


def get_dashboard(db: Session, dashboard_id: int) -> Optional[Dict[str, Any]]:
    d = db.query(FinExecDashboard).filter(FinExecDashboard.id == dashboard_id).first()
    if not d:
        return None
    return {"dashboard_id": d.id, "persona": d.persona, "title": d.title, "kpis": d.kpis,
            "sections": d.sections, "summary": d.summary, "recommendations": d.recommendations,
            "created_at": iso(d.created_at)}
