"""ML facade — resolves an API request's financial source into a feature vector.

Keeps request-shape orchestration out of the routes: given the several accepted
input shapes (assessment engine input, raw financials, or a pre-built feature
mapping), it returns a feature-vector payload the rest of the ML layer consumes.
"""

from __future__ import annotations

from typing import Any, Mapping, Optional

from backend.app.services.financial_analysis.statement import from_mapping

from .features import feature_pipeline
from .features.feature_registry import FEATURE_SET_VERSION


def _wrap_feature_mapping(features: Mapping[str, Any]) -> dict:
    """Wrap a bare {name: value} mapping in a minimal vector payload so it flows
    through the same downstream path as a fully built vector."""
    feature_list = [{"feature_name": k, "value": v} for k, v in features.items()]
    return {
        "feature_set_version": FEATURE_SET_VERSION,
        "generated_time": None,
        "period": {"label": None, "period_type": "annual", "fiscal_year": None},
        "features": feature_list,
        "feature_count": len(feature_list),
        "populated_count": sum(1 for f in feature_list if f["value"] is not None),
        "low_confidence_count": 0,
        "coverage": 0.0,
        "features_by_category": {},
        "category_summary": {},
        "registry": {},
        "source": "provided_features",
    }


def vector_from_source(
    *,
    engine_input: Optional[Mapping[str, Any]] = None,
    financials: Optional[Mapping[str, Any]] = None,
    context: Optional[Mapping[str, Any]] = None,
    previous: Optional[Mapping[str, Any]] = None,
    features: Optional[Mapping[str, Any]] = None,
) -> dict:
    """Build a feature-vector payload from whichever source was provided."""
    if features:
        return _wrap_feature_mapping(features)
    if engine_input:
        prev = from_mapping(previous) if previous else None
        return feature_pipeline.build_from_engine_input(engine_input, previous=prev)
    if financials:
        return feature_pipeline.build_from_mapping(financials, context=context, previous=previous)
    # Empty source -> an all-missing vector (still valid, all features None).
    return feature_pipeline.build_from_mapping({})
