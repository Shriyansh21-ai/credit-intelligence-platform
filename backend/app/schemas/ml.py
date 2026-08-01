"""Enterprise AI Risk Intelligence API schemas.

ML payloads (feature vectors, predictions, explanations) are engine-driven and
deeply nested, so the GET endpoints return the engine payload as-is. Only the
ad-hoc POST requests need a typed contract.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, model_validator


class _FinancialSource(BaseModel):
    """A financials source shared by the ML compute endpoints.

    Provide exactly one of
      * ``engine_input`` — a flattened assessment engine-input dict (has banking
        and qualitative fields, so it yields the richest feature set), or
      * ``financials`` — a mapping whose keys match ``FinancialStatement`` fields.
    ``features`` may be supplied directly to skip feature building entirely.
    """

    engine_input: Optional[Dict[str, Any]] = None
    financials: Optional[Dict[str, Any]] = None
    context: Optional[Dict[str, Any]] = None
    previous: Optional[Dict[str, Any]] = None
    features: Optional[Dict[str, Any]] = Field(
        default=None, description="Raw {feature_name: value} mapping (bypasses feature building)."
    )
    # When set, the route resolves the persisted assessment's saved engine input
    # as the source — so any ML endpoint can be driven by a saved assessment.
    assessment_id: Optional[int] = None

    @model_validator(mode="after")
    def _one_source(self) -> "_FinancialSource":
        provided = [
            s for s in (self.engine_input, self.financials, self.features, self.assessment_id)
            if s
        ]
        if not provided:
            raise ValueError(
                "Provide one of 'engine_input', 'financials', 'features' or 'assessment_id'."
            )
        return self


class FeatureComputeRequest(_FinancialSource):
    persist: bool = False


class PredictRequest(_FinancialSource):
    model_type: Optional[str] = Field(
        default=None, description="Registered model_type; defaults to the configured model."
    )


class ExplainRequest(_FinancialSource):
    model_type: Optional[str] = None
    method: Optional[str] = Field(
        default=None, description="Explanation method: auto | contribution | shap | lime."
    )
    persist: bool = False


class ScenarioRequest(_FinancialSource):
    """A what-if scenario: a set of deltas applied to the base inputs."""

    adjustments: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="List of {factor, mode, amount} adjustments to apply.",
    )
    model_type: Optional[str] = None


class StressTestRequest(_FinancialSource):
    scenarios: Optional[List[str]] = Field(
        default=None, description="Named stress scenarios to run; all if omitted."
    )
    model_type: Optional[str] = None


class AlertScanRequest(_FinancialSource):
    persist: bool = False


class ReportRequest(_FinancialSource):
    model_type: Optional[str] = None
