"""Financial Analysis API schemas.

Analysis results are deeply nested and engine-driven, so the GET endpoints
return the engine payload as-is (a JSON object). Only the ad-hoc compute request
needs a typed contract.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, model_validator


class AnalysisComputeRequest(BaseModel):
    """Compute an analysis without a persisted assessment.

    Provide exactly one financial source
      * ``financials`` — a mapping whose keys match ``FinancialStatement`` fields
      * ``document_fields`` — a ``DocumentExtraction.fields`` payload
    """

    financials: Optional[Dict[str, Any]] = None
    document_fields: Optional[List[Dict[str, Any]]] = None
    context: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Optional company profile (years_in_business, employee_count, "
        "business_expansion_stage) used by business-stability scoring.",
    )
    previous: Optional[Dict[str, Any]] = Field(
        default=None, description="Optional prior-period financials for growth analysis."
    )
    assessment_id: Optional[int] = None
    persist: bool = False

    @model_validator(mode="after")
    def _one_source(self) -> "AnalysisComputeRequest":
        if not self.financials and not self.document_fields:
            raise ValueError("Provide either 'financials' or 'document_fields'.")
        if self.financials and self.document_fields:
            raise ValueError("Provide only one of 'financials' or 'document_fields'.")
        return self
