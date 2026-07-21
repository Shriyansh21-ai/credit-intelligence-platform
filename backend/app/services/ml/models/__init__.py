"""Enterprise ML engine (Phase 4, Milestone 2).

A modular, configurable inference architecture. Every model implements
:class:`BaseRiskModel`, so business logic depends only on the interface and
never on a concrete algorithm. New algorithms are added by registering a class —
no change to callers.

No models are trained yet (per the phase brief). Until a trained artifact is
supplied, each model falls back to a shared, fully **deterministic and
explainable** estimator — never a random or fabricated prediction — so the
platform behaves correctly today and is ready to swap in real ML later.
"""

from .base import (  # noqa: F401
    BaseRiskModel,
    ModelMetadata,
    ModelPrediction,
)
from .registry import (  # noqa: F401
    available_models,
    default_model_type,
    get_model,
    register_model,
)
