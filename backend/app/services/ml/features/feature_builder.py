"""Feature builder — materialises the registry against a context.

Given a :class:`FeatureContext`, this evaluates every registered definition into
a :class:`Feature` carrying its value plus full provenance (source, version
generation time and a confidence score). Confidence encodes how much a downstream
model should trust the value

* ``0.0`` - the input was missing, so ``value`` is ``None``.
* ``base * 0.7`` - the value is real but derived from an *estimated* balance
  sheet (total assets inferred from the accounting identity).
* ``base`` - the value is computed directly from reported figures.

Nothing here fabricates data: an absent feature is reported honestly with a
``None`` value and zero confidence.
"""

from __future__ import annotations

from datetime import datetime
from typing import List

from .feature_registry import (
    Feature,
    FeatureContext,
    FeatureDefinition,
    get_registry,
)

# Confidence discount applied to asset-based features when total assets are an
# estimate rather than a reported figure.
_ESTIMATED_ASSETS_DISCOUNT = 0.7


def _confidence(defn: FeatureDefinition, value, ctx: FeatureContext) -> float:
    if value is None:
        return 0.0
    conf = defn.base_confidence
    if defn.depends_on_assets and ctx.statement.total_assets_is_estimated:
        conf *= _ESTIMATED_ASSETS_DISCOUNT
    return round(conf, 3)


def build_feature(defn: FeatureDefinition, ctx: FeatureContext, generated_time: str) -> Feature:
    value = defn.compute(ctx)
    return Feature(
        feature_name=defn.name,
        category=defn.category,
        description=defn.description,
        value=value,
        unit=defn.unit,
        version=defn.version,
        source=defn.source,
        confidence=_confidence(defn, value, ctx),
        generated_time=generated_time,
    )


def build_features(ctx: FeatureContext) -> List[Feature]:
    """Compute every registered feature for ``ctx``, preserving registry order.

    A single ``generated_time`` stamp is shared across the vector so the whole
    vector is treated as one atomic generation event.
    """
    generated_time = datetime.utcnow().isoformat()
    return [build_feature(defn, ctx, generated_time) for defn in get_registry()]
