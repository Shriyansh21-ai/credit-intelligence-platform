"""M9 — Enterprise conversational AI.

A ChatGPT-style assistant grounded in the whole platform. It answers questions
about customers, portfolios, loans, documents, compliance, fraud, policies,
banking regulations and committee history — and **every** answer carries
evidence (grounded facts + RAG citations), because the assistant never speaks
without first assembling deterministic grounding.

The flow per turn: classify intent → assemble grounding from the relevant
source(s) (M1 RAG, the Phase 1-10 engines via ``autonomous.data_access``, the M2
specialist agents and M3 conversation memory) → compose via the grounding-first
LLM → persist the turn with its citations + confidence. Conversation memory gives
continuity across turns.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from backend.app.models.ai_platform import AIPConversation, AIPMessage
from backend.app.services.ai_platform import (
    agents as agents_svc, common, llm as llm_mod, memory as memory_svc, rag,
)
from backend.app.services.autonomous import data_access

# Intent → (source_types, agent_role) routing hints.
_INTENTS = {
    "fraud": (None, "fraud_investigator"),
    "compliance": (["credit_policy"], "compliance_officer"),
    "policy": (["credit_policy", "external_manual"], "banking_policy_expert"),
    "regulation": (["rbi_circular", "basel_guideline"], "regulatory_expert"),
    "financials": (None, "financial_statement_expert"),
    "portfolio": (None, "portfolio_manager"),
    "documents": (["annual_report", "loan_agreement", "financial_statement", "ocr_document"], "document_specialist"),
    "general": (None, None),
}

_INTENT_KEYWORDS = {
    "fraud": ["fraud", "forensic", "suspicious", "anomaly", "red flag"],
    "compliance": ["compliance", "covenant", "breach", "conform", "kyc"],
    "policy": ["policy", "guideline", "manual", "procedure"],
    "regulation": ["rbi", "basel", "npa", "regulation", "regulatory", "provision", "circular"],
    "financials": ["ratio", "liquidity", "margin", "balance sheet", "cash flow", "financial"],
    "portfolio": ["portfolio", "concentration", "sector", "diversification", "exposure across"],
    "documents": ["document", "annual report", "agreement", "statement", "evidence"],
}


def classify_intent(message: str) -> str:
    m = (message or "").lower()
    best, best_hits = "general", 0
    for intent, kws in _INTENT_KEYWORDS.items():
        hits = sum(1 for k in kws if k in m)
        if hits > best_hits:
            best, best_hits = intent, hits
    return best


# ---------------------------------------------------------------------------
# Conversations
# ---------------------------------------------------------------------------
def create_conversation(db: Session, *, title: Optional[str] = None,
                        bindings: Optional[Dict[str, Any]] = None,
                        user_ref: Optional[str] = None,
                        tenant_id: Optional[int] = None) -> AIPConversation:
    conv = AIPConversation(tenant_id=tenant_id, title=title or "New conversation",
                           user_ref=user_ref, bindings=bindings or {}, status="open",
                           created_at=common.utcnow(), updated_at=common.utcnow())
    db.add(conv)
    db.commit()
    db.refresh(conv)
    return conv


def list_conversations(db, *, tenant_id=None, limit=50) -> List[AIPConversation]:
    return (db.query(AIPConversation).filter(AIPConversation.tenant_id == tenant_id)
            .order_by(AIPConversation.id.desc()).limit(limit).all())


def get_messages(db, *, conversation_id: int) -> List[AIPMessage]:
    return (db.query(AIPMessage).filter(AIPMessage.conversation_id == conversation_id)
            .order_by(AIPMessage.id).all())


# ---------------------------------------------------------------------------
# Ask
# ---------------------------------------------------------------------------
def ask(db: Session, *, conversation_id: int, message: str,
        tenant_id: Optional[int] = None, provider: Optional[str] = None,
        user_ref: Optional[str] = None) -> Dict[str, Any]:
    conv = db.query(AIPConversation).filter(AIPConversation.id == conversation_id).first()
    if conv is None:
        raise ValueError("conversation not found")
    bindings = conv.bindings or {}
    company_ref = bindings.get("company_ref")
    assessment_id = bindings.get("assessment_id")
    intent = classify_intent(message)
    source_types, agent_role = _INTENTS.get(intent, (None, None))

    profile = None
    if company_ref or assessment_id:
        profile = data_access.profile(
            data_access.resolve(db, assessment_id=assessment_id, company_ref=company_ref))
    ctx = {"profile": profile, "tenant_id": tenant_id, "provider": provider,
           "goal": message, "company_ref": company_ref}

    facts: List[Dict[str, Any]] = []
    citations: List[Dict[str, Any]] = []
    narrative = ""

    # 1. Knowledge / RAG grounding.
    hits = rag.search(db, query=message, top_k=4, tenant_id=tenant_id, source_types=source_types)
    if hits:
        citations = rag.build_citations(hits)
        narrative = hits[0]["snippet"]
        facts += [{"label": c["label"], "value": c["snippet"]} for c in citations]

    # 2. Intent-specific engine grounding.
    if intent == "portfolio":
        profiles = data_access.portfolio_profiles(db)
        total_el = sum((q.get("expected_loss") or 0) for q in profiles)
        facts += [{"label": "Portfolio positions", "value": len(profiles)},
                  {"label": "Total expected loss", "value": common.round_opt(total_el, 2)}]
    elif agent_role and profile:
        g = agents_svc.AGENTS[agent_role].gather(db, ctx)
        facts += g.get("facts", [])
        if not narrative:
            narrative = g.get("recommendation", "")
        if g.get("citations"):
            citations += g["citations"]
    if profile:
        facts += [{"label": "Credit score", "value": profile.get("credit_score")},
                  {"label": "Rating", "value": profile.get("rating")},
                  {"label": "PD", "value": profile.get("pd")}]

    # 3. Conversation memory for continuity.
    mem = memory_svc.recall(db, query=message, scope="conversation",
                            scope_ref=str(conversation_id), tenant_id=tenant_id, top_k=3)
    prior = [m["content"] for m in mem]

    grounding = {
        "headline": f"Response ({intent})",
        "narrative": narrative or "Answering from grounded platform data.",
        "facts": facts,
        "citations": citations,
    }
    grounded = bool(facts)
    result = llm_mod.get_llm(provider).generate(
        prompt=f"User question: {message}\nPrior context: {' | '.join(prior)[:400]}",
        system=("You are an enterprise banking assistant. Answer using ONLY the "
                "grounding; always ground claims in the cited evidence."),
        grounding=grounding if grounded else None)
    confidence = common.round_opt(common.clamp(
        0.3 + 0.1 * len(facts) + (0.2 if citations else 0.0) + (0.1 if profile else 0.0)), 4)

    # Persist the turn.
    db.add(AIPMessage(conversation_id=conv.id, role="user", content=message,
                      intent=intent, created_at=common.utcnow()))
    assistant = AIPMessage(conversation_id=conv.id, role="assistant", content=result.text,
                           intent=intent, grounding=grounding, citations=citations,
                           confidence=confidence, provider=result.provider,
                           tokens=result.total_tokens, created_at=common.utcnow())
    db.add(assistant)
    conv.message_count = (conv.message_count or 0) + 2
    conv.updated_at = common.utcnow()
    db.commit()
    db.refresh(assistant)

    # Remember this turn for continuity.
    try:
        memory_svc.write(db, content=f"Q: {message}\nA: {common.truncate(result.text, 300)}",
                         memory_type="conversation", scope="conversation",
                         scope_ref=str(conversation_id), importance=0.4, tenant_id=tenant_id)
    except Exception:
        pass

    return {"conversation_id": conv.id, "message_id": assistant.id, "intent": intent,
            "answer": result.text, "evidence": facts, "citations": citations,
            "confidence": confidence, "grounded": grounded, "provider": result.provider}


def conversation_detail(db: Session, *, conversation_id: int) -> Optional[Dict[str, Any]]:
    conv = db.query(AIPConversation).filter(AIPConversation.id == conversation_id).first()
    if not conv:
        return None
    msgs = get_messages(db, conversation_id=conversation_id)
    return {"conversation_id": conv.id, "title": conv.title, "bindings": conv.bindings,
            "status": conv.status, "message_count": conv.message_count,
            "messages": [{"id": m.id, "role": m.role, "content": m.content,
                          "intent": m.intent, "citations": m.citations,
                          "confidence": m.confidence} for m in msgs]}
