"""Pydantic v2 request schemas for the Phase 9 Autonomous Intelligence APIs.

Responses are plain dicts assembled by the service layer (kept deliberately
flexible); only inbound bodies are typed here.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# -- Knowledge Graph (M1) ---------------------------------------------------
class EntityCreate(BaseModel):
    entity_type: str
    ref: str
    name: Optional[str] = None
    attributes: Dict[str, Any] = Field(default_factory=dict)
    risk_score: Optional[float] = None


class RelationshipCreate(BaseModel):
    source_id: int
    target_id: int
    rel_type: str
    strength: Optional[float] = None
    exposure: Optional[float] = None
    attributes: Dict[str, Any] = Field(default_factory=dict)


class GraphIngest(BaseModel):
    company_ref: str
    relationships: List[Dict[str, Any]] = Field(default_factory=list)


class GraphSeed(BaseModel):
    assessment_id: Optional[int] = None
    company_ref: Optional[str] = None


# -- Monitoring (M2) --------------------------------------------------------
class MonitoringRun(BaseModel):
    company_ref: str
    assessment_id: Optional[int] = None
    observations: Dict[str, Any] = Field(default_factory=dict)
    exposure: Optional[float] = None
    escalate: bool = True


# -- EWS (M3) ---------------------------------------------------------------
class EWSRequest(BaseModel):
    company_ref: Optional[str] = None
    assessment_id: Optional[int] = None
    context: Dict[str, Any] = Field(default_factory=dict)
    persist: bool = True


# -- Alerts -----------------------------------------------------------------
class AlertStatusUpdate(BaseModel):
    status: str


# -- Copilot (M4) -----------------------------------------------------------
class CopilotAsk(BaseModel):
    question: str
    conversation_id: Optional[int] = None
    company_ref: Optional[str] = None
    assessment_id: Optional[int] = None
    provider: Optional[str] = None


# -- Simulation (M5) --------------------------------------------------------
class SimulationRequest(BaseModel):
    shocks: Dict[str, float]
    company_ref: Optional[str] = None
    assessment_id: Optional[int] = None
    persist: bool = True


# -- Stress (M6) ------------------------------------------------------------
class StressRequest(BaseModel):
    scenario: str = "severe"
    scope: str = "portfolio"
    scope_ref: Optional[str] = None
    custom_shocks: Optional[Dict[str, float]] = None
    persist: bool = True


# -- Portfolio optimization (M7) --------------------------------------------
class OptimizationRequest(BaseModel):
    objective: str = "risk_adjusted_return"
    constraints: Dict[str, Any] = Field(default_factory=dict)
    persist: bool = False


# -- RM workspace (M8) ------------------------------------------------------
class InteractionCreate(BaseModel):
    company_ref: str
    interaction_type: str
    subject: Optional[str] = None
    detail: Optional[str] = None
    outcome: Optional[str] = None
    payload: Dict[str, Any] = Field(default_factory=dict)


class OpportunityCreate(BaseModel):
    company_ref: str
    product: str
    rationale: Optional[str] = None
    estimated_value: Optional[float] = None
    confidence: float = 0.5


# -- NL analytics (M10) -----------------------------------------------------
class NLQueryRequest(BaseModel):
    question: str
    persist: bool = True


# -- Recommendations (M11) --------------------------------------------------
class RecommendRequest(BaseModel):
    company_ref: Optional[str] = None
    assessment_id: Optional[int] = None
    context: Dict[str, Any] = Field(default_factory=dict)
    persist: bool = True


class RecommendationStatusUpdate(BaseModel):
    status: str


# -- Workflow intelligence (M12) --------------------------------------------
class WorkflowRunRequest(BaseModel):
    company_ref: Optional[str] = None
    assessment_id: Optional[int] = None
    mode: str = "proposed"


# -- Governance (M13) -------------------------------------------------------
class ValidateRequest(BaseModel):
    thresholds: Optional[Dict[str, float]] = None


class GovernanceApprove(BaseModel):
    require_validation: bool = True


# -- Data lake (M14) --------------------------------------------------------
class DataLakeIngest(BaseModel):
    namespace: str
    content: Dict[str, Any]
    partition: Optional[str] = None
    entity_ref: Optional[str] = None


class DataLakeAggregate(BaseModel):
    namespace: str
    group_by: str
    metric: Optional[str] = None
    agg: str = "count"
