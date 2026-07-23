"""Unsupervised anomaly detectors for the fraud ML engine (Phase 6, M10).

A small abstraction, :class:`AnomalyDetector`, unifies several unsupervised
methods behind ``fit`` / ``anomaly_score`` (higher = more anomalous, normalised
to ~[0, 1]):

* :class:`IsolationForestDetector`     — tree-isolation outlier scoring.
* :class:`LocalOutlierFactorDetector`  — density-based (novelty) scoring.
* :class:`ReconstructionDetector`      — PCA reconstruction error, the
  autoencoder-ready abstraction (swap the PCA transform for a trained
  autoencoder without changing the interface).

:class:`FraudEnsemble` fits all three plus a KMeans risk-clustering model and
combines their normalised scores into a single fraud signal, a percentile-based
fraud probability and a cluster assignment.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict, List, Optional

import numpy as np


def _normalise(scores: np.ndarray, lo: float, hi: float) -> np.ndarray:
    if hi - lo < 1e-12:
        return np.zeros_like(scores)
    return np.clip((scores - lo) / (hi - lo), 0.0, 1.0)


class AnomalyDetector(ABC):
    """Common interface for unsupervised anomaly detectors."""

    name: str = "base"

    def __init__(self) -> None:
        self._lo = 0.0
        self._hi = 1.0

    @abstractmethod
    def _raw_scores(self, X: np.ndarray) -> np.ndarray:
        """Raw anomaly scores (higher = more anomalous)."""

    def fit(self, X: np.ndarray) -> "AnomalyDetector":
        self._fit(X)
        raw = self._raw_scores(X)
        self._lo, self._hi = float(np.min(raw)), float(np.max(raw))
        return self

    @abstractmethod
    def _fit(self, X: np.ndarray) -> None:
        ...

    def anomaly_score(self, X: np.ndarray) -> np.ndarray:
        return _normalise(self._raw_scores(X), self._lo, self._hi)


class IsolationForestDetector(AnomalyDetector):
    name = "isolation_forest"

    def __init__(self, *, contamination: float = 0.05, random_state: int = 17) -> None:
        super().__init__()
        self._contamination = contamination
        self._random_state = random_state
        self._model = None

    def _fit(self, X: np.ndarray) -> None:
        from sklearn.ensemble import IsolationForest
        self._model = IsolationForest(
            n_estimators=200, contamination=self._contamination,
            random_state=self._random_state, n_jobs=-1,
        ).fit(X)

    def _raw_scores(self, X: np.ndarray) -> np.ndarray:
        # score_samples: higher = more normal; negate so higher = more anomalous.
        return -self._model.score_samples(X)

    def predict_outlier(self, X: np.ndarray) -> np.ndarray:
        return (self._model.predict(X) == -1).astype(int)


class LocalOutlierFactorDetector(AnomalyDetector):
    name = "local_outlier_factor"

    def __init__(self, *, n_neighbors: int = 20, contamination: float = 0.05) -> None:
        super().__init__()
        self._n_neighbors = n_neighbors
        self._contamination = contamination
        self._model = None

    def _fit(self, X: np.ndarray) -> None:
        from sklearn.neighbors import LocalOutlierFactor
        n_neighbors = min(self._n_neighbors, max(2, X.shape[0] - 1))
        self._model = LocalOutlierFactor(
            n_neighbors=n_neighbors, contamination=self._contamination, novelty=True,
        ).fit(X)

    def _raw_scores(self, X: np.ndarray) -> np.ndarray:
        return -self._model.score_samples(X)


class ReconstructionDetector(AnomalyDetector):
    """PCA reconstruction-error detector — the autoencoder-ready abstraction.

    A linear PCA encoder/decoder stands in for a neural autoencoder: anomalies
    reconstruct poorly and score high. Replacing the PCA transform with a trained
    autoencoder requires no change to this class's interface or callers.
    """

    name = "autoencoder"

    def __init__(self, *, n_components: Optional[int] = None) -> None:
        super().__init__()
        self._n_components = n_components
        self._model = None

    def _fit(self, X: np.ndarray) -> None:
        from sklearn.decomposition import PCA
        k = self._n_components or max(1, min(X.shape[1] // 2, X.shape[0] - 1, 10))
        self._model = PCA(n_components=k, random_state=3).fit(X)

    def _raw_scores(self, X: np.ndarray) -> np.ndarray:
        reconstructed = self._model.inverse_transform(self._model.transform(X))
        return np.mean((X - reconstructed) ** 2, axis=1)


class FraudEnsemble:
    """Ensemble of anomaly detectors + KMeans risk clustering."""

    def __init__(self, *, contamination: float = 0.05, n_clusters: int = 4) -> None:
        self._detectors: List[AnomalyDetector] = [
            IsolationForestDetector(contamination=contamination),
            LocalOutlierFactorDetector(contamination=contamination),
            ReconstructionDetector(),
        ]
        self._contamination = contamination
        self._n_clusters = n_clusters
        self._scaler = None
        self._kmeans = None
        self._train_ensemble_scores: Optional[np.ndarray] = None
        self.feature_names: List[str] = []

    def fit(self, X: np.ndarray, feature_names: List[str]) -> "FraudEnsemble":
        from sklearn.cluster import KMeans
        from sklearn.preprocessing import StandardScaler

        self.feature_names = list(feature_names)
        self._scaler = StandardScaler().fit(X)
        Xs = self._scaler.transform(X)
        for det in self._detectors:
            det.fit(Xs)
        n_clusters = min(self._n_clusters, max(1, X.shape[0]))
        self._kmeans = KMeans(n_clusters=n_clusters, random_state=5, n_init=10).fit(Xs)
        self._train_ensemble_scores = np.sort(self._ensemble_scores(Xs))
        return self

    def _ensemble_scores(self, Xs: np.ndarray) -> np.ndarray:
        stacked = np.column_stack([det.anomaly_score(Xs) for det in self._detectors])
        return stacked.mean(axis=1)

    def score(self, X: np.ndarray) -> Dict[str, np.ndarray]:
        Xs = self._scaler.transform(X)
        method_scores = {det.name: det.anomaly_score(Xs) for det in self._detectors}
        ensemble = np.column_stack(list(method_scores.values())).mean(axis=1)
        # Fraud probability = percentile of the ensemble score within the training
        # population (fraction of the population that is less anomalous).
        probs = np.searchsorted(self._train_ensemble_scores, ensemble, side="right") / \
            max(1, len(self._train_ensemble_scores))
        # Flag as anomalous if Isolation Forest isolates it OR the ensemble score
        # sits in the top-contamination tail of the training population. Combining
        # both keeps the flag consistent with the reported fraud probability.
        forest_outlier = self._detectors[0].predict_outlier(Xs) \
            if hasattr(self._detectors[0], "predict_outlier") else np.zeros(len(ensemble), dtype=int)
        tail = (probs >= (1.0 - self._contamination)).astype(int)
        is_anomaly = ((forest_outlier == 1) | (tail == 1)).astype(int)
        clusters = self._kmeans.predict(Xs)
        return {
            "method_scores": method_scores,
            "ensemble": ensemble,
            "fraud_probability": probs,
            "is_anomaly": np.asarray(is_anomaly).astype(int),
            "cluster": clusters,
        }
