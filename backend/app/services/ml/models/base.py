"""Base contracts for the enterprise ML engine.

``BaseRiskModel`` is the single interface every risk model implements. Callers
(inference service, explainability, scenario/stress engines) depend only on this
abstraction, so swapping a deterministic placeholder for a trained model later
requires no business-logic change.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Mapping, Optional

Number = Optional[float]


@dataclass
class ModelMetadata:
    """Describes a model instance for auditing and API responses."""

    model_type: str
    algorithm: str
    trained: bool
    backend_available: bool
    feature_set_version: str
    model_version: str
    description: str
    trained_at: Optional[str] = None
    inference_mode: str = "deterministic_fallback"  # or "trained_artifact"

    def as_dict(self) -> dict:
        return {
            "model_type": self.model_type,
            "algorithm": self.algorithm,
            "trained": self.trained,
            "backend_available": self.backend_available,
            "feature_set_version": self.feature_set_version,
            "model_version": self.model_version,
            "description": self.description,
            "trained_at": self.trained_at,
            "inference_mode": self.inference_mode,
        }


@dataclass
class ModelPrediction:
    """A single risk prediction with the signals downstream layers consume."""

    model_type: str
    probability_of_default: float
    risk_score: int                      # 300-900, aligned with the scorecard band
    risk_grade: str
    approval: bool
    # Signed per-feature contributions in log-odds space (risk-increasing > 0).
    # This is the substrate the explainability layer turns into narratives.
    contributions: Dict[str, float] = field(default_factory=dict)
    inference_mode: str = "deterministic_fallback"

    def as_dict(self) -> dict:
        return {
            "model_type": self.model_type,
            "probability_of_default": round(self.probability_of_default, 6),
            "risk_score": self.risk_score,
            "risk_grade": self.risk_grade,
            "approval": self.approval,
            "contributions": {k: round(v, 6) for k, v in self.contributions.items()},
            "inference_mode": self.inference_mode,
        }


class BaseRiskModel(ABC):
    """Interface every enterprise risk model must implement.

    Feature inputs are always a ``{feature_name: value}`` mapping keyed by the
    registry's feature names, so models are decoupled from how features are built
    or persisted.
    """

    # Stable identifier used for registry lookup and configuration.
    model_type: str = "base"
    # Human-facing algorithm name.
    algorithm: str = "Base Risk Model"

    @abstractmethod
    def load_model(self, path: Optional[str] = None) -> "BaseRiskModel":
        """Load a persisted artifact. Implementations that have no trained
        artifact yet remain in deterministic-fallback mode and return ``self``."""

    @abstractmethod
    def save_model(self, path: Optional[str] = None) -> str:
        """Persist the trained artifact, returning its path."""

    @abstractmethod
    def predict(self, features: Mapping[str, Number]) -> int:
        """Return the predicted class: ``1`` = elevated default risk, ``0`` = not."""

    @abstractmethod
    def predict_proba(self, features: Mapping[str, Number]) -> List[float]:
        """Return ``[p_no_default, p_default]`` — a proper 2-class distribution."""

    @abstractmethod
    def feature_importance(self) -> Dict[str, float]:
        """Return global feature importances (non-negative, larger = stronger)."""

    @abstractmethod
    def model_metadata(self) -> ModelMetadata:
        """Return this instance's metadata."""

    # -- Convenience shared by all models (not abstract) -----------------
    def predict_risk(self, features: Mapping[str, Number]) -> ModelPrediction:
        """Full prediction envelope (PD + score + grade + contributions).

        The default implementation composes the abstract methods; subclasses may
        override for efficiency but are not required to.
        """
        raise NotImplementedError  # concrete base provided in deterministic.py
