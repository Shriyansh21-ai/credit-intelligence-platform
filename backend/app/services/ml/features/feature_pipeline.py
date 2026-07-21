"""Feature pipeline — high-level entrypoints for producing feature vectors.

Mirrors ``financial_analysis.analysis_service``: adapters accept the same input
shapes used elsewhere in the platform (an assessment ``engine_input``, a raw
financials mapping, or reviewed document fields) and return a single
serialisable payload that is *both* the API response shape and the persistence
input for :mod:`feature_store`.

The payload is a versioned feature vector: an ordered list of features plus a
category breakdown and coverage/confidence summary that a credit analyst — and a
future model — can consume directly.
"""

from __future__ import annotations

from typing import Any, List, Mapping, Optional

from backend.app.services.financial_analysis.ratio_engine import ratios_by_key
from backend.app.services.financial_analysis.statement import (
    FinancialStatement,
    from_document_fields,
    from_engine_input,
    from_mapping,
)

from .feature_builder import build_features
from .feature_registry import (
    CATEGORIES,
    FEATURE_SET_VERSION,
    Feature,
    FeatureContext,
    registry_metadata,
)

# Features below this confidence are surfaced for analyst attention (typically
# missing inputs, which read as confidence 0).
_LOW_CONFIDENCE = 0.5


def _summarise(features: List[Feature]) -> dict:
    by_category: dict = {cat: [] for cat in CATEGORIES}
    for feature in features:
        by_category.setdefault(feature.category, []).append(feature)

    category_summary = {}
    for cat, feats in by_category.items():
        populated = [f for f in feats if f.value is not None]
        confidences = [f.confidence for f in feats]
        category_summary[cat] = {
            "count": len(feats),
            "populated": len(populated),
            "mean_confidence": round(sum(confidences) / len(confidences), 3) if confidences else 0.0,
        }

    populated_total = sum(1 for f in features if f.value is not None)
    low_confidence = sum(1 for f in features if f.confidence < _LOW_CONFIDENCE)

    return {
        "features_by_category": {
            cat: [f.as_dict() for f in feats] for cat, feats in by_category.items()
        },
        "category_summary": category_summary,
        "feature_count": len(features),
        "populated_count": populated_total,
        "low_confidence_count": low_confidence,
        "coverage": round(populated_total / len(features), 4) if features else 0.0,
    }


def build_vector(ctx: FeatureContext) -> dict:
    """Materialise the full versioned feature vector for a context."""
    features = build_features(ctx)
    generated_time = features[0].generated_time if features else None
    summary = _summarise(features)
    return {
        "feature_set_version": FEATURE_SET_VERSION,
        "generated_time": generated_time,
        "period": ctx.statement.period.as_dict(),
        "features": [f.as_dict() for f in features],
        **summary,
        "registry": registry_metadata(),
    }


def _context(
    statement: FinancialStatement,
    engine_input: Optional[Mapping[str, Any]],
    previous: Optional[FinancialStatement],
) -> FeatureContext:
    return FeatureContext(
        statement=statement,
        ratios=ratios_by_key(statement),
        engine_input=dict(engine_input or {}),
        previous=previous,
        previous_ratios=ratios_by_key(previous) if previous is not None else {},
    )


def build_from_statement(
    statement: FinancialStatement,
    engine_input: Optional[Mapping[str, Any]] = None,
    previous: Optional[FinancialStatement] = None,
) -> dict:
    return build_vector(_context(statement, engine_input, previous))


def build_from_engine_input(
    engine_input: Mapping[str, Any],
    previous: Optional[FinancialStatement] = None,
) -> dict:
    """Build features from an enterprise assessment ``engine_input`` dict — the
    qualitative/banking context comes from the same dict."""
    statement = from_engine_input(engine_input)
    return build_vector(_context(statement, engine_input, previous))


def build_from_mapping(
    financials: Mapping[str, Any],
    context: Optional[Mapping[str, Any]] = None,
    previous: Optional[Mapping[str, Any]] = None,
) -> dict:
    prev_statement = from_mapping(previous) if previous else None
    return build_vector(_context(from_mapping(financials), context, prev_statement))


def build_from_document_fields(
    fields: Any,
    context: Optional[Mapping[str, Any]] = None,
) -> dict:
    return build_vector(_context(from_document_fields(fields), context, None))
