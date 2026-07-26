"""Enterprise Banking Operating System APIs (Phase 10).

Focused, additive routers under ``/api/os/*``. Every route is new; nothing from
Phases 1-9 is modified. RBAC is enforced with the Phase 10 permission catalog
(``policy.*``, ``committee.*``, ``prompt.*``, ``llm.*``, ``fabric.*``,
``workflowstudio.*``, ``marketplace.*``) plus the existing ``search.use``.

    /api/os/policy      Enterprise Policy Engine (M7)
    /api/os/committee   Loan Committee Workspace (M4)
    /api/os/search      Enterprise Search Engine (M2)
    /api/os/prompt      Prompt Management Platform (M8)
    /api/os/llm         Multi-LLM Intelligence Layer (M9)
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.app.core.dependencies import get_current_user
from backend.app.db.database import get_db
from backend.app.models.user import User
from backend.app.schemas.banking_os import (
    AgendaItemCreate, AttendanceUpdate, CommitteeCreate, CompletionRequest,
    ContractCreate, DatasetCreate, DriftRequest, FairnessRequest, IndexDocumentRequest,
    LineageCreate, MarketplaceRunRequest, MeetingCreate, MinutesUpdate, PluginStateUpdate,
    PolicyCreate, PolicyDomainEvaluateRequest, PolicyEvaluateRequest,
    PolicyPlaygroundRequest, PolicyVersionCreate, ProviderCreate, ProviderUpdate,
    PromptCreate, PromptEvaluateRequest, PromptRenderRequest, PromptVersionCreate,
    QualityRunRequest, RecStatusUpdate, RouteRequest, SavedSearchCreate, ScenarioRunRequest,
    SearchRequest, VoteCreate, WorkflowCreate, WorkflowResumeRequest, WorkflowRunRequest,
    WorkflowValidateRequest,
)
from backend.app.services.rbac import require_permission
from backend.app.services.banking_os import (
    committee as committee_svc, data_fabric, exec_center, fairness, graph_advanced,
    llm_router, marketplace, policy as policy_svc, prompt as prompt_svc, scenario,
    search as search_svc, workflow_studio,
)


def _tenant(explicit: Optional[int] = None) -> Optional[int]:
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
# M7 — Enterprise Policy Engine
# ===========================================================================
policy_router = APIRouter(prefix="/api/os/policy", tags=["OS: Policy Engine"])


@policy_router.get("/domains")
def policy_domains(_u=Depends(require_permission("policy.view"))):
    return {"domains": policy_svc.DOMAINS, "operators": policy_svc.OPERATORS,
            "decisions": list(policy_svc.DECISION_SEVERITY.keys())}


@policy_router.get("")
def list_policies(domain: Optional[str] = None, status: Optional[str] = None,
                  tenant_id: Optional[int] = None, db: Session = Depends(get_db),
                  _u=Depends(require_permission("policy.view"))):
    return {"policies": [policy_svc.policy_dict(p) for p in
                         policy_svc.list_policies(db, tenant_id=_tenant(tenant_id),
                                                  domain=domain, status=status)]}


@policy_router.post("")
def create_policy(body: PolicyCreate, tenant_id: Optional[int] = None,
                  db: Session = Depends(get_db),
                  user: User = Depends(require_permission("policy.manage"))):
    try:
        p = policy_svc.create_policy(db, key=body.key, name=body.name, domain=body.domain,
                                     description=body.description, tenant_id=_tenant(tenant_id),
                                     tags=body.tags, created_by=getattr(user, "email", None))
    except ValueError as ex:
        _bad(ex)
    return policy_svc.policy_dict(p)


@policy_router.get("/{policy_id}")
def get_policy(policy_id: int, db: Session = Depends(get_db),
               _u=Depends(require_permission("policy.view"))):
    p = policy_svc.get_policy(db, policy_id=policy_id)
    if p is None:
        raise HTTPException(status_code=404, detail="policy not found")
    return {**policy_svc.policy_dict(p),
            "versions": [policy_svc.version_dict(v) for v in policy_svc.list_versions(db, policy_id)]}


@policy_router.post("/{policy_id}/versions")
def add_version(policy_id: int, body: PolicyVersionCreate, db: Session = Depends(get_db),
                user: User = Depends(require_permission("policy.manage"))):
    try:
        v = policy_svc.add_version(db, policy_id, rules=body.rules, combine=body.combine,
                                   default_decision=body.default_decision, notes=body.notes,
                                   created_by=getattr(user, "email", None), publish=body.publish)
    except ValueError as ex:
        _bad(ex)
    return policy_svc.version_dict(v)


@policy_router.post("/{policy_id}/versions/{version}/publish")
def publish_version(policy_id: int, version: int, db: Session = Depends(get_db),
                    _u=Depends(require_permission("policy.manage"))):
    try:
        p = policy_svc.publish_version(db, policy_id, version)
    except ValueError as ex:
        _bad(ex)
    return policy_svc.policy_dict(p)


@policy_router.post("/{policy_id}/archive")
def archive_policy(policy_id: int, db: Session = Depends(get_db),
                   _u=Depends(require_permission("policy.manage"))):
    try:
        p = policy_svc.archive_policy(db, policy_id)
    except ValueError as ex:
        _bad(ex)
    return policy_svc.policy_dict(p)


@policy_router.post("/{policy_key}/evaluate")
def evaluate_policy(policy_key: str, body: PolicyEvaluateRequest, tenant_id: Optional[int] = None,
                    db: Session = Depends(get_db),
                    _u=Depends(require_permission("policy.evaluate"))):
    try:
        return policy_svc.evaluate(db, policy_key=policy_key, data=body.data,
                                   subject_ref=body.subject_ref, tenant_id=_tenant(tenant_id),
                                   persist=body.persist)
    except ValueError as ex:
        _bad(ex)


@policy_router.post("/evaluate-domain")
def evaluate_domain(body: PolicyDomainEvaluateRequest, tenant_id: Optional[int] = None,
                    db: Session = Depends(get_db),
                    _u=Depends(require_permission("policy.evaluate"))):
    return policy_svc.evaluate_domain(db, domain=body.domain, data=body.data,
                                      subject_ref=body.subject_ref, tenant_id=_tenant(tenant_id),
                                      persist=body.persist)


@policy_router.post("/playground")
def policy_playground(body: PolicyPlaygroundRequest,
                      _u=Depends(require_permission("policy.view"))):
    return policy_svc.playground(body.rules, body.data, combine=body.combine,
                                 default_decision=body.default_decision)


@policy_router.get("/{policy_key}/history")
def policy_history(policy_key: str, subject_ref: Optional[str] = None,
                   tenant_id: Optional[int] = None, db: Session = Depends(get_db),
                   _u=Depends(require_permission("policy.view"))):
    return {"history": [policy_svc.evaluation_dict(e) for e in
                        policy_svc.evaluation_history(db, policy_key=policy_key,
                                                      subject_ref=subject_ref,
                                                      tenant_id=_tenant(tenant_id))]}


# ===========================================================================
# M4 — Loan Committee Workspace
# ===========================================================================
committee_router = APIRouter(prefix="/api/os/committee", tags=["OS: Committee Workspace"])


@committee_router.post("/committees")
def create_committee(body: CommitteeCreate, tenant_id: Optional[int] = None,
                     db: Session = Depends(get_db),
                     _u=Depends(require_permission("committee.manage"))):
    c = committee_svc.create_committee(db, name=body.name, description=body.description,
                                       quorum=body.quorum, members=body.members,
                                       tenant_id=_tenant(tenant_id))
    return committee_svc.committee_dict(c)


@committee_router.get("/committees")
def list_committees(tenant_id: Optional[int] = None, db: Session = Depends(get_db),
                    _u=Depends(require_permission("committee.view"))):
    return {"committees": [committee_svc.committee_dict(c) for c in
                           committee_svc.list_committees(db, tenant_id=_tenant(tenant_id))]}


@committee_router.post("/meetings")
def create_meeting(body: MeetingCreate, tenant_id: Optional[int] = None,
                   db: Session = Depends(get_db),
                   _u=Depends(require_permission("committee.manage"))):
    try:
        m = committee_svc.create_meeting(db, committee_id=body.committee_id, title=body.title,
                                         scheduled_at=body.scheduled_at, location=body.location,
                                         chair=body.chair, tenant_id=_tenant(tenant_id))
    except ValueError as ex:
        _bad(ex)
    return committee_svc.meeting_dict(m)


@committee_router.get("/meetings")
def list_meetings(committee_id: Optional[int] = None, status: Optional[str] = None,
                  tenant_id: Optional[int] = None, db: Session = Depends(get_db),
                  _u=Depends(require_permission("committee.view"))):
    return {"meetings": [committee_svc.meeting_dict(m) for m in
                         committee_svc.list_meetings(db, committee_id=committee_id,
                                                     status=status, tenant_id=_tenant(tenant_id))]}


@committee_router.get("/meetings/{meeting_id}")
def get_meeting(meeting_id: int, db: Session = Depends(get_db),
                _u=Depends(require_permission("committee.view"))):
    m = committee_svc.get_meeting(db, meeting_id)
    if m is None:
        raise HTTPException(status_code=404, detail="meeting not found")
    return committee_svc.meeting_detail(db, m)


@committee_router.post("/meetings/{meeting_id}/open")
def open_meeting(meeting_id: int, db: Session = Depends(get_db),
                 _u=Depends(require_permission("committee.manage"))):
    try:
        return committee_svc.meeting_dict(committee_svc.open_meeting(db, meeting_id))
    except ValueError as ex:
        _bad(ex)


@committee_router.post("/meetings/{meeting_id}/close")
def close_meeting(meeting_id: int, db: Session = Depends(get_db),
                  _u=Depends(require_permission("committee.manage"))):
    try:
        return committee_svc.close_meeting(db, meeting_id)
    except ValueError as ex:
        _bad(ex)


@committee_router.post("/meetings/{meeting_id}/attendance")
def mark_attendance(meeting_id: int, body: AttendanceUpdate, db: Session = Depends(get_db),
                    _u=Depends(require_permission("committee.participate"))):
    try:
        return committee_svc.meeting_dict(
            committee_svc.mark_attendance(db, meeting_id, user_id=body.user_id,
                                          name=body.name, present=body.present))
    except ValueError as ex:
        _bad(ex)


@committee_router.patch("/meetings/{meeting_id}/minutes")
def update_minutes(meeting_id: int, body: MinutesUpdate, db: Session = Depends(get_db),
                   _u=Depends(require_permission("committee.manage"))):
    try:
        return committee_svc.meeting_dict(committee_svc.set_minutes(db, meeting_id, body.minutes))
    except ValueError as ex:
        _bad(ex)


@committee_router.post("/agenda")
def add_agenda_item(body: AgendaItemCreate, tenant_id: Optional[int] = None,
                    db: Session = Depends(get_db),
                    _u=Depends(require_permission("committee.manage"))):
    try:
        i = committee_svc.add_agenda_item(
            db, meeting_id=body.meeting_id, title=body.title, subject_ref=body.subject_ref,
            assessment_id=body.assessment_id, presenter=body.presenter, summary=body.summary,
            proposed_action=body.proposed_action, amount=body.amount, materials=body.materials,
            order_no=body.order_no, tenant_id=_tenant(tenant_id))
    except ValueError as ex:
        _bad(ex)
    return committee_svc.agenda_dict(i)


@committee_router.post("/agenda/{item_id}/vote")
def cast_vote(item_id: int, body: VoteCreate, tenant_id: Optional[int] = None,
              db: Session = Depends(get_db),
              user: User = Depends(require_permission("committee.participate"))):
    try:
        return committee_svc.cast_vote(db, item_id, vote=body.vote, rationale=body.rationale,
                                       voter_user_id=getattr(user, "id", None),
                                       voter_name=body.voter_name or getattr(user, "email", None),
                                       weight=body.weight, tenant_id=_tenant(tenant_id))
    except ValueError as ex:
        _bad(ex)


@committee_router.get("/agenda/{item_id}/tally")
def vote_tally(item_id: int, db: Session = Depends(get_db),
               _u=Depends(require_permission("committee.view"))):
    try:
        return committee_svc.tally(db, item_id)
    except ValueError as ex:
        _bad(ex)


@committee_router.post("/agenda/{item_id}/decide")
def decide_item(item_id: int, db: Session = Depends(get_db),
                _u=Depends(require_permission("committee.manage"))):
    try:
        return committee_svc.finalize_decision(db, item_id)
    except ValueError as ex:
        _bad(ex)


@committee_router.get("/analytics")
def committee_analytics(tenant_id: Optional[int] = None, db: Session = Depends(get_db),
                        _u=Depends(require_permission("committee.view"))):
    return committee_svc.analytics(db, tenant_id=_tenant(tenant_id))


# ===========================================================================
# M2 — Enterprise Search Engine
# ===========================================================================
search_router = APIRouter(prefix="/api/os/search", tags=["OS: Enterprise Search"])


@search_router.post("/index")
def index_document(body: IndexDocumentRequest, tenant_id: Optional[int] = None,
                   db: Session = Depends(get_db),
                   _u=Depends(require_permission("search.use"))):
    d = search_svc.index_document(db, doc_type=body.doc_type, ref=body.ref, title=body.title,
                                  body=body.body, keywords=body.keywords, metadata=body.metadata,
                                  url=body.url, numeric_fields=body.numeric_fields,
                                  tenant_id=_tenant(tenant_id))
    return {"id": d.id, "doc_type": d.doc_type, "ref": d.ref}


@search_router.post("/reindex")
def reindex(tenant_id: Optional[int] = None, db: Session = Depends(get_db),
            _u=Depends(require_permission("search.use"))):
    return search_svc.reindex_platform(db, tenant_id=_tenant(tenant_id))


@search_router.post("")
def search(body: SearchRequest, tenant_id: Optional[int] = None, db: Session = Depends(get_db),
           user: User = Depends(require_permission("search.use"))):
    return search_svc.search(db, query=body.query, doc_types=body.doc_types, filters=body.filters,
                             mode=body.mode, limit=body.limit, tenant_id=_tenant(tenant_id),
                             user_id=getattr(user, "id", None), persist=body.persist)


@search_router.get("/autocomplete")
def autocomplete(q: str, limit: int = 10, tenant_id: Optional[int] = None,
                 db: Session = Depends(get_db), _u=Depends(require_permission("search.use"))):
    return {"suggestions": search_svc.autocomplete(db, q, limit=limit, tenant_id=_tenant(tenant_id))}


@search_router.get("/facets")
def facets(tenant_id: Optional[int] = None, db: Session = Depends(get_db),
           _u=Depends(require_permission("search.use"))):
    return search_svc.facets(db, tenant_id=_tenant(tenant_id))


@search_router.post("/saved")
def save_search(body: SavedSearchCreate, tenant_id: Optional[int] = None,
                db: Session = Depends(get_db),
                user: User = Depends(require_permission("search.use"))):
    s = search_svc.save_search(db, name=body.name, query=body.query, filters=body.filters,
                               user_id=getattr(user, "id", None), tenant_id=_tenant(tenant_id))
    return {"id": s.id, "name": s.name}


@search_router.get("/saved")
def list_saved(tenant_id: Optional[int] = None, db: Session = Depends(get_db),
               user: User = Depends(require_permission("search.use"))):
    return {"saved": search_svc.list_saved(db, user_id=getattr(user, "id", None),
                                           tenant_id=_tenant(tenant_id))}


@search_router.get("/history")
def search_history(tenant_id: Optional[int] = None, db: Session = Depends(get_db),
                   user: User = Depends(require_permission("search.use"))):
    return {"history": search_svc.history(db, user_id=getattr(user, "id", None),
                                          tenant_id=_tenant(tenant_id))}


# ===========================================================================
# M8 — Prompt Management Platform
# ===========================================================================
prompt_router = APIRouter(prefix="/api/os/prompt", tags=["OS: Prompt Management"])


@prompt_router.get("")
def list_prompts(category: Optional[str] = None, tenant_id: Optional[int] = None,
                 db: Session = Depends(get_db), _u=Depends(require_permission("prompt.view"))):
    return {"prompts": [prompt_svc.template_dict(t) for t in
                        prompt_svc.list_templates(db, category=category, tenant_id=_tenant(tenant_id))]}


@prompt_router.post("")
def create_prompt(body: PromptCreate, tenant_id: Optional[int] = None,
                  db: Session = Depends(get_db),
                  user: User = Depends(require_permission("prompt.manage"))):
    try:
        t = prompt_svc.create_template(db, key=body.key, name=body.name, category=body.category,
                                       description=body.description, tenant_id=_tenant(tenant_id),
                                       created_by=getattr(user, "email", None))
    except ValueError as ex:
        _bad(ex)
    return prompt_svc.template_dict(t)


@prompt_router.get("/{template_id}")
def get_prompt(template_id: int, db: Session = Depends(get_db),
               _u=Depends(require_permission("prompt.view"))):
    t = prompt_svc.get_template(db, template_id)
    if t is None:
        raise HTTPException(status_code=404, detail="prompt not found")
    return {**prompt_svc.template_dict(t),
            "versions": [prompt_svc.version_dict(v) for v in prompt_svc.list_versions(db, template_id)]}


@prompt_router.post("/{template_id}/versions")
def add_prompt_version(template_id: int, body: PromptVersionCreate, db: Session = Depends(get_db),
                       user: User = Depends(require_permission("prompt.manage"))):
    try:
        v = prompt_svc.add_version(db, template_id, content=body.content, variables=body.variables,
                                   model_hint=body.model_hint, params=body.params,
                                   created_by=getattr(user, "email", None))
    except ValueError as ex:
        _bad(ex)
    return prompt_svc.version_dict(v)


@prompt_router.post("/{template_id}/versions/{version}/approve")
def approve_prompt(template_id: int, version: int, db: Session = Depends(get_db),
                   user: User = Depends(require_permission("prompt.manage"))):
    try:
        return prompt_svc.version_dict(
            prompt_svc.approve_version(db, template_id, version, approver=getattr(user, "email", None)))
    except ValueError as ex:
        _bad(ex)


@prompt_router.post("/{template_id}/versions/{version}/deploy")
def deploy_prompt(template_id: int, version: int, db: Session = Depends(get_db),
                  _u=Depends(require_permission("prompt.manage"))):
    try:
        return prompt_svc.template_dict(prompt_svc.deploy_version(db, template_id, version))
    except ValueError as ex:
        _bad(ex)


@prompt_router.post("/{template_id}/evaluate")
def evaluate_prompt(template_id: int, body: PromptEvaluateRequest, db: Session = Depends(get_db),
                    user: User = Depends(require_permission("prompt.manage"))):
    try:
        return prompt_svc.evaluate(db, template_id, version=body.version, cases=body.cases,
                                   created_by=getattr(user, "email", None))
    except ValueError as ex:
        _bad(ex)


@prompt_router.post("/{template_id}/render")
def render_prompt(template_id: int, body: PromptRenderRequest, db: Session = Depends(get_db),
                  _u=Depends(require_permission("prompt.view"))):
    try:
        return prompt_svc.render(db, template_id, variables=body.variables, version=body.version)
    except ValueError as ex:
        _bad(ex)


# ===========================================================================
# M9 — Multi-LLM Intelligence Layer
# ===========================================================================
llm_router_api = APIRouter(prefix="/api/os/llm", tags=["OS: Multi-LLM Layer"])


@llm_router_api.get("/providers")
def list_providers(tenant_id: Optional[int] = None, db: Session = Depends(get_db),
                   _u=Depends(require_permission("llm.view"))):
    return {"providers": [llm_router.provider_dict(p) for p in
                          llm_router.list_providers(db, tenant_id=_tenant(tenant_id))],
            "kinds": llm_router.PROVIDER_KINDS}


@llm_router_api.post("/providers")
def register_provider(body: ProviderCreate, tenant_id: Optional[int] = None,
                      db: Session = Depends(get_db),
                      _u=Depends(require_permission("llm.manage"))):
    try:
        p = llm_router.register_provider(
            db, name=body.name, kind=body.kind, model=body.model, priority=body.priority,
            cost_per_1k_input=body.cost_per_1k_input, cost_per_1k_output=body.cost_per_1k_output,
            avg_latency_ms=body.avg_latency_ms, quality_score=body.quality_score,
            capabilities=body.capabilities, config=body.config, enabled=body.enabled,
            tenant_id=_tenant(tenant_id))
    except ValueError as ex:
        _bad(ex)
    return llm_router.provider_dict(p)


@llm_router_api.patch("/providers/{provider_id}")
def update_provider(provider_id: int, body: ProviderUpdate, db: Session = Depends(get_db),
                    _u=Depends(require_permission("llm.manage"))):
    try:
        return llm_router.provider_dict(
            llm_router.update_provider(db, provider_id, **body.model_dump(exclude_none=True)))
    except ValueError as ex:
        _bad(ex)


@llm_router_api.post("/route")
def route(body: RouteRequest, tenant_id: Optional[int] = None, db: Session = Depends(get_db),
          _u=Depends(require_permission("llm.view"))):
    try:
        return llm_router.route(db, strategy=body.strategy, capabilities=body.capabilities,
                                est_tokens_in=body.est_tokens_in, est_tokens_out=body.est_tokens_out,
                                tenant_id=_tenant(tenant_id))
    except ValueError as ex:
        _bad(ex)


@llm_router_api.post("/complete")
def complete(body: CompletionRequest, tenant_id: Optional[int] = None,
             db: Session = Depends(get_db), _u=Depends(require_permission("llm.view"))):
    return llm_router.complete(db, prompt=body.prompt, strategy=body.strategy,
                               capabilities=body.capabilities, prompt_ref=body.prompt_ref,
                               tenant_id=_tenant(tenant_id))


@llm_router_api.get("/analytics")
def llm_analytics(tenant_id: Optional[int] = None, db: Session = Depends(get_db),
                  _u=Depends(require_permission("llm.view"))):
    return llm_router.analytics(db, tenant_id=_tenant(tenant_id))


# ===========================================================================
# M14 — Enterprise Data Fabric
# ===========================================================================
fabric_router = APIRouter(prefix="/api/os/fabric", tags=["OS: Data Fabric"])


@fabric_router.get("/catalog")
def catalog(domain: Optional[str] = None, tenant_id: Optional[int] = None,
            db: Session = Depends(get_db), _u=Depends(require_permission("fabric.view"))):
    return {"datasets": [data_fabric.dataset_dict(d) for d in
                         data_fabric.list_datasets(db, tenant_id=_tenant(tenant_id), domain=domain)],
            "classifications": data_fabric.CLASSIFICATIONS}


@fabric_router.post("/datasets")
def register_dataset(body: DatasetCreate, tenant_id: Optional[int] = None,
                     db: Session = Depends(get_db),
                     _u=Depends(require_permission("fabric.manage"))):
    try:
        d = data_fabric.register_dataset(
            db, name=body.name, domain=body.domain, description=body.description,
            owner=body.owner, source=body.source, classification=body.classification,
            schema_fields=body.schema_fields, tags=body.tags, tenant_id=_tenant(tenant_id))
    except ValueError as ex:
        _bad(ex)
    return data_fabric.dataset_dict(d)


@fabric_router.get("/datasets/{name}")
def get_dataset(name: str, tenant_id: Optional[int] = None, db: Session = Depends(get_db),
                _u=Depends(require_permission("fabric.view"))):
    d = data_fabric.get_dataset(db, name, tenant_id=_tenant(tenant_id))
    if d is None:
        raise HTTPException(status_code=404, detail="dataset not found")
    return {**data_fabric.dataset_dict(d),
            "lineage": data_fabric.lineage_graph(db, name, tenant_id=_tenant(tenant_id))}


@fabric_router.post("/lineage")
def add_lineage(body: LineageCreate, tenant_id: Optional[int] = None,
                db: Session = Depends(get_db), _u=Depends(require_permission("fabric.manage"))):
    try:
        e = data_fabric.add_lineage(db, dataset=body.dataset, upstream=body.upstream,
                                    transform=body.transform, tenant_id=_tenant(tenant_id))
    except ValueError as ex:
        _bad(ex)
    return {"id": e.id, "dataset": e.dataset, "upstream": e.upstream}


@fabric_router.get("/lineage/{name}")
def lineage(name: str, tenant_id: Optional[int] = None, db: Session = Depends(get_db),
            _u=Depends(require_permission("fabric.view"))):
    return data_fabric.lineage_graph(db, name, tenant_id=_tenant(tenant_id))


@fabric_router.get("/impact/{name}")
def impact(name: str, tenant_id: Optional[int] = None, db: Session = Depends(get_db),
           _u=Depends(require_permission("fabric.view"))):
    return data_fabric.impact_analysis(db, name, tenant_id=_tenant(tenant_id))


@fabric_router.post("/contracts")
def add_contract(body: ContractCreate, tenant_id: Optional[int] = None,
                 db: Session = Depends(get_db), user: User = Depends(require_permission("fabric.manage"))):
    try:
        c = data_fabric.add_contract(db, dataset=body.dataset, spec=body.spec,
                                     created_by=getattr(user, "email", None),
                                     tenant_id=_tenant(tenant_id))
    except ValueError as ex:
        _bad(ex)
    return data_fabric.contract_dict(c)


@fabric_router.get("/contracts/{name}")
def latest_contract(name: str, tenant_id: Optional[int] = None, db: Session = Depends(get_db),
                    _u=Depends(require_permission("fabric.view"))):
    c = data_fabric.latest_contract(db, name, tenant_id=_tenant(tenant_id))
    if c is None:
        raise HTTPException(status_code=404, detail="no active contract")
    return data_fabric.contract_dict(c)


@fabric_router.post("/quality")
def run_quality(body: QualityRunRequest, tenant_id: Optional[int] = None,
                db: Session = Depends(get_db), _u=Depends(require_permission("fabric.view"))):
    try:
        return data_fabric.run_quality(db, dataset=body.dataset, records=body.records,
                                       spec=body.spec, tenant_id=_tenant(tenant_id))
    except ValueError as ex:
        _bad(ex)


@fabric_router.get("/stats")
def fabric_stats(tenant_id: Optional[int] = None, db: Session = Depends(get_db),
                 _u=Depends(require_permission("fabric.view"))):
    return data_fabric.catalog_stats(db, tenant_id=_tenant(tenant_id))


# ===========================================================================
# M11 — Enterprise Workflow Studio
# ===========================================================================
workflow_router = APIRouter(prefix="/api/os/workflow", tags=["OS: Workflow Studio"])


@workflow_router.get("/node-types")
def node_types(_u=Depends(require_permission("workflowstudio.view"))):
    return {"node_types": workflow_studio.NODE_TYPES}


@workflow_router.get("/definitions")
def list_definitions(tenant_id: Optional[int] = None, db: Session = Depends(get_db),
                     _u=Depends(require_permission("workflowstudio.view"))):
    return {"definitions": [workflow_studio.definition_dict(d) for d in
                            workflow_studio.list_definitions(db, tenant_id=_tenant(tenant_id))]}


@workflow_router.post("/definitions")
def create_definition(body: WorkflowCreate, tenant_id: Optional[int] = None,
                      db: Session = Depends(get_db),
                      user: User = Depends(require_permission("workflowstudio.manage"))):
    try:
        wf = workflow_studio.create_definition(db, key=body.key, name=body.name, graph=body.graph,
                                               description=body.description, publish=body.publish,
                                               created_by=getattr(user, "email", None),
                                               tenant_id=_tenant(tenant_id))
    except ValueError as ex:
        _bad(ex)
    return workflow_studio.definition_dict(wf)


@workflow_router.post("/validate")
def validate_workflow(body: WorkflowValidateRequest,
                      _u=Depends(require_permission("workflowstudio.view"))):
    problems = workflow_studio.validate_graph(body.graph)
    return {"valid": not problems, "problems": problems}


@workflow_router.post("/definitions/{key}/publish")
def publish_definition(key: str, version: int, tenant_id: Optional[int] = None,
                       db: Session = Depends(get_db),
                       _u=Depends(require_permission("workflowstudio.manage"))):
    try:
        return workflow_studio.definition_dict(
            workflow_studio.publish_definition(db, key, version, tenant_id=_tenant(tenant_id)))
    except ValueError as ex:
        _bad(ex)


@workflow_router.post("/run")
def run_workflow(body: WorkflowRunRequest, tenant_id: Optional[int] = None,
                 db: Session = Depends(get_db),
                 _u=Depends(require_permission("workflowstudio.manage"))):
    try:
        return workflow_studio.run(db, key=body.key, context=body.context,
                                   subject_ref=body.subject_ref, version=body.version,
                                   tenant_id=_tenant(tenant_id))
    except ValueError as ex:
        _bad(ex)


@workflow_router.post("/runs/{run_id}/resume")
def resume_workflow(run_id: int, body: WorkflowResumeRequest, db: Session = Depends(get_db),
                    _u=Depends(require_permission("workflowstudio.manage"))):
    try:
        return workflow_studio.resume(db, run_id, context_update=body.context_update)
    except ValueError as ex:
        _bad(ex)


@workflow_router.get("/runs")
def list_runs(key: Optional[str] = None, status: Optional[str] = None,
              tenant_id: Optional[int] = None, db: Session = Depends(get_db),
              _u=Depends(require_permission("workflowstudio.view"))):
    return {"runs": [workflow_studio.run_dict(r) for r in
                     workflow_studio.list_runs(db, key=key, status=status, tenant_id=_tenant(tenant_id))]}


# ===========================================================================
# M12 — AI Recommendation Marketplace
# ===========================================================================
marketplace_router = APIRouter(prefix="/api/os/marketplace", tags=["OS: Recommendation Marketplace"])


@marketplace_router.get("/plugins")
def list_plugins(installed_only: bool = False, tenant_id: Optional[int] = None,
                 db: Session = Depends(get_db), _u=Depends(require_permission("marketplace.view"))):
    return {"plugins": [marketplace.plugin_dict(p) for p in
                        marketplace.list_plugins(db, tenant_id=_tenant(tenant_id),
                                                 installed_only=installed_only)]}


@marketplace_router.post("/seed")
def seed_plugins(tenant_id: Optional[int] = None, db: Session = Depends(get_db),
                 _u=Depends(require_permission("marketplace.manage"))):
    n = marketplace.seed_builtin_plugins(db, tenant_id=_tenant(tenant_id))
    return {"seeded": n}


@marketplace_router.patch("/plugins/{key}")
def update_plugin(key: str, body: PluginStateUpdate, tenant_id: Optional[int] = None,
                  db: Session = Depends(get_db), _u=Depends(require_permission("marketplace.manage"))):
    try:
        return marketplace.plugin_dict(
            marketplace.set_plugin_state(db, key, installed=body.installed, enabled=body.enabled,
                                         tenant_id=_tenant(tenant_id)))
    except ValueError as ex:
        _bad(ex)


@marketplace_router.post("/run")
def run_marketplace(body: MarketplaceRunRequest, tenant_id: Optional[int] = None,
                    db: Session = Depends(get_db),
                    _u=Depends(require_permission("marketplace.view"))):
    return marketplace.run_marketplace(db, subject_ref=body.subject_ref,
                                       assessment_id=body.assessment_id, context=body.context,
                                       tenant_id=_tenant(tenant_id), persist=body.persist)


@marketplace_router.get("/recommendations")
def list_recs(subject_ref: Optional[str] = None, plugin_key: Optional[str] = None,
              tenant_id: Optional[int] = None, db: Session = Depends(get_db),
              _u=Depends(require_permission("marketplace.view"))):
    return {"recommendations": [marketplace.recommendation_dict(r) for r in
                                marketplace.list_recommendations(db, subject_ref=subject_ref,
                                    plugin_key=plugin_key, tenant_id=_tenant(tenant_id))]}


@marketplace_router.patch("/recommendations/{rec_id}")
def update_rec(rec_id: int, body: RecStatusUpdate, db: Session = Depends(get_db),
               _u=Depends(require_permission("marketplace.view"))):
    try:
        return marketplace.recommendation_dict(
            marketplace.set_recommendation_status(db, rec_id, body.status))
    except ValueError as ex:
        _bad(ex)


# ===========================================================================
# M5 / M6 — Scenario Planning
# ===========================================================================
scenario_router = APIRouter(prefix="/api/os/scenario", tags=["OS: Scenario Planning"])


@scenario_router.get("/library")
def scenario_library(_u=Depends(require_permission("simulation.run"))):
    return {"scenarios": scenario.SCENARIOS, "library": scenario.SCENARIO_LIBRARY}


@scenario_router.post("/run")
def run_scenarios(body: ScenarioRunRequest, tenant_id: Optional[int] = None,
                  db: Session = Depends(get_db),
                  user: User = Depends(require_permission("simulation.run"))):
    try:
        return scenario.run_plan(db, name=body.name, scope=body.scope, scope_ref=body.scope_ref,
                                 scenarios=body.scenarios, positions=body.positions,
                                 custom=body.custom, monte_carlo_draws=body.monte_carlo_draws,
                                 tenant_id=_tenant(tenant_id), user_id=getattr(user, "id", None),
                                 persist=body.persist)
    except ValueError as ex:
        _bad(ex)


@scenario_router.get("/plans")
def list_plans(tenant_id: Optional[int] = None, db: Session = Depends(get_db),
               _u=Depends(require_permission("simulation.run"))):
    return {"plans": [{"id": p.id, "name": p.name, "scope": p.scope, "scope_ref": p.scope_ref,
                       "created_at": p.created_at.isoformat() if p.created_at else None}
                      for p in scenario.list_plans(db, tenant_id=_tenant(tenant_id))]}


# ===========================================================================
# M13 — Model Governance: Fairness / Drift
# ===========================================================================
fairness_router = APIRouter(prefix="/api/os/fairness", tags=["OS: Fairness & Drift"])


@fairness_router.post("/evaluate")
def evaluate_fairness(body: FairnessRequest, tenant_id: Optional[int] = None,
                      db: Session = Depends(get_db),
                      _u=Depends(require_permission("governance.view"))):
    return fairness.run_fairness(db, model_key=body.model_key, records=body.records,
                                 protected_attribute=body.protected_attribute,
                                 tenant_id=_tenant(tenant_id))


@fairness_router.post("/drift")
def evaluate_drift(body: DriftRequest, tenant_id: Optional[int] = None,
                   db: Session = Depends(get_db),
                   _u=Depends(require_permission("governance.view"))):
    return fairness.run_drift(db, model_key=body.model_key, baseline=body.baseline,
                              current=body.current, tenant_id=_tenant(tenant_id))


@fairness_router.get("/history")
def fairness_history(model_key: Optional[str] = None, kind: Optional[str] = None,
                     tenant_id: Optional[int] = None, db: Session = Depends(get_db),
                     _u=Depends(require_permission("governance.view"))):
    return {"history": [fairness.run_dict(r) for r in
                        fairness.history(db, model_key=model_key, kind=kind,
                                         tenant_id=_tenant(tenant_id))]}


# ===========================================================================
# M1 — Knowledge Graph: advanced analytics
# ===========================================================================
graph_router = APIRouter(prefix="/api/os/graph", tags=["OS: Graph Analytics"])


@graph_router.get("/ubo/{company_ref}")
def ubo(company_ref: str, min_fraction: float = 0.10, tenant_id: Optional[int] = None,
        db: Session = Depends(get_db), _u=Depends(require_permission("intelligence.view"))):
    try:
        return graph_advanced.ultimate_beneficial_owners(db, company_ref,
                                                          min_fraction=min_fraction,
                                                          tenant_id=_tenant(tenant_id))
    except ValueError as ex:
        _bad(ex)


@graph_router.get("/connected-lending/{entity_ref}")
def connected_lending(entity_ref: str, max_depth: int = 3, tenant_id: Optional[int] = None,
                      db: Session = Depends(get_db),
                      _u=Depends(require_permission("intelligence.view"))):
    try:
        return graph_advanced.connected_lending(db, entity_ref, max_depth=max_depth,
                                                tenant_id=_tenant(tenant_id))
    except ValueError as ex:
        _bad(ex)


@graph_router.get("/cross-holdings")
def cross_holdings(tenant_id: Optional[int] = None, db: Session = Depends(get_db),
                   _u=Depends(require_permission("intelligence.view"))):
    return graph_advanced.cross_holdings(db, tenant_id=_tenant(tenant_id))


@graph_router.get("/timeline/{entity_ref}")
def timeline(entity_ref: str, tenant_id: Optional[int] = None, db: Session = Depends(get_db),
             _u=Depends(require_permission("intelligence.view"))):
    try:
        return graph_advanced.timeline(db, entity_ref, tenant_id=_tenant(tenant_id))
    except ValueError as ex:
        _bad(ex)


# ===========================================================================
# M10 — Executive Intelligence Center
# ===========================================================================
exec_router = APIRouter(prefix="/api/os/exec", tags=["OS: Executive Center"])


@exec_router.get("/personas")
def exec_personas(_u=Depends(require_permission("command.center"))):
    return {"personas": exec_center.PERSONAS}


@exec_router.get("/dashboard/{persona}")
def exec_dashboard(persona: str, tenant_id: Optional[int] = None, db: Session = Depends(get_db),
                   _u=Depends(require_permission("command.center"))):
    try:
        return exec_center.dashboard(db, persona, tenant_id=_tenant(tenant_id))
    except ValueError as ex:
        _bad(ex)


ROUTERS = [
    policy_router, committee_router, search_router, prompt_router, llm_router_api,
    fabric_router, workflow_router, marketplace_router, scenario_router, fairness_router,
    graph_router, exec_router,
]
