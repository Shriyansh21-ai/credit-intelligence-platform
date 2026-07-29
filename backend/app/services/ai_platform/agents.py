"""M2 — Production multi-agent AI system.

A grounding-first multi-agent framework: a **planner** decomposes a goal into a
set of specialist **worker agents**, a **coordinator** executes them (with retry
and self-critique/reflection), and their contributions are fused by **consensus
voting** with explicit **conflict resolution** and an executive synthesis.

Twelve specialist roles are provided (credit analyst, risk analyst, fraud
investigator, compliance officer, portfolio manager, relationship manager,
financial-statement expert, banking-policy expert, regulatory expert,
underwriter, document specialist, executive advisor). Each agent first assembles
*deterministic grounding* from real platform data (the Phase 1-10 engines via
``autonomous.data_access`` and the M1 RAG index) and only then phrases it via the
grounding-first LLM client — so the whole system is reproducible and offline by
default, and never fabricates numbers.

Every run and every step is persisted (``aip_agent_runs`` / ``aip_agent_steps``)
for full traceability.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from sqlalchemy.orm import Session

from backend.app.models.ai_platform import AIPAgentRun, AIPAgentStep
from backend.app.services.ai_platform import common, llm as llm_mod, rag
from backend.app.services.autonomous import data_access

# Signal → vote weight (confidence-weighted downstream).
_SIGNAL_VOTE = {"positive": 1.0, "neutral": 0.0, "caution": -0.35, "negative": -1.0}


@dataclass
class Contribution:
    role: str
    title: str
    summary: str
    facts: List[Dict[str, Any]] = field(default_factory=list)
    signal: str = "neutral"
    confidence: float = 0.5
    recommendation: str = ""
    citations: List[Dict[str, Any]] = field(default_factory=list)
    critique: str = ""
    status: str = "done"

    def as_dict(self) -> Dict[str, Any]:
        return {
            "role": self.role, "title": self.title, "summary": self.summary,
            "facts": self.facts, "signal": self.signal,
            "confidence": common.round_opt(self.confidence, 4),
            "recommendation": self.recommendation, "citations": self.citations,
            "critique": self.critique, "status": self.status,
        }


# ---------------------------------------------------------------------------
# Grounding helpers shared by agents
# ---------------------------------------------------------------------------
def _score_signal(profile: Optional[Dict[str, Any]]) -> str:
    if not profile:
        return "neutral"
    score = profile.get("credit_score")
    pd = profile.get("pd")
    if score is None and pd is None:
        return "neutral"
    if (score is not None and score >= 720) or (pd is not None and pd <= 0.03):
        return "positive"
    if (score is not None and score < 560) or (pd is not None and pd >= 0.12):
        return "negative"
    if (score is not None and score < 640) or (pd is not None and pd >= 0.07):
        return "caution"
    return "positive" if (score or 0) >= 680 else "neutral"


def _conf_from_profile(profile: Optional[Dict[str, Any]], base: float = 0.6) -> float:
    if not profile:
        return 0.3
    present = sum(1 for k in ("credit_score", "pd", "lgd", "rating") if profile.get(k) is not None)
    return common.clamp(base + 0.1 * present - 0.2)


def _rag_grounding(db, ctx, source_types, query) -> List[Dict[str, Any]]:
    try:
        return rag.search(db, query=query, top_k=3, tenant_id=ctx.get("tenant_id"),
                          source_types=source_types)
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Agent base + registry
# ---------------------------------------------------------------------------
class Agent:
    role = "agent"
    title = "Agent"
    persona = "A banking specialist."
    keywords: List[str] = []

    def gather(self, db: Session, ctx: Dict[str, Any]) -> Dict[str, Any]:
        """Return {facts, signal, confidence, recommendation, narrative, citations}."""
        raise NotImplementedError

    def contribute(self, db: Session, ctx: Dict[str, Any]) -> Contribution:
        g = self.gather(db, ctx)
        grounding = {
            "headline": f"{self.title} assessment",
            "narrative": g.get("narrative", ""),
            "facts": g.get("facts", []),
            "recommended_actions": [g["recommendation"]] if g.get("recommendation") else [],
            "citations": g.get("citations", []),
        }
        client = llm_mod.get_llm(ctx.get("provider"))
        text = client.generate(prompt=f"As a {self.title}, {ctx.get('goal', 'assess the borrower')}.",
                               system=self.persona, grounding=grounding).text
        return Contribution(
            role=self.role, title=self.title, summary=text,
            facts=g.get("facts", []), signal=g.get("signal", "neutral"),
            confidence=g.get("confidence", 0.5),
            recommendation=g.get("recommendation", ""),
            citations=g.get("citations", []),
        )


class CreditAnalyst(Agent):
    role, title = "credit_analyst", "Credit Analyst"
    persona = "You are a senior credit analyst evaluating repayment capacity."
    keywords = ["credit", "score", "repayment", "loan", "borrower", "approve"]

    def gather(self, db, ctx):
        p = ctx.get("profile")
        facts = []
        if p:
            facts = [{"label": "Credit score", "value": p.get("credit_score")},
                     {"label": "Risk rating", "value": p.get("rating")},
                     {"label": "PD", "value": p.get("pd")},
                     {"label": "Exposure", "value": p.get("exposure")}]
        sig = _score_signal(p)
        rec = {"positive": "Recommend approval within policy limits.",
               "caution": "Approve with enhanced covenants and monitoring.",
               "negative": "Recommend decline or heavy risk mitigation.",
               "neutral": "Insufficient data — request financials."}[sig]
        return {"facts": facts, "signal": sig, "confidence": _conf_from_profile(p),
                "recommendation": rec,
                "narrative": "Creditworthiness assessed from the enterprise scorecard."}


class RiskAnalyst(Agent):
    role, title = "risk_analyst", "Risk Analyst"
    persona = "You are a risk analyst quantifying expected and unexpected loss."
    keywords = ["risk", "pd", "lgd", "loss", "exposure", "default"]

    def gather(self, db, ctx):
        p = ctx.get("profile") or {}
        pd = p.get("pd"); lgd = p.get("lgd"); ead = p.get("exposure")
        el = p.get("expected_loss")
        if el is None and None not in (pd, lgd, ead):
            el = pd * lgd * ead
        facts = [{"label": "PD", "value": pd}, {"label": "LGD", "value": lgd},
                 {"label": "EAD", "value": ead}, {"label": "Expected loss", "value": common.round_opt(el, 2)}]
        sig = "negative" if (pd or 0) >= 0.12 else ("caution" if (pd or 0) >= 0.07 else
              ("positive" if pd is not None and pd <= 0.03 else "neutral"))
        return {"facts": facts, "signal": sig, "confidence": _conf_from_profile(p, 0.55),
                "recommendation": "Price for the quantified expected loss and set risk limits.",
                "narrative": "Loss profile derived from PD/LGD/EAD."}


class FraudInvestigator(Agent):
    role, title = "fraud_investigator", "Fraud Investigator"
    persona = "You are a forensic fraud investigator looking for red flags."
    keywords = ["fraud", "forensic", "red flag", "anomaly", "suspicious"]

    def gather(self, db, ctx):
        p = ctx.get("profile") or {}
        eng = p.get("engine_input") or {}
        flags = []
        rev = eng.get("revenue"); ocf = eng.get("operating_cash_flow")
        nm = eng.get("net_margin"); de = eng.get("debt_to_equity")
        if rev and ocf is not None and ocf < 0:
            flags.append("Negative operating cash flow against positive revenue")
        if nm is not None and nm < 0:
            flags.append("Reported net losses")
        if de is not None and de > 3:
            flags.append("Very high leverage (D/E > 3)")
        sig = "negative" if len(flags) >= 2 else ("caution" if flags else "positive")
        return {"facts": [{"label": "Red flags", "value": len(flags)}] +
                [{"label": f"Flag {i+1}", "value": f} for i, f in enumerate(flags)],
                "signal": sig, "confidence": 0.5 + 0.1 * len(flags) if flags else 0.55,
                "recommendation": ("Escalate to forensic review." if flags
                                   else "No structural fraud indicators in the financials."),
                "narrative": "Rule-based forensic screen over the financial inputs."}


class ComplianceOfficer(Agent):
    role, title = "compliance_officer", "Compliance Officer"
    persona = "You are a compliance officer checking policy conformance."
    keywords = ["compliance", "policy", "covenant", "conform", "kyc"]

    def gather(self, db, ctx):
        p = ctx.get("profile") or {}
        eng = p.get("engine_input") or {}
        cr = eng.get("current_ratio")
        breaches = []
        if cr is not None and cr < 1.2:
            breaches.append(f"Current ratio {cr} below policy minimum 1.2")
        cites = _rag_grounding(db, ctx, ["credit_policy"], ctx.get("goal", "credit policy requirements"))
        sig = "negative" if breaches else ("positive" if cites else "neutral")
        return {"facts": [{"label": "Policy breaches", "value": len(breaches)}] +
                [{"label": f"Breach {i+1}", "value": b} for i, b in enumerate(breaches)],
                "signal": sig, "confidence": 0.6 if (breaches or cites) else 0.4,
                "recommendation": ("Remediate policy breaches before approval." if breaches
                                   else "No policy breaches detected against indexed policy."),
                "citations": rag.build_citations(cites),
                "narrative": "Policy conformance checked against indexed credit policy."}


class PortfolioManager(Agent):
    role, title = "portfolio_manager", "Portfolio Manager"
    persona = "You are a portfolio manager assessing concentration and diversification."
    keywords = ["portfolio", "concentration", "diversification", "sector", "capital"]

    def gather(self, db, ctx):
        profiles = data_access.portfolio_profiles(db)
        p = ctx.get("profile") or {}
        total_el = sum((q.get("expected_loss") or 0) for q in profiles)
        same_sector = [q for q in profiles if q.get("industry") == p.get("industry")]
        conc = common.safe_div(len(same_sector), len(profiles)) if profiles else None
        facts = [{"label": "Portfolio positions", "value": len(profiles)},
                 {"label": "Total expected loss", "value": common.round_opt(total_el, 2)},
                 {"label": "Same-sector share", "value": common.round_opt(conc, 3)}]
        sig = "caution" if (conc or 0) > 0.4 else "positive"
        return {"facts": facts, "signal": sig, "confidence": 0.5,
                "recommendation": ("Watch sector concentration." if (conc or 0) > 0.4
                                   else "Exposure fits within diversification limits."),
                "narrative": "Portfolio context from latest per-company assessments."}


class RelationshipManager(Agent):
    role, title = "relationship_manager", "Relationship Manager"
    persona = "You are a relationship manager focused on the client relationship."
    keywords = ["relationship", "client", "cross-sell", "opportunity", "engagement"]

    def gather(self, db, ctx):
        p = ctx.get("profile") or {}
        facts = [{"label": "Company", "value": p.get("company_name")},
                 {"label": "Industry", "value": p.get("industry")},
                 {"label": "Years in business", "value": p.get("years_in_business")}]
        return {"facts": facts, "signal": "neutral", "confidence": 0.45,
                "recommendation": "Deepen the relationship with tailored facilities.",
                "narrative": "Relationship overview for engagement planning."}


class FinancialStatementExpert(Agent):
    role, title = "financial_statement_expert", "Financial Statement Expert"
    persona = "You are an expert in financial statement analysis and ratios."
    keywords = ["financial", "statement", "ratio", "balance sheet", "liquidity", "margin"]

    def gather(self, db, ctx):
        p = ctx.get("profile") or {}
        eng = p.get("engine_input") or {}
        facts = [{"label": k.replace("_", " ").title(), "value": eng.get(k)}
                 for k in ("revenue", "net_margin", "current_ratio", "debt_to_equity",
                           "operating_cash_flow") if k in eng]
        cr = eng.get("current_ratio"); de = eng.get("debt_to_equity")
        weak = ((cr is not None and cr < 1.0) or (de is not None and de > 2.5))
        sig = "negative" if weak else ("positive" if facts else "neutral")
        return {"facts": facts, "signal": sig, "confidence": 0.5 + 0.05 * len(facts),
                "recommendation": ("Liquidity/leverage concerns require attention." if weak
                                   else "Financial ratios are within acceptable bounds."),
                "narrative": "Ratio analysis of the submitted financials."}


class BankingPolicyExpert(Agent):
    role, title = "banking_policy_expert", "Banking Policy Expert"
    persona = "You are an expert on internal banking credit policy."
    keywords = ["policy", "internal", "guideline", "manual", "procedure"]

    def gather(self, db, ctx):
        cites = _rag_grounding(db, ctx, ["credit_policy", "external_manual"],
                               ctx.get("goal", "applicable credit policy"))
        return {"facts": [{"label": c["label"], "value": c["snippet"]} for c in cites],
                "signal": "positive" if cites else "neutral",
                "confidence": 0.6 if cites else 0.35,
                "recommendation": ("Apply the cited policy clauses." if cites
                                   else "No internal policy indexed for this query."),
                "citations": rag.build_citations(cites),
                "narrative": "Relevant internal policy retrieved from the knowledge base."}


class RegulatoryExpert(Agent):
    role, title = "regulatory_expert", "Regulatory Expert"
    persona = "You are a regulatory expert on RBI and Basel requirements."
    keywords = ["regulatory", "rbi", "basel", "npa", "provision", "regulation"]

    def gather(self, db, ctx):
        cites = _rag_grounding(db, ctx, ["rbi_circular", "basel_guideline"],
                               ctx.get("goal", "regulatory requirements"))
        return {"facts": [{"label": c["label"], "value": c["snippet"]} for c in cites],
                "signal": "positive" if cites else "neutral",
                "confidence": 0.6 if cites else 0.35,
                "recommendation": ("Ensure conformance with the cited regulations." if cites
                                   else "No regulatory circulars indexed for this query."),
                "citations": rag.build_citations(cites),
                "narrative": "Applicable regulatory guidance retrieved from the knowledge base."}


class Underwriter(Agent):
    role, title = "underwriter", "Underwriter"
    persona = "You are an underwriter structuring the facility and conditions."
    keywords = ["underwrite", "structure", "collateral", "tenor", "pricing", "facility"]

    def gather(self, db, ctx):
        p = ctx.get("profile") or {}
        facts = [{"label": "Recommended exposure", "value": p.get("exposure")},
                 {"label": "Indicative rate", "value": p.get("interest_rate")},
                 {"label": "Rating", "value": p.get("rating")}]
        sig = _score_signal(p)
        rec = ("Structure with standard covenants." if sig == "positive"
               else "Require additional collateral and tighter covenants."
               if sig in ("caution", "negative") else "Await complete financials.")
        return {"facts": facts, "signal": sig, "confidence": _conf_from_profile(p, 0.5),
                "recommendation": rec,
                "narrative": "Facility structuring based on rating and exposure."}


class DocumentSpecialist(Agent):
    role, title = "document_specialist", "Document Specialist"
    persona = "You are a document specialist verifying supporting evidence."
    keywords = ["document", "evidence", "annual report", "agreement", "statement", "verify"]

    def gather(self, db, ctx):
        cites = _rag_grounding(db, ctx, ["annual_report", "loan_agreement",
                                         "financial_statement", "ocr_document"],
                               ctx.get("goal", "supporting documents"))
        return {"facts": [{"label": c["label"], "value": c["snippet"]} for c in cites],
                "signal": "positive" if cites else "caution",
                "confidence": 0.55 if cites else 0.4,
                "recommendation": ("Documentary evidence located." if cites
                                   else "Request supporting documents for the file."),
                "citations": rag.build_citations(cites),
                "narrative": "Supporting documents retrieved from the knowledge base."}


# executive_advisor is synthesised by the coordinator (sees all contributions).
_AGENT_CLASSES: List[type] = [
    CreditAnalyst, RiskAnalyst, FraudInvestigator, ComplianceOfficer,
    PortfolioManager, RelationshipManager, FinancialStatementExpert,
    BankingPolicyExpert, RegulatoryExpert, Underwriter, DocumentSpecialist,
]
AGENTS: Dict[str, Agent] = {cls.role: cls() for cls in _AGENT_CLASSES}
ROLES: List[str] = list(AGENTS.keys()) + ["executive_advisor"]


def roster() -> List[Dict[str, str]]:
    out = [{"role": a.role, "title": a.title, "persona": a.persona} for a in AGENTS.values()]
    out.append({"role": "executive_advisor", "title": "Executive Advisor",
                "persona": "You are an executive advisor synthesising the committee."})
    return out


# ---------------------------------------------------------------------------
# Planner
# ---------------------------------------------------------------------------
def plan(goal: str, *, roles: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    """Select and order the specialist agents for a goal.

    If ``roles`` is given it is honoured; otherwise the planner scores each agent
    by keyword overlap with the goal and always includes the core credit/risk
    agents, ending with the executive advisor synthesis.
    """
    if roles:
        chosen = [r for r in roles if r in AGENTS]
    else:
        gk = set(common.keywords(goal))
        scored = []
        for a in AGENTS.values():
            overlap = len(gk & set(a.keywords))
            scored.append((overlap, a.role))
        core = {"credit_analyst", "risk_analyst"}
        chosen = sorted([r for s, r in scored if s > 0] , key=lambda r: r)
        chosen = list(dict.fromkeys(list(core) + chosen))
        if len(chosen) < 4:  # ensure a meaningful committee
            chosen = list(dict.fromkeys(chosen + ["compliance_officer",
                                                  "financial_statement_expert",
                                                  "underwriter"]))
    return [{"ordinal": i, "role": r, "title": AGENTS[r].title,
             "rationale": f"{AGENTS[r].title} contributes domain expertise to the goal."}
            for i, r in enumerate(chosen)]


# ---------------------------------------------------------------------------
# Reflection / critique
# ---------------------------------------------------------------------------
def _critique(contribution: Contribution) -> str:
    if contribution.status != "done":
        return "Step failed; excluded from consensus."
    if not contribution.facts:
        return "Low evidence: no grounded facts were available for this role."
    if contribution.confidence < 0.4:
        return "Low confidence: treat this contribution as indicative only."
    return "Grounded and consistent with the available evidence."


# ---------------------------------------------------------------------------
# Consensus / voting / conflict resolution
# ---------------------------------------------------------------------------
def _consensus(contribs: List[Contribution]) -> Dict[str, Any]:
    active = [c for c in contribs if c.status == "done"]
    total_w = sum(c.confidence for c in active) or 1.0
    weighted = sum(_SIGNAL_VOTE.get(c.signal, 0.0) * c.confidence for c in active)
    score = weighted / total_w
    tally: Dict[str, int] = {}
    for c in active:
        tally[c.signal] = tally.get(c.signal, 0) + 1
    if score >= 0.4:
        decision = "APPROVE"
    elif score <= -0.4:
        decision = "DECLINE"
    else:
        decision = "REVIEW"
    strong_pos = [c for c in active if c.signal == "positive" and c.confidence >= 0.5]
    strong_neg = [c for c in active if c.signal == "negative" and c.confidence >= 0.5]
    conflicts = []
    if strong_pos and strong_neg:
        conflicts.append({
            "type": "signal_conflict",
            "positive_roles": [c.role for c in strong_pos],
            "negative_roles": [c.role for c in strong_neg],
            "resolution": "Deferred to executive synthesis; overall confidence reduced.",
        })
    agreement = (max(tally.values()) / len(active)) if active else 0.0
    confidence = common.clamp(0.5 + 0.5 * abs(score)) * (0.7 if conflicts else 1.0)
    return {
        "decision": decision,
        "vote_score": common.round_opt(score, 4),
        "tally": tally,
        "agreement": common.round_opt(agreement, 3),
        "confidence": common.round_opt(confidence, 4),
        "conflicts": conflicts,
        "participants": len(active),
    }


# ---------------------------------------------------------------------------
# Coordinator
# ---------------------------------------------------------------------------
def _run_agent(agent: Agent, db: Session, ctx: Dict[str, Any], *, retries: int = 1) -> Contribution:
    attempt = 0
    last_err = None
    while attempt <= retries:
        try:
            c = agent.contribute(db, ctx)
            c.critique = _critique(c)
            return c
        except Exception as e:  # pragma: no cover - defensive retry path
            last_err = e
            attempt += 1
    return Contribution(role=agent.role, title=agent.title,
                        summary=f"Agent failed after {retries + 1} attempts: {last_err}",
                        signal="neutral", confidence=0.0, status="failed")


def run(db: Session, *, goal: str, company_ref: Optional[str] = None,
        assessment_id: Optional[int] = None, roles: Optional[List[str]] = None,
        mode: str = "plan_execute", parallel: bool = False,
        tenant_id: Optional[int] = None, provider: Optional[str] = None,
        created_by: Optional[str] = None, retries: int = 1) -> Dict[str, Any]:
    """Execute a multi-agent run and persist it with full step-level traceability."""
    assessment = data_access.resolve(db, assessment_id=assessment_id, company_ref=company_ref)
    profile = data_access.profile(assessment)
    ctx = {"goal": goal, "company_ref": company_ref or (profile or {}).get("company_ref"),
           "assessment_id": assessment_id or (profile or {}).get("assessment_id"),
           "profile": profile, "tenant_id": tenant_id, "provider": provider}
    steps_plan = plan(goal, roles=roles)
    agents = [AGENTS[s["role"]] for s in steps_plan]

    if parallel and len(agents) > 1:
        with ThreadPoolExecutor(max_workers=min(6, len(agents))) as ex:
            contribs = list(ex.map(lambda a: _run_agent(a, db, ctx, retries=retries), agents))
    else:
        contribs = [_run_agent(a, db, ctx, retries=retries) for a in agents]

    consensus = _consensus(contribs)

    # Executive advisor synthesis (sees everything).
    exec_grounding = {
        "headline": f"Committee synthesis: {common.truncate(goal, 120)}",
        "narrative": f"Decision {consensus['decision']} with "
                     f"{consensus['participants']} specialists "
                     f"(agreement {consensus['agreement']}).",
        "facts": [{"label": c.title, "value": f"{c.signal} — {common.truncate(c.recommendation, 80)}"}
                  for c in contribs],
        "recommended_actions": [c.recommendation for c in contribs if c.recommendation][:5],
    }
    exec_text = llm_mod.get_llm(provider).generate(
        prompt=f"Synthesise the committee's view on: {goal}",
        system="You are an executive advisor synthesising a credit committee.",
        grounding=exec_grounding).text

    run_row = AIPAgentRun(
        tenant_id=tenant_id, goal=goal, company_ref=ctx["company_ref"],
        assessment_id=ctx["assessment_id"], mode=mode, status="completed",
        roles=[s["role"] for s in steps_plan], plan=steps_plan,
        result={"decision": consensus["decision"],
                "executive_summary": exec_text,
                "contributions": [c.as_dict() for c in contribs]},
        consensus=consensus, confidence=consensus["confidence"],
        provider=llm_mod.get_llm(provider).name, created_by=created_by,
        created_at=common.utcnow(), completed_at=common.utcnow(),
    )
    db.add(run_row)
    db.commit()
    db.refresh(run_row)

    for i, c in enumerate(contribs):
        db.add(AIPAgentStep(
            run_id=run_row.id, ordinal=i, role=c.role, action="contribute",
            input={"goal": goal}, output=c.summary, critique=c.critique,
            score=c.confidence, status=c.status, created_at=common.utcnow()))
    db.commit()

    return {
        "run_id": run_row.id, "goal": goal, "mode": mode,
        "company_ref": ctx["company_ref"], "assessment_id": ctx["assessment_id"],
        "plan": steps_plan, "decision": consensus["decision"],
        "executive_summary": exec_text, "consensus": consensus,
        "contributions": [c.as_dict() for c in contribs],
        "provider": run_row.provider, "confidence": consensus["confidence"],
    }


def get_run(db: Session, run_id: int) -> Optional[Dict[str, Any]]:
    r = db.query(AIPAgentRun).filter(AIPAgentRun.id == run_id).first()
    if not r:
        return None
    steps = (db.query(AIPAgentStep).filter(AIPAgentStep.run_id == r.id)
             .order_by(AIPAgentStep.ordinal).all())
    return {
        "run_id": r.id, "goal": r.goal, "mode": r.mode, "status": r.status,
        "decision": (r.result or {}).get("decision"),
        "executive_summary": (r.result or {}).get("executive_summary"),
        "consensus": r.consensus, "plan": r.plan, "confidence": r.confidence,
        "contributions": (r.result or {}).get("contributions", []),
        "steps": [{"ordinal": s.ordinal, "role": s.role, "status": s.status,
                   "critique": s.critique, "score": s.score} for s in steps],
        "created_at": common.iso(r.created_at),
    }


def list_runs(db: Session, *, tenant_id: Optional[int] = None, limit: int = 50) -> List[Dict[str, Any]]:
    q = db.query(AIPAgentRun).filter(AIPAgentRun.tenant_id == tenant_id)
    return [{"run_id": r.id, "goal": r.goal, "decision": (r.result or {}).get("decision"),
             "confidence": r.confidence, "created_at": common.iso(r.created_at)}
            for r in q.order_by(AIPAgentRun.id.desc()).limit(limit).all()]
