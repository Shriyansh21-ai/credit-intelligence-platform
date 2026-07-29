"""AI Intelligence Platform APIs (Track 2).

Additive routers exposing the whole AI layer under ``/api/aip/*``. Every route is
new; no existing route is modified. RBAC is enforced with the Track 2 permission
catalog (``aip.*``). Routers are collected into ``ROUTERS`` and mounted in
``main.py``; each milestone appends its router here.

    /api/aip/rag            enterprise RAG platform (M1)
    /api/aip/agents         multi-agent AI system (M2)
    /api/aip/memory         long-term memory (M3)
    /api/aip/prompts        prompt engineering platform (M4)
    /api/aip/eval           AI evaluation framework (M5)
    /api/aip/investigate    autonomous investigation (M6)
    /api/aip/reports        AI report generation (M7)
    /api/aip/workflows      AI workflow builder (M8)
    /api/aip/chat           enterprise conversational AI (M9)
    /api/aip/research       AI research assistant (M10)
    /api/aip/learning       continuous learning (M11)
    /api/aip/governance     AI governance (M12)
    /api/aip/explain        explainable enterprise AI (M13)
    /api/aip/monitoring     AI monitoring (M14)
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.app.core.dependencies import get_current_user
from backend.app.db.database import get_db
from backend.app.models.user import User
from backend.app.services.rbac import require_permission
from backend.app.schemas.ai_platform import (
    AgentRunRequest, DocumentIngest, ExperimentResult, ExperimentStart,
    MemoryForget, MemoryLink, MemoryRecall, MemorySummarize, MemoryWrite,
    EvalCaseCreate, EvaluateRequest, InvestigateRequest, PlanRequest, PromptApprove,
    PromptCreate, PromptDeploy, PromptEvalRequest, PromptRender, PromptVersionCreate,
    AssetRegister, AssetTransition, ChatAsk, ConversationCreate, ExplainRequest,
    FeedbackCreate, MetricRecord, RagAnswer, RagSearch, ReportRequest, ResearchRequest,
    SignalCreate, SourceCreate, TrainingEventUpdate, TriggerRequest, WorkflowRunRequest,
    WorkflowSave,
)
from backend.app.services.ai_platform import (
    agents as agents_svc, ai_monitoring as monitoring_svc, chat as chat_svc,
    evaluation as eval_svc, explainability as explain_svc, governance as governance_svc,
    investigation as investigation_svc, learning as learning_svc, memory as memory_svc,
    prompts as prompts_svc, rag, reports as reports_svc, research as research_svc,
    workflows as workflows_svc,
)


def _tenant(explicit: Optional[int] = None) -> Optional[int]:
    if explicit is not None:
        return explicit
    try:
        from backend.app.services.saas import context as tenant_ctx
        return tenant_ctx.current_tenant_id()
    except Exception:
        return None


def _uref(user: Optional[User]) -> Optional[str]:
    return getattr(user, "email", None) if user else None


def _bad(exc: Exception):
    raise HTTPException(status_code=400, detail=str(exc))


# ===========================================================================
# M1 — Enterprise RAG Platform
# ===========================================================================
rag_router = APIRouter(prefix="/api/aip/rag", tags=["AIP: RAG"])


@rag_router.get("/sources")
def list_sources(tenant_id: Optional[int] = None, db: Session = Depends(get_db),
                 _u=Depends(require_permission("aip.rag.view"))):
    return [
        {"id": s.id, "key": s.key, "name": s.name, "source_type": s.source_type,
         "description": s.description, "status": s.status,
         "document_count": s.document_count, "created_at": s.created_at.isoformat()
         if s.created_at else None}
        for s in rag.list_sources(db, tenant_id=_tenant(tenant_id))
    ]


@rag_router.post("/sources")
def create_source(body: SourceCreate, tenant_id: Optional[int] = None,
                  db: Session = Depends(get_db), user=Depends(get_current_user),
                  _u=Depends(require_permission("aip.rag.manage"))):
    try:
        s = rag.register_source(db, key=body.key, name=body.name,
                                source_type=body.source_type, description=body.description,
                                config=body.config, tenant_id=_tenant(tenant_id),
                                created_by=_uref(user))
    except ValueError as e:
        _bad(e)
    return {"id": s.id, "key": s.key, "name": s.name, "source_type": s.source_type}


@rag_router.get("/source-types")
def source_types(_u=Depends(require_permission("aip.rag.view"))):
    return {"source_types": rag.SOURCE_TYPES}


@rag_router.post("/documents")
def ingest_document(body: DocumentIngest, tenant_id: Optional[int] = None,
                    db: Session = Depends(get_db), user=Depends(get_current_user),
                    _u=Depends(require_permission("aip.rag.manage"))):
    try:
        doc = rag.ingest_document(
            db, title=body.title, text=body.text, source_key=body.source_key,
            source_id=body.source_id, doc_type=body.doc_type,
            external_id=body.external_id, uri=body.uri, language=body.language,
            metadata=body.metadata, tenant_id=_tenant(tenant_id),
            created_by=_uref(user), chunk_size=body.chunk_size, overlap=body.overlap)
    except ValueError as e:
        _bad(e)
    return {"id": doc.id, "title": doc.title, "version": doc.version,
            "is_current": doc.is_current, "chunk_count": doc.chunk_count,
            "checksum": doc.checksum, "lineage": doc.lineage,
            "source_id": doc.source_id}


@rag_router.get("/documents")
def list_documents(source_id: Optional[int] = None, current_only: bool = True,
                   tenant_id: Optional[int] = None, db: Session = Depends(get_db),
                   _u=Depends(require_permission("aip.rag.view"))):
    docs = rag.list_documents(db, source_id=source_id, tenant_id=_tenant(tenant_id),
                              current_only=current_only)
    return [{"id": d.id, "title": d.title, "version": d.version,
             "is_current": d.is_current, "doc_type": d.doc_type,
             "chunk_count": d.chunk_count, "source_id": d.source_id,
             "checksum": d.checksum} for d in docs]


@rag_router.post("/search")
def search(body: RagSearch, tenant_id: Optional[int] = None,
           db: Session = Depends(get_db),
           _u=Depends(require_permission("aip.rag.query"))):
    hits = rag.search(db, query=body.query, top_k=body.top_k,
                      tenant_id=_tenant(tenant_id), source_types=body.source_types,
                      doc_type=body.doc_type, metadata_filter=body.metadata_filter,
                      semantic_weight=body.semantic_weight)
    return {"query": body.query, "count": len(hits), "hits": hits}


@rag_router.post("/answer")
def answer(body: RagAnswer, tenant_id: Optional[int] = None,
           db: Session = Depends(get_db), user=Depends(get_current_user),
           _u=Depends(require_permission("aip.rag.query"))):
    return rag.answer(db, question=body.question, top_k=body.top_k,
                      tenant_id=_tenant(tenant_id), source_types=body.source_types,
                      doc_type=body.doc_type, metadata_filter=body.metadata_filter,
                      provider=body.provider, created_by=_uref(user))


@rag_router.get("/stats")
def stats(tenant_id: Optional[int] = None, db: Session = Depends(get_db),
          _u=Depends(require_permission("aip.rag.view"))):
    return rag.stats(db, tenant_id=_tenant(tenant_id))


# ===========================================================================
# M2 — Multi-Agent AI System
# ===========================================================================
agents_router = APIRouter(prefix="/api/aip/agents", tags=["AIP: Multi-Agent"])


@agents_router.get("/roster")
def roster(_u=Depends(require_permission("aip.agents.run"))):
    return {"roles": agents_svc.roster()}


@agents_router.post("/plan")
def plan(body: PlanRequest, _u=Depends(require_permission("aip.agents.run"))):
    return {"goal": body.goal, "plan": agents_svc.plan(body.goal, roles=body.roles)}


@agents_router.post("/run")
def run_agents(body: AgentRunRequest, tenant_id: Optional[int] = None,
               db: Session = Depends(get_db), user=Depends(get_current_user),
               _u=Depends(require_permission("aip.agents.run"))):
    try:
        return agents_svc.run(db, goal=body.goal, company_ref=body.company_ref,
                              assessment_id=body.assessment_id, roles=body.roles,
                              mode=body.mode, parallel=body.parallel,
                              tenant_id=_tenant(tenant_id), provider=body.provider,
                              created_by=_uref(user))
    except ValueError as e:
        _bad(e)


@agents_router.get("/runs")
def list_agent_runs(tenant_id: Optional[int] = None, limit: int = 50,
                    db: Session = Depends(get_db),
                    _u=Depends(require_permission("aip.agents.run"))):
    return {"runs": agents_svc.list_runs(db, tenant_id=_tenant(tenant_id), limit=limit)}


@agents_router.get("/runs/{run_id}")
def get_agent_run(run_id: int, db: Session = Depends(get_db),
                  _u=Depends(require_permission("aip.agents.run"))):
    out = agents_svc.get_run(db, run_id)
    if not out:
        raise HTTPException(status_code=404, detail="run not found")
    return out


# ===========================================================================
# M3 — Long-Term Memory
# ===========================================================================
memory_router = APIRouter(prefix="/api/aip/memory", tags=["AIP: Memory"])


@memory_router.get("/types")
def memory_types(_u=Depends(require_permission("aip.memory.view"))):
    return {"memory_types": memory_svc.MEMORY_TYPES}


@memory_router.post("/write")
def memory_write(body: MemoryWrite, tenant_id: Optional[int] = None,
                 db: Session = Depends(get_db),
                 _u=Depends(require_permission("aip.memory.manage"))):
    try:
        m = memory_svc.write(db, content=body.content, memory_type=body.memory_type,
                             scope=body.scope, scope_ref=body.scope_ref, key=body.key,
                             importance=body.importance, decay=body.decay,
                             source=body.source, related_ids=body.related_ids,
                             meta=body.meta, tenant_id=_tenant(tenant_id))
    except ValueError as e:
        _bad(e)
    return {"memory_id": m.id, "scope": m.scope, "memory_type": m.memory_type,
            "importance": m.importance}


@memory_router.post("/recall")
def memory_recall(body: MemoryRecall, tenant_id: Optional[int] = None,
                  db: Session = Depends(get_db),
                  _u=Depends(require_permission("aip.memory.view"))):
    hits = memory_svc.recall(db, query=body.query, scope=body.scope,
                             scope_ref=body.scope_ref, memory_type=body.memory_type,
                             top_k=body.top_k, tenant_id=_tenant(tenant_id))
    return {"query": body.query, "count": len(hits), "memories": hits}


@memory_router.post("/link")
def memory_link(body: MemoryLink, db: Session = Depends(get_db),
                _u=Depends(require_permission("aip.memory.manage"))):
    memory_svc.link(db, memory_id=body.memory_id, related_id=body.related_id)
    return {"linked": [body.memory_id, body.related_id]}


@memory_router.get("/neighbors/{memory_id}")
def memory_neighbors(memory_id: int, depth: int = 1, db: Session = Depends(get_db),
                     _u=Depends(require_permission("aip.memory.view"))):
    return {"memory_id": memory_id,
            "neighbors": memory_svc.neighbors(db, memory_id=memory_id, depth=depth)}


@memory_router.post("/summarize")
def memory_summarize(body: MemorySummarize, tenant_id: Optional[int] = None,
                     db: Session = Depends(get_db),
                     _u=Depends(require_permission("aip.memory.manage"))):
    row = memory_svc.summarize(db, scope=body.scope, scope_ref=body.scope_ref,
                               tenant_id=_tenant(tenant_id))
    return {"summary_id": row.id, "summary": row.summary,
            "memory_count": row.memory_count}


@memory_router.post("/forget")
def memory_forget(body: MemoryForget, tenant_id: Optional[int] = None,
                  db: Session = Depends(get_db),
                  _u=Depends(require_permission("aip.memory.manage"))):
    return memory_svc.apply_forgetting(db, scope=body.scope,
                                       tenant_id=_tenant(tenant_id),
                                       threshold=body.threshold,
                                       hard_delete=body.hard_delete)


@memory_router.get("/stats")
def memory_stats(tenant_id: Optional[int] = None, db: Session = Depends(get_db),
                 _u=Depends(require_permission("aip.memory.view"))):
    return memory_svc.stats(db, tenant_id=_tenant(tenant_id))


# ===========================================================================
# M4 — Prompt Engineering Platform
# ===========================================================================
prompts_router = APIRouter(prefix="/api/aip/prompts", tags=["AIP: Prompts"])


@prompts_router.get("")
def list_prompts(tenant_id: Optional[int] = None, db: Session = Depends(get_db),
                 _u=Depends(require_permission("aip.prompts.view"))):
    return [{"id": p.id, "key": p.key, "name": p.name, "task": p.task,
             "current_version": p.current_version, "deployed_version": p.deployed_version,
             "tags": p.tags} for p in prompts_svc.list_prompts(db, tenant_id=_tenant(tenant_id))]


@prompts_router.post("")
def create_prompt(body: PromptCreate, tenant_id: Optional[int] = None,
                  db: Session = Depends(get_db), user=Depends(get_current_user),
                  _u=Depends(require_permission("aip.prompts.manage"))):
    p = prompts_svc.register(db, key=body.key, name=body.name, description=body.description,
                             task=body.task, tags=body.tags, tenant_id=_tenant(tenant_id),
                             created_by=_uref(user))
    return {"id": p.id, "key": p.key, "current_version": p.current_version}


@prompts_router.post("/seed-defaults")
def seed_prompts(tenant_id: Optional[int] = None, db: Session = Depends(get_db),
                 _u=Depends(require_permission("aip.prompts.manage"))):
    return {"seeded": prompts_svc.seed_defaults(db, tenant_id=_tenant(tenant_id))}


@prompts_router.get("/{prompt_id}/versions")
def prompt_versions(prompt_id: int, db: Session = Depends(get_db),
                    _u=Depends(require_permission("aip.prompts.view"))):
    return [{"id": v.id, "version": v.version, "status": v.status,
             "variables": v.variables, "eval_score": v.eval_score,
             "model": v.model} for v in prompts_svc.list_versions(db, prompt_id=prompt_id)]


@prompts_router.post("/versions")
def create_version(body: PromptVersionCreate, tenant_id: Optional[int] = None,
                   db: Session = Depends(get_db), user=Depends(get_current_user),
                   _u=Depends(require_permission("aip.prompts.manage"))):
    try:
        v = prompts_svc.add_version(db, template=body.template, prompt_id=body.prompt_id,
                                    key=body.key, system=body.system, model=body.model,
                                    params=body.params, variables=body.variables,
                                    notes=body.notes, tenant_id=_tenant(tenant_id),
                                    created_by=_uref(user))
    except ValueError as e:
        _bad(e)
    return {"id": v.id, "version": v.version, "status": v.status, "variables": v.variables}


@prompts_router.post("/render")
def render_prompt(body: PromptRender, tenant_id: Optional[int] = None,
                  db: Session = Depends(get_db),
                  _u=Depends(require_permission("aip.prompts.view"))):
    try:
        return prompts_svc.render(db, variables=body.variables, key=body.key,
                                  prompt_id=body.prompt_id, version=body.version,
                                  tenant_id=_tenant(tenant_id))
    except ValueError as e:
        _bad(e)


@prompts_router.post("/evaluate")
def evaluate_prompt(body: PromptEvalRequest, db: Session = Depends(get_db),
                    _u=Depends(require_permission("aip.prompts.manage"))):
    try:
        ev = prompts_svc.evaluate_version(db, version_id=body.version_id, dataset=body.dataset)
    except ValueError as e:
        _bad(e)
    return {"id": ev.id, "score": ev.score, "passed": ev.passed, "metrics": ev.metrics}


@prompts_router.post("/approve")
def approve_prompt(body: PromptApprove, db: Session = Depends(get_db),
                   user=Depends(get_current_user),
                   _u=Depends(require_permission("aip.prompts.manage"))):
    try:
        v = prompts_svc.approve(db, version_id=body.version_id, approver=_uref(user))
    except ValueError as e:
        _bad(e)
    return {"id": v.id, "version": v.version, "status": v.status}


@prompts_router.post("/deploy")
def deploy_prompt(body: PromptDeploy, db: Session = Depends(get_db),
                  _u=Depends(require_permission("aip.prompts.manage"))):
    try:
        p = prompts_svc.deploy(db, prompt_id=body.prompt_id, version=body.version)
    except ValueError as e:
        _bad(e)
    return {"prompt_id": p.id, "deployed_version": p.deployed_version}


@prompts_router.post("/rollback")
def rollback_prompt(body: PromptDeploy, db: Session = Depends(get_db),
                    _u=Depends(require_permission("aip.prompts.manage"))):
    try:
        p = prompts_svc.rollback(db, prompt_id=body.prompt_id, to_version=body.version)
    except ValueError as e:
        _bad(e)
    return {"prompt_id": p.id, "deployed_version": p.deployed_version}


@prompts_router.post("/experiments")
def start_experiment(body: ExperimentStart, tenant_id: Optional[int] = None,
                     db: Session = Depends(get_db),
                     _u=Depends(require_permission("aip.prompts.manage"))):
    try:
        e = prompts_svc.start_experiment(db, prompt_id=body.prompt_id, name=body.name,
                                         variant_a_version=body.variant_a_version,
                                         variant_b_version=body.variant_b_version,
                                         allocation=body.allocation,
                                         tenant_id=_tenant(tenant_id))
    except ValueError as ex:
        _bad(ex)
    return {"id": e.id, "status": e.status}


@prompts_router.post("/experiments/result")
def experiment_result(body: ExperimentResult, db: Session = Depends(get_db),
                      _u=Depends(require_permission("aip.prompts.manage"))):
    try:
        e = prompts_svc.record_experiment_result(db, experiment_id=body.experiment_id,
                                                 variant=body.variant, score=body.score)
    except ValueError as ex:
        _bad(ex)
    return {"id": e.id, "results": e.results}


@prompts_router.post("/experiments/{experiment_id}/conclude")
def conclude_experiment(experiment_id: int, db: Session = Depends(get_db),
                        _u=Depends(require_permission("aip.prompts.manage"))):
    try:
        e = prompts_svc.conclude_experiment(db, experiment_id=experiment_id)
    except ValueError as ex:
        _bad(ex)
    return {"id": e.id, "winner": e.winner, "results": e.results}


# ===========================================================================
# M5 — AI Evaluation Framework
# ===========================================================================
eval_router = APIRouter(prefix="/api/aip/eval", tags=["AIP: Evaluation"])


@eval_router.post("/score")
def eval_score(body: EvaluateRequest, tenant_id: Optional[int] = None,
               db: Session = Depends(get_db), user=Depends(get_current_user),
               _u=Depends(require_permission("aip.eval.run"))):
    return eval_svc.evaluate(
        db, target_type=body.target_type, output_text=body.output_text,
        grounding_text=body.grounding_text, citations=body.citations,
        expected=body.expected, expected_decision=body.expected_decision,
        samples=body.samples, usage=body.usage, target_ref=body.target_ref,
        suite=body.suite, require_citations=body.require_citations,
        tenant_id=_tenant(tenant_id), created_by=_uref(user))


@eval_router.post("/rag/{query_id}")
def eval_rag(query_id: int, tenant_id: Optional[int] = None,
             db: Session = Depends(get_db),
             _u=Depends(require_permission("aip.eval.run"))):
    try:
        return eval_svc.evaluate_rag_query(db, query_id=query_id, tenant_id=_tenant(tenant_id))
    except ValueError as e:
        _bad(e)


@eval_router.post("/agent-run/{run_id}")
def eval_agent(run_id: int, tenant_id: Optional[int] = None,
               db: Session = Depends(get_db),
               _u=Depends(require_permission("aip.eval.run"))):
    try:
        return eval_svc.evaluate_agent_run(db, run_id=run_id, tenant_id=_tenant(tenant_id))
    except ValueError as e:
        _bad(e)


@eval_router.post("/report/{report_id}")
def eval_report(report_id: int, tenant_id: Optional[int] = None,
                db: Session = Depends(get_db),
                _u=Depends(require_permission("aip.eval.run"))):
    try:
        return eval_svc.evaluate_report(db, report_id=report_id, tenant_id=_tenant(tenant_id))
    except ValueError as e:
        _bad(e)


@eval_router.post("/cases")
def eval_case_create(body: EvalCaseCreate, tenant_id: Optional[int] = None,
                     db: Session = Depends(get_db),
                     _u=Depends(require_permission("aip.eval.run"))):
    row = eval_svc.add_case(db, suite=body.suite, name=body.name, input=body.input,
                            expected=body.expected, tenant_id=_tenant(tenant_id))
    return {"id": row.id, "suite": row.suite, "name": row.name}


@eval_router.get("/list")
def eval_list(target_type: Optional[str] = None, limit: int = 50,
              tenant_id: Optional[int] = None, db: Session = Depends(get_db),
              _u=Depends(require_permission("aip.eval.run"))):
    return {"evaluations": eval_svc.list_evaluations(db, tenant_id=_tenant(tenant_id),
                                                     target_type=target_type, limit=limit)}


@eval_router.get("/summary")
def eval_summary(tenant_id: Optional[int] = None, db: Session = Depends(get_db),
                 _u=Depends(require_permission("aip.eval.run"))):
    return eval_svc.summary(db, tenant_id=_tenant(tenant_id))


# ===========================================================================
# M6 — Autonomous Investigation
# ===========================================================================
investigate_router = APIRouter(prefix="/api/aip/investigate", tags=["AIP: Investigation"])


@investigate_router.post("/run")
def run_investigation(body: InvestigateRequest, tenant_id: Optional[int] = None,
                      db: Session = Depends(get_db), user=Depends(get_current_user),
                      _u=Depends(require_permission("aip.investigate.run"))):
    return investigation_svc.investigate(db, company_ref=body.company_ref,
                                         assessment_id=body.assessment_id,
                                         tenant_id=_tenant(tenant_id),
                                         provider=body.provider, created_by=_uref(user))


@investigate_router.get("/list")
def list_investigations(tenant_id: Optional[int] = None, limit: int = 50,
                        db: Session = Depends(get_db),
                        _u=Depends(require_permission("aip.investigate.run"))):
    return {"investigations": investigation_svc.list_investigations(
        db, tenant_id=_tenant(tenant_id), limit=limit)}


@investigate_router.get("/{investigation_id}")
def get_investigation(investigation_id: int, db: Session = Depends(get_db),
                      _u=Depends(require_permission("aip.investigate.run"))):
    out = investigation_svc.get_investigation(db, investigation_id)
    if not out:
        raise HTTPException(status_code=404, detail="investigation not found")
    return out


# ===========================================================================
# M7 — AI Report Generation
# ===========================================================================
reports_router = APIRouter(prefix="/api/aip/reports", tags=["AIP: Reports"])


@reports_router.get("/types")
def report_types(_u=Depends(require_permission("aip.reports.generate"))):
    return {"report_types": reports_svc.REPORT_TYPES}


@reports_router.post("/generate")
def generate_report(body: ReportRequest, tenant_id: Optional[int] = None,
                    db: Session = Depends(get_db), user=Depends(get_current_user),
                    _u=Depends(require_permission("aip.reports.generate"))):
    try:
        return reports_svc.generate(db, report_type=body.report_type,
                                    company_ref=body.company_ref,
                                    assessment_id=body.assessment_id, title=body.title,
                                    tenant_id=_tenant(tenant_id), provider=body.provider,
                                    created_by=_uref(user))
    except ValueError as e:
        _bad(e)


@reports_router.get("/list")
def list_reports(report_type: Optional[str] = None, limit: int = 50,
                 tenant_id: Optional[int] = None, db: Session = Depends(get_db),
                 _u=Depends(require_permission("aip.reports.generate"))):
    return {"reports": reports_svc.list_reports(db, tenant_id=_tenant(tenant_id),
                                                report_type=report_type, limit=limit)}


@reports_router.get("/{report_id}")
def get_report(report_id: int, db: Session = Depends(get_db),
               _u=Depends(require_permission("aip.reports.generate"))):
    out = reports_svc.get_report(db, report_id)
    if not out:
        raise HTTPException(status_code=404, detail="report not found")
    return out


# ===========================================================================
# M8 — AI Workflow Builder
# ===========================================================================
workflows_router = APIRouter(prefix="/api/aip/workflows", tags=["AIP: Workflows"])


@workflows_router.get("/node-types")
def node_types(_u=Depends(require_permission("aip.workflows.view"))):
    return {"node_types": workflows_svc.NODE_TYPES}


@workflows_router.get("")
def list_workflows(tenant_id: Optional[int] = None, db: Session = Depends(get_db),
                   _u=Depends(require_permission("aip.workflows.view"))):
    return [{"id": w.id, "key": w.key, "name": w.name, "version": w.version,
             "status": w.status, "node_count": len((w.graph or {}).get("nodes", []))}
            for w in workflows_svc.list_workflows(db, tenant_id=_tenant(tenant_id))]


@workflows_router.post("")
def save_workflow(body: WorkflowSave, tenant_id: Optional[int] = None,
                  db: Session = Depends(get_db), user=Depends(get_current_user),
                  _u=Depends(require_permission("aip.workflows.manage"))):
    try:
        w = workflows_svc.save_workflow(db, key=body.key, name=body.name, graph=body.graph,
                                        description=body.description, tags=body.tags,
                                        tenant_id=_tenant(tenant_id), created_by=_uref(user))
    except ValueError as e:
        _bad(e)
    return {"id": w.id, "key": w.key, "version": w.version}


@workflows_router.post("/validate")
def validate_workflow(body: WorkflowSave, _u=Depends(require_permission("aip.workflows.view"))):
    errors = workflows_svc.validate_graph(body.graph)
    return {"valid": not errors, "errors": errors}


@workflows_router.post("/run")
def run_workflow(body: WorkflowRunRequest, tenant_id: Optional[int] = None,
                 db: Session = Depends(get_db), user=Depends(get_current_user),
                 _u=Depends(require_permission("aip.workflows.manage"))):
    try:
        return workflows_svc.run_workflow(db, workflow_id=body.workflow_id, key=body.key,
                                          run_input=body.input, tenant_id=_tenant(tenant_id),
                                          provider=body.provider, created_by=_uref(user))
    except ValueError as e:
        _bad(e)


@workflows_router.get("/runs/{run_id}")
def get_workflow_run(run_id: int, db: Session = Depends(get_db),
                     _u=Depends(require_permission("aip.workflows.view"))):
    out = workflows_svc.get_run(db, run_id)
    if not out:
        raise HTTPException(status_code=404, detail="run not found")
    return out


@workflows_router.get("/{workflow_id}")
def get_workflow(workflow_id: int, tenant_id: Optional[int] = None,
                 db: Session = Depends(get_db),
                 _u=Depends(require_permission("aip.workflows.view"))):
    w = workflows_svc.get_workflow(db, workflow_id=workflow_id, tenant_id=_tenant(tenant_id))
    if not w:
        raise HTTPException(status_code=404, detail="workflow not found")
    return {"id": w.id, "key": w.key, "name": w.name, "version": w.version,
            "graph": w.graph, "runs": workflows_svc.list_runs(db, workflow_id=w.id)}


# ===========================================================================
# M9 — Enterprise Conversational AI
# ===========================================================================
chat_router = APIRouter(prefix="/api/aip/chat", tags=["AIP: Conversational"])


@chat_router.post("/conversations")
def create_conversation(body: ConversationCreate, tenant_id: Optional[int] = None,
                        db: Session = Depends(get_db), user=Depends(get_current_user),
                        _u=Depends(require_permission("aip.chat.use"))):
    conv = chat_svc.create_conversation(db, title=body.title, bindings=body.bindings,
                                        user_ref=_uref(user), tenant_id=_tenant(tenant_id))
    return {"conversation_id": conv.id, "title": conv.title, "bindings": conv.bindings}


@chat_router.get("/conversations")
def list_conversations(tenant_id: Optional[int] = None, db: Session = Depends(get_db),
                       _u=Depends(require_permission("aip.chat.use"))):
    return [{"conversation_id": c.id, "title": c.title, "message_count": c.message_count,
             "bindings": c.bindings}
            for c in chat_svc.list_conversations(db, tenant_id=_tenant(tenant_id))]


@chat_router.get("/conversations/{conversation_id}")
def get_conversation(conversation_id: int, db: Session = Depends(get_db),
                     _u=Depends(require_permission("aip.chat.use"))):
    out = chat_svc.conversation_detail(db, conversation_id=conversation_id)
    if not out:
        raise HTTPException(status_code=404, detail="conversation not found")
    return out


@chat_router.post("/ask")
def chat_ask(body: ChatAsk, tenant_id: Optional[int] = None,
             db: Session = Depends(get_db), user=Depends(get_current_user),
             _u=Depends(require_permission("aip.chat.use"))):
    try:
        return chat_svc.ask(db, conversation_id=body.conversation_id, message=body.message,
                            tenant_id=_tenant(tenant_id), provider=body.provider,
                            user_ref=_uref(user))
    except ValueError as e:
        _bad(e)


# ===========================================================================
# M10 — AI Research Assistant
# ===========================================================================
research_router = APIRouter(prefix="/api/aip/research", tags=["AIP: Research"])


@research_router.get("/types")
def research_types(_u=Depends(require_permission("aip.research.run"))):
    return {"research_types": research_svc.RESEARCH_TYPES}


@research_router.post("/run")
def run_research(body: ResearchRequest, tenant_id: Optional[int] = None,
                 db: Session = Depends(get_db), user=Depends(get_current_user),
                 _u=Depends(require_permission("aip.research.run"))):
    try:
        return research_svc.research(db, topic=body.topic, research_type=body.research_type,
                                     subject_ref=body.subject_ref, tenant_id=_tenant(tenant_id),
                                     provider=body.provider, created_by=_uref(user))
    except ValueError as e:
        _bad(e)


@research_router.get("/list")
def list_research(research_type: Optional[str] = None, limit: int = 50,
                  tenant_id: Optional[int] = None, db: Session = Depends(get_db),
                  _u=Depends(require_permission("aip.research.run"))):
    return {"research": research_svc.list_research(db, tenant_id=_tenant(tenant_id),
                                                   research_type=research_type, limit=limit)}


@research_router.get("/{research_id}")
def get_research(research_id: int, db: Session = Depends(get_db),
                 _u=Depends(require_permission("aip.research.run"))):
    out = research_svc.get_research(db, research_id)
    if not out:
        raise HTTPException(status_code=404, detail="research not found")
    return out


# ===========================================================================
# M11 — Continuous Learning
# ===========================================================================
learning_router = APIRouter(prefix="/api/aip/learning", tags=["AIP: Learning"])


@learning_router.post("/feedback")
def submit_feedback(body: FeedbackCreate, tenant_id: Optional[int] = None,
                    db: Session = Depends(get_db), user=Depends(get_current_user),
                    _u=Depends(require_permission("aip.learning.manage"))):
    f = learning_svc.record_feedback(db, target_type=body.target_type, target_ref=body.target_ref,
                                     feedback_type=body.feedback_type, rating=body.rating,
                                     label=body.label, comment=body.comment,
                                     correction=body.correction, user_ref=_uref(user),
                                     tenant_id=_tenant(tenant_id))
    return {"id": f.id, "target_type": f.target_type}


@learning_router.post("/signal")
def submit_signal(body: SignalCreate, tenant_id: Optional[int] = None,
                  db: Session = Depends(get_db),
                  _u=Depends(require_permission("aip.learning.manage"))):
    s = learning_svc.record_signal(db, signal_type=body.signal_type, target_ref=body.target_ref,
                                   source=body.source, payload=body.payload,
                                   outcome=body.outcome, tenant_id=_tenant(tenant_id))
    return {"id": s.id, "signal_type": s.signal_type}


@learning_router.post("/evaluate-triggers")
def evaluate_triggers(body: TriggerRequest, tenant_id: Optional[int] = None,
                      db: Session = Depends(get_db), user=Depends(get_current_user),
                      _u=Depends(require_permission("aip.learning.manage"))):
    return learning_svc.evaluate_triggers(db, tenant_id=_tenant(tenant_id),
                                          thresholds=body.thresholds,
                                          create_events=body.create_events,
                                          created_by=_uref(user))


@learning_router.post("/training-events/update")
def update_training_event(body: TrainingEventUpdate, db: Session = Depends(get_db),
                          _u=Depends(require_permission("aip.learning.manage"))):
    try:
        e = learning_svc.update_training_event(db, event_id=body.event_id, status=body.status,
                                               metrics=body.metrics, model_ref=body.model_ref)
    except ValueError as ex:
        _bad(ex)
    return {"id": e.id, "status": e.status, "version": e.version}


@learning_router.get("/feedback")
def list_feedback(target_type: Optional[str] = None, tenant_id: Optional[int] = None,
                  db: Session = Depends(get_db),
                  _u=Depends(require_permission("aip.learning.view"))):
    return {"feedback": learning_svc.list_feedback(db, tenant_id=_tenant(tenant_id),
                                                   target_type=target_type)}


@learning_router.get("/training-events")
def list_training_events(tenant_id: Optional[int] = None, db: Session = Depends(get_db),
                         _u=Depends(require_permission("aip.learning.view"))):
    return {"training_events": learning_svc.list_training_events(db, tenant_id=_tenant(tenant_id))}


@learning_router.get("/stats")
def learning_stats(tenant_id: Optional[int] = None, db: Session = Depends(get_db),
                   _u=Depends(require_permission("aip.learning.view"))):
    return learning_svc.stats(db, tenant_id=_tenant(tenant_id))


# ===========================================================================
# M12 — AI Governance
# ===========================================================================
governance_router = APIRouter(prefix="/api/aip/governance", tags=["AIP: Governance"])


@governance_router.get("/asset-types")
def asset_types(_u=Depends(require_permission("aip.governance.view"))):
    return {"asset_types": governance_svc.ASSET_TYPES}


@governance_router.post("/assets")
def register_asset(body: AssetRegister, tenant_id: Optional[int] = None,
                   db: Session = Depends(get_db), user=Depends(get_current_user),
                   _u=Depends(require_permission("aip.governance.manage"))):
    try:
        a = governance_svc.register_asset(db, asset_type=body.asset_type, asset_ref=body.asset_ref,
                                          name=body.name, version=body.version, lineage=body.lineage,
                                          owner=body.owner or _uref(user), meta=body.meta,
                                          tenant_id=_tenant(tenant_id), actor=_uref(user))
    except ValueError as e:
        _bad(e)
    return {"id": a.id, "state": a.state, "checksum": a.checksum, "version": a.version}


@governance_router.post("/assets/transition")
def transition_asset(body: AssetTransition, db: Session = Depends(get_db),
                     user=Depends(get_current_user),
                     _u=Depends(require_permission("aip.governance.manage"))):
    try:
        a = governance_svc.transition(db, asset_id=body.asset_id, action=body.action,
                                      actor=_uref(user), detail=body.detail)
    except ValueError as e:
        _bad(e)
    return {"id": a.id, "state": a.state}


@governance_router.get("/assets")
def list_assets(asset_type: Optional[str] = None, state: Optional[str] = None,
                tenant_id: Optional[int] = None, db: Session = Depends(get_db),
                _u=Depends(require_permission("aip.governance.view"))):
    return {"assets": governance_svc.list_assets(db, tenant_id=_tenant(tenant_id),
                                                 asset_type=asset_type, state=state)}


@governance_router.get("/summary")
def governance_summary(tenant_id: Optional[int] = None, db: Session = Depends(get_db),
                       _u=Depends(require_permission("aip.governance.view"))):
    return governance_svc.registry_summary(db, tenant_id=_tenant(tenant_id))


@governance_router.get("/assets/{asset_id}/lineage")
def asset_lineage(asset_id: int, db: Session = Depends(get_db),
                  _u=Depends(require_permission("aip.governance.view"))):
    try:
        return governance_svc.lineage(db, asset_id=asset_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ===========================================================================
# M13 — Explainable Enterprise AI
# ===========================================================================
explain_router = APIRouter(prefix="/api/aip/explain", tags=["AIP: Explainability"])


@explain_router.post("/decision")
def explain_decision(body: ExplainRequest, tenant_id: Optional[int] = None,
                     db: Session = Depends(get_db),
                     _u=Depends(require_permission("aip.explain.view"))):
    try:
        return explain_svc.explain(db, target_type=body.target_type,
                                   company_ref=body.company_ref, assessment_id=body.assessment_id,
                                   target_ref=body.target_ref, method=body.method,
                                   tenant_id=_tenant(tenant_id), provider=body.provider)
    except ValueError as e:
        _bad(e)


@explain_router.get("/list")
def list_explanations(tenant_id: Optional[int] = None, db: Session = Depends(get_db),
                      _u=Depends(require_permission("aip.explain.view"))):
    return {"explanations": explain_svc.list_explanations(db, tenant_id=_tenant(tenant_id))}


@explain_router.get("/{explanation_id}")
def get_explanation(explanation_id: int, db: Session = Depends(get_db),
                    _u=Depends(require_permission("aip.explain.view"))):
    out = explain_svc.get_explanation(db, explanation_id)
    if not out:
        raise HTTPException(status_code=404, detail="explanation not found")
    return out


# ===========================================================================
# M14 — AI Monitoring
# ===========================================================================
monitoring_router = APIRouter(prefix="/api/aip/monitoring", tags=["AIP: Monitoring"])


@monitoring_router.post("/run")
def run_monitoring(tenant_id: Optional[int] = None, db: Session = Depends(get_db),
                   _u=Depends(require_permission("aip.monitoring.manage"))):
    return monitoring_svc.run_monitoring(db, tenant_id=_tenant(tenant_id))


@monitoring_router.post("/metric")
def record_metric(body: MetricRecord, tenant_id: Optional[int] = None,
                  db: Session = Depends(get_db),
                  _u=Depends(require_permission("aip.monitoring.manage"))):
    m = monitoring_svc.record_metric(db, metric_type=body.metric_type, value=body.value,
                                     subject=body.subject, unit=body.unit, window=body.window,
                                     meta=body.meta, tenant_id=_tenant(tenant_id))
    return {"id": m.id, "metric_type": m.metric_type, "value": m.value}


@monitoring_router.get("/dashboard")
def monitoring_dashboard(tenant_id: Optional[int] = None, db: Session = Depends(get_db),
                         _u=Depends(require_permission("aip.monitoring.view"))):
    return monitoring_svc.dashboard(db, tenant_id=_tenant(tenant_id))


@monitoring_router.get("/incidents")
def list_incidents(status: Optional[str] = None, tenant_id: Optional[int] = None,
                   db: Session = Depends(get_db),
                   _u=Depends(require_permission("aip.monitoring.view"))):
    return {"incidents": monitoring_svc.list_incidents(db, tenant_id=_tenant(tenant_id), status=status)}


@monitoring_router.post("/incidents/{incident_id}/resolve")
def resolve_incident(incident_id: int, db: Session = Depends(get_db),
                     _u=Depends(require_permission("aip.monitoring.manage"))):
    try:
        i = monitoring_svc.resolve_incident(db, incident_id=incident_id)
    except ValueError as e:
        _bad(e)
    return {"id": i.id, "status": i.status}


# ===========================================================================
# ROUTERS — appended to by each milestone.
# ===========================================================================
ROUTERS = [
    rag_router,
    agents_router,
    memory_router,
    prompts_router,
    eval_router,
    investigate_router,
    reports_router,
    workflows_router,
    chat_router,
    research_router,
    learning_router,
    governance_router,
    explain_router,
    monitoring_router,
]
