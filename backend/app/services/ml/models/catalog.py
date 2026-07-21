"""Model catalogue — the concrete risk models the engine ships with.

Each class is a thin, declarative specialisation of
:class:`DeterministicRiskModel`: it declares its ``model_type``, human-facing
``algorithm`` name and the library used to report backend availability. Adding a
new algorithm is a matter of adding a class here and registering it — no
business logic changes. All models currently share the deterministic estimator
(no training yet), which keeps every prediction explainable and reproducible.
"""

from __future__ import annotations

from .deterministic import DeterministicRiskModel


class ScorecardModel(DeterministicRiskModel):
    """The reference model available today: the transparent scorecard estimator.
    Always 'trained' in the sense that its weights are the deterministic
    reference weights."""

    model_type = "scorecard"
    algorithm = "Deterministic Commercial Scorecard"
    probe_module = "math"  # always available; pure-Python
    description = (
        "Transparent additive log-odds commercial scorecard. The always-available "
        "reference model; other algorithms fall back to it until trained."
    )


class LogisticRegressionModel(DeterministicRiskModel):
    model_type = "logistic_regression"
    algorithm = "Logistic Regression"
    probe_module = "sklearn"
    description = "Linear log-odds classifier (scikit-learn). Deterministic fallback until trained."


class RandomForestModel(DeterministicRiskModel):
    model_type = "random_forest"
    algorithm = "Random Forest"
    probe_module = "sklearn"
    description = "Bagged decision-tree ensemble (scikit-learn). Deterministic fallback until trained."


class XGBoostModel(DeterministicRiskModel):
    model_type = "xgboost"
    algorithm = "XGBoost"
    probe_module = "xgboost"
    description = "Gradient-boosted trees (XGBoost). Deterministic fallback until trained."


class LightGBMModel(DeterministicRiskModel):
    model_type = "lightgbm"
    algorithm = "LightGBM"
    probe_module = "lightgbm"
    description = "Gradient-boosting framework (LightGBM). Deterministic fallback until trained."


class CatBoostModel(DeterministicRiskModel):
    model_type = "catboost"
    algorithm = "CatBoost"
    probe_module = "catboost"
    description = "Gradient boosting with categorical support (CatBoost). Deterministic fallback until trained."


class NeuralNetworkModel(DeterministicRiskModel):
    model_type = "neural_network"
    algorithm = "Neural Network (MLP)"
    probe_module = "sklearn"
    description = "Multi-layer perceptron classifier. Deterministic fallback until trained."


# The order here is the order surfaced in listing APIs.
CATALOG = (
    ScorecardModel,
    LogisticRegressionModel,
    RandomForestModel,
    XGBoostModel,
    LightGBMModel,
    CatBoostModel,
    NeuralNetworkModel,
)
