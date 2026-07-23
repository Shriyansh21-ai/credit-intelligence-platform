"""The modular ML training pipeline (Phase 6, Milestone 2).

One entrypoint, :func:`train`, runs the full enterprise training flow:

    data loading → cleaning → feature engineering → encoding/scaling →
    cross-validation → (optional) hyperparameter tuning → fit →
    evaluation → serialisation-ready artifact → training report

Each stage is a small, testable function so the pipeline is easy to extend
(add an algorithm, swap a scaler, plug a new metric) without touching the
orchestration. The result is a :class:`TrainingResult` carrying a ready-to-
register :class:`TrainedRiskModel` plus a complete, serialisable report —
metrics, cross-validation, hyperparameters, feature importances and timing —
that the model registry (Milestone 3) persists verbatim for reproducibility.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import numpy as np

from ..data.dataset import TrainingDataset, train_test_split
from . import estimators
from .evaluation import EvaluationResult, evaluate
from .trained_model import TrainedRiskModel


@dataclass
class TrainingResult:
    """Everything produced by a training run."""

    model: TrainedRiskModel
    algorithm: str
    hyperparameters: Dict[str, Any]
    metrics: EvaluationResult
    cv_scores: List[float]
    cv_mean: float
    cv_std: float
    feature_importances: Dict[str, float]
    feature_names: List[str]
    dataset_snapshot: Dict
    training_time_seconds: float
    trained_at: str
    n_train: int
    n_test: int
    tuned: bool

    def report(self) -> dict:
        """A serialisable training report (persisted by the registry)."""
        return {
            "algorithm": self.algorithm,
            "hyperparameters": self.hyperparameters,
            "metrics": self.metrics.as_dict(),
            "cross_validation": {
                "scoring": "roc_auc",
                "scores": [round(s, 6) for s in self.cv_scores],
                "mean": round(self.cv_mean, 6),
                "std": round(self.cv_std, 6),
            },
            "feature_importances": {
                k: round(v, 6) for k, v in sorted(
                    self.feature_importances.items(), key=lambda kv: kv[1], reverse=True
                )
            },
            "feature_names": self.feature_names,
            "dataset": self.dataset_snapshot,
            "training_time_seconds": round(self.training_time_seconds, 4),
            "trained_at": self.trained_at,
            "n_train": self.n_train,
            "n_test": self.n_test,
            "tuned": self.tuned,
        }


# ---------------------------------------------------------------------------
# Pipeline stages
# ---------------------------------------------------------------------------

def clean(X: np.ndarray) -> np.ndarray:
    """Coerce to float and replace non-finite values with NaN (the imputer then
    fills them). Never drops rows silently — data volume is auditable."""
    X = np.asarray(X, dtype=float)
    X[~np.isfinite(X)] = np.nan
    return X


def build_preprocessor():
    """Encoding/scaling stage: median-impute then standardise. All platform
    features are numeric, so a single numeric pipeline suffices; categoricals are
    already encoded to scores upstream by the feature registry."""
    from sklearn.impute import SimpleImputer
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler

    return Pipeline([
        ("impute", SimpleImputer(strategy="median")),
        ("scale", StandardScaler()),
    ])


def _global_importances(estimator, feature_names: List[str]) -> Dict[str, float]:
    """Extract normalised global importances from whatever estimator was fitted."""
    importances: Optional[np.ndarray] = None
    if hasattr(estimator, "feature_importances_"):
        importances = np.asarray(estimator.feature_importances_, dtype=float)
    elif hasattr(estimator, "coef_"):
        importances = np.abs(np.asarray(estimator.coef_, dtype=float).ravel())
    if importances is None or importances.size != len(feature_names):
        # Uniform fallback (e.g. MLP has no native importances).
        importances = np.ones(len(feature_names), dtype=float)
    total = float(importances.sum()) or 1.0
    return {name: float(importances[i] / total) for i, name in enumerate(feature_names)}


def _cross_val_auc(pipeline, X: np.ndarray, y: np.ndarray, *, folds: int, seed: int) -> List[float]:
    """Stratified k-fold ROC-AUC without a hard sklearn cross_val dependency."""
    from copy import deepcopy

    rng = np.random.default_rng(seed)
    idx_by_class = {c: np.where(y == c)[0] for c in np.unique(y)}
    for c in idx_by_class:
        rng.shuffle(idx_by_class[c])
    fold_assignment = np.empty(len(y), dtype=int)
    for c, idx in idx_by_class.items():
        fold_assignment[idx] = np.arange(len(idx)) % folds

    scores: List[float] = []
    for f in range(folds):
        test_mask = fold_assignment == f
        if test_mask.sum() == 0 or (~test_mask).sum() == 0:
            continue
        model = deepcopy(pipeline)
        model.fit(X[~test_mask], y[~test_mask])
        proba = model.predict_proba(X[test_mask])[:, list(model.classes_).index(1)]
        scores.append(evaluate(y[test_mask], proba).roc_auc)
    return scores


def _tune(algorithm: str, base_pipeline, X: np.ndarray, y: np.ndarray, *, seed: int):
    """Small grid search over the algorithm's tuning grid (ROC-AUC)."""
    from sklearn.model_selection import GridSearchCV, StratifiedKFold

    grid = estimators.tuning_grid(algorithm)
    if not grid:
        base_pipeline.fit(X, y)
        return base_pipeline, {}
    param_grid = {f"model__{k}": v for k, v in grid.items()}
    cv = StratifiedKFold(n_splits=3, shuffle=True, random_state=seed)
    search = GridSearchCV(base_pipeline, param_grid, scoring="roc_auc", cv=cv, n_jobs=-1)
    search.fit(X, y)
    best = {k.replace("model__", ""): v for k, v in search.best_params_.items()}
    return search.best_estimator_, best


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

def train(
    dataset: TrainingDataset,
    algorithm: str,
    *,
    hyperparameters: Optional[Dict[str, Any]] = None,
    test_size: float = 0.25,
    cv_folds: int = 5,
    tune: bool = False,
    random_state: int = 13,
    model_version: str = "1.0",
) -> TrainingResult:
    """Run the full training pipeline for one algorithm on one dataset."""
    from sklearn.pipeline import Pipeline

    if not estimators.backend_available(algorithm):
        raise estimators.BackendUnavailableError(
            f"Cannot train '{algorithm}': backing library not installed."
        )

    started = time.perf_counter()

    # 1-2. Load + clean.
    X_train, X_test, y_train, y_test = train_test_split(
        dataset, test_size=test_size, seed=random_state
    )
    X_train, X_test = clean(X_train), clean(X_test)

    # 3-4. Feature engineering / encoding / scaling wrapped with the estimator.
    estimator = estimators.build_estimator(algorithm, hyperparameters, random_state=random_state)
    pipeline = Pipeline([("pre", build_preprocessor()), ("model", estimator)])

    # 5. Cross-validation on the training split.
    cv_scores = _cross_val_auc(pipeline, X_train, y_train, folds=cv_folds, seed=random_state)

    # 6. Optional tuning (fits on the training split); else fit directly.
    tuned = False
    resolved_hyperparams = dict(estimators.default_hyperparameters(algorithm))
    if hyperparameters:
        resolved_hyperparams.update(hyperparameters)
    if tune:
        pipeline, best = _tune(algorithm, pipeline, X_train, y_train, seed=random_state)
        resolved_hyperparams.update(best)
        tuned = True
    else:
        pipeline.fit(X_train, y_train)

    # 7. Evaluation on the held-out test split.
    fitted_model = pipeline.named_steps["model"]
    pos_index = list(pipeline.classes_).index(1)
    test_proba = pipeline.predict_proba(X_test)[:, pos_index]
    metrics = evaluate(y_test, test_proba)

    # 8. Importances + baseline (median profile) for local explanations.
    importances = _global_importances(fitted_model, dataset.feature_names)
    baseline = {
        name: float(np.nanmedian(X_train[:, i]))
        for i, name in enumerate(dataset.feature_names)
    }

    cv_mean = float(np.mean(cv_scores)) if cv_scores else 0.0
    cv_std = float(np.std(cv_scores)) if cv_scores else 0.0
    trained_at = datetime.now(timezone.utc).isoformat()
    elapsed = time.perf_counter() - started

    # Retain a small representative background sample for on-demand SHAP.
    n_bg = min(120, X_train.shape[0])
    bg_idx = np.random.default_rng(random_state).choice(X_train.shape[0], size=n_bg, replace=False)
    background = X_train[bg_idx]

    model = TrainedRiskModel(
        model_type=algorithm,
        algorithm=algorithm,
        pipeline=pipeline,
        feature_names=dataset.feature_names,
        importances=importances,
        baseline=baseline,
        model_version=model_version,
        feature_set_version="1.0",
        trained_at=trained_at,
        description=f"Trained {algorithm} risk model (ROC-AUC {metrics.roc_auc:.3f}).",
        background=background,
    )

    return TrainingResult(
        model=model,
        algorithm=algorithm,
        hyperparameters=resolved_hyperparams,
        metrics=metrics,
        cv_scores=cv_scores,
        cv_mean=cv_mean,
        cv_std=cv_std,
        feature_importances=importances,
        feature_names=dataset.feature_names,
        dataset_snapshot=dataset.snapshot(),
        training_time_seconds=elapsed,
        trained_at=trained_at,
        n_train=int(X_train.shape[0]),
        n_test=int(X_test.shape[0]),
        tuned=tuned,
    )
