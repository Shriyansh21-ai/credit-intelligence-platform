"""M4 — AI Credit Copilot.

An enterprise assistant that answers questions about assessments, explains
decisions/ratios/SHAP/fraud, summarizes financials, recommends next actions and
generates executive summaries — always from *deterministic platform data*. The
LLM (see :mod:`llm`) is used only to phrase the grounded facts; it never invents
numbers. Conversations + messages are persisted for audit and continuity.

Flow: ``ask`` → detect intent → build grounding (real data) → provider.compose →
persist assistant message with grounding + citations.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from backend.app.models.autonomous import CopilotConversation, CopilotMessage
from backend.app.models.financial_analysis import FinancialAnalysis
from backend.app.models.fraud import FraudCheck
from backend.app.models.risk_explanation import RiskExplanation
from . import data_access
from . import llm as llm_mod
from .common import evidence

# Intent → keyword triggers (first match wins; ordered most-specific first).
_INTENT_RULES: List[tuple] = [
    ("explain_shap", ["shap", "feature importance", "contribution", "driver", "waterfall"]),
    ("explain_fraud", ["fraud", "anomaly", "suspicious"]),
    ("explain_ratios", ["ratio", "dscr", "current ratio", "leverage", "margin", "liquidity ratio"]),
    ("summarize_financials", ["summarize financ", "financial statement", "financials", "balance sheet", "p&l", "profit and loss"]),
    ("explain_decision", ["why", "explain the decision", "decision", "rejected", "approved", "reason"]),
    ("next_actions", ["next action", "what should", "recommend", "next step", "what do i do"]),
    ("executive_summary", ["executive summary", "summary", "brief", "overview", "tl;dr"]),
    ("navigate", ["where", "how do i find", "navigate", "which page", "go to"]),
    ("explain_assessment", ["assessment", "credit score", "rating", "pd", "risk", "how risky"]),
]

# Navigation map for the "navigate" intent (deterministic, from the real routes).
_NAV_MAP = {
    "risk": "/risk-intelligence", "explain": "/explainability", "scenario": "/scenario",
    "stress": "/stress-testing", "portfolio": "/portfolio-intelligence",
    "alert": "/alerts", "report": "/analyst-report", "document": "/documents",
    "fraud": "/fraud", "analysis": "/analysis", "knowledge graph": "/knowledge-graph",
    "monitoring": "/risk-monitoring", "early warning": "/early-warning",
    "copilot": "/copilot", "command center": "/command-center",
}


def detect_intent(question: str) -> str:
    q = (question or "").lower()
    for intent, triggers in _INTENT_RULES:
        if any(t in q for t in triggers):
            return intent
    return "explain_assessment"


# ---------------------------------------------------------------------------
# Grounding builders — each returns {headline, narrative, facts, citations, ...}
# ---------------------------------------------------------------------------
def _latest_financial(db: Session, assessment_id: Optional[int], company_ref: Optional[str]) -> Optional[FinancialAnalysis]:
    try:
        q = db.query(FinancialAnalysis).filter(FinancialAnalysis.is_current == True)  # noqa: E712
        if assessment_id:
            q = q.filter(FinancialAnalysis.assessment_id == assessment_id)
        return q.order_by(FinancialAnalysis.id.desc()).first()
    except Exception:
        return None


def _latest_explanation(db: Session, assessment_id: Optional[int]) -> Optional[RiskExplanation]:
    try:
        q = db.query(RiskExplanation).filter(RiskExplanation.is_current == True)  # noqa: E712
        if assessment_id:
            q = q.filter(RiskExplanation.assessment_id == assessment_id)
        return q.order_by(RiskExplanation.id.desc()).first()
    except Exception:
        return None


def _ground_assessment(db, prof, ctx) -> Dict[str, Any]:
    if not prof:
        return {"headline": "No assessment found for that company.", "facts": [], "citations": []}
    facts = [
        evidence("Company", prof.get("company_ref")),
        evidence("Industry", prof.get("industry")),
        evidence("Credit score", prof.get("credit_score")),
        evidence("Risk rating", prof.get("rating")),
        evidence("Probability of default", _pct(prof.get("pd"))),
        evidence("Expected loss", prof.get("expected_loss")),
        evidence("Recommended exposure", prof.get("exposure")),
    ]
    return {
        "headline": f"Credit assessment for {prof.get('company_ref')}",
        "narrative": (f"{prof.get('company_ref')} carries a {prof.get('rating')} rating with a "
                      f"credit score of {prof.get('credit_score')} and an estimated PD of "
                      f"{_pct(prof.get('pd'))}."),
        "facts": facts, "citations": [{"type": "assessment", "id": prof.get("assessment_id")}],
    }


def _ground_ratios(db, prof, ctx) -> Dict[str, Any]:
    fa = _latest_financial(db, prof.get("assessment_id") if prof else None, prof.get("company_ref") if prof else None)
    if fa is None:
        return {"headline": "No financial analysis available to explain ratios.",
                "facts": [], "citations": []}
    ratios = fa.ratios or []
    facts = [evidence(r.get("name") or r.get("key"),
                      f"{r.get('value')} — {r.get('interpretation') or r.get('status')}")
             for r in ratios[:12] if isinstance(r, dict)]
    return {"headline": f"Key financial ratios (health {fa.overall_health_score}/100, "
                        f"{fa.overall_health_status})",
            "narrative": "Ratios are computed by the deterministic financial-analysis engine.",
            "facts": facts, "citations": [{"type": "financial_analysis", "id": fa.id}]}


def _ground_shap(db, prof, ctx) -> Dict[str, Any]:
    ex = _latest_explanation(db, prof.get("assessment_id") if prof else None)
    if ex is None:
        return {"headline": "No explainability record available yet.", "facts": [], "citations": []}
    pos = ex.top_positive or []
    neg = ex.top_negative or []
    facts = [evidence(f"↑ risk: {c.get('feature')}", c.get("contribution")) for c in neg[:5]]
    facts += [evidence(f"↓ risk: {c.get('feature')}", c.get("contribution")) for c in pos[:5]]
    return {"headline": f"Model attribution ({ex.method}, {ex.model_type})",
            "narrative": ex.summary or "Signed feature attributions drive the risk score.",
            "facts": facts, "citations": [{"type": "risk_explanation", "id": ex.id}]}


def _ground_fraud(db, prof, ctx) -> Dict[str, Any]:
    try:
        fc = (db.query(FraudCheck).order_by(FraudCheck.id.desc()).first())
    except Exception:
        fc = None
    if fc is None:
        return {"headline": "No fraud check on record.", "facts": [], "citations": []}
    return {"headline": f"Fraud assessment: {'DETECTED' if fc.fraud_detected else 'clear'}",
            "narrative": fc.ai_analysis or "",
            "facts": [evidence("Fraud detected", fc.fraud_detected),
                      evidence("Fraud risk", fc.fraud_risk),
                      evidence("Anomaly score", fc.anomaly_score)],
            "citations": [{"type": "fraud_check", "id": fc.id}]}


def _ground_financials(db, prof, ctx) -> Dict[str, Any]:
    fa = _latest_financial(db, prof.get("assessment_id") if prof else None, None)
    if fa is None:
        return _ground_assessment(db, prof, ctx)
    insights = [i.get("message") if isinstance(i, dict) else str(i) for i in (fa.insights or [])][:5]
    facts = [evidence("Overall health", f"{fa.overall_health_score}/100 ({fa.overall_health_status})"),
             evidence("Liquidity", fa.liquidity_health), evidence("Profitability", fa.profitability_health),
             evidence("Leverage", fa.leverage_health), evidence("Cash flow", fa.cash_flow_health),
             evidence("Risk flags", fa.risk_flag_count)]
    return {"headline": f"Financial summary for {prof.get('company_ref') if prof else 'company'}",
            "narrative": " ".join(insights) if insights else "Deterministic engine summary.",
            "facts": facts, "citations": [{"type": "financial_analysis", "id": fa.id}]}


def _ground_next_actions(db, prof, ctx) -> Dict[str, Any]:
    from . import recommendations as rec_svc
    if not prof:
        return {"headline": "Bind a company to get recommendations.", "facts": [], "citations": []}
    recs = rec_svc.recommend(db, company_ref=prof.get("company_ref"),
                             assessment_id=prof.get("assessment_id"), persist=False)
    actions = [r["title"] for r in recs.get("recommendations", [])]
    facts = [evidence(r["action"], f"{r['title']} ({int(r['confidence']*100)}% conf)")
             for r in recs.get("recommendations", [])[:6]]
    return {"headline": f"Recommended next actions for {prof.get('company_ref')}",
            "narrative": recs.get("summary", ""), "facts": facts,
            "recommended_actions": actions[:6],
            "citations": [{"type": "assessment", "id": prof.get("assessment_id")}]}


def _ground_executive(db, prof, ctx) -> Dict[str, Any]:
    base = _ground_assessment(db, prof, ctx)
    fin = _ground_financials(db, prof, ctx)
    ex = _latest_explanation(db, prof.get("assessment_id") if prof else None)
    facts = base["facts"] + [f for f in fin["facts"] if f not in base["facts"]][:4]
    narrative = base.get("narrative", "")
    if ex and ex.summary:
        narrative += " " + ex.summary
    return {"headline": f"Executive summary — {prof.get('company_ref') if prof else 'company'}",
            "narrative": narrative, "facts": facts,
            "citations": base["citations"] + fin["citations"]}


def _ground_navigate(db, prof, ctx, question: str) -> Dict[str, Any]:
    q = question.lower()
    for key, route in _NAV_MAP.items():
        if key in q:
            return {"headline": f"You can find that under {route}",
                    "narrative": f"Navigate to {route} in the left sidebar.",
                    "facts": [evidence("route", route)], "citations": []}
    return {"headline": "Here are the main areas of the platform.",
            "facts": [evidence(k, v) for k, v in list(_NAV_MAP.items())[:8]], "citations": []}


_GROUNDERS = {
    "explain_assessment": _ground_assessment, "explain_decision": _ground_assessment,
    "explain_ratios": _ground_ratios, "explain_shap": _ground_shap,
    "explain_fraud": _ground_fraud, "summarize_financials": _ground_financials,
    "next_actions": _ground_next_actions, "executive_summary": _ground_executive,
}


def _pct(v) -> Optional[str]:
    return f"{v*100:.2f}%" if isinstance(v, (int, float)) else None


def build_grounding(db: Session, question: str, intent: str, *,
                    company_ref: Optional[str] = None, assessment_id: Optional[int] = None) -> Dict[str, Any]:
    assessment = data_access.resolve(db, assessment_id=assessment_id, company_ref=company_ref)
    prof = data_access.profile(assessment)
    ctx: Dict[str, Any] = {}
    if intent == "navigate":
        return _ground_navigate(db, prof, ctx, question)
    grounder = _GROUNDERS.get(intent, _ground_assessment)
    return grounder(db, prof, ctx)


# ---------------------------------------------------------------------------
# Conversation persistence + ask
# ---------------------------------------------------------------------------
def start_conversation(db: Session, *, user_id: Optional[int] = None, title: Optional[str] = None,
                       context_ref: Optional[str] = None, tenant_id: Optional[int] = None) -> CopilotConversation:
    conv = CopilotConversation(user_id=user_id, title=title or "New conversation",
                               context_ref=context_ref, tenant_id=tenant_id)
    db.add(conv)
    db.commit()
    db.refresh(conv)
    return conv


def ask(db: Session, question: str, *, conversation_id: Optional[int] = None,
        company_ref: Optional[str] = None, assessment_id: Optional[int] = None,
        user_id: Optional[int] = None, tenant_id: Optional[int] = None,
        provider: Optional[str] = None) -> Dict[str, Any]:
    """Answer a question, grounded in platform data, persisting the exchange."""
    intent = detect_intent(question)
    conv = None
    if conversation_id is not None:
        conv = db.query(CopilotConversation).filter(CopilotConversation.id == conversation_id).first()
    if conv is None:
        conv = start_conversation(db, user_id=user_id, title=question[:80],
                                  context_ref=company_ref, tenant_id=tenant_id)
    company_ref = company_ref or conv.context_ref

    grounding = build_grounding(db, question, intent, company_ref=company_ref, assessment_id=assessment_id)
    prov = llm_mod.get_provider(provider)
    answer = prov.compose(question=question, grounding=grounding, intent=intent)

    db.add(CopilotMessage(conversation_id=conv.id, role="user", content=question, intent=intent))
    msg = CopilotMessage(conversation_id=conv.id, role="assistant", content=answer, intent=intent,
                         provider=prov.name, grounding=grounding,
                         citations=grounding.get("citations", []))
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return {
        "conversation_id": conv.id, "message_id": msg.id, "intent": intent,
        "provider": prov.name, "answer": answer,
        "grounding": grounding, "citations": grounding.get("citations", []),
    }


def get_messages(db: Session, conversation_id: int) -> List[CopilotMessage]:
    return (db.query(CopilotMessage).filter(CopilotMessage.conversation_id == conversation_id)
            .order_by(CopilotMessage.id.asc()).all())


def list_conversations(db: Session, *, user_id: Optional[int] = None,
                       tenant_id: Optional[int] = None, limit: int = 50) -> List[CopilotConversation]:
    q = db.query(CopilotConversation).filter(CopilotConversation.tenant_id == tenant_id)
    if user_id is not None:
        q = q.filter(CopilotConversation.user_id == user_id)
    return q.order_by(CopilotConversation.updated_at.desc()).limit(limit).all()
