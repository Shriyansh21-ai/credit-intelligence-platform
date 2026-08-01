"""Trained model artifact — a ``BaseRiskModel`` backed by a fitted pipeline.

This is the object that makes "real": it wraps a fitted scikit-learn /
gradient-boosting pipeline and implements the exact same
:class:`~backend.app.services.ml.models.base.BaseRiskModel` interface the
deterministic placeholder used. Every consumer downstream — inference
serving, explainability, scenario, stress — keeps working unchanged; they now
just get learned probabilities instead of the scorecard's closed form.

Local explanations are produced by an honest, model-agnostic *one-at-a-time*
log-odds decomposition against a stored baseline (median) profile: each
feature's contribution is the change in predicted log-odds when that feature
moves from the baseline to its observed value. This keeps the contribution
contract (signed log-odds, additive-ish) identical to the deterministic
estimator's, so the existing explainability layer works without modification
and the SHAP layer can refine it when available.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Dict, List, Mapping, Optional

import numpy as np

from backend.app.services.enterprise_assessment import map_grade

from backend.app.services.ml.models.base import BaseRiskModel, ModelMetadata, ModelPrediction
from backend.app.services.ml.models.estimator import pd_to_score

_DEFAULT_THRESHOLD = 0.20
_EPS = 1e-9


def _logit(p: float) -> float:
    p = min(1 - _EPS, max(_EPS, p))
    return math.log(p / (1 - p))


class TrainedRiskModel(BaseRiskModel):
    """A concrete risk model backed by a trained estimator pipeline."""

    def __init__(
        self,
        *,
        model_type: str,
        algorithm: str,
        pipeline,
        feature_names: List[str],
        importances: Optional[Dict[str, float]] = None,
        baseline: Optional[Mapping[str, float]] = None,
        model_version: str = "1.0",
        feature_set_version: str = "1.0",
        trained_at: Optional[str] = None,
        description: str = "Trained risk model.",
        threshold: float = _DEFAULT_THRESHOLD,
        background: Optional[np.ndarray] = None,
    ) -> None:
        self.model_type = model_type
        self.algorithm = algorithm
        self._pipeline = pipeline
        self._feature_names = list(feature_names)
        self._importances = dict(importances or {})
        self._baseline = dict(baseline or {name: 0.0 for name in feature_names})
        self.model_version = model_version
        self.feature_set_version = feature_set_version
        self._trained_at = trained_at
        self.description = description
        self._threshold = threshold
        # A small representative sample of the training matrix, retained so SHAP
        # can be computed on demand without re-loading the dataset.
        self._background = None if background is None else np.asarray(background, dtype=float)

    # -- vector assembly -------------------------------------------------
    def _vector(self, features: Mapping[str, float]) -> np.ndarray:
        row = [features.get(name, np.nan) for name in self._feature_names]
        arr = np.array([row], dtype=float)
        return arr

    # -- BaseRiskModel interface ----------------------------------------
    def predict_proba(self, features: Mapping[str, float]) -> List[float]:
        proba = self._pipeline.predict_proba(self._vector(features))[0]
        # Ensure [p_no_default, p_default] ordering via the fitted classes_.
        classes = list(getattr(self._pipeline, "classes_", [0, 1]))
        if classes == [0, 1]:
            return [float(proba[0]), float(proba[1])]
        idx1 = classes.index(1) if 1 in classes else 1
        idx0 = classes.index(0) if 0 in classes else 0
        return [float(proba[idx0]), float(proba[idx1])]

    def predict(self, features: Mapping[str, float]) -> int:
        return int(self.predict_proba(features)[1] >= self._threshold)

    def feature_importance(self) -> Dict[str, float]:
        return dict(self._importances)

    def model_metadata(self) -> ModelMetadata:
        return ModelMetadata(
            model_type=self.model_type,
            algorithm=self.algorithm,
            trained=True,
            backend_available=True,
            feature_set_version=self.feature_set_version,
            model_version=self.model_version,
            description=self.description,
            trained_at=self._trained_at,
            inference_mode="trained_artifact",
        )

    def predict_risk(self, features: Mapping[str, float]) -> ModelPrediction:
        pd = self.predict_proba(features)[1]
        score = pd_to_score(pd)
        return ModelPrediction(
            model_type=self.model_type,
            probability_of_default=pd,
            risk_score=score,
            risk_grade=map_grade(score),
            approval=score >= 640 and pd < self._threshold,
            contributions=self._local_contributions(features),
            inference_mode="trained_artifact",
        )

    # -- explanation substrate ------------------------------------------
    def _local_contributions(self, features: Mapping[str, float]) -> Dict[str, float]:
        """Signed one-at-a-time log-odds attribution against the baseline.

        Contribution(f) = logit(model at baseline with f set to observed value)
                          - logit(model at baseline). Positive = raises PD.
        Only features actually supplied are attributed; the rest stay at baseline.
        """
        base_vec = {name: self._baseline.get(name, 0.0) for name in self._feature_names}
        base_logit = _logit(self.predict_proba(base_vec)[1])
        contribs: Dict[str, float] = {}
        for name in self._feature_names:
            value = features.get(name)
            if value is None:
                continue
            probe = dict(base_vec)
            probe[name] = float(value)
            contribs[name] = _logit(self.predict_proba(probe)[1]) - base_logit
        return contribs

    # -- SHAP (genuine, best-effort) ------------------------------------
    def _shap_explainer(self):
        """Build a SHAP explainer over the fitted classifier + background.

        Returns ``(explainer, transformed_background, positive_index)`` or
        ``None`` when SHAP is unavailable or cannot be built for this model.
        """
        if self._background is None:
            return None
        try:
            import shap  # local import: optional dependency
        except Exception:
            return None
        try:
            pre = self._pipeline.named_steps["pre"]
            clf = self._pipeline.named_steps["model"]
            bg = pre.transform(self._background)
            classes = list(getattr(clf, "classes_", [0, 1]))
            pos = classes.index(1) if 1 in classes else len(classes) - 1
            explainer = shap.TreeExplainer(clf)
            return explainer, bg, pos
        except Exception:
            return None

    @staticmethod
    def _select_positive(values, pos: int):
        """Normalise SHAP output (list / 2-D / 3-D) to a positive-class matrix."""
        if isinstance(values, list):
            values = values[pos] if len(values) > pos else values[-1]
        values = np.asarray(values)
        if values.ndim == 3:  # (n_samples, n_features, n_classes)
            values = values[:, :, pos] if values.shape[-1] > pos else values[:, :, -1]
        return values

    def shap_global_importance(self) -> Optional[Dict[str, float]]:
        """Genuine SHAP global importance: mean |SHAP| over the background
        sample, normalised to sum to 1. Returns ``None`` if SHAP is unavailable."""
        built = self._shap_explainer()
        if built is None:
            return None
        explainer, bg, pos = built
        try:
            values = self._select_positive(explainer.shap_values(bg), pos)
            mean_abs = np.abs(values).mean(axis=0)
            total = float(mean_abs.sum()) or 1.0
            return {name: float(mean_abs[i] / total) for i, name in enumerate(self._feature_names)}
        except Exception:
            return None

    def shap_values(self, features: Mapping[str, float]) -> Optional[Dict[str, float]]:
        """Per-instance SHAP values (native margin units). ``None`` if unavailable."""
        built = self._shap_explainer()
        if built is None:
            return None
        explainer, _bg, pos = built
        try:
            pre = self._pipeline.named_steps["pre"]
            xi = pre.transform(self._vector(features))
            values = self._select_positive(explainer.shap_values(xi), pos)
            row = np.asarray(values)[0]
            return {name: float(row[i]) for i, name in enumerate(self._feature_names)}
        except Exception:
            return None

    # -- persistence -----------------------------------------------------
    def payload(self) -> dict:
        return {
            "model_type": self.model_type,
            "algorithm": self.algorithm,
            "pipeline": self._pipeline,
            "feature_names": self._feature_names,
            "importances": self._importances,
            "baseline": self._baseline,
            "model_version": self.model_version,
            "feature_set_version": self.feature_set_version,
            "trained_at": self._trained_at,
            "description": self.description,
            "threshold": self._threshold,
            "background": self._background,
        }

    def save_model(self, path: Optional[str] = None) -> str:
        import joblib
        if path is None:
            raise ValueError("A path is required to save a trained model artifact.")
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self.payload(), target)
        return str(target)

    def load_model(self, path: Optional[str] = None) -> "TrainedRiskModel":
        # Trained models are constructed pre-loaded; load is via ``from_artifact``.
        return self

    @classmethod
    def from_artifact(cls, path: str) -> "TrainedRiskModel":
        import joblib
        payload = joblib.load(path)
        return cls(
            model_type=payload["model_type"],
            algorithm=payload["algorithm"],
            pipeline=payload["pipeline"],
            feature_names=payload["feature_names"],
            importances=payload.get("importances"),
            baseline=payload.get("baseline"),
            model_version=payload.get("model_version", "1.0"),
            feature_set_version=payload.get("feature_set_version", "1.0"),
            trained_at=payload.get("trained_at"),
            description=payload.get("description", "Trained risk model."),
            threshold=payload.get("threshold", _DEFAULT_THRESHOLD),
            background=payload.get("background"),
        )
