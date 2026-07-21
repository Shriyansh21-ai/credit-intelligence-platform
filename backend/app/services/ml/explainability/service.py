"""Explanation service — features/vector -> explanation payload.

The single entrypoint the API and other layers call. Selects the model and the
explanation method, produces an :class:`Explanation`, and returns a serialisable
payload. Persistence is handled by :mod:`explanation_store`.
"""

from __future__ import annotations

from typing import Any, Optional

from backend.app.services.ml.inference import features_to_mapping
from backend.app.services.ml.models import get_model

from .registry import get_explainer


def explain_features(features: Any, *, model_type: Optional[str] = None,
                     method: Optional[str] = None) -> dict:
    """Explain a feature set (mapping, vector payload or feature list)."""
    model = get_model(model_type)
    mapping = features_to_mapping(features)
    explainer = get_explainer(method, model_trained=model.model_metadata().trained)
    explanation = explainer.explain(mapping, model)
    payload = explanation.as_dict()
    payload["model_metadata"] = model.model_metadata().as_dict()
    return payload


def explain_vector(vector: Any, *, model_type: Optional[str] = None,
                   method: Optional[str] = None) -> dict:
    """Explain a persisted/computed feature-vector payload."""
    return explain_features(vector, model_type=model_type, method=method)
