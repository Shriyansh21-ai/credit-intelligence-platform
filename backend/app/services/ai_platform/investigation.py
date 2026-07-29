"""M6 — Autonomous company investigation.

Runs the full investigative workflow end-to-end and records every stage for
traceability:

    receive company → collect documents → search knowledge → analyze statements
    → check fraud → verify compliance → compare industry → calculate risk
    → explain reasoning → prepare recommendation → produce executive report

Each stage assembles deterministic grounding (the Phase 1-10 engines via
``autonomous.data_access``, the M1 RAG index and the M2 specialist agents) and
appends an ``aip_investigation_steps`` row with its output + evidence, so the
whole chain is auditable. The final stage produces an M7 due-diligence report and
links it back to the investigation.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from backend.app.models.ai_platform import AIPInvestigation, AIPInvestigationStep
from backend.app.services.ai_platform import agents as agents_svc, common, rag, reports
from backend.app.services.autonomous import data_access

STAGES = [
    "collect_documents", "search_knowledge", "analyze_statements", "check_fraud",
    "verify_compliance", "compare_industry", "calculate_risk",
    "explain_reasoning", "prepare_recommendation", "produce_report",
]


def investigate(db: Session, *, company_ref: Optional[str] = None,
                assessment_id: Optional[int] = None, tenant_id: Optional[int] = None,
                provider: Optional[str] = None, created_by: Optional[str] = None) -> Dict[str, Any]:
    assessment = data_access.resolve(db, assessment_id=assessment_id, company_ref=company_ref)
    profile = data_access.profile(assessment)
    company = company_ref or (profile or {}).get("company_ref") or "unknown"
    ctx = {"profile": profile, "tenant_id": tenant_id, "provider": provider,
           "goal": f"investigate {company}", "company_ref": company}

    inv = AIPInvestigation(
        tenant_id=tenant_id, company_ref=company,
        assessment_id=(profile or {}).get("assessment_id"), status="running",
        plan=[{"ordinal": i, "stage": s} for i, s in enumerate(STAGES)],
        findings={}, risk_summary={}, trace=[], created_by=created_by,
        created_at=common.utcnow())
    db.add(inv)
    db.commit()
    db.refresh(inv)

    findings: Dict[str, Any] = {}
    trace: List[Dict[str, Any]] = []

    def _step(ordinal: int, stage: str, output: Dict[str, Any],
              evidence: Optional[List[Any]] = None):
        db.add(AIPInvestigationStep(investigation_id=inv.id, ordinal=ordinal, stage=stage,
                                    status="done", output=output, evidence=evidence or [],
                                    created_at=common.utcnow()))
        db.commit()
        trace.append({"ordinal": ordinal, "stage": stage, "summary": output.get("summary")})

    # 1. Collect documents
    docs = rag.search(db, query=company, top_k=5, tenant_id=tenant_id,
                      source_types=["annual_report", "loan_agreement",
                                    "financial_statement", "ocr_document"]) if company else []
    _step(0, "collect_documents",
          {"summary": f"Located {len(docs)} supporting document chunk(s).",
           "count": len(docs)}, rag.build_citations(docs))
    findings["documents"] = rag.build_citations(docs)

    # 2. Search knowledge
    know = rag.search(db, query=f"credit policy and regulation for {(profile or {}).get('industry','lending')}",
                      top_k=5, tenant_id=tenant_id,
                      source_types=["credit_policy", "rbi_circular", "basel_guideline"])
    _step(1, "search_knowledge",
          {"summary": f"Retrieved {len(know)} relevant policy/regulatory passage(s).",
           "count": len(know)}, rag.build_citations(know))
    findings["knowledge"] = rag.build_citations(know)

    # 3. Analyze statements
    fin = agents_svc.AGENTS["financial_statement_expert"].gather(db, ctx)
    _step(2, "analyze_statements", {"summary": fin.get("recommendation"),
                                    "signal": fin.get("signal")}, fin.get("facts"))
    findings["financials"] = fin

    # 4. Check fraud
    fraud = agents_svc.AGENTS["fraud_investigator"].gather(db, ctx)
    _step(3, "check_fraud", {"summary": fraud.get("recommendation"),
                             "signal": fraud.get("signal")}, fraud.get("facts"))
    findings["fraud"] = fraud

    # 5. Verify compliance
    comp = agents_svc.AGENTS["compliance_officer"].gather(db, ctx)
    _step(4, "verify_compliance", {"summary": comp.get("recommendation"),
                                   "signal": comp.get("signal")}, comp.get("facts"))
    findings["compliance"] = comp

    # 6. Compare industry
    peers = [q for q in data_access.portfolio_profiles(db)
             if q.get("industry") == (profile or {}).get("industry")
             and q.get("company_ref") != company]
    peer_scores = [q.get("credit_score") for q in peers if q.get("credit_score") is not None]
    peer_avg = common.round_opt(sum(peer_scores) / len(peer_scores), 1) if peer_scores else None
    my_score = (profile or {}).get("credit_score")
    rel = None
    if peer_avg is not None and my_score is not None:
        rel = "above peer average" if my_score >= peer_avg else "below peer average"
    _step(5, "compare_industry",
          {"summary": f"Peer benchmark: {rel or 'no peers indexed'}.",
           "peer_average_score": peer_avg, "peer_count": len(peers)},
          [{"label": "Peers", "value": len(peers)}, {"label": "Peer avg score", "value": peer_avg}])
    findings["industry_comparison"] = {"peer_average_score": peer_avg,
                                        "peer_count": len(peers), "relative": rel}

    # 7. Calculate risk
    risk = agents_svc.AGENTS["risk_analyst"].gather(db, ctx)
    pd = (profile or {}).get("pd")
    _step(6, "calculate_risk", {"summary": risk.get("recommendation"),
                                "signal": risk.get("signal"), "pd": pd}, risk.get("facts"))
    findings["risk"] = risk
    risk_summary = {"pd": pd, "lgd": (profile or {}).get("lgd"),
                    "expected_loss": (profile or {}).get("expected_loss"),
                    "rating": (profile or {}).get("rating"), "signal": risk.get("signal")}

    # 8. Explain reasoning (chain)
    signals = {k: findings[k].get("signal") for k in ("financials", "fraud", "compliance", "risk")
               if isinstance(findings.get(k), dict)}
    reasoning_chain = [
        f"Documents: {len(docs)} chunk(s) located.",
        f"Financial health signal: {signals.get('financials')}.",
        f"Fraud screen signal: {signals.get('fraud')}.",
        f"Compliance signal: {signals.get('compliance')}.",
        f"Industry: {rel or 'no peers'}.",
        f"Risk signal: {signals.get('risk')} (PD {pd}).",
    ]
    _step(7, "explain_reasoning", {"summary": "Reasoning chain assembled.",
                                   "chain": reasoning_chain})
    findings["reasoning_chain"] = reasoning_chain

    # 9. Prepare recommendation
    negatives = sum(1 for s in signals.values() if s == "negative")
    cautions = sum(1 for s in signals.values() if s == "caution")
    if negatives >= 2 or (pd is not None and pd >= 0.12):
        decision, rec = "DECLINE", "Decline: multiple adverse findings / high default risk."
    elif negatives or cautions >= 2:
        decision, rec = "REVIEW", "Refer to committee with enhanced covenants and monitoring."
    else:
        decision, rec = "APPROVE", "Approve within policy limits; standard monitoring."
    _step(8, "prepare_recommendation", {"summary": rec, "decision": decision})
    findings["recommendation"] = {"decision": decision, "note": rec}

    # 10. Produce executive report
    report = reports.generate(db, report_type="due_diligence", company_ref=company,
                              assessment_id=assessment_id, tenant_id=tenant_id,
                              provider=provider, created_by=created_by,
                              title=f"Due Diligence — {company}")
    _step(9, "produce_report", {"summary": "Executive due-diligence report generated.",
                                "report_id": report["report_id"]})

    completeness = sum(1 for k in ("credit_score", "pd", "rating") if (profile or {}).get(k) is not None)
    confidence = common.round_opt(common.clamp(0.4 + 0.15 * completeness + 0.05 * (1 if docs else 0)), 4)

    inv.status = "completed"
    inv.findings = findings
    inv.risk_summary = risk_summary
    inv.recommendation = rec
    inv.confidence = confidence
    inv.report_id = report["report_id"]
    inv.trace = trace
    inv.completed_at = common.utcnow()
    db.commit()
    db.refresh(inv)

    return {"investigation_id": inv.id, "company_ref": company, "status": inv.status,
            "decision": decision, "recommendation": rec, "confidence": confidence,
            "risk_summary": risk_summary, "findings": findings,
            "reasoning_chain": reasoning_chain, "report_id": report["report_id"],
            "trace": trace, "stages": len(STAGES)}


def get_investigation(db: Session, investigation_id: int) -> Optional[Dict[str, Any]]:
    inv = db.query(AIPInvestigation).filter(AIPInvestigation.id == investigation_id).first()
    if not inv:
        return None
    steps = (db.query(AIPInvestigationStep)
             .filter(AIPInvestigationStep.investigation_id == inv.id)
             .order_by(AIPInvestigationStep.ordinal).all())
    return {"investigation_id": inv.id, "company_ref": inv.company_ref, "status": inv.status,
            "recommendation": inv.recommendation, "confidence": inv.confidence,
            "risk_summary": inv.risk_summary, "findings": inv.findings,
            "report_id": inv.report_id, "trace": inv.trace,
            "steps": [{"ordinal": s.ordinal, "stage": s.stage, "status": s.status,
                       "output": s.output, "evidence": s.evidence} for s in steps],
            "created_at": common.iso(inv.created_at)}


def list_investigations(db: Session, *, tenant_id: Optional[int] = None,
                        limit: int = 50) -> List[Dict[str, Any]]:
    q = db.query(AIPInvestigation).filter(AIPInvestigation.tenant_id == tenant_id)
    return [{"investigation_id": i.id, "company_ref": i.company_ref, "status": i.status,
             "recommendation": i.recommendation, "confidence": i.confidence,
             "report_id": i.report_id, "created_at": common.iso(i.created_at)}
            for i in q.order_by(AIPInvestigation.id.desc()).limit(limit).all()]
