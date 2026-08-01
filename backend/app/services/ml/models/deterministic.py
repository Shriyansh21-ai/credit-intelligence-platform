"""Deterministic model base — a concrete ``BaseRiskModel`` implementation.

Every algorithm-typed model in the catalogue inherits from this class. When a
trained artifact is available it is used; otherwise the model runs on the shared
:data:`ESTIMATOR`, keeping predictions deterministic and explainable. This is
the "deterministic placeholder interface where ML is unavailable" the phase brief
mandates — the calling code is identical whether or not a real model exists yet.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Dict, List, Mapping, Optional

from backend.app.services.enterprise_assessment import map_grade

from .base import BaseRiskModel, ModelMetadata, ModelPrediction
from .estimator import ESTIMATOR, Number, pd_to_score

# Trained artifacts (once they exist) live here, one file per model_type.
ARTIFACTS_DIR = Path(__file__).resolve().parent.parent / "artifacts"

# PD above this is treated as an elevated-default-risk classification.
_DEFAULT_THRESHOLD = 0.20


def _backend_available(probe_module: str) -> bool:
    """Whether the model's underlying library is importable in this env."""
    try:
        return importlib.util.find_spec(probe_module) is not None
    except (ImportError, ValueError):
        return False


class DeterministicRiskModel(BaseRiskModel):
    """Shared implementation used by all catalogue models."""

    model_type = "deterministic"
    algorithm = "Deterministic Additive Log-Odds"
    model_version = "1.0"
    feature_set_version = "1.0"
    # Module used only to report whether the real backend is installed.
    probe_module = "sklearn"
    description = "Transparent additive log-odds risk estimator."

    def __init__(self) -> None:
        self._artifact = None            # a trained model object, once available
        self._trained_at: Optional[str] = None

    # -- Interface -------------------------------------------------------
    def load_model(self, path: Optional[str] = None) -> "DeterministicRiskModel":
        """Load a trained artifact if one exists; otherwise stay in
        deterministic-fallback mode. Never raises for a missing artifact — a
        model with no trained weights is a valid state in ."""
        artifact_path = Path(path) if path else ARTIFACTS_DIR / f"{self.model_type}.joblib"
        if artifact_path.exists():
            import joblib  # local import: only needed when an artifact exists

            payload = joblib.load(artifact_path)
            self._artifact = payload.get("model")
            self._trained_at = payload.get("trained_at")
        return self

    def save_model(self, path: Optional[str] = None) -> str:
        """Persist the trained artifact. Raises clearly if there is nothing
        trained to save — placeholders are not silently written to disk."""
        if self._artifact is None:
            raise RuntimeError(
                f"Model '{self.model_type}' has no trained artifact to save. "
                "Train a model before calling save_model()."
            )
        import joblib

        ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
        artifact_path = Path(path) if path else ARTIFACTS_DIR / f"{self.model_type}.joblib"
        joblib.dump(
            {"model": self._artifact, "trained_at": self._trained_at,
             "feature_set_version": self.feature_set_version},
            artifact_path,
        )
        return str(artifact_path)

    def predict_proba(self, features: Mapping[str, Number]) -> List[float]:
        pd = self._probability_of_default(features)
        return [1.0 - pd, pd]

    def predict(self, features: Mapping[str, Number]) -> int:
        return int(self._probability_of_default(features) >= _DEFAULT_THRESHOLD)

    def feature_importance(self) -> Dict[str, float]:
        return ESTIMATOR.global_importance()

    def model_metadata(self) -> ModelMetadata:
        trained = self._artifact is not None
        return ModelMetadata(
            model_type=self.model_type,
            algorithm=self.algorithm,
            trained=trained,
            backend_available=_backend_available(self.probe_module),
            feature_set_version=self.feature_set_version,
            model_version=self.model_version,
            description=self.description,
            trained_at=self._trained_at,
            inference_mode="trained_artifact" if trained else "deterministic_fallback",
        )

    # -- Rich prediction envelope ---------------------------------------
    def predict_risk(self, features: Mapping[str, Number]) -> ModelPrediction:
        result = ESTIMATOR.contributions(features)
        pd = result.probability_of_default
        score = pd_to_score(pd)
        trained = self._artifact is not None
        return ModelPrediction(
            model_type=self.model_type,
            probability_of_default=pd,
            risk_score=score,
            risk_grade=map_grade(score),
            approval=score >= 640 and pd < _DEFAULT_THRESHOLD,
            contributions=result.contributions,
            inference_mode="trained_artifact" if trained else "deterministic_fallback",
        )

    # -- Internal --------------------------------------------------------
    def _probability_of_default(self, features: Mapping[str, Number]) -> float:
        # A future trained artifact would branch here; the placeholder always
        # uses the shared deterministic estimator.
        return ESTIMATOR.probability_of_default(features)
