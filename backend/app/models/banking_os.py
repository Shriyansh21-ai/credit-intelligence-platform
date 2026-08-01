"""Enterprise Banking Operating System persistence.

Every table here is **additive** — nothing from Phases 1-9 is altered or dropped.
Schema is created by the Alembic migration ``e2f3a4b5c6d7_banking_os_phase10`` (the
app never calls ``create_all`` outside tests).

 turns the platform into an AI-native *operating system* for enterprise
banking. Like , rows reference a company/subject by a stable string
``*_ref`` (company name / GSTIN / PAN / CIN / application id) and preserve
multi-tenancy via a nullable ``tenant_id`` (legacy single-tenant flows keep
working with ``tenant_id = None``).

Table groups (this migration)

* Policy Engine (M7) — ``os_policies``, ``os_policy_versions``, ``os_policy_evaluations``
* Committee Workspace (M4) — ``os_committees``, ``os_committee_meetings``
                              ``os_agenda_items``, ``os_committee_votes``
* Enterprise Search (M2) — ``os_search_documents``, ``os_saved_searches``, ``os_search_history``
* Prompt Management (M8) — ``os_prompt_templates``, ``os_prompt_versions``, ``os_prompt_evaluations``
* Multi-LLM Layer (M9) — ``os_llm_providers``, ``os_llm_invocations``
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean, Column, DateTime, Float, ForeignKey, Integer, JSON, String, Text,
    UniqueConstraint,
)

from backend.app.db.database import Base


# ===========================================================================
# M7 — Enterprise Policy Engine
# ===========================================================================
class Policy(Base):
    """A named, versioned business-rule policy in a governance ``domain``.

    The active ruleset lives on the :class:`PolicyVersion` referenced by
    ``current_version``; the ``Policy`` row is the stable, human-facing handle
    (unique on ``tenant_id + key``). Policies are evaluated deterministically at
    runtime — no code, no LLM.
    """

    __tablename__ = "os_policies"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, nullable=True, index=True)
    key = Column(String, nullable=False, index=True)
    name = Column(String, nullable=False)
    domain = Column(String, nullable=False, index=True)  # loan|aml|kyc|exposure|sector|collateral|approval|country|risk_appetite|fraud
    description = Column(Text, nullable=True)
    status = Column(String, nullable=False, default="draft", index=True)  # draft|active|archived
    current_version = Column(Integer, nullable=False, default=0)
    tags = Column(JSON, nullable=False, default=list)
    created_by = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("tenant_id", "key", name="uq_os_policy_key"),
    )


class PolicyVersion(Base):
    """An immutable ruleset revision for a :class:`Policy`.

    ``rules`` is the no-code rule DSL: a list of
    ``{id, name, when:[conditions], then:{action, params}, priority, stop}``
    entries evaluated in priority order. Kept immutable so evaluations remain
    reproducible and auditable.
    """

    __tablename__ = "os_policy_versions"

    id = Column(Integer, primary_key=True, index=True)
    policy_id = Column(Integer, ForeignKey("os_policies.id"), nullable=False, index=True)
    version = Column(Integer, nullable=False)
    rules = Column(JSON, nullable=False, default=list)
    # combine mode when several rules match: first_match|highest_priority|all
    combine = Column(String, nullable=False, default="first_match")
    default_decision = Column(String, nullable=False, default="pass")
    status = Column(String, nullable=False, default="draft")  # draft|published
    notes = Column(Text, nullable=True)
    created_by = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    __table_args__ = (
        UniqueConstraint("policy_id", "version", name="uq_os_policy_version"),
    )


class PolicyEvaluation(Base):
    """A single deterministic evaluation of a policy against an input subject."""

    __tablename__ = "os_policy_evaluations"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, nullable=True, index=True)
    policy_id = Column(Integer, nullable=False, index=True)
    policy_key = Column(String, nullable=False, index=True)
    version = Column(Integer, nullable=False)
    subject_ref = Column(String, nullable=True, index=True)
    input = Column(JSON, nullable=False, default=dict)
    decision = Column(String, nullable=False, index=True)  # pass|refer|reject|flag|<custom>
    matched_rules = Column(JSON, nullable=False, default=list)
    actions = Column(JSON, nullable=False, default=list)
    reasons = Column(JSON, nullable=False, default=list)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


# ===========================================================================
# M4 — Loan Committee Workspace
# ===========================================================================
class Committee(Base):
    """A standing decision body (credit committee, ALCO, risk committee)."""

    __tablename__ = "os_committees"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, nullable=True, index=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    quorum = Column(Integer, nullable=False, default=1)
    # members: [{user_id, name, role, voting_weight}]
    members = Column(JSON, nullable=False, default=list)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class CommitteeMeeting(Base):
    """A convened committee session with an agenda, attendance and minutes."""

    __tablename__ = "os_committee_meetings"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, nullable=True, index=True)
    committee_id = Column(Integer, ForeignKey("os_committees.id"), nullable=False, index=True)
    title = Column(String, nullable=False)
    scheduled_at = Column(DateTime, nullable=True)
    status = Column(String, nullable=False, default="scheduled", index=True)  # scheduled|in_session|closed|cancelled
    location = Column(String, nullable=True)
    # attendees: [{user_id, name, present, joined_at}]
    attendees = Column(JSON, nullable=False, default=list)
    minutes = Column(Text, nullable=True)
    chair = Column(String, nullable=True)
    opened_at = Column(DateTime, nullable=True)
    closed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class AgendaItem(Base):
    """One decision item on a meeting agenda (usually a loan application)."""

    __tablename__ = "os_agenda_items"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, nullable=True, index=True)
    meeting_id = Column(Integer, ForeignKey("os_committee_meetings.id"), nullable=False, index=True)
    order_no = Column(Integer, nullable=False, default=0)
    title = Column(String, nullable=False)
    subject_ref = Column(String, nullable=True, index=True)  # company / application ref
    assessment_id = Column(Integer, nullable=True, index=True)
    presenter = Column(String, nullable=True)
    summary = Column(Text, nullable=True)
    proposed_action = Column(String, nullable=True)  # approve|reject|restructure|...
    amount = Column(Float, nullable=True)
    materials = Column(JSON, nullable=False, default=list)  # evidence/doc refs
    status = Column(String, nullable=False, default="pending", index=True)  # pending|tabled|decided|deferred
    decision = Column(String, nullable=True)  # approve|reject|defer|conditional
    decision_rationale = Column(Text, nullable=True)
    decided_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class CommitteeVote(Base):
    """A single member's vote on an agenda item (with a digital signature)."""

    __tablename__ = "os_committee_votes"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, nullable=True, index=True)
    agenda_item_id = Column(Integer, ForeignKey("os_agenda_items.id"), nullable=False, index=True)
    meeting_id = Column(Integer, nullable=False, index=True)
    voter_user_id = Column(Integer, nullable=True, index=True)
    voter_name = Column(String, nullable=True)
    vote = Column(String, nullable=False)  # approve|reject|abstain|defer
    weight = Column(Float, nullable=False, default=1.0)
    rationale = Column(Text, nullable=True)
    signature = Column(String, nullable=True)  # deterministic digital signature hash
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    __table_args__ = (
        UniqueConstraint("agenda_item_id", "voter_user_id", name="uq_os_vote_member"),
    )


# ===========================================================================
# M2 — Enterprise Search Engine
# ===========================================================================
class SearchDocument(Base):
    """A denormalized, indexable record for universal search.

    One row per searchable platform object (company, application, document
    report, alert, task, policy, model, …). ``terms`` caches the tokenized
    lowercased term list so ranking can run in-memory without re-tokenizing.
    """

    __tablename__ = "os_search_documents"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, nullable=True, index=True)
    doc_type = Column(String, nullable=False, index=True)  # company|application|document|report|alert|task|policy|model|transaction|...
    ref = Column(String, nullable=False, index=True)
    title = Column(String, nullable=False)
    body = Column(Text, nullable=True)
    keywords = Column(JSON, nullable=False, default=list)
    doc_metadata = Column(JSON, nullable=False, default=dict)
    url = Column(String, nullable=True)
    terms = Column(JSON, nullable=False, default=list)
    numeric_fields = Column(JSON, nullable=False, default=dict)  # filterable numerics (amount, score, pd)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("tenant_id", "doc_type", "ref", name="uq_os_search_doc"),
    )


class SavedSearch(Base):
    __tablename__ = "os_saved_searches"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, nullable=True, index=True)
    user_id = Column(Integer, nullable=True, index=True)
    name = Column(String, nullable=False)
    query = Column(String, nullable=False)
    filters = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class SearchHistory(Base):
    __tablename__ = "os_search_history"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, nullable=True, index=True)
    user_id = Column(Integer, nullable=True, index=True)
    query = Column(String, nullable=False)
    filters = Column(JSON, nullable=False, default=dict)
    result_count = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


# ===========================================================================
# M8 — Prompt Management Platform
# ===========================================================================
class PromptTemplate(Base):
    """A named, versioned LLM prompt (unique on ``tenant_id + key``)."""

    __tablename__ = "os_prompt_templates"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, nullable=True, index=True)
    key = Column(String, nullable=False, index=True)
    name = Column(String, nullable=False)
    category = Column(String, nullable=True, index=True)  # credit_memo|summary|explanation|committee_note|...
    description = Column(Text, nullable=True)
    current_version = Column(Integer, nullable=False, default=0)
    deployed_version = Column(Integer, nullable=True)
    status = Column(String, nullable=False, default="draft", index=True)  # draft|active|archived
    created_by = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("tenant_id", "key", name="uq_os_prompt_key"),
    )


class PromptVersion(Base):
    """An immutable revision of a prompt template."""

    __tablename__ = "os_prompt_versions"

    id = Column(Integer, primary_key=True, index=True)
    template_id = Column(Integer, ForeignKey("os_prompt_templates.id"), nullable=False, index=True)
    version = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    variables = Column(JSON, nullable=False, default=list)  # declared {{placeholders}}
    model_hint = Column(String, nullable=True)  # preferred provider/model
    params = Column(JSON, nullable=False, default=dict)  # temperature, max_tokens, ...
    status = Column(String, nullable=False, default="draft")  # draft|approved|deployed|archived
    approved_by = Column(String, nullable=True)
    approved_at = Column(DateTime, nullable=True)
    eval_score = Column(Float, nullable=True)
    created_by = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    __table_args__ = (
        UniqueConstraint("template_id", "version", name="uq_os_prompt_version"),
    )


class PromptEvaluation(Base):
    """A scored evaluation run of a prompt version against test cases."""

    __tablename__ = "os_prompt_evaluations"

    id = Column(Integer, primary_key=True, index=True)
    template_id = Column(Integer, nullable=False, index=True)
    version = Column(Integer, nullable=False)
    cases = Column(JSON, nullable=False, default=list)  # [{input, expected, output, score, passed}]
    score = Column(Float, nullable=False, default=0.0)
    passed = Column(Boolean, nullable=False, default=False)
    metrics = Column(JSON, nullable=False, default=dict)
    created_by = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


# ===========================================================================
# M9 — Multi-LLM Intelligence Layer
# ===========================================================================
class LLMProvider(Base):
    """A registered LLM backend with routing economics and health.

    Deterministic cost/latency/quality attributes drive the router; ``kind``
    identifies the vendor (openai|anthropic|gemini|llama|mistral|azure_openai|
    ollama|local). Only ``local`` is guaranteed available offline.
    """

    __tablename__ = "os_llm_providers"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, nullable=True, index=True)
    name = Column(String, nullable=False, index=True)
    kind = Column(String, nullable=False)  # openai|anthropic|gemini|llama|mistral|azure_openai|ollama|local
    model = Column(String, nullable=True)
    enabled = Column(Boolean, nullable=False, default=True)
    priority = Column(Integer, nullable=False, default=100)  # lower = preferred
    cost_per_1k_input = Column(Float, nullable=False, default=0.0)
    cost_per_1k_output = Column(Float, nullable=False, default=0.0)
    avg_latency_ms = Column(Float, nullable=False, default=0.0)
    quality_score = Column(Float, nullable=False, default=0.5)  # 0..1
    capabilities = Column(JSON, nullable=False, default=list)  # ["chat","json","long_context",...]
    config = Column(JSON, nullable=False, default=dict)
    is_available = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_os_llm_provider"),
    )


class LLMInvocation(Base):
    """A logged LLM call for cost/latency/quality analytics and routing feedback."""

    __tablename__ = "os_llm_invocations"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, nullable=True, index=True)
    provider = Column(String, nullable=False, index=True)
    kind = Column(String, nullable=True)
    strategy = Column(String, nullable=True)  # cost|latency|quality|priority|balanced
    prompt_ref = Column(String, nullable=True, index=True)
    tokens_in = Column(Integer, nullable=False, default=0)
    tokens_out = Column(Integer, nullable=False, default=0)
    latency_ms = Column(Float, nullable=False, default=0.0)
    cost = Column(Float, nullable=False, default=0.0)
    quality = Column(Float, nullable=True)
    success = Column(Boolean, nullable=False, default=True)
    fallback_used = Column(Boolean, nullable=False, default=False)
    routed_reason = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


# ===========================================================================
# M14 — Enterprise Data Fabric
# ===========================================================================
class Dataset(Base):
    """A catalog entry for a governed logical dataset (unique on ``tenant_id + name``).

    Carries ownership, classification, a declared schema and a cached quality
    score. Lineage edges and data contracts reference the dataset by ``name`` so
    the fabric stays loosely coupled to physical storage.
    """

    __tablename__ = "os_datasets"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, nullable=True, index=True)
    name = Column(String, nullable=False, index=True)
    domain = Column(String, nullable=True, index=True)  # credit|risk|customer|finance|ops|...
    description = Column(Text, nullable=True)
    owner = Column(String, nullable=True)
    source = Column(String, nullable=True)  # connector|ml|manual|derived
    classification = Column(String, nullable=False, default="internal")  # public|internal|confidential|restricted
    schema_fields = Column(JSON, nullable=False, default=list)  # [{name, type, nullable, description}]
    tags = Column(JSON, nullable=False, default=list)
    row_count = Column(Integer, nullable=False, default=0)
    quality_score = Column(Float, nullable=True)
    status = Column(String, nullable=False, default="active")  # active|deprecated|draft
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_os_dataset_name"),
    )


class DataLineageEdge(Base):
    """A directed lineage edge: ``upstream`` dataset feeds ``dataset`` via ``transform``."""

    __tablename__ = "os_data_lineage"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, nullable=True, index=True)
    dataset = Column(String, nullable=False, index=True)
    upstream = Column(String, nullable=False, index=True)
    transform = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("tenant_id", "dataset", "upstream", name="uq_os_lineage_edge"),
    )


class DataContract(Base):
    """A versioned data contract: the schema + constraints a dataset must satisfy."""

    __tablename__ = "os_data_contracts"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, nullable=True, index=True)
    dataset = Column(String, nullable=False, index=True)
    version = Column(Integer, nullable=False)
    # spec: {fields:[{name,type,nullable,allowed,min,max,pattern}], required:[...]}
    spec = Column(JSON, nullable=False, default=dict)
    status = Column(String, nullable=False, default="active")  # active|superseded
    created_by = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    __table_args__ = (
        UniqueConstraint("tenant_id", "dataset", "version", name="uq_os_contract_version"),
    )


class DataQualityRun(Base):
    """A stored data-quality evaluation of a dataset against its contract/checks."""

    __tablename__ = "os_data_quality_runs"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, nullable=True, index=True)
    dataset = Column(String, nullable=False, index=True)
    checks = Column(JSON, nullable=False, default=list)  # [{name, dimension, passed, detail}]
    score = Column(Float, nullable=False, default=0.0)  # 0..1
    passed = Column(Boolean, nullable=False, default=False)
    rows_checked = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


# ===========================================================================
# M11 — Enterprise Workflow Studio
# ===========================================================================
class WorkflowDefinition(Base):
    """A visual, versioned BPMN-like workflow (nodes + edges) — unique per key.

    ``graph`` is ``{nodes:[{id,type,name,config}], edges:[{from,to,condition}]}``
    node types: start, task, decision, approval, automation, notification, end.
    Executed deterministically by the workflow engine.
    """

    __tablename__ = "os_workflow_definitions"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, nullable=True, index=True)
    key = Column(String, nullable=False, index=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    version = Column(Integer, nullable=False, default=1)
    status = Column(String, nullable=False, default="draft", index=True)  # draft|active|archived
    graph = Column(JSON, nullable=False, default=dict)
    created_by = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("tenant_id", "key", "version", name="uq_os_workflow_key_version"),
    )


class WorkflowRun(Base):
    """An execution instance of a workflow definition with a full step trace."""

    __tablename__ = "os_workflow_runs"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, nullable=True, index=True)
    definition_key = Column(String, nullable=False, index=True)
    definition_version = Column(Integer, nullable=False, default=1)
    subject_ref = Column(String, nullable=True, index=True)
    status = Column(String, nullable=False, default="running", index=True)  # running|completed|failed|waiting|cancelled
    context = Column(JSON, nullable=False, default=dict)
    trace = Column(JSON, nullable=False, default=list)
    path = Column(JSON, nullable=False, default=list)
    current_node = Column(String, nullable=True)
    outputs = Column(JSON, nullable=False, default=dict)
    started_at = Column(DateTime, default=datetime.utcnow, index=True)
    finished_at = Column(DateTime, nullable=True)


# ===========================================================================
# M12 — AI Recommendation Marketplace
# ===========================================================================
class MarketplacePlugin(Base):
    """An installable recommendation plugin (built-in or custom) with config."""

    __tablename__ = "os_marketplace_plugins"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, nullable=True, index=True)
    key = Column(String, nullable=False, index=True)  # restructure_loan|increase_collateral|...
    name = Column(String, nullable=False)
    category = Column(String, nullable=True, index=True)
    description = Column(Text, nullable=True)
    version = Column(String, nullable=False, default="1.0.0")
    publisher = Column(String, nullable=True)
    installed = Column(Boolean, nullable=False, default=False)
    enabled = Column(Boolean, nullable=False, default=True)
    config = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("tenant_id", "key", name="uq_os_plugin_key"),
    )


class PluginRecommendation(Base):
    """A recommendation produced by a marketplace plugin for a subject."""

    __tablename__ = "os_plugin_recommendations"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, nullable=True, index=True)
    plugin_key = Column(String, nullable=False, index=True)
    subject_ref = Column(String, nullable=True, index=True)
    assessment_id = Column(Integer, nullable=True, index=True)
    action = Column(String, nullable=False)
    title = Column(String, nullable=False)
    rationale = Column(Text, nullable=True)
    confidence = Column(Float, nullable=False, default=0.5)
    priority = Column(String, nullable=False, default="medium")
    evidence = Column(JSON, nullable=False, default=list)
    params = Column(JSON, nullable=False, default=dict)
    status = Column(String, nullable=False, default="proposed", index=True)  # proposed|accepted|rejected
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


# ===========================================================================
# M5 / M6 — Digital Twin + Scenario Planning
# ===========================================================================
class ScenarioPlan(Base):
    """A saved multi-scenario plan (best/base/worst/stress/black-swan/custom) with
    Monte Carlo + sensitivity results over a portfolio or company."""

    __tablename__ = "os_scenario_plans"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, nullable=True, index=True)
    user_id = Column(Integer, nullable=True, index=True)
    name = Column(String, nullable=False)
    scope = Column(String, nullable=False, default="portfolio")  # portfolio|company|industry
    scope_ref = Column(String, nullable=True, index=True)
    scenarios = Column(JSON, nullable=False, default=list)
    result = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


# ===========================================================================
# M13 — Model Governance: Bias / Fairness / Drift
# ===========================================================================
class ModelFairnessRun(Base):
    """A deterministic fairness/bias/drift evaluation over a model's predictions."""

    __tablename__ = "os_model_fairness_runs"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, nullable=True, index=True)
    model_key = Column(String, nullable=False, index=True)
    kind = Column(String, nullable=False, default="fairness")  # fairness|drift
    protected_attribute = Column(String, nullable=True)
    metrics = Column(JSON, nullable=False, default=dict)
    groups = Column(JSON, nullable=False, default=list)
    passed = Column(Boolean, nullable=False, default=True)
    summary = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
