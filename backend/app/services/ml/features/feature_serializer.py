"""Feature serialisation — vector payload <-> persistence row / API shape.

Keeps the mapping between the pipeline payload and the ``FeatureVector`` ORM row
in one place, so the store and the API never duplicate field-plucking logic.
"""

from __future__ import annotations

from typing import Mapping

from backend.app.models.feature_vector import FeatureVector


def headline_columns(vector: Mapping) -> dict:
    """Extract the queryable headline columns from a pipeline payload."""
    period = vector.get("period", {}) or {}
    return {
        "feature_set_version": vector.get("feature_set_version", "1.0"),
        "generated_time": vector.get("generated_time"),
        "period_label": period.get("label"),
        "period_type": period.get("period_type", "annual"),
        "fiscal_year": period.get("fiscal_year"),
        "feature_count": vector.get("feature_count", 0),
        "populated_count": vector.get("populated_count", 0),
        "low_confidence_count": vector.get("low_confidence_count", 0),
        "coverage": vector.get("coverage", 0.0),
    }


def json_columns(vector: Mapping) -> dict:
    """Extract the JSON-blob columns from a pipeline payload."""
    return {
        "features": vector.get("features", []),
        "features_by_category": vector.get("features_by_category", {}),
        "category_summary": vector.get("category_summary", {}),
        "registry_metadata": vector.get("registry", {}),
    }


def serialize_record(record: FeatureVector) -> dict:
    """Reconstruct the API/pipeline payload from a persisted row."""
    return {
        "id": record.id,
        "assessment_id": record.assessment_id,
        "version": record.version,
        "is_current": record.is_current,
        "created_at": str(record.created_at) if record.created_at else None,
        "feature_set_version": record.feature_set_version,
        "generated_time": record.generated_time,
        "period": {
            "label": record.period_label,
            "period_type": record.period_type,
            "fiscal_year": record.fiscal_year,
        },
        "feature_count": record.feature_count,
        "populated_count": record.populated_count,
        "low_confidence_count": record.low_confidence_count,
        "coverage": record.coverage,
        "features": record.features or [],
        "features_by_category": record.features_by_category or {},
        "category_summary": record.category_summary or {},
        "registry": record.registry_metadata or {},
    }
