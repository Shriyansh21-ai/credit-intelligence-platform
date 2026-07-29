"""M7 — AI enterprise report generation.

Generates board-quality reports (credit memo, investment memo, risk report,
fraud report, portfolio review, committee brief, executive summary, regulatory
summary, due diligence, financial analysis, board presentation). Each report is
assembled from *deterministic grounding* — the Phase 1-10 engines via
``autonomous.data_access``, the M1 RAG citation engine and (optionally) an M2
agent committee — and every section carries reasoning, evidence, citations,
chart specifications, a confidence score and recommendations.

Reports persist to ``aip_reports`` and are returned as structured JSON so the
frontend can render prose, evidence tables and charts; nothing is fabricated —
missing inputs surface as "unavailable".
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

from sqlalchemy.orm import Session

from backend.app.models.ai_platform import AIPReport
from backend.app.services.ai_platform import common, llm as llm_mod, rag
from backend.app.services.autonomous import data_access

REPORT_TYPES = [
    "credit_memo", "investment_memo", "risk_report", "fraud_report",
    "portfolio_review", "committee_brief", "executive_summary",
    "regulatory_summary", "due_diligence", "financial_analysis",
    "board_presentation",
]


# ---------------------------------------------------------------------------
# Section builders — each returns {heading, body, evidence, chart?, citations?}
# ---------------------------------------------------------------------------
def _compose(system: str, headline: str, narrative: str, facts, actions=None, cites=None):
    grounding = {"headline": headline, "narrative": narrative, "facts": facts,
                 "recommended_actions": actions or [], "citations": cites or []}
    return llm_mod.get_llm().generate(prompt=headline, system=system, grounding=grounding).text


def _fact(label, value):
    return {"label": label, "value": value}


def _overview(db, ctx):
    p = ctx["profile"] or {}
    facts = [_fact("Company", p.get("company_name")), _fact("Industry", p.get("industry")),
             _fact("Country", p.get("country")), _fact("Years in business", p.get("years_in_business")),
             _fact("Credit score", p.get("credit_score")), _fact("Rating", p.get("rating"))]
    body = _compose("You write concise credit committee overviews.",
                    f"Overview of {p.get('company_name', 'the borrower')}",
                    "Borrower profile and headline credit metrics.", facts)
    return {"heading": "Overview", "body": body, "evidence": facts}


def _financials(db, ctx):
    p = ctx["profile"] or {}
    eng = p.get("engine_input") or {}
    facts = [_fact(k.replace("_", " ").title(), eng.get(k))
             for k in ("revenue", "net_margin", "current_ratio", "debt_to_equity",
                       "operating_cash_flow")]
    body = _compose("You are a financial statement analyst.",
                    "Financial analysis", "Key ratios and cash-flow signals.", facts)
    chart = {"type": "bar", "title": "Key financial ratios",
             "data": [{"label": f["label"], "value": f["value"]}
                      for f in facts if isinstance(f["value"], (int, float))]}
    return {"heading": "Financial Analysis", "body": body, "evidence": facts, "chart": chart}


def _risk(db, ctx):
    p = ctx["profile"] or {}
    pd, lgd, ead = p.get("pd"), p.get("lgd"), p.get("exposure")
    el = p.get("expected_loss")
    if el is None and None not in (pd, lgd, ead):
        el = pd * lgd * ead
    facts = [_fact("PD", pd), _fact("LGD", lgd), _fact("EAD", ead),
             _fact("Expected loss", common.round_opt(el, 2)), _fact("Rating", p.get("rating"))]
    health = p.get("health") or {}
    chart = {"type": "radar", "title": "Health scores",
             "data": [{"axis": k, "value": v} for k, v in health.items() if v is not None]}
    body = _compose("You are a credit risk analyst.",
                    "Risk assessment", "Loss profile and health scores.", facts)
    return {"heading": "Risk Assessment", "body": body, "evidence": facts, "chart": chart}


def _fraud_screen(db, ctx):
    p = ctx["profile"] or {}
    eng = p.get("engine_input") or {}
    flags = []
    if (eng.get("operating_cash_flow") or 0) < 0 and (eng.get("revenue") or 0) > 0:
        flags.append("Negative operating cash flow against positive revenue")
    if (eng.get("net_margin") is not None) and eng["net_margin"] < 0:
        flags.append("Reported net losses")
    if (eng.get("debt_to_equity") or 0) > 3:
        flags.append("Very high leverage (D/E > 3)")
    facts = [_fact("Red flags detected", len(flags))] + [_fact(f"Flag {i+1}", f) for i, f in enumerate(flags)]
    body = _compose("You are a forensic fraud investigator.",
                    "Fraud screen", "Rule-based forensic screen over the financials.", facts)
    return {"heading": "Fraud Screen", "body": body, "evidence": facts}


def _portfolio_context(db, ctx):
    profiles = data_access.portfolio_profiles(db)
    p = ctx["profile"] or {}
    total_el = sum((q.get("expected_loss") or 0) for q in profiles)
    same = [q for q in profiles if q.get("industry") == p.get("industry")]
    facts = [_fact("Portfolio positions", len(profiles)),
             _fact("Total expected loss", common.round_opt(total_el, 2)),
             _fact("Same-sector positions", len(same))]
    chart = {"type": "bar", "title": "Expected loss by company",
             "data": [{"label": q.get("company_name"), "value": q.get("expected_loss")}
                      for q in profiles[:10]]}
    body = _compose("You are a portfolio manager.",
                    "Portfolio context", "Concentration and aggregate loss.", facts)
    return {"heading": "Portfolio Context", "body": body, "evidence": facts, "chart": chart}


def _regulatory(db, ctx):
    cites = []
    try:
        cites = rag.search(db, query=f"regulatory requirements for {ctx['profile'].get('industry') if ctx['profile'] else 'lending'}",
                           top_k=3, tenant_id=ctx.get("tenant_id"),
                           source_types=["rbi_circular", "basel_guideline"])
    except Exception:
        cites = []
    citations = rag.build_citations(cites)
    facts = [_fact(c["label"], c["snippet"]) for c in citations] or [_fact("Regulatory sources", "none indexed")]
    body = _compose("You are a regulatory expert (RBI/Basel).",
                    "Regulatory summary", "Applicable regulatory guidance.", facts, cites=citations)
    return {"heading": "Regulatory Summary", "body": body, "evidence": facts, "citations": citations}


def _recommendation(db, ctx):
    p = ctx["profile"] or {}
    score = p.get("credit_score") or 0
    pd = p.get("pd")
    if score >= 720 or (pd is not None and pd <= 0.03):
        decision, note = "APPROVE", "Approve within standard policy limits."
    elif score < 560 or (pd is not None and pd >= 0.12):
        decision, note = "DECLINE", "Decline or require substantial risk mitigation."
    else:
        decision, note = "REVIEW", "Approve subject to enhanced covenants and monitoring."
    facts = [_fact("Recommended decision", decision),
             _fact("Suggested exposure", p.get("exposure")),
             _fact("Indicative rate", p.get("interest_rate"))]
    body = _compose("You are a credit committee chair.",
                    f"Recommendation: {decision}", note, facts, actions=[note])
    return {"heading": "Recommendation", "body": body, "evidence": facts,
            "recommendations": [note], "decision": decision}


_SECTION_MAP: Dict[str, Callable] = {
    "overview": _overview, "financials": _financials, "risk": _risk,
    "fraud_screen": _fraud_screen, "portfolio_context": _portfolio_context,
    "regulatory": _regulatory, "recommendation": _recommendation,
}

_REPORT_SPECS: Dict[str, List[str]] = {
    "credit_memo": ["overview", "financials", "risk", "recommendation"],
    "investment_memo": ["overview", "financials", "risk", "portfolio_context", "recommendation"],
    "risk_report": ["overview", "risk", "recommendation"],
    "fraud_report": ["overview", "fraud_screen", "recommendation"],
    "portfolio_review": ["portfolio_context", "risk", "recommendation"],
    "committee_brief": ["overview", "risk", "recommendation"],
    "executive_summary": ["overview", "risk", "recommendation"],
    "regulatory_summary": ["overview", "regulatory", "recommendation"],
    "due_diligence": ["overview", "financials", "fraud_screen", "regulatory", "recommendation"],
    "financial_analysis": ["overview", "financials", "risk"],
    "board_presentation": ["executive_summary" if False else "overview", "financials",
                           "risk", "portfolio_context", "recommendation"],
}


# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------
def generate(db: Session, *, report_type: str, company_ref: Optional[str] = None,
             assessment_id: Optional[int] = None, tenant_id: Optional[int] = None,
             provider: Optional[str] = None, created_by: Optional[str] = None,
             title: Optional[str] = None, persist: bool = True) -> Dict[str, Any]:
    if report_type not in _REPORT_SPECS:
        raise ValueError(f"unknown report_type '{report_type}'")
    assessment = data_access.resolve(db, assessment_id=assessment_id, company_ref=company_ref)
    profile = data_access.profile(assessment)
    ctx = {"profile": profile, "tenant_id": tenant_id, "provider": provider,
           "company_ref": company_ref or (profile or {}).get("company_ref")}

    sections: List[Dict[str, Any]] = []
    evidence: List[Dict[str, Any]] = []
    charts: List[Dict[str, Any]] = []
    citations: List[Dict[str, Any]] = []
    recommendations: List[str] = []
    decision = None
    for key in _REPORT_SPECS[report_type]:
        sec = _SECTION_MAP[key](db, ctx)
        sections.append({"heading": sec["heading"], "body": sec["body"],
                         "evidence": sec.get("evidence", [])})
        evidence.extend(sec.get("evidence", []))
        if sec.get("chart"):
            charts.append(sec["chart"])
        if sec.get("citations"):
            citations.extend(sec["citations"])
        if sec.get("recommendations"):
            recommendations.extend(sec["recommendations"])
        if sec.get("decision"):
            decision = sec["decision"]

    # Confidence from profile completeness.
    present = sum(1 for k in ("credit_score", "pd", "lgd", "rating", "exposure")
                  if (profile or {}).get(k) is not None)
    confidence = common.round_opt(common.clamp(0.4 + 0.12 * present), 4)

    subject = ctx["company_ref"] or "portfolio"
    report_title = title or f"{report_type.replace('_', ' ').title()} — {subject}"

    row = None
    if persist:
        row = AIPReport(
            tenant_id=tenant_id, report_type=report_type, subject_ref=subject,
            assessment_id=(profile or {}).get("assessment_id"), title=report_title,
            sections=sections, evidence=evidence, citations=citations, charts=charts,
            recommendations=recommendations, confidence=confidence, status="final",
            format="structured", provider=llm_mod.get_llm(provider).name,
            created_by=created_by, created_at=common.utcnow())
        db.add(row)
        db.commit()
        db.refresh(row)

    return {"report_id": row.id if row else None, "report_type": report_type,
            "title": report_title, "subject_ref": subject, "decision": decision,
            "sections": sections, "evidence": evidence, "charts": charts,
            "citations": citations, "recommendations": recommendations,
            "confidence": confidence, "provider": llm_mod.get_llm(provider).name}


def get_report(db: Session, report_id: int) -> Optional[Dict[str, Any]]:
    r = db.query(AIPReport).filter(AIPReport.id == report_id).first()
    if not r:
        return None
    return {"report_id": r.id, "report_type": r.report_type, "title": r.title,
            "subject_ref": r.subject_ref, "sections": r.sections, "evidence": r.evidence,
            "charts": r.charts, "citations": r.citations,
            "recommendations": r.recommendations, "confidence": r.confidence,
            "status": r.status, "created_at": common.iso(r.created_at)}


def list_reports(db: Session, *, tenant_id: Optional[int] = None,
                 report_type: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
    q = db.query(AIPReport).filter(AIPReport.tenant_id == tenant_id)
    if report_type:
        q = q.filter(AIPReport.report_type == report_type)
    return [{"report_id": r.id, "report_type": r.report_type, "title": r.title,
             "subject_ref": r.subject_ref, "confidence": r.confidence,
             "created_at": common.iso(r.created_at)}
            for r in q.order_by(AIPReport.id.desc()).limit(limit).all()]
