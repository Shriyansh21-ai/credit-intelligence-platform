"""Autonomous AI Banking Intelligence Platform APIs (Phase 9).

Focused, additive routers exposing the whole "AI Brain" under ``/api/ai/*``.
Every route is new; no existing route is modified. RBAC is enforced with the
Phase 9 permission catalog (``intelligence.*``, ``copilot.use``, ``simulation.run``,
``portfolio.optimize``, ``rm.workspace``, ``command.center``, ``recommendations.*``,
``governance.*``, ``datalake.*``).

    /api/ai/graph            knowledge graph (M1)
    /api/ai/monitoring       real-time monitoring (M2)
    /api/ai/ews              early-warning signals (M3)
    /api/ai/alerts           unified intelligence alerts (M2/3/11)
    /api/ai/copilot          AI Credit Copilot (M4)
    /api/ai/simulation       scenario simulation (M5)
    /api/ai/stress           stress testing (M6)
    /api/ai/portfolio        portfolio optimization (M7)
    /api/ai/rm               relationship-manager workspace (M8)
    /api/ai/command          executive command center (M9)
    /api/ai/nlq              natural-language analytics (M10)
    /api/ai/recommendations  recommendation engine (M11)
    /api/ai/workflow         autonomous workflow intelligence (M12)
    /api/ai/governance       model governance (M13)
    /api/ai/datalake         enterprise data lake (M14)
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.app.core.dependencies import get_current_user
from backend.app.db.database import get_db
from backend.app.models.user import User
from backend.app.schemas.autonomous import (
    AlertStatusUpdate, CopilotAsk, DataLakeAggregate, DataLakeIngest, EntityCreate,
    EWSRequest, GovernanceApprove, GraphIngest, GraphSeed, InteractionCreate,
    MonitoringRun, NLQueryRequest, OpportunityCreate, OptimizationRequest,
    RecommendRequest, RecommendationStatusUpdate, RelationshipCreate,
    SimulationRequest, StressRequest, ValidateRequest, WorkflowRunRequest,
)
from backend.app.services.rbac import require_permission
from backend.app.services.autonomous import (
    alerts as alerts_svc, command, copilot, data_access, datalake, ews as ews_svc,
    governance, graph, llm, monitoring, nlq, optimization, recommendations, rm,
    simulation, stress, workflow,
)


def _tenant(explicit: Optional[int] = None) -> Optional[int]:
    """Resolve tenant scope (best-effort). Legacy single-tenant flows use None."""
    if explicit is not None:
        return explicit
    try:
        from backend.app.services.saas import context as tenant_ctx
        return tenant_ctx.current_tenant_id()
    except Exception:
        return None


def _bad(exc: Exception):
    raise HTTPException(status_code=400, detail=str(exc))


# ===========================================================================
# M1 — Knowledge Graph
# ===========================================================================
graph_router = APIRouter(prefix="/api/ai/graph", tags=["AI: Knowledge Graph"])


@graph_router.get("/entities")
def list_entities(entity_type: Optional[str] = None, tenant_id: Optional[int] = None,
                  db: Session = Depends(get_db), _u=Depends(require_permission("intelligence.view"))):
    return [{"id": e.id, "entity_type": e.entity_type, "ref": e.ref, "name": e.name,
             "risk_score": e.risk_score, "attributes": e.attributes}
            for e in graph.list_entities(db, tenant_id=_tenant(tenant_id), entity_type=entity_type)]


@graph_router.post("/entities")
def create_entity(body: EntityCreate, tenant_id: Optional[int] = None, db: Session = Depends(get_db),
                  _u=Depends(require_permission("intelligence.manage"))):
    try:
        e = graph.upsert_entity(db, entity_type=body.entity_type, ref=body.ref, name=body.name,
                                tenant_id=_tenant(tenant_id), attributes=body.attributes,
                                risk_score=body.risk_score)
    except ValueError as ex:
        _bad(ex)
    return {"id": e.id, "ref": e.ref, "entity_type": e.entity_type}


@graph_router.post("/relationships")
def create_relationship(body: RelationshipCreate, tenant_id: Optional[int] = None,
                        db: Session = Depends(get_db), _u=Depends(require_permission("intelligence.manage"))):
    src = graph.get_entity(db, body.source_id)
    tgt = graph.get_entity(db, body.target_id)
    if src is None or tgt is None:
        raise HTTPException(status_code=404, detail="source/target entity not found")
    r = graph.add_relationship(db, src, tgt, body.rel_type, strength=body.strength,
                               exposure=body.exposure, attributes=body.attributes,
                               tenant_id=_tenant(tenant_id))
    return {"id": r.id, "rel_type": r.rel_type, "strength": r.strength}


@graph_router.get("/entities/{entity_id}/connected")
def connected(entity_id: int, max_depth: int = 2, tenant_id: Optional[int] = None,
              db: Session = Depends(get_db), _u=Depends(require_permission("intelligence.view"))):
    return {"connected": graph.connected_entities(db, entity_id, max_depth=max_depth,
                                                   tenant_id=_tenant(tenant_id))}


@graph_router.get("/entities/{entity_id}/exposure")
def exposure(entity_id: int, max_depth: int = 2, tenant_id: Optional[int] = None,
             db: Session = Depends(get_db), _u=Depends(require_permission("intelligence.view"))):
    return graph.connected_exposure(db, entity_id, max_depth=max_depth, tenant_id=_tenant(tenant_id))


@graph_router.get("/entities/{entity_id}/similar")
def similar(entity_id: int, top_k: int = 10, tenant_id: Optional[int] = None,
            db: Session = Depends(get_db), _u=Depends(require_permission("intelligence.view"))):
    return {"similar": graph.entity_similarity(db, entity_id, tenant_id=_tenant(tenant_id), top_k=top_k)}


@graph_router.get("/relationship-score")
def rel_score(source_id: int, target_id: int, tenant_id: Optional[int] = None,
              db: Session = Depends(get_db), _u=Depends(require_permission("intelligence.view"))):
    return graph.relationship_score(db, source_id, target_id, tenant_id=_tenant(tenant_id))


@graph_router.get("/network")
def network(root_id: Optional[int] = None, max_depth: int = 2, tenant_id: Optional[int] = None,
            db: Session = Depends(get_db), _u=Depends(require_permission("intelligence.view"))):
    return graph.network(db, root_id=root_id, max_depth=max_depth, tenant_id=_tenant(tenant_id))


@graph_router.get("/stats")
def graph_stats(tenant_id: Optional[int] = None, db: Session = Depends(get_db),
                _u=Depends(require_permission("intelligence.view"))):
    return graph.stats(db, tenant_id=_tenant(tenant_id))


@graph_router.post("/propagate-risk")
def propagate(tenant_id: Optional[int] = None, iterations: int = 3, db: Session = Depends(get_db),
              _u=Depends(require_permission("intelligence.manage"))):
    result = graph.propagate_risk(db, tenant_id=_tenant(tenant_id), iterations=iterations)
    return {"propagated": len(result)}


@graph_router.post("/ingest")
def ingest_network(body: GraphIngest, tenant_id: Optional[int] = None, db: Session = Depends(get_db),
                   _u=Depends(require_permission("intelligence.manage"))):
    return graph.ingest_network(db, body.company_ref, body.relationships, tenant_id=_tenant(tenant_id))


@graph_router.post("/seed")
def seed(body: GraphSeed, tenant_id: Optional[int] = None, db: Session = Depends(get_db),
         _u=Depends(require_permission("intelligence.manage"))):
    a = data_access.resolve(db, assessment_id=body.assessment_id, company_ref=body.company_ref)
    if a is None:
        raise HTTPException(status_code=404, detail="assessment not found")
    e = graph.seed_from_assessment(db, a, tenant_id=_tenant(tenant_id))
    return {"id": e.id, "ref": e.ref}


# ===========================================================================
# M2 — Monitoring
# ===========================================================================
monitoring_router = APIRouter(prefix="/api/ai/monitoring", tags=["AI: Monitoring"])


@monitoring_router.post("/run")
def run_monitoring(body: MonitoringRun, tenant_id: Optional[int] = None, db: Session = Depends(get_db),
                   _u=Depends(require_permission("intelligence.manage"))):
    return monitoring.run_monitoring(db, body.company_ref, body.observations,
                                     assessment_id=body.assessment_id, tenant_id=_tenant(tenant_id),
                                     exposure=body.exposure, escalate=body.escalate)


@monitoring_router.get("/signals")
def signals(company_ref: Optional[str] = None, source: Optional[str] = None,
            tenant_id: Optional[int] = None, limit: int = 100, db: Session = Depends(get_db),
            _u=Depends(require_permission("intelligence.view"))):
    return {"signals": [monitoring._signal_dict(s) for s in
                        monitoring.recent_signals(db, company_ref=company_ref, source=source,
                                                  tenant_id=_tenant(tenant_id), limit=limit)]}


@monitoring_router.get("/sources")
def sources(_u=Depends(require_permission("intelligence.view"))):
    return {"sources": monitoring.MONITORING_SOURCES}


# ===========================================================================
# M3 — Early Warning
# ===========================================================================
ews_router = APIRouter(prefix="/api/ai/ews", tags=["AI: Early Warning"])


@ews_router.post("/evaluate")
def evaluate(body: EWSRequest, tenant_id: Optional[int] = None, db: Session = Depends(get_db),
             _u=Depends(require_permission("intelligence.view"))):
    return ews_svc.evaluate(db, company_ref=body.company_ref, assessment_id=body.assessment_id,
                            context=body.context, tenant_id=_tenant(tenant_id), persist=body.persist)


@ews_router.get("/catalog")
def catalog(_u=Depends(require_permission("intelligence.view"))):
    return {"signals": ews_svc.EWS_CATALOG}


@ews_router.get("/history")
def ews_history(company_ref: str, tenant_id: Optional[int] = None, db: Session = Depends(get_db),
                _u=Depends(require_permission("intelligence.view"))):
    return {"history": [{"id": r.id, "ews_score": r.ews_score, "ews_band": r.ews_band,
                         "signal_count": r.signal_count, "summary": r.summary,
                         "created_at": r.created_at.isoformat() if r.created_at else None}
                        for r in ews_svc.history(db, company_ref, tenant_id=_tenant(tenant_id))]}


# ===========================================================================
# Unified alerts
# ===========================================================================
alerts_router = APIRouter(prefix="/api/ai/alerts", tags=["AI: Alerts"])


@alerts_router.get("")
def list_alerts(category: Optional[str] = None, company_ref: Optional[str] = None,
                status: Optional[str] = None, severity: Optional[str] = None,
                tenant_id: Optional[int] = None, limit: int = 100, db: Session = Depends(get_db),
                _u=Depends(require_permission("intelligence.view"))):
    return {"alerts": [alerts_svc.as_dict(a) for a in
                       alerts_svc.list_alerts(db, tenant_id=_tenant(tenant_id), category=category,
                                              company_ref=company_ref, status=status,
                                              severity=severity, limit=limit)]}


@alerts_router.get("/summary")
def alerts_summary(tenant_id: Optional[int] = None, db: Session = Depends(get_db),
                   _u=Depends(require_permission("intelligence.view"))):
    return alerts_svc.summary(db, tenant_id=_tenant(tenant_id))


@alerts_router.patch("/{alert_id}")
def update_alert(alert_id: int, body: AlertStatusUpdate, db: Session = Depends(get_db),
                 _u=Depends(require_permission("intelligence.manage"))):
    try:
        a = alerts_svc.set_status(db, alert_id, body.status)
    except ValueError as ex:
        _bad(ex)
    return alerts_svc.as_dict(a)


# ===========================================================================
# M4 — Copilot
# ===========================================================================
copilot_router = APIRouter(prefix="/api/ai/copilot", tags=["AI: Copilot"])


@copilot_router.post("/ask")
def ask(body: CopilotAsk, tenant_id: Optional[int] = None, db: Session = Depends(get_db),
        user: User = Depends(require_permission("copilot.use"))):
    return copilot.ask(db, body.question, conversation_id=body.conversation_id,
                       company_ref=body.company_ref, assessment_id=body.assessment_id,
                       user_id=getattr(user, "id", None), tenant_id=_tenant(tenant_id),
                       provider=body.provider)


@copilot_router.get("/conversations")
def conversations(tenant_id: Optional[int] = None, db: Session = Depends(get_db),
                  user: User = Depends(require_permission("copilot.use"))):
    return {"conversations": [{"id": c.id, "title": c.title, "context_ref": c.context_ref,
                               "updated_at": c.updated_at.isoformat() if c.updated_at else None}
                              for c in copilot.list_conversations(db, user_id=getattr(user, "id", None),
                                                                  tenant_id=_tenant(tenant_id))]}


@copilot_router.get("/conversations/{conversation_id}/messages")
def messages(conversation_id: int, db: Session = Depends(get_db),
             _u=Depends(require_permission("copilot.use"))):
    return {"messages": [{"id": m.id, "role": m.role, "content": m.content, "intent": m.intent,
                          "provider": m.provider, "citations": m.citations,
                          "created_at": m.created_at.isoformat() if m.created_at else None}
                         for m in copilot.get_messages(db, conversation_id)]}


@copilot_router.get("/provider")
def provider_status(_u=Depends(require_permission("copilot.use"))):
    return llm.provider_status()


# ===========================================================================
# M5 — Simulation
# ===========================================================================
simulation_router = APIRouter(prefix="/api/ai/simulation", tags=["AI: Simulation"])


@simulation_router.get("/scenarios")
def scenarios(_u=Depends(require_permission("simulation.run"))):
    return {"scenarios": simulation.available_scenarios()}


@simulation_router.post("/run")
def simulate(body: SimulationRequest, tenant_id: Optional[int] = None, db: Session = Depends(get_db),
             user: User = Depends(require_permission("simulation.run"))):
    return simulation.simulate(db, body.shocks, company_ref=body.company_ref,
                               assessment_id=body.assessment_id, user_id=getattr(user, "id", None),
                               tenant_id=_tenant(tenant_id), persist=body.persist)


@simulation_router.get("/runs")
def sim_runs(company_ref: Optional[str] = None, tenant_id: Optional[int] = None,
             db: Session = Depends(get_db), _u=Depends(require_permission("simulation.run"))):
    return {"runs": [{"id": r.id, "company_ref": r.company_ref, "scenario_types": r.scenario_types,
                      "delta": r.delta, "created_at": r.created_at.isoformat() if r.created_at else None}
                     for r in simulation.list_runs(db, company_ref=company_ref, tenant_id=_tenant(tenant_id))]}


# ===========================================================================
# M6 — Stress testing
# ===========================================================================
stress_router = APIRouter(prefix="/api/ai/stress", tags=["AI: Stress Testing"])


@stress_router.get("/scenarios")
def stress_scenarios(_u=Depends(require_permission("simulation.run"))):
    return {"scenarios": list(stress.STRESS_SCENARIOS.keys()) + ["custom"],
            "definitions": stress.STRESS_SCENARIOS}


@stress_router.post("/run")
def run_stress(body: StressRequest, tenant_id: Optional[int] = None, db: Session = Depends(get_db),
               user: User = Depends(require_permission("simulation.run"))):
    return stress.run(db, scenario=body.scenario, scope=body.scope, scope_ref=body.scope_ref,
                      custom_shocks=body.custom_shocks, user_id=getattr(user, "id", None),
                      tenant_id=_tenant(tenant_id), persist=body.persist)


@stress_router.get("/compare")
def compare(scope: str = "portfolio", scope_ref: Optional[str] = None, tenant_id: Optional[int] = None,
            db: Session = Depends(get_db), _u=Depends(require_permission("simulation.run"))):
    return stress.compare_scenarios(db, scope=scope, scope_ref=scope_ref, tenant_id=_tenant(tenant_id))


@stress_router.get("/runs")
def stress_runs(tenant_id: Optional[int] = None, db: Session = Depends(get_db),
                _u=Depends(require_permission("simulation.run"))):
    return {"runs": [{"id": r.id, "scenario": r.scenario, "scope": r.scope,
                      "positions": r.positions, "result": r.result.get("expected_loss") if r.result else None,
                      "created_at": r.created_at.isoformat() if r.created_at else None}
                     for r in stress.list_runs(db, tenant_id=_tenant(tenant_id))]}


# ===========================================================================
# M7 — Portfolio optimization
# ===========================================================================
portfolio_router = APIRouter(prefix="/api/ai/portfolio", tags=["AI: Portfolio Optimization"])


@portfolio_router.post("/optimize")
def optimize(body: OptimizationRequest, tenant_id: Optional[int] = None, db: Session = Depends(get_db),
             user: User = Depends(require_permission("portfolio.optimize"))):
    return optimization.analyze(db, objective=body.objective, constraints=body.constraints,
                                tenant_id=_tenant(tenant_id), user_id=getattr(user, "id", None),
                                persist=body.persist)


@portfolio_router.get("/analysis")
def analysis(tenant_id: Optional[int] = None, db: Session = Depends(get_db),
             _u=Depends(require_permission("portfolio.optimize"))):
    return optimization.analyze(db, tenant_id=_tenant(tenant_id), persist=False)


# ===========================================================================
# M8 — RM workspace
# ===========================================================================
rm_router = APIRouter(prefix="/api/ai/rm", tags=["AI: RM Workspace"])


@rm_router.get("/workspace/{company_ref}")
def rm_workspace(company_ref: str, tenant_id: Optional[int] = None, db: Session = Depends(get_db),
                 _u=Depends(require_permission("rm.workspace"))):
    return rm.workspace(db, company_ref, tenant_id=_tenant(tenant_id))


@rm_router.post("/interactions")
def add_interaction(body: InteractionCreate, tenant_id: Optional[int] = None, db: Session = Depends(get_db),
                    user: User = Depends(require_permission("rm.workspace"))):
    try:
        i = rm.log_interaction(db, body.company_ref, body.interaction_type, subject=body.subject,
                               detail=body.detail, outcome=body.outcome,
                               rm_user_id=getattr(user, "id", None), payload=body.payload,
                               tenant_id=_tenant(tenant_id))
    except ValueError as ex:
        _bad(ex)
    return {"id": i.id, "interaction_type": i.interaction_type}


@rm_router.get("/interactions/{company_ref}")
def list_interactions(company_ref: str, tenant_id: Optional[int] = None, db: Session = Depends(get_db),
                      _u=Depends(require_permission("rm.workspace"))):
    return {"interactions": [{"id": i.id, "type": i.interaction_type, "subject": i.subject,
                              "detail": i.detail, "outcome": i.outcome,
                              "occurred_at": i.occurred_at.isoformat() if i.occurred_at else None}
                             for i in rm.list_interactions(db, company_ref, tenant_id=_tenant(tenant_id))]}


@rm_router.post("/opportunities")
def add_opportunity(body: OpportunityCreate, tenant_id: Optional[int] = None, db: Session = Depends(get_db),
                    _u=Depends(require_permission("rm.workspace"))):
    o = rm.add_opportunity(db, body.company_ref, body.product, rationale=body.rationale,
                           estimated_value=body.estimated_value, confidence=body.confidence,
                           tenant_id=_tenant(tenant_id))
    return {"id": o.id, "product": o.product}


@rm_router.get("/opportunities/{company_ref}")
def list_opportunities(company_ref: str, tenant_id: Optional[int] = None, db: Session = Depends(get_db),
                       _u=Depends(require_permission("rm.workspace"))):
    return {"identified": rm.identify_opportunities(db, company_ref, tenant_id=_tenant(tenant_id)),
            "tracked": [{"id": o.id, "product": o.product, "status": o.status,
                         "estimated_value": o.estimated_value}
                        for o in rm.list_opportunities(db, company_ref, tenant_id=_tenant(tenant_id))]}


@rm_router.get("/health/{company_ref}")
def rm_health(company_ref: str, tenant_id: Optional[int] = None, db: Session = Depends(get_db),
              _u=Depends(require_permission("rm.workspace"))):
    return rm.customer_health(db, company_ref, tenant_id=_tenant(tenant_id))


# ===========================================================================
# M9 — Command center
# ===========================================================================
command_router = APIRouter(prefix="/api/ai/command", tags=["AI: Command Center"])


@command_router.get("/dashboard/{persona}")
def command_dashboard(persona: str, region: Optional[str] = None, tenant_id: Optional[int] = None,
                      db: Session = Depends(get_db), _u=Depends(require_permission("command.center"))):
    try:
        return command.dashboard(db, persona, tenant_id=_tenant(tenant_id), region=region)
    except ValueError as ex:
        _bad(ex)


@command_router.get("/personas")
def personas(_u=Depends(require_permission("command.center"))):
    return {"personas": ["ceo", "chief_risk_officer", "chief_credit_officer", "board", "regional_head"]}


@command_router.get("/kpis")
def kpis(tenant_id: Optional[int] = None, db: Session = Depends(get_db),
         _u=Depends(require_permission("command.center"))):
    return command.portfolio_kpis(db, tenant_id=_tenant(tenant_id))


# ===========================================================================
# M10 — NL analytics
# ===========================================================================
nlq_router = APIRouter(prefix="/api/ai/nlq", tags=["AI: NL Analytics"])


@nlq_router.post("/query")
def nlq_query(body: NLQueryRequest, tenant_id: Optional[int] = None, db: Session = Depends(get_db),
              user: User = Depends(require_permission("copilot.use"))):
    return nlq.query(db, body.question, user_id=getattr(user, "id", None),
                     tenant_id=_tenant(tenant_id), persist=body.persist)


@nlq_router.get("/history")
def nlq_history(tenant_id: Optional[int] = None, db: Session = Depends(get_db),
                user: User = Depends(require_permission("copilot.use"))):
    return {"history": [{"id": r.id, "question": r.question, "intent": r.intent,
                         "result_count": r.result_count, "confidence": r.confidence,
                         "created_at": r.created_at.isoformat() if r.created_at else None}
                        for r in nlq.history(db, user_id=getattr(user, "id", None),
                                             tenant_id=_tenant(tenant_id))]}


# ===========================================================================
# M11 — Recommendations
# ===========================================================================
rec_router = APIRouter(prefix="/api/ai/recommendations", tags=["AI: Recommendations"])


@rec_router.post("/generate")
def generate(body: RecommendRequest, tenant_id: Optional[int] = None, db: Session = Depends(get_db),
             _u=Depends(require_permission("recommendations.view"))):
    return recommendations.recommend(db, company_ref=body.company_ref, assessment_id=body.assessment_id,
                                     context=body.context, tenant_id=_tenant(tenant_id),
                                     persist=body.persist)


@rec_router.get("")
def list_recs(company_ref: Optional[str] = None, action: Optional[str] = None,
              status: Optional[str] = None, tenant_id: Optional[int] = None,
              db: Session = Depends(get_db), _u=Depends(require_permission("recommendations.view"))):
    return {"recommendations": [recommendations.as_dict(r) for r in
                                recommendations.list_recommendations(db, company_ref=company_ref,
                                                                     action=action, status=status,
                                                                     tenant_id=_tenant(tenant_id))]}


@rec_router.patch("/{rec_id}")
def update_rec(rec_id: int, body: RecommendationStatusUpdate, db: Session = Depends(get_db),
               _u=Depends(require_permission("recommendations.act"))):
    try:
        r = recommendations.set_status(db, rec_id, body.status)
    except ValueError as ex:
        _bad(ex)
    return recommendations.as_dict(r)


# ===========================================================================
# M12 — Workflow intelligence
# ===========================================================================
workflow_router = APIRouter(prefix="/api/ai/workflow", tags=["AI: Workflow Intelligence"])


@workflow_router.post("/plan")
def wf_plan(body: WorkflowRunRequest, tenant_id: Optional[int] = None, db: Session = Depends(get_db),
            _u=Depends(require_permission("recommendations.view"))):
    return {"actions": workflow.plan(db, company_ref=body.company_ref,
                                     assessment_id=body.assessment_id, tenant_id=_tenant(tenant_id))}


@workflow_router.post("/run")
def wf_run(body: WorkflowRunRequest, tenant_id: Optional[int] = None, db: Session = Depends(get_db),
           user: User = Depends(require_permission("recommendations.act"))):
    try:
        return workflow.run(db, company_ref=body.company_ref, assessment_id=body.assessment_id,
                            mode=body.mode, tenant_id=_tenant(tenant_id),
                            actor_user_id=getattr(user, "id", None))
    except ValueError as ex:
        _bad(ex)


@workflow_router.get("/actions")
def wf_actions(company_ref: Optional[str] = None, status: Optional[str] = None,
               tenant_id: Optional[int] = None, db: Session = Depends(get_db),
               _u=Depends(require_permission("recommendations.view"))):
    return {"actions": [workflow.as_dict(a) for a in
                        workflow.list_actions(db, company_ref=company_ref, status=status,
                                              tenant_id=_tenant(tenant_id))]}


# ===========================================================================
# M13 — Model governance
# ===========================================================================
governance_router = APIRouter(prefix="/api/ai/governance", tags=["AI: Model Governance"])


@governance_router.get("/dashboard")
def gov_dashboard(db: Session = Depends(get_db), _u=Depends(require_permission("governance.view"))):
    return governance.governance_dashboard(db)


@governance_router.post("/models/{model_id}/validate")
def gov_validate(model_id: int, body: ValidateRequest, db: Session = Depends(get_db),
                 user: User = Depends(require_permission("governance.manage"))):
    try:
        return governance.validate_model(db, model_id, validator=getattr(user, "email", None),
                                         thresholds=body.thresholds)
    except ValueError as ex:
        _bad(ex)


@governance_router.post("/models/{model_id}/approve")
def gov_approve(model_id: int, body: GovernanceApprove, db: Session = Depends(get_db),
                user: User = Depends(require_permission("governance.manage"))):
    try:
        return governance.approve_with_governance(db, model_id, actor=getattr(user, "email", None),
                                                  require_validation=body.require_validation)
    except ValueError as ex:
        _bad(ex)


@governance_router.post("/models/{model_id}/promote")
def gov_promote(model_id: int, db: Session = Depends(get_db),
                user: User = Depends(require_permission("governance.manage"))):
    try:
        return governance.promote_with_governance(db, model_id, actor=getattr(user, "email", None))
    except ValueError as ex:
        _bad(ex)


@governance_router.post("/models/{model_key}/rollback")
def gov_rollback(model_key: str, db: Session = Depends(get_db),
                 user: User = Depends(require_permission("governance.manage"))):
    try:
        return governance.rollback_with_governance(db, model_key, actor=getattr(user, "email", None))
    except ValueError as ex:
        _bad(ex)


@governance_router.get("/models/{model_key}/champion-challenger")
def gov_cc(model_key: str, db: Session = Depends(get_db),
           _u=Depends(require_permission("governance.view"))):
    return governance.champion_challenger(db, model_key)


@governance_router.get("/models/{model_key}/lineage")
def gov_lineage(model_key: str, db: Session = Depends(get_db),
                _u=Depends(require_permission("governance.view"))):
    return governance.model_lineage(db, model_key)


# ===========================================================================
# M14 — Data lake
# ===========================================================================
datalake_router = APIRouter(prefix="/api/ai/datalake", tags=["AI: Data Lake"])


@datalake_router.get("/catalog")
def dl_catalog(tenant_id: Optional[int] = None, db: Session = Depends(get_db),
               _u=Depends(require_permission("datalake.view"))):
    return {"datasets": datalake.catalog(db, tenant_id=_tenant(tenant_id)),
            "namespaces": datalake.NAMESPACES}


@datalake_router.get("/stats")
def dl_stats(tenant_id: Optional[int] = None, db: Session = Depends(get_db),
             _u=Depends(require_permission("datalake.view"))):
    return datalake.stats(db, tenant_id=_tenant(tenant_id))


@datalake_router.post("/ingest")
def dl_ingest(body: DataLakeIngest, tenant_id: Optional[int] = None, db: Session = Depends(get_db),
              _u=Depends(require_permission("datalake.manage"))):
    return datalake.ingest(db, body.namespace, body.content, partition=body.partition,
                           entity_ref=body.entity_ref, tenant_id=_tenant(tenant_id))


@datalake_router.post("/run-ingestion/{namespace}")
def dl_run_ingestion(namespace: str, tenant_id: Optional[int] = None, db: Session = Depends(get_db),
                     _u=Depends(require_permission("datalake.manage"))):
    try:
        return datalake.run_ingestion(db, namespace, tenant_id=_tenant(tenant_id))
    except ValueError as ex:
        _bad(ex)


@datalake_router.post("/run-ingestion")
def dl_run_all(tenant_id: Optional[int] = None, db: Session = Depends(get_db),
               _u=Depends(require_permission("datalake.manage"))):
    return datalake.run_all_ingestion(db, tenant_id=_tenant(tenant_id))


@datalake_router.get("/query/{namespace}")
def dl_query(namespace: str, partition: Optional[str] = None, entity_ref: Optional[str] = None,
             tenant_id: Optional[int] = None, limit: int = 200, db: Session = Depends(get_db),
             _u=Depends(require_permission("datalake.view"))):
    return {"records": datalake.query(db, namespace, partition=partition, entity_ref=entity_ref,
                                      tenant_id=_tenant(tenant_id), limit=limit)}


@datalake_router.post("/aggregate")
def dl_aggregate(body: DataLakeAggregate, tenant_id: Optional[int] = None, db: Session = Depends(get_db),
                 _u=Depends(require_permission("datalake.view"))):
    return datalake.aggregate(db, body.namespace, group_by=body.group_by, metric=body.metric,
                              agg=body.agg, tenant_id=_tenant(tenant_id))


ROUTERS = [
    graph_router, monitoring_router, ews_router, alerts_router, copilot_router,
    simulation_router, stress_router, portfolio_router, rm_router, command_router,
    nlq_router, rec_router, workflow_router, governance_router, datalake_router,
]
