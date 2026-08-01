"""Pydantic request models for the Banking OS APIs.

Typed, additive schemas. Response payloads are plain dicts assembled by the
service ``*_dict`` serializers (mirroring the convention).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# M7 — Policy Engine
# ---------------------------------------------------------------------------
class PolicyCreate(BaseModel):
    key: str
    name: str
    domain: str
    description: Optional[str] = None
    tags: List[str] = Field(default_factory=list)


class PolicyVersionCreate(BaseModel):
    rules: List[Dict[str, Any]]
    combine: str = "first_match"
    default_decision: str = "pass"
    notes: Optional[str] = None
    publish: bool = False


class PolicyEvaluateRequest(BaseModel):
    data: Dict[str, Any]
    subject_ref: Optional[str] = None
    persist: bool = True


class PolicyDomainEvaluateRequest(BaseModel):
    domain: str
    data: Dict[str, Any]
    subject_ref: Optional[str] = None
    persist: bool = True


class PolicyPlaygroundRequest(BaseModel):
    rules: List[Dict[str, Any]]
    data: Dict[str, Any]
    combine: str = "first_match"
    default_decision: str = "pass"


# ---------------------------------------------------------------------------
# M4 — Committee Workspace
# ---------------------------------------------------------------------------
class CommitteeCreate(BaseModel):
    name: str
    description: Optional[str] = None
    quorum: int = 1
    members: List[Dict[str, Any]] = Field(default_factory=list)


class MeetingCreate(BaseModel):
    committee_id: int
    title: str
    scheduled_at: Optional[str] = None
    location: Optional[str] = None
    chair: Optional[str] = None


class AgendaItemCreate(BaseModel):
    meeting_id: int
    title: str
    subject_ref: Optional[str] = None
    assessment_id: Optional[int] = None
    presenter: Optional[str] = None
    summary: Optional[str] = None
    proposed_action: Optional[str] = None
    amount: Optional[float] = None
    materials: List[Dict[str, Any]] = Field(default_factory=list)
    order_no: Optional[int] = None


class VoteCreate(BaseModel):
    vote: str
    rationale: Optional[str] = None
    voter_name: Optional[str] = None
    weight: float = 1.0


class AttendanceUpdate(BaseModel):
    user_id: Optional[int] = None
    name: str
    present: bool = True


class MinutesUpdate(BaseModel):
    minutes: str


# ---------------------------------------------------------------------------
# M2 — Enterprise Search
# ---------------------------------------------------------------------------
class SearchRequest(BaseModel):
    query: str = ""
    doc_types: Optional[List[str]] = None
    filters: Dict[str, Any] = Field(default_factory=dict)
    mode: str = "hybrid"  # keyword|semantic|hybrid
    limit: int = 20
    persist: bool = True


class IndexDocumentRequest(BaseModel):
    doc_type: str
    ref: str
    title: str
    body: Optional[str] = None
    keywords: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    url: Optional[str] = None
    numeric_fields: Dict[str, float] = Field(default_factory=dict)


class SavedSearchCreate(BaseModel):
    name: str
    query: str
    filters: Dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# M8 — Prompt Management
# ---------------------------------------------------------------------------
class PromptCreate(BaseModel):
    key: str
    name: str
    category: Optional[str] = None
    description: Optional[str] = None


class PromptVersionCreate(BaseModel):
    content: str
    variables: List[str] = Field(default_factory=list)
    model_hint: Optional[str] = None
    params: Dict[str, Any] = Field(default_factory=dict)


class PromptEvaluateRequest(BaseModel):
    version: int
    cases: List[Dict[str, Any]]


class PromptRenderRequest(BaseModel):
    variables: Dict[str, Any] = Field(default_factory=dict)
    version: Optional[int] = None


# ---------------------------------------------------------------------------
# M9 — Multi-LLM Layer
# ---------------------------------------------------------------------------
class ProviderCreate(BaseModel):
    name: str
    kind: str
    model: Optional[str] = None
    priority: int = 100
    cost_per_1k_input: float = 0.0
    cost_per_1k_output: float = 0.0
    avg_latency_ms: float = 0.0
    quality_score: float = 0.5
    capabilities: List[str] = Field(default_factory=list)
    config: Dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True


class ProviderUpdate(BaseModel):
    enabled: Optional[bool] = None
    priority: Optional[int] = None
    quality_score: Optional[float] = None
    avg_latency_ms: Optional[float] = None
    is_available: Optional[bool] = None


class RouteRequest(BaseModel):
    strategy: str = "balanced"  # cost|latency|quality|priority|balanced
    capabilities: List[str] = Field(default_factory=list)
    est_tokens_in: int = 500
    est_tokens_out: int = 500


class CompletionRequest(BaseModel):
    prompt: str
    strategy: str = "balanced"
    capabilities: List[str] = Field(default_factory=list)
    prompt_ref: Optional[str] = None


# ---------------------------------------------------------------------------
# M14 — Enterprise Data Fabric
# ---------------------------------------------------------------------------
class DatasetCreate(BaseModel):
    name: str
    domain: Optional[str] = None
    description: Optional[str] = None
    owner: Optional[str] = None
    source: Optional[str] = None
    classification: str = "internal"
    schema_fields: List[Dict[str, Any]] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)


class LineageCreate(BaseModel):
    dataset: str
    upstream: str
    transform: Optional[str] = None


class ContractCreate(BaseModel):
    dataset: str
    spec: Dict[str, Any]


class QualityRunRequest(BaseModel):
    dataset: str
    records: List[Dict[str, Any]]
    spec: Optional[Dict[str, Any]] = None


# ---------------------------------------------------------------------------
# M11 — Workflow Studio
# ---------------------------------------------------------------------------
class WorkflowCreate(BaseModel):
    key: str
    name: str
    graph: Dict[str, Any]
    description: Optional[str] = None
    publish: bool = False


class WorkflowRunRequest(BaseModel):
    key: str
    context: Dict[str, Any] = Field(default_factory=dict)
    subject_ref: Optional[str] = None
    version: Optional[int] = None


class WorkflowResumeRequest(BaseModel):
    context_update: Dict[str, Any] = Field(default_factory=dict)


class WorkflowValidateRequest(BaseModel):
    graph: Dict[str, Any]


# ---------------------------------------------------------------------------
# M12 — Recommendation Marketplace
# ---------------------------------------------------------------------------
class PluginStateUpdate(BaseModel):
    installed: Optional[bool] = None
    enabled: Optional[bool] = None


class MarketplaceRunRequest(BaseModel):
    subject_ref: Optional[str] = None
    assessment_id: Optional[int] = None
    context: Dict[str, Any] = Field(default_factory=dict)
    persist: bool = True


class RecStatusUpdate(BaseModel):
    status: str


# ---------------------------------------------------------------------------
# M5 / M6 — Scenario Planning
# ---------------------------------------------------------------------------
class ScenarioRunRequest(BaseModel):
    name: str
    scope: str = "portfolio"
    scope_ref: Optional[str] = None
    scenarios: Optional[List[str]] = None
    positions: Optional[List[Dict[str, Any]]] = None
    custom: Optional[Dict[str, Any]] = None
    monte_carlo_draws: int = 2000
    persist: bool = True


# ---------------------------------------------------------------------------
# M13 — Fairness / Drift
# ---------------------------------------------------------------------------
class FairnessRequest(BaseModel):
    model_key: str
    records: List[Dict[str, Any]]
    protected_attribute: str = "group"


class DriftRequest(BaseModel):
    model_key: str
    baseline: List[float]
    current: List[float]
