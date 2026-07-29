"""AI Intelligence Platform persistence (Track 2).

Every table here is **additive** — nothing from Phases 1-11 / Track 1 is altered
or dropped. Schema is created by the Alembic migration
``f3a4b5c6d7e8_ai_platform_track2`` (the app never calls ``create_all``).

The Track 2 AI layer sits on top of every previous phase. To stay loosely
coupled (and avoid cross-model FK-ordering pain in targeted test schemas) rows
reference domain objects by stable string refs (``company_ref``, ``target_ref``)
and optionally carry an ``assessment_id`` when derived from a concrete
:class:`EnterpriseAssessment`. Multi-tenancy is preserved by an optional
nullable ``tenant_id`` column so legacy single-tenant flows keep working.

Table groups:
    Foundation      — aip_vectors
    M1  RAG         — aip_knowledge_sources, aip_documents, aip_chunks, aip_rag_queries
    M2  Agents      — aip_agent_runs, aip_agent_steps
    M3  Memory      — aip_memories, aip_memory_summaries
    M4  Prompts     — aip_prompts, aip_prompt_versions, aip_prompt_evals, aip_prompt_experiments
    M5  Evaluation  — aip_evaluations, aip_eval_cases
    M6  Investigate — aip_investigations, aip_investigation_steps
    M7  Reports     — aip_reports
    M8  Workflows   — aip_workflows, aip_workflow_runs
    M9  Chat        — aip_conversations, aip_messages
    M10 Research    — aip_research
    M11 Learning    — aip_feedback, aip_learning_signals, aip_training_events
    M12 Governance  — aip_ai_assets, aip_ai_asset_events
    M13 Explain     — aip_explanations
    M14 Monitoring  — aip_ai_metrics, aip_ai_incidents
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean, Column, DateTime, Float, ForeignKey, Integer, JSON, String, Text,
    UniqueConstraint,
)

from backend.app.db.database import Base


# ===========================================================================
# Foundation — unified vector store table (RAG chunks + memory + any retrieval)
# ===========================================================================
class AIPVector(Base):
    __tablename__ = "aip_vectors"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, nullable=True, index=True)
    namespace = Column(String, nullable=False, index=True)
    ref_type = Column(String, nullable=False, index=True)  # chunk | memory | ...
    ref_id = Column(String, nullable=False, index=True)
    model = Column(String, nullable=False, default="hashing")
    dim = Column(Integer, nullable=False, default=0)
    vector = Column(JSON, nullable=False, default=list)
    text = Column(Text, nullable=True)
    meta = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("tenant_id", "namespace", "ref_type", "ref_id",
                         name="uq_aip_vector_ref"),
    )


# ===========================================================================
# M1 — Enterprise RAG Platform
# ===========================================================================
class AIPKnowledgeSource(Base):
    __tablename__ = "aip_knowledge_sources"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, nullable=True, index=True)
    key = Column(String, nullable=False, index=True)
    name = Column(String, nullable=False)
    source_type = Column(String, nullable=False, index=True)  # policy|circular|basel|...
    description = Column(Text, nullable=True)
    config = Column(JSON, nullable=False, default=dict)
    status = Column(String, nullable=False, default="active")
    document_count = Column(Integer, nullable=False, default=0)
    created_by = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (UniqueConstraint("tenant_id", "key", name="uq_aip_ksource_key"),)


class AIPDocument(Base):
    __tablename__ = "aip_documents"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, nullable=True, index=True)
    source_id = Column(Integer, ForeignKey("aip_knowledge_sources.id"), nullable=False, index=True)
    external_id = Column(String, nullable=True, index=True)
    title = Column(String, nullable=False)
    uri = Column(String, nullable=True)
    doc_type = Column(String, nullable=True)
    language = Column(String, nullable=True, default="en")
    checksum = Column(String, nullable=True, index=True)
    version = Column(Integer, nullable=False, default=1)
    is_current = Column(Boolean, nullable=False, default=True)
    supersedes_id = Column(Integer, nullable=True)
    lineage = Column(JSON, nullable=False, default=dict)
    meta = Column(JSON, nullable=False, default=dict)
    chunk_count = Column(Integer, nullable=False, default=0)
    status = Column(String, nullable=False, default="indexed")
    created_by = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class AIPChunk(Base):
    __tablename__ = "aip_chunks"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, nullable=True, index=True)
    document_id = Column(Integer, ForeignKey("aip_documents.id"), nullable=False, index=True)
    source_id = Column(Integer, nullable=True, index=True)
    ordinal = Column(Integer, nullable=False, default=0)
    text = Column(Text, nullable=False)
    token_count = Column(Integer, nullable=False, default=0)
    meta = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)


class AIPRagQuery(Base):
    __tablename__ = "aip_rag_queries"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, nullable=True, index=True)
    question = Column(Text, nullable=False)
    answer = Column(Text, nullable=True)
    confidence = Column(Float, nullable=True)
    retrieved = Column(JSON, nullable=False, default=list)
    citations = Column(JSON, nullable=False, default=list)
    filters = Column(JSON, nullable=False, default=dict)
    provider = Column(String, nullable=True)
    total_tokens = Column(Integer, nullable=True)
    latency_ms = Column(Float, nullable=True)
    created_by = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


# ===========================================================================
# M2 — Multi-Agent AI System
# ===========================================================================
class AIPAgentRun(Base):
    __tablename__ = "aip_agent_runs"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, nullable=True, index=True)
    goal = Column(Text, nullable=False)
    company_ref = Column(String, nullable=True, index=True)
    assessment_id = Column(Integer, nullable=True, index=True)
    mode = Column(String, nullable=False, default="plan_execute")  # plan_execute|consensus|single
    status = Column(String, nullable=False, default="completed")
    roles = Column(JSON, nullable=False, default=list)
    plan = Column(JSON, nullable=False, default=list)
    result = Column(JSON, nullable=False, default=dict)
    consensus = Column(JSON, nullable=False, default=dict)
    confidence = Column(Float, nullable=True)
    provider = Column(String, nullable=True)
    total_tokens = Column(Integer, nullable=True)
    created_by = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)


class AIPAgentStep(Base):
    __tablename__ = "aip_agent_steps"

    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(Integer, ForeignKey("aip_agent_runs.id"), nullable=False, index=True)
    ordinal = Column(Integer, nullable=False, default=0)
    role = Column(String, nullable=False)
    action = Column(String, nullable=True)
    input = Column(JSON, nullable=False, default=dict)
    output = Column(Text, nullable=True)
    critique = Column(Text, nullable=True)
    score = Column(Float, nullable=True)
    status = Column(String, nullable=False, default="done")
    retries = Column(Integer, nullable=False, default=0)
    tokens = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


# ===========================================================================
# M3 — Long-Term Memory
# ===========================================================================
class AIPMemory(Base):
    __tablename__ = "aip_memories"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, nullable=True, index=True)
    memory_type = Column(String, nullable=False, index=True)  # semantic|episodic|procedural|...
    scope = Column(String, nullable=False, index=True)        # org|tenant|user|conversation|case|...
    scope_ref = Column(String, nullable=True, index=True)
    key = Column(String, nullable=True, index=True)
    content = Column(Text, nullable=False)
    importance = Column(Float, nullable=False, default=0.5)
    decay = Column(Float, nullable=False, default=0.0)
    access_count = Column(Integer, nullable=False, default=0)
    last_accessed = Column(DateTime, nullable=True)
    source = Column(String, nullable=True)
    meta = Column(JSON, nullable=False, default=dict)
    superseded = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class AIPMemorySummary(Base):
    __tablename__ = "aip_memory_summaries"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, nullable=True, index=True)
    scope = Column(String, nullable=False, index=True)
    scope_ref = Column(String, nullable=True, index=True)
    summary = Column(Text, nullable=False)
    covered_ids = Column(JSON, nullable=False, default=list)
    memory_count = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)


# ===========================================================================
# M4 — Prompt Engineering Platform
# ===========================================================================
class AIPPrompt(Base):
    __tablename__ = "aip_prompts"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, nullable=True, index=True)
    key = Column(String, nullable=False, index=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    task = Column(String, nullable=True, index=True)
    status = Column(String, nullable=False, default="active")
    current_version = Column(Integer, nullable=False, default=0)
    deployed_version = Column(Integer, nullable=True)
    tags = Column(JSON, nullable=False, default=list)
    created_by = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (UniqueConstraint("tenant_id", "key", name="uq_aip_prompt_key"),)


class AIPPromptVersion(Base):
    __tablename__ = "aip_prompt_versions"

    id = Column(Integer, primary_key=True, index=True)
    prompt_id = Column(Integer, ForeignKey("aip_prompts.id"), nullable=False, index=True)
    version = Column(Integer, nullable=False)
    template = Column(Text, nullable=False)
    system = Column(Text, nullable=True)
    variables = Column(JSON, nullable=False, default=list)
    model = Column(String, nullable=True)
    params = Column(JSON, nullable=False, default=dict)
    status = Column(String, nullable=False, default="draft")  # draft|in_review|approved|deployed|archived
    notes = Column(Text, nullable=True)
    eval_score = Column(Float, nullable=True)
    created_by = Column(String, nullable=True)
    approved_by = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (UniqueConstraint("prompt_id", "version", name="uq_aip_prompt_version"),)


class AIPPromptEval(Base):
    __tablename__ = "aip_prompt_evals"

    id = Column(Integer, primary_key=True, index=True)
    prompt_version_id = Column(Integer, ForeignKey("aip_prompt_versions.id"), nullable=False, index=True)
    dataset = Column(JSON, nullable=False, default=list)
    metrics = Column(JSON, nullable=False, default=dict)
    score = Column(Float, nullable=True)
    passed = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class AIPPromptExperiment(Base):
    __tablename__ = "aip_prompt_experiments"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, nullable=True, index=True)
    prompt_id = Column(Integer, ForeignKey("aip_prompts.id"), nullable=False, index=True)
    name = Column(String, nullable=False)
    variant_a_version = Column(Integer, nullable=False)
    variant_b_version = Column(Integer, nullable=False)
    allocation = Column(Float, nullable=False, default=0.5)
    status = Column(String, nullable=False, default="running")
    results = Column(JSON, nullable=False, default=dict)
    winner = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


# ===========================================================================
# M5 — AI Evaluation Framework
# ===========================================================================
class AIPEvaluation(Base):
    __tablename__ = "aip_evaluations"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, nullable=True, index=True)
    target_type = Column(String, nullable=False, index=True)  # rag|agent_run|report|prompt|answer
    target_ref = Column(String, nullable=True, index=True)
    suite = Column(String, nullable=False, default="default")
    metrics = Column(JSON, nullable=False, default=dict)
    scores = Column(JSON, nullable=False, default=dict)
    overall_score = Column(Float, nullable=True)
    passed = Column(Boolean, nullable=False, default=False)
    provider = Column(String, nullable=True)
    meta = Column(JSON, nullable=False, default=dict)
    created_by = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class AIPEvalCase(Base):
    __tablename__ = "aip_eval_cases"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, nullable=True, index=True)
    suite = Column(String, nullable=False, index=True)
    name = Column(String, nullable=False)
    input = Column(JSON, nullable=False, default=dict)
    expected = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)


# ===========================================================================
# M6 — Autonomous Investigation
# ===========================================================================
class AIPInvestigation(Base):
    __tablename__ = "aip_investigations"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, nullable=True, index=True)
    company_ref = Column(String, nullable=False, index=True)
    assessment_id = Column(Integer, nullable=True, index=True)
    status = Column(String, nullable=False, default="completed")
    plan = Column(JSON, nullable=False, default=list)
    findings = Column(JSON, nullable=False, default=dict)
    risk_summary = Column(JSON, nullable=False, default=dict)
    recommendation = Column(Text, nullable=True)
    confidence = Column(Float, nullable=True)
    report_id = Column(Integer, nullable=True)
    trace = Column(JSON, nullable=False, default=list)
    created_by = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)


class AIPInvestigationStep(Base):
    __tablename__ = "aip_investigation_steps"

    id = Column(Integer, primary_key=True, index=True)
    investigation_id = Column(Integer, ForeignKey("aip_investigations.id"), nullable=False, index=True)
    ordinal = Column(Integer, nullable=False, default=0)
    stage = Column(String, nullable=False)
    status = Column(String, nullable=False, default="done")
    output = Column(JSON, nullable=False, default=dict)
    evidence = Column(JSON, nullable=False, default=list)
    created_at = Column(DateTime, default=datetime.utcnow)


# ===========================================================================
# M7 — AI Report Generation
# ===========================================================================
class AIPReport(Base):
    __tablename__ = "aip_reports"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, nullable=True, index=True)
    report_type = Column(String, nullable=False, index=True)
    subject_ref = Column(String, nullable=True, index=True)
    assessment_id = Column(Integer, nullable=True, index=True)
    title = Column(String, nullable=False)
    sections = Column(JSON, nullable=False, default=list)
    evidence = Column(JSON, nullable=False, default=list)
    citations = Column(JSON, nullable=False, default=list)
    charts = Column(JSON, nullable=False, default=list)
    recommendations = Column(JSON, nullable=False, default=list)
    confidence = Column(Float, nullable=True)
    status = Column(String, nullable=False, default="final")
    format = Column(String, nullable=False, default="structured")
    provider = Column(String, nullable=True)
    created_by = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


# ===========================================================================
# M8 — AI Workflow Builder
# ===========================================================================
class AIPWorkflow(Base):
    __tablename__ = "aip_workflows"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, nullable=True, index=True)
    key = Column(String, nullable=False, index=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    graph = Column(JSON, nullable=False, default=dict)
    version = Column(Integer, nullable=False, default=1)
    status = Column(String, nullable=False, default="draft")
    tags = Column(JSON, nullable=False, default=list)
    created_by = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (UniqueConstraint("tenant_id", "key", name="uq_aip_workflow_key"),)


class AIPWorkflowRun(Base):
    __tablename__ = "aip_workflow_runs"

    id = Column(Integer, primary_key=True, index=True)
    workflow_id = Column(Integer, ForeignKey("aip_workflows.id"), nullable=False, index=True)
    tenant_id = Column(Integer, nullable=True, index=True)
    status = Column(String, nullable=False, default="completed")
    input = Column(JSON, nullable=False, default=dict)
    context = Column(JSON, nullable=False, default=dict)
    node_results = Column(JSON, nullable=False, default=list)
    error = Column(Text, nullable=True)
    created_by = Column(String, nullable=True)
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)


# ===========================================================================
# M9 — Enterprise Conversational AI
# ===========================================================================
class AIPConversation(Base):
    __tablename__ = "aip_conversations"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, nullable=True, index=True)
    title = Column(String, nullable=True)
    user_ref = Column(String, nullable=True, index=True)
    bindings = Column(JSON, nullable=False, default=dict)  # company_ref / assessment_id / portfolio
    status = Column(String, nullable=False, default="open")
    message_count = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class AIPMessage(Base):
    __tablename__ = "aip_messages"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("aip_conversations.id"), nullable=False, index=True)
    role = Column(String, nullable=False)  # user | assistant
    content = Column(Text, nullable=False)
    intent = Column(String, nullable=True)
    grounding = Column(JSON, nullable=False, default=dict)
    citations = Column(JSON, nullable=False, default=list)
    confidence = Column(Float, nullable=True)
    provider = Column(String, nullable=True)
    tokens = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


# ===========================================================================
# M10 — AI Research Assistant
# ===========================================================================
class AIPResearch(Base):
    __tablename__ = "aip_research"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, nullable=True, index=True)
    topic = Column(String, nullable=False)
    research_type = Column(String, nullable=False, index=True)  # industry|peer|sector|macro|esg|...
    subject_ref = Column(String, nullable=True, index=True)
    status = Column(String, nullable=False, default="completed")
    sections = Column(JSON, nullable=False, default=list)
    findings = Column(JSON, nullable=False, default=dict)
    sources = Column(JSON, nullable=False, default=list)
    confidence = Column(Float, nullable=True)
    report_id = Column(Integer, nullable=True)
    created_by = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)


# ===========================================================================
# M11 — Continuous Learning
# ===========================================================================
class AIPFeedback(Base):
    __tablename__ = "aip_feedback"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, nullable=True, index=True)
    target_type = Column(String, nullable=False, index=True)  # answer|report|recommendation|prediction
    target_ref = Column(String, nullable=True, index=True)
    feedback_type = Column(String, nullable=False, default="rating")  # rating|correction|approval|outcome
    rating = Column(Float, nullable=True)
    label = Column(String, nullable=True)
    comment = Column(Text, nullable=True)
    correction = Column(JSON, nullable=False, default=dict)
    user_ref = Column(String, nullable=True)
    meta = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)


class AIPLearningSignal(Base):
    __tablename__ = "aip_learning_signals"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, nullable=True, index=True)
    signal_type = Column(String, nullable=False, index=True)  # repayment|default|approval|correction|drift
    source = Column(String, nullable=True)
    target_ref = Column(String, nullable=True, index=True)
    payload = Column(JSON, nullable=False, default=dict)
    outcome = Column(String, nullable=True)
    processed = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class AIPTrainingEvent(Base):
    __tablename__ = "aip_training_events"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, nullable=True, index=True)
    trigger = Column(String, nullable=False)  # manual|scheduled|drift|volume|feedback
    dataset_ref = Column(String, nullable=True)
    model_ref = Column(String, nullable=True)
    status = Column(String, nullable=False, default="proposed")
    metrics = Column(JSON, nullable=False, default=dict)
    version = Column(String, nullable=True)
    notes = Column(Text, nullable=True)
    created_by = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


# ===========================================================================
# M12 — AI Governance
# ===========================================================================
class AIPAsset(Base):
    __tablename__ = "aip_ai_assets"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, nullable=True, index=True)
    asset_type = Column(String, nullable=False, index=True)  # prompt|model|dataset|agent|workflow|rag_index|report
    asset_ref = Column(String, nullable=False, index=True)
    name = Column(String, nullable=False)
    version = Column(String, nullable=False, default="1")
    state = Column(String, nullable=False, default="registered")  # registered|validated|approved|deployed|retired
    lineage = Column(JSON, nullable=False, default=dict)
    checksum = Column(String, nullable=True, index=True)
    owner = Column(String, nullable=True)
    meta = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("tenant_id", "asset_type", "asset_ref", "version",
                         name="uq_aip_asset_version"),
    )


class AIPAssetEvent(Base):
    __tablename__ = "aip_ai_asset_events"

    id = Column(Integer, primary_key=True, index=True)
    asset_id = Column(Integer, ForeignKey("aip_ai_assets.id"), nullable=False, index=True)
    event_type = Column(String, nullable=False)  # register|validate|approve|deploy|retire|use
    actor = Column(String, nullable=True)
    detail = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)


# ===========================================================================
# M13 — Explainable Enterprise AI
# ===========================================================================
class AIPExplanation(Base):
    __tablename__ = "aip_explanations"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, nullable=True, index=True)
    target_type = Column(String, nullable=False, index=True)  # prediction|answer|report|recommendation
    target_ref = Column(String, nullable=True, index=True)
    method = Column(String, nullable=False, default="contribution")  # shap|lime|counterfactual|tree|rule|nl
    contributions = Column(JSON, nullable=False, default=list)
    counterfactuals = Column(JSON, nullable=False, default=list)
    reasoning_chain = Column(JSON, nullable=False, default=list)
    evidence = Column(JSON, nullable=False, default=list)
    nl_explanation = Column(Text, nullable=True)
    confidence = Column(Float, nullable=True)
    confidence_interval = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)


# ===========================================================================
# M14 — AI Monitoring
# ===========================================================================
class AIPMetric(Base):
    __tablename__ = "aip_ai_metrics"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, nullable=True, index=True)
    metric_type = Column(String, nullable=False, index=True)  # hallucination|drift|latency|cost|accuracy|feedback|kpi
    subject = Column(String, nullable=True, index=True)
    value = Column(Float, nullable=False, default=0.0)
    unit = Column(String, nullable=True)
    window = Column(String, nullable=True)
    meta = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)


class AIPIncident(Base):
    __tablename__ = "aip_ai_incidents"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, nullable=True, index=True)
    incident_type = Column(String, nullable=False, index=True)
    severity = Column(String, nullable=False, default="info")  # info|low|medium|high|critical
    subject = Column(String, nullable=True, index=True)
    description = Column(Text, nullable=True)
    value = Column(Float, nullable=True)
    threshold = Column(Float, nullable=True)
    status = Column(String, nullable=False, default="open")
    detail = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)
