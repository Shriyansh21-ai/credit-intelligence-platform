"""M14 — Strategic Intelligence Platform.

Enterprise strategic reports: executive briefings, market/industry/competitor/
economic/regulatory/portfolio/investment reports and long-term outlooks. Each
report combines *deterministic analytics* (pulled from the other Track-3 engines)
with AI reasoning that only phrases those grounded facts — every section carries
its evidence/citation (the source engine and its result checksum), so reports are
auditable and reproducible.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from backend.app.models.financial_intelligence import FinStrategicReport
from . import benchmarking as benchmarking_svc
from . import data_access as da
from . import economic as economic_svc
from . import esg as esg_svc
from . import executive as executive_svc
from . import forecasting as forecasting_svc
from . import market as market_svc
from . import regulatory as regulatory_svc
from .common import checksum, grounding_block, iso, pct, safe_div, utcnow

REPORT_TYPES = ["executive_briefing", "market", "industry", "competitor", "economic",
                "regulatory", "portfolio", "investment", "outlook"]


def _cite(source: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    return {"source": source, "checksum": checksum(payload), "generated_at": iso(utcnow())}


def _section(title: str, body: str, evidence: Dict[str, Any], facts: Dict[str, Any]) -> Dict[str, Any]:
    return {"title": title, "body": body, "facts": facts, "evidence": evidence}


def _company_sections(db, subject_ref, assessment_id, tenant_id) -> Any:
    sections: List[Dict[str, Any]] = []
    citations: List[Dict[str, Any]] = []
    prof = da.company_or_none(db, assessment_id=assessment_id, company_ref=subject_ref)
    if not prof:
        return sections, citations
    # Benchmark
    try:
        bm = benchmarking_svc.benchmark(db, subject_ref=subject_ref, assessment_id=assessment_id,
                                       tenant_id=tenant_id)
        ev = _cite("benchmarking", bm)
        citations.append(ev)
        sections.append(_section(
            "Competitive Position",
            f"{subject_ref} sits in the {bm['overall_percentile']}th percentile of {bm['industry']} "
            f"peers ({bm['competitive_position'].replace('_', ' ')}). Strengths: "
            f"{', '.join(bm['strengths']) or 'none material'}. Watch: {', '.join(bm['weaknesses']) or 'none'}.",
            ev, {"overall_percentile": bm["overall_percentile"], "position": bm["competitive_position"]}))
    except Exception:
        pass
    # Forecast
    try:
        fc = forecasting_svc.forecast(db, forecast_type="revenue", subject_ref=subject_ref,
                                     assessment_id=assessment_id, horizon=12, tenant_id=tenant_id)
        ev = _cite("forecasting", fc)
        citations.append(ev)
        sections.append(_section(
            "Financial Outlook",
            f"Revenue is projected to reach {fc['metrics']['terminal_value']:,.0f} over 12 months "
            f"(95% CI {fc['metrics']['terminal_range']}).",
            ev, fc["metrics"]))
    except Exception:
        pass
    # ESG
    try:
        es = esg_svc.assess(db, subject_ref=subject_ref, assessment_id=assessment_id, tenant_id=tenant_id)
        ev = _cite("esg", es)
        citations.append(ev)
        sections.append(_section(
            "ESG & Climate",
            f"ESG score {es['esg_score']} ({es['esg_band']}); transition risk {es['transition_risk']}. "
            f"{'Green-financing eligible.' if es['green_financing_eligible'] else 'Transition-exposed.'}",
            ev, {"esg_score": es["esg_score"], "transition_risk": es["transition_risk"]}))
    except Exception:
        pass
    return sections, citations  # type: ignore


def _platform_sections(db, tenant_id) -> Any:
    sections = []
    citations = []
    try:
        reg = regulatory_svc.portfolio_dashboard(db, tenant_id=tenant_id)["results"]
        ev = _cite("regulatory", reg)
        citations.append(ev)
        sections.append(_section(
            "Regulatory Position",
            f"Total RWA {reg.get('total_rwa'):,.0f}; lifetime ECL {reg.get('total_ecl_lifetime'):,.0f}; "
            f"provision coverage {reg.get('provision_coverage_pct')}%.",
            ev, reg))
    except Exception:
        pass
    try:
        econ = economic_svc.propagate(db, scenario_type="adverse", tenant_id=tenant_id)
        ev = _cite("economic", econ)
        citations.append(ev)
        sections.append(_section(
            "Macro Sensitivity",
            f"An adverse macro scenario lifts expected loss by {econ['el_uplift_pct']}% "
            f"(PD ×{econ['pd_multiplier']}).",
            ev, {"el_uplift_pct": econ["el_uplift_pct"], "pd_multiplier": econ["pd_multiplier"]}))
    except Exception:
        pass
    try:
        sentiment = market_svc.market_sentiment(db, tenant_id=tenant_id)
        ev = _cite("market", sentiment)
        citations.append(ev)
        sections.append(_section(
            "Market Backdrop",
            f"Market mood is {sentiment['mood']} (avg sentiment {sentiment['avg_sentiment']}).",
            ev, sentiment))
    except Exception:
        pass
    return sections, citations


def generate(db: Session, *, report_type: str, subject_ref: Optional[str] = None,
             assessment_id: Optional[int] = None, title: Optional[str] = None,
             tenant_id: Optional[int] = None, created_by: Optional[str] = None) -> Dict[str, Any]:
    if report_type not in REPORT_TYPES:
        raise ValueError(f"unknown report_type '{report_type}'")
    sections: List[Dict[str, Any]] = []
    citations: List[Dict[str, Any]] = []

    if report_type in ("competitor", "investment") and subject_ref:
        comp = _company_sections(db, subject_ref, assessment_id, tenant_id)
        sections += comp[0]
        citations += comp[1]
    plat = _platform_sections(db, tenant_id)
    sections += plat[0]
    citations += plat[1]

    if report_type == "executive_briefing":
        try:
            dash = executive_svc.build_dashboard(db, persona="ceo", tenant_id=tenant_id)
            citations.append(_cite("executive", dash))
            sections.insert(0, _section("Executive Summary", dash["summary"],
                                        _cite("executive", dash),
                                        {"recommendations": dash["recommendations"]}))
        except Exception:
            pass

    # Synthesize recommendations across sections.
    recommendations = []
    for s in sections:
        f = s.get("facts", {})
        if "el_uplift_pct" in f and (f.get("el_uplift_pct") or 0) > 20:
            recommendations.append("Pre-provision against the adverse macro scenario.")
        if f.get("position") == "laggard":
            recommendations.append(f"Address competitive weaknesses for {subject_ref}.")
    if not recommendations:
        recommendations.append("Maintain the current strategy; monitor grounded KPIs quarterly.")

    outlook = ("Base case holds subject to macro sensitivity above; downside is driven by the "
               "adverse-scenario EL uplift and any concentration build-up.")
    grounding = grounding_block(f"{report_type} report",
                                {"section_count": len(sections), "citation_count": len(citations)})
    report_title = title or f"{report_type.replace('_', ' ').title()} Report"
    row = FinStrategicReport(
        tenant_id=tenant_id, report_type=report_type, subject_ref=subject_ref, title=report_title,
        sections=sections, citations=citations,
        recommendations=list(dict.fromkeys(recommendations)) + [outlook],
        grounding=grounding, checksum=checksum({"sections": sections, "citations": citations}),
        created_by=created_by)
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"report_id": row.id, "report_type": report_type, "title": report_title,
            "sections": sections, "citations": citations,
            "recommendations": row.recommendations, "checksum": row.checksum}


def list_reports(db: Session, *, report_type: Optional[str] = None, subject_ref: Optional[str] = None,
                 limit: int = 50, tenant_id: Optional[int] = None) -> List[Dict[str, Any]]:
    q = db.query(FinStrategicReport)
    if tenant_id is not None:
        q = q.filter(FinStrategicReport.tenant_id == tenant_id)
    if report_type:
        q = q.filter(FinStrategicReport.report_type == report_type)
    if subject_ref:
        q = q.filter(FinStrategicReport.subject_ref == subject_ref)
    return [{"report_id": r.id, "report_type": r.report_type, "title": r.title,
             "subject_ref": r.subject_ref, "checksum": r.checksum, "created_at": iso(r.created_at)}
            for r in q.order_by(FinStrategicReport.id.desc()).limit(limit).all()]


def get_report(db: Session, report_id: int) -> Optional[Dict[str, Any]]:
    r = db.query(FinStrategicReport).filter(FinStrategicReport.id == report_id).first()
    if not r:
        return None
    return {"report_id": r.id, "report_type": r.report_type, "title": r.title,
            "subject_ref": r.subject_ref, "sections": r.sections, "citations": r.citations,
            "recommendations": r.recommendations, "grounding": r.grounding,
            "created_at": iso(r.created_at)}
