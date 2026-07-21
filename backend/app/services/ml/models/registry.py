"""Model registry — configurable, extensible model selection.

Model choice is never hardcoded in business logic. Callers ask the registry for
a model by ``model_type`` (or take the configured default), and new algorithms
are added by registering a class. The default is read from configuration
(``ML_DEFAULT_MODEL``), so deployments can switch the active model without code
changes.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Type

from backend.app.config import settings

from .base import BaseRiskModel
from .catalog import CATALOG

_REGISTRY: Dict[str, Type[BaseRiskModel]] = {cls.model_type: cls for cls in CATALOG}

_FALLBACK_DEFAULT = "scorecard"


def register_model(model_cls: Type[BaseRiskModel]) -> None:
    """Register (or override) a model class by its ``model_type``."""
    if not getattr(model_cls, "model_type", None):
        raise ValueError("Model class must define a non-empty 'model_type'.")
    _REGISTRY[model_cls.model_type] = model_cls


def registered_types() -> List[str]:
    return list(_REGISTRY)


def default_model_type() -> str:
    """The configured default model, falling back to the scorecard if the
    configured value is unknown."""
    configured = getattr(settings, "ML_DEFAULT_MODEL", None)
    if configured and configured in _REGISTRY:
        return configured
    return _FALLBACK_DEFAULT if _FALLBACK_DEFAULT in _REGISTRY else next(iter(_REGISTRY))


def get_model(model_type: Optional[str] = None) -> BaseRiskModel:
    """Instantiate a model by type (or the configured default) and load any
    trained artifact. Unknown types raise a clear error."""
    resolved = model_type or default_model_type()
    if resolved not in _REGISTRY:
        raise KeyError(
            f"Unknown model_type '{resolved}'. Available: {sorted(_REGISTRY)}"
        )
    model = _REGISTRY[resolved]()
    return model.load_model()


def available_models() -> List[dict]:
    """Metadata for every registered model — powers the model-selection UI."""
    models = []
    for model_type in _REGISTRY:
        meta = get_model(model_type).model_metadata().as_dict()
        meta["is_default"] = model_type == default_model_type()
        models.append(meta)
    return models
