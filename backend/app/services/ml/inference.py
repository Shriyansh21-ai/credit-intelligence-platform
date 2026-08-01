"""Inference service — the single entrypoint from features to a risk prediction.

Bridges the Feature Store and the ML engine: it
accepts either a raw ``{feature_name: value}`` mapping or a full feature-vector
payload (as produced by :mod:`feature_pipeline` or persisted by the feature
store), selects a model via the registry, and returns a :class:`ModelPrediction`.

Business logic depends only on this service and the model interface, never on a
concrete algorithm.
"""

from __future__ import annotations

from typing import Any, Mapping, Optional

from .models import get_model
from .models.base import ModelPrediction


def features_to_mapping(features: Any) -> dict:
    """Normalise the several feature shapes into ``{feature_name: value}``.

    Accepts
      * a plain ``{name: value}`` mapping
      * a feature-vector payload with a ``features`` list of feature dicts
      * a bare list of feature dicts.
    """
    if isinstance(features, Mapping) and "features" in features:
        features = features["features"]
    if isinstance(features, Mapping):
        return dict(features)
    mapping: dict = {}
    for item in features or []:
        if isinstance(item, Mapping) and "feature_name" in item:
            mapping[item["feature_name"]] = item.get("value")
    return mapping


def run_inference(features: Any, model_type: Optional[str] = None) -> ModelPrediction:
    """Run risk inference over a feature set with the selected (or default)
    model."""
    model = get_model(model_type)
    return model.predict_risk(features_to_mapping(features))


def predict_from_vector(vector: Mapping, model_type: Optional[str] = None) -> dict:
    """Convenience for API/route callers: run inference on a feature-vector
    payload and return a serialisable prediction enriched with model metadata."""
    model = get_model(model_type)
    mapping = features_to_mapping(vector)
    prediction = model.predict_risk(mapping)
    payload = prediction.as_dict()
    payload["model_metadata"] = model.model_metadata().as_dict()
    payload["feature_importance"] = model.feature_importance()
    return payload
