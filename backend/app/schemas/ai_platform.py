"""Inbound Pydantic schemas for the AI Intelligence Platform APIs.

Request bodies only — responses are plain JSON dicts assembled by the services
(mirroring the /10 convention). Grouped by milestone.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# --- M1 RAG ---------------------------------------------------------------
class SourceCreate(BaseModel):
    key: str
    name: str
    source_type: str = "other"
    description: Optional[str] = None
    config: Dict[str, Any] = Field(default_factory=dict)


class DocumentIngest(BaseModel):
    title: str
    text: str
    source_key: Optional[str] = None
    source_id: Optional[int] = None
    doc_type: Optional[str] = None
    external_id: Optional[str] = None
    uri: Optional[str] = None
    language: str = "en"
    metadata: Dict[str, Any] = Field(default_factory=dict)
    chunk_size: int = 900
    overlap: int = 150


class RagSearch(BaseModel):
    query: str
    top_k: int = 5
    source_types: Optional[List[str]] = None
    doc_type: Optional[str] = None
    metadata_filter: Optional[Dict[str, Any]] = None
    semantic_weight: float = 0.6


class RagAnswer(BaseModel):
    question: str
    top_k: int = 5
    source_types: Optional[List[str]] = None
    doc_type: Optional[str] = None
    metadata_filter: Optional[Dict[str, Any]] = None
    provider: Optional[str] = None


# --- M2 Multi-agent -------------------------------------------------------
class AgentRunRequest(BaseModel):
    goal: str
    company_ref: Optional[str] = None
    assessment_id: Optional[int] = None
    roles: Optional[List[str]] = None
    mode: str = "plan_execute"
    parallel: bool = False
    provider: Optional[str] = None


class PlanRequest(BaseModel):
    goal: str
    roles: Optional[List[str]] = None


# --- M3 Memory ------------------------------------------------------------
class MemoryWrite(BaseModel):
    content: str
    memory_type: str = "semantic"
    scope: str = "organization"
    scope_ref: Optional[str] = None
    key: Optional[str] = None
    importance: float = 0.5
    decay: float = 0.02
    source: Optional[str] = None
    related_ids: Optional[List[int]] = None
    meta: Dict[str, Any] = Field(default_factory=dict)


class MemoryRecall(BaseModel):
    query: str
    scope: str = "organization"
    scope_ref: Optional[str] = None
    memory_type: Optional[str] = None
    top_k: int = 5


class MemoryLink(BaseModel):
    memory_id: int
    related_id: int


class MemorySummarize(BaseModel):
    scope: str
    scope_ref: Optional[str] = None


class MemoryForget(BaseModel):
    scope: Optional[str] = None
    threshold: float = 0.15
    hard_delete: bool = False


# --- M4 Prompts -----------------------------------------------------------
class PromptCreate(BaseModel):
    key: str
    name: str
    description: Optional[str] = None
    task: Optional[str] = None
    tags: List[str] = Field(default_factory=list)


class PromptVersionCreate(BaseModel):
    prompt_id: Optional[int] = None
    key: Optional[str] = None
    template: str
    system: Optional[str] = None
    model: Optional[str] = None
    params: Dict[str, Any] = Field(default_factory=dict)
    variables: Optional[List[str]] = None
    notes: Optional[str] = None


class PromptRender(BaseModel):
    key: Optional[str] = None
    prompt_id: Optional[int] = None
    version: Optional[int] = None
    variables: Dict[str, Any] = Field(default_factory=dict)


class PromptEvalRequest(BaseModel):
    version_id: int
    dataset: Optional[List[Dict[str, Any]]] = None


class PromptApprove(BaseModel):
    version_id: int


class PromptDeploy(BaseModel):
    prompt_id: int
    version: int


class ExperimentStart(BaseModel):
    prompt_id: int
    name: str
    variant_a_version: int
    variant_b_version: int
    allocation: float = 0.5


class ExperimentResult(BaseModel):
    experiment_id: int
    variant: str
    score: float


# --- M5 Evaluation --------------------------------------------------------
class EvaluateRequest(BaseModel):
    target_type: str = "answer"
    output_text: str
    grounding_text: str = ""
    citations: Optional[List[Any]] = None
    expected: Optional[str] = None
    expected_decision: Optional[str] = None
    samples: Optional[List[str]] = None
    usage: Optional[Dict[str, Any]] = None
    target_ref: Optional[str] = None
    suite: str = "default"
    require_citations: bool = True


class EvalCaseCreate(BaseModel):
    suite: str
    name: str
    input: Dict[str, Any] = Field(default_factory=dict)
    expected: Dict[str, Any] = Field(default_factory=dict)


# --- M6 Investigation -----------------------------------------------------
class InvestigateRequest(BaseModel):
    company_ref: Optional[str] = None
    assessment_id: Optional[int] = None
    provider: Optional[str] = None


# --- M7 Reports -----------------------------------------------------------
class ReportRequest(BaseModel):
    report_type: str
    company_ref: Optional[str] = None
    assessment_id: Optional[int] = None
    title: Optional[str] = None
    provider: Optional[str] = None


# --- M8 Workflows ---------------------------------------------------------
class WorkflowSave(BaseModel):
    key: str
    name: str
    graph: Dict[str, Any]
    description: Optional[str] = None
    tags: List[str] = Field(default_factory=list)


class WorkflowRunRequest(BaseModel):
    workflow_id: Optional[int] = None
    key: Optional[str] = None
    input: Dict[str, Any] = Field(default_factory=dict)
    provider: Optional[str] = None


# --- M9 Chat --------------------------------------------------------------
class ConversationCreate(BaseModel):
    title: Optional[str] = None
    bindings: Dict[str, Any] = Field(default_factory=dict)


class ChatAsk(BaseModel):
    conversation_id: int
    message: str
    provider: Optional[str] = None


# --- M10 Research ---------------------------------------------------------
class ResearchRequest(BaseModel):
    topic: str
    research_type: str = "sector_analysis"
    subject_ref: Optional[str] = None
    provider: Optional[str] = None


# --- M11 Continuous Learning ----------------------------------------------
class FeedbackCreate(BaseModel):
    target_type: str
    target_ref: Optional[str] = None
    feedback_type: str = "rating"
    rating: Optional[float] = None
    label: Optional[str] = None
    comment: Optional[str] = None
    correction: Dict[str, Any] = Field(default_factory=dict)


class SignalCreate(BaseModel):
    signal_type: str
    target_ref: Optional[str] = None
    source: Optional[str] = None
    payload: Dict[str, Any] = Field(default_factory=dict)
    outcome: Optional[str] = None


class TriggerRequest(BaseModel):
    thresholds: Optional[Dict[str, int]] = None
    create_events: bool = True


class TrainingEventUpdate(BaseModel):
    event_id: int
    status: Optional[str] = None
    metrics: Optional[Dict[str, Any]] = None
    model_ref: Optional[str] = None


# --- M12 Governance -------------------------------------------------------
class AssetRegister(BaseModel):
    asset_type: str
    asset_ref: str
    name: str
    version: str = "1"
    lineage: Dict[str, Any] = Field(default_factory=dict)
    owner: Optional[str] = None
    meta: Dict[str, Any] = Field(default_factory=dict)


class AssetTransition(BaseModel):
    asset_id: int
    action: str
    detail: Dict[str, Any] = Field(default_factory=dict)


# --- M13 Explainability ---------------------------------------------------
class ExplainRequest(BaseModel):
    target_type: str = "prediction"
    company_ref: Optional[str] = None
    assessment_id: Optional[int] = None
    target_ref: Optional[str] = None
    method: str = "all"
    provider: Optional[str] = None


# --- M14 Monitoring -------------------------------------------------------
class MetricRecord(BaseModel):
    metric_type: str
    value: float
    subject: Optional[str] = None
    unit: Optional[str] = None
    window: Optional[str] = None
    meta: Dict[str, Any] = Field(default_factory=dict)
