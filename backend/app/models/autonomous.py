"""Autonomous AI Banking Intelligence persistence (Phase 9).

Every table here is **additive** — nothing from Phases 1-8 is altered or dropped.
Schema is created by the Alembic migration ``d0e1f2a3b4c5_autonomous_intelligence_phase9``
(the app never calls ``create_all``).

The Phase 9 "AI Brain" layers sit on top of the existing deterministic engines,
ML platform, connectors and SaaS platform. To stay loosely coupled (and to avoid
cross-model FK-ordering pain in targeted test schemas) most rows reference a
company by a stable ``company_ref`` string (company name / GSTIN / PAN / CIN) and
optionally carry an ``assessment_id`` when they were derived from a concrete
:class:`EnterpriseAssessment`. Multi-tenancy is preserved by an optional
``tenant_id`` column (nullable → legacy single-tenant flows keep working).

Table groups:

* Knowledge Graph (M1)      — ``kg_entities``, ``kg_relationships``
* Monitoring (M2)           — ``monitoring_signals``
* Unified alerting (M2/3/11)— ``intelligence_alerts``
* Early Warning (M3)        — ``ews_assessments``
* AI Copilot (M4)           — ``copilot_conversations``, ``copilot_messages``
* Scenario simulation (M5)  — ``simulation_runs``
* Stress testing (M6)       — ``stress_test_runs``
* Portfolio optimization(M7)— ``portfolio_optimizations``
* RM workspace (M8)         — ``rm_interactions``, ``rm_opportunities``
* NL analytics (M10)        — ``nl_query_logs``
* Recommendations (M11)     — ``recommendations``
* Workflow intelligence(M12)— ``workflow_actions``
* Model governance (M13)    — ``model_governance_events``, ``model_validations``
* Data lake (M14)           — ``datalake_datasets``, ``datalake_objects``
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean, Column, DateTime, Float, ForeignKey, Integer, JSON, String, Text,
    UniqueConstraint,
)

from backend.app.db.database import Base


# ===========================================================================
# M1 — Enterprise Knowledge Graph
# ===========================================================================
class KGEntity(Base):
    """A node in the enterprise knowledge graph.

    ``entity_type`` is one of the taxonomy kinds (company, director, promoter,
    subsidiary, supplier, customer, lender, guarantor, shareholder, sector,
    region, collateral, connected_entity). ``ref`` is a stable external key
    (GSTIN / PAN / CIN / name) unique per tenant + type.
    """

    __tablename__ = "kg_entities"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, nullable=True, index=True)
    entity_type = Column(String, nullable=False, index=True)
    ref = Column(String, nullable=False, index=True)
    name = Column(String, nullable=False)
    attributes = Column(JSON, nullable=False, default=dict)
    # Cached intrinsic risk score 0-100 (higher = riskier); recomputed by service.
    risk_score = Column(Float, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("tenant_id", "entity_type", "ref", name="uq_kg_entity_ref"),
    )


class KGRelationship(Base):
    """A directed, weighted edge between two :class:`KGEntity` nodes."""

    __tablename__ = "kg_relationships"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, nullable=True, index=True)
    source_id = Column(Integer, ForeignKey("kg_entities.id"), nullable=False, index=True)
    target_id = Column(Integer, ForeignKey("kg_entities.id"), nullable=False, index=True)
    rel_type = Column(String, nullable=False, index=True)  # director_of|subsidiary_of|supplies|...
    # 0..1 relationship strength (edge weight for traversal + exposure decay).
    strength = Column(Float, nullable=False, default=0.5)
    # Optional monetary exposure carried along the edge (loans/guarantees).
    exposure = Column(Float, nullable=True)
    attributes = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("source_id", "target_id", "rel_type", name="uq_kg_edge"),
    )


# ===========================================================================
# M2 — Real-Time Risk Monitoring
# ===========================================================================
class MonitoringSignal(Base):
    """A single detected change on a monitored company from any source."""

    __tablename__ = "monitoring_signals"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, nullable=True, index=True)
    company_ref = Column(String, nullable=False, index=True)
    assessment_id = Column(Integer, nullable=True, index=True)
    source = Column(String, nullable=False, index=True)  # financial|connector|payment|gst|mca|bureau|portfolio|news|document|market
    signal_type = Column(String, nullable=False)
    direction = Column(String, nullable=False, default="neutral")  # positive|negative|neutral
    magnitude = Column(Float, nullable=True)
    severity = Column(String, nullable=False, default="info", index=True)  # info|low|medium|high|critical
    priority_score = Column(Float, nullable=False, default=0.0)
    detail = Column(Text, nullable=True)
    payload = Column(JSON, nullable=False, default=dict)
    detected_at = Column(DateTime, default=datetime.utcnow, index=True)


# ===========================================================================
# M2 / M3 / M11 — Unified intelligence alerts
# ===========================================================================
class IntelligenceAlert(Base):
    """A prioritized, actionable alert produced by monitoring/EWS/recommendation.

    ``category`` distinguishes the producing engine (monitoring|ews|recommendation
    |workflow). Alerts carry severity, a 0..1 confidence, a recommended action and
    supporting evidence, and follow a small open→ack→resolved lifecycle.
    """

    __tablename__ = "intelligence_alerts"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, nullable=True, index=True)
    company_ref = Column(String, nullable=False, index=True)
    assessment_id = Column(Integer, nullable=True, index=True)
    category = Column(String, nullable=False, index=True)
    alert_type = Column(String, nullable=False)
    title = Column(String, nullable=False)
    severity = Column(String, nullable=False, default="medium", index=True)
    confidence = Column(Float, nullable=False, default=0.5)
    priority_score = Column(Float, nullable=False, default=0.0, index=True)
    business_impact = Column(Text, nullable=True)
    recommended_action = Column(Text, nullable=True)
    evidence = Column(JSON, nullable=False, default=list)
    status = Column(String, nullable=False, default="open", index=True)  # open|acknowledged|resolved|dismissed
    dedup_key = Column(String, nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# ===========================================================================
# M3 — Early Warning Signal Engine
# ===========================================================================
class EWSAssessment(Base):
    """A stored Early-Warning run for a company: aggregate score + signals."""

    __tablename__ = "ews_assessments"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, nullable=True, index=True)
    company_ref = Column(String, nullable=False, index=True)
    assessment_id = Column(Integer, nullable=True, index=True)
    ews_score = Column(Float, nullable=False, default=0.0)  # 0-100, higher = more distress
    ews_band = Column(String, nullable=False, default="green")  # green|amber|red
    signal_count = Column(Integer, nullable=False, default=0)
    signals = Column(JSON, nullable=False, default=list)
    summary = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


# ===========================================================================
# M4 — AI Credit Copilot
# ===========================================================================
class CopilotConversation(Base):
    __tablename__ = "copilot_conversations"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, nullable=True, index=True)
    user_id = Column(Integer, nullable=True, index=True)
    title = Column(String, nullable=True)
    context_ref = Column(String, nullable=True)  # optional bound company/assessment
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class CopilotMessage(Base):
    __tablename__ = "copilot_messages"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("copilot_conversations.id"), nullable=False, index=True)
    role = Column(String, nullable=False)  # user|assistant|system
    content = Column(Text, nullable=False)
    intent = Column(String, nullable=True)
    provider = Column(String, nullable=True)  # local|claude
    # Deterministic data the answer was grounded in (never fabricated).
    grounding = Column(JSON, nullable=False, default=dict)
    citations = Column(JSON, nullable=False, default=list)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


# ===========================================================================
# M5 — Scenario Simulation Engine
# ===========================================================================
class SimulationRun(Base):
    __tablename__ = "simulation_runs"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, nullable=True, index=True)
    user_id = Column(Integer, nullable=True, index=True)
    company_ref = Column(String, nullable=True, index=True)
    assessment_id = Column(Integer, nullable=True, index=True)
    scenario_types = Column(JSON, nullable=False, default=list)
    shocks = Column(JSON, nullable=False, default=dict)
    baseline = Column(JSON, nullable=False, default=dict)
    result = Column(JSON, nullable=False, default=dict)
    delta = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


# ===========================================================================
# M6 — Stress Testing Framework
# ===========================================================================
class StressTestRun(Base):
    __tablename__ = "stress_test_runs"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, nullable=True, index=True)
    user_id = Column(Integer, nullable=True, index=True)
    scope = Column(String, nullable=False, default="portfolio")  # company|portfolio|industry|region
    scope_ref = Column(String, nullable=True)
    scenario = Column(String, nullable=False, default="severe")  # base|moderate|severe|custom
    custom_shocks = Column(JSON, nullable=True)
    positions = Column(Integer, nullable=False, default=0)
    result = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


# ===========================================================================
# M7 — Portfolio Optimization AI
# ===========================================================================
class PortfolioOptimization(Base):
    __tablename__ = "portfolio_optimizations"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, nullable=True, index=True)
    user_id = Column(Integer, nullable=True, index=True)
    objective = Column(String, nullable=False, default="risk_adjusted_return")
    constraints = Column(JSON, nullable=False, default=dict)
    result = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


# ===========================================================================
# M8 — Relationship Manager Workspace
# ===========================================================================
class RMInteraction(Base):
    """A timeline entry for a customer: call, email, meeting, note, visit."""

    __tablename__ = "rm_interactions"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, nullable=True, index=True)
    company_ref = Column(String, nullable=False, index=True)
    rm_user_id = Column(Integer, nullable=True, index=True)
    interaction_type = Column(String, nullable=False)  # call|email|meeting|visit|note|task
    subject = Column(String, nullable=True)
    detail = Column(Text, nullable=True)
    outcome = Column(String, nullable=True)
    occurred_at = Column(DateTime, default=datetime.utcnow, index=True)
    payload = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)


class RMOpportunity(Base):
    """A cross-sell / relationship-expansion opportunity for a customer."""

    __tablename__ = "rm_opportunities"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, nullable=True, index=True)
    company_ref = Column(String, nullable=False, index=True)
    product = Column(String, nullable=False)
    rationale = Column(Text, nullable=True)
    estimated_value = Column(Float, nullable=True)
    confidence = Column(Float, nullable=False, default=0.5)
    status = Column(String, nullable=False, default="identified")  # identified|pursuing|won|lost
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


# ===========================================================================
# M10 — Natural Language Analytics
# ===========================================================================
class NLQueryLog(Base):
    __tablename__ = "nl_query_logs"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, nullable=True, index=True)
    user_id = Column(Integer, nullable=True, index=True)
    question = Column(Text, nullable=False)
    intent = Column(String, nullable=True, index=True)
    structured_query = Column(JSON, nullable=False, default=dict)
    result_count = Column(Integer, nullable=True)
    confidence = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


# ===========================================================================
# M11 — Enterprise Recommendation Engine
# ===========================================================================
class Recommendation(Base):
    __tablename__ = "recommendations"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, nullable=True, index=True)
    company_ref = Column(String, nullable=False, index=True)
    assessment_id = Column(Integer, nullable=True, index=True)
    action = Column(String, nullable=False, index=True)  # approve|reject|increase_limit|...
    title = Column(String, nullable=False)
    reason = Column(Text, nullable=True)
    confidence = Column(Float, nullable=False, default=0.5)
    priority = Column(String, nullable=False, default="medium")
    evidence = Column(JSON, nullable=False, default=list)
    supporting_metrics = Column(JSON, nullable=False, default=dict)
    status = Column(String, nullable=False, default="proposed")  # proposed|accepted|rejected|expired
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


# ===========================================================================
# M12 — Autonomous Workflow Intelligence
# ===========================================================================
class WorkflowAction(Base):
    """A proactive action the AI proposed or took (task/reassess/escalate/etc.)."""

    __tablename__ = "workflow_actions"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, nullable=True, index=True)
    company_ref = Column(String, nullable=True, index=True)
    assessment_id = Column(Integer, nullable=True, index=True)
    action_type = Column(String, nullable=False, index=True)  # create_task|assign_reviewer|trigger_reassessment|...
    trigger = Column(String, nullable=True)
    rationale = Column(Text, nullable=True)
    params = Column(JSON, nullable=False, default=dict)
    mode = Column(String, nullable=False, default="proposed")  # proposed|executed
    status = Column(String, nullable=False, default="pending", index=True)  # pending|executed|skipped|failed
    result = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


# ===========================================================================
# M13 — Model Governance Platform
# ===========================================================================
class ModelGovernanceEvent(Base):
    """An auditable governance action over a Phase 6 registered model."""

    __tablename__ = "model_governance_events"

    id = Column(Integer, primary_key=True, index=True)
    model_id = Column(Integer, nullable=True, index=True)
    model_key = Column(String, nullable=True, index=True)
    version = Column(Integer, nullable=True)
    event_type = Column(String, nullable=False, index=True)  # validation|approval|deployment|rollback|champion_challenger|review
    actor = Column(String, nullable=True)
    detail = Column(Text, nullable=True)
    payload = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class ModelValidation(Base):
    """A formal validation report for a model version (gate before approval)."""

    __tablename__ = "model_validations"

    id = Column(Integer, primary_key=True, index=True)
    model_id = Column(Integer, nullable=True, index=True)
    model_key = Column(String, nullable=True, index=True)
    version = Column(Integer, nullable=True)
    status = Column(String, nullable=False, default="pending")  # passed|failed|pending|conditional
    checks = Column(JSON, nullable=False, default=list)
    metrics = Column(JSON, nullable=False, default=dict)
    validator = Column(String, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


# ===========================================================================
# M14 — Enterprise Data Lake
# ===========================================================================
class DataLakeDataset(Base):
    """Catalog entry for a logical analytical dataset (namespace)."""

    __tablename__ = "datalake_datasets"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, nullable=True, index=True)
    namespace = Column(String, nullable=False, index=True)
    description = Column(Text, nullable=True)
    schema_fields = Column(JSON, nullable=False, default=list)
    record_count = Column(Integer, nullable=False, default=0)
    last_ingested_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("tenant_id", "namespace", name="uq_datalake_ns"),
    )


class DataLakeObject(Base):
    """An immutable, content-hashed analytical record in the data lake.

    Append-only and read-optimized: transactional workloads are untouched;
    analytics read from here. Idempotent on ``(namespace, partition, content_hash)``.
    """

    __tablename__ = "datalake_objects"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, nullable=True, index=True)
    namespace = Column(String, nullable=False, index=True)
    partition = Column(String, nullable=True, index=True)  # e.g. 2026-07 or industry
    entity_ref = Column(String, nullable=True, index=True)
    content_hash = Column(String, nullable=False, index=True)
    content = Column(JSON, nullable=False, default=dict)
    ingested_at = Column(DateTime, default=datetime.utcnow, index=True)

    __table_args__ = (
        UniqueConstraint("namespace", "partition", "content_hash", name="uq_datalake_obj"),
    )
