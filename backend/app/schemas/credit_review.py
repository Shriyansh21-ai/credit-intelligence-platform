"""Request schemas for enterprise credit reviews."""

from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class CreditReviewCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    company_id: int = Field(gt=0)
    review_type: Literal[
        "initial_assessment", "periodic_review", "renewal", "material_change"
    ] = "initial_assessment"
    title: str = Field(min_length=1, max_length=200)
    purpose: Optional[str] = Field(default=None, max_length=4000)
    due_date: Optional[date] = None


class CreditReviewAssignment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    analyst_id: int = Field(gt=0)
    reviewer_id: Optional[int] = Field(default=None, gt=0)


class EvidenceReferences(BaseModel):
    model_config = ConfigDict(extra="forbid")

    financial_ids: list[int] = Field(default_factory=list, max_length=100)
    document_ids: list[int] = Field(default_factory=list, max_length=100)


class AssessmentDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str = Field(default="", max_length=10000)
    strengths: list[str] = Field(default_factory=list, max_length=30)
    weaknesses: list[str] = Field(default_factory=list, max_length=30)
    risk_indicators: list[str] = Field(default_factory=list, max_length=30)
    data_quality_concerns: list[str] = Field(default_factory=list, max_length=30)
    mitigations: list[str] = Field(default_factory=list, max_length=30)
    outstanding_questions: list[str] = Field(default_factory=list, max_length=30)
    evidence_refs: EvidenceReferences = Field(default_factory=EvidenceReferences)
    recommendation: Literal[
        "recommend_approval",
        "recommend_approval_with_conditions",
        "recommend_decline",
        "request_information",
        "escalate",
    ] = "request_information"
    recommendation_rationale: str = Field(default="", max_length=10000)
    submit: bool = False


class DecisionCondition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    description: str = Field(min_length=1, max_length=4000)
    responsible_user_id: Optional[int] = Field(default=None, gt=0)
    due_date: Optional[date] = None


class CreditReviewDecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    outcome: Literal[
        "approved",
        "approved_with_conditions",
        "declined",
        "deferred",
        "returned_for_revision",
    ]
    rationale: str = Field(min_length=1, max_length=10000)
    conditions: list[DecisionCondition] = Field(default_factory=list, max_length=30)


class ResumeReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=1, max_length=4000)


class ConditionUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["completed", "waived"]
    notes: str = Field(min_length=1, max_length=4000)
