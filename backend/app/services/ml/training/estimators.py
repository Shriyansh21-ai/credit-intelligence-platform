"""Algorithm factory — maps an algorithm name to a fitted-ready estimator.

The training pipeline is decoupled from any specific library: it asks this
factory for an estimator by name. scikit-learn algorithms are always available
the gradient-boosting libraries (XGBoost, LightGBM, CatBoost) are used when
installed and *degrade gracefully* otherwise — exactly the optional-dependency
pattern the platform already uses for report rendering. A caller can check
:func:`backend_available` before training to give a clear, actionable error
instead of an import traceback.
"""

from __future__ import annotations

import importlib.util
from typing import Any, Callable, Dict, List, Optional

# Canonical algorithm identifiers. These line up with the model catalogue's
# ``model_type`` values so a trained artifact slots straight into the registry.
LOGISTIC_REGRESSION = "logistic_regression"
RANDOM_FOREST = "random_forest"
GRADIENT_BOOSTING = "gradient_boosting"
XGBOOST = "xgboost"
LIGHTGBM = "lightgbm"
CATBOOST = "catboost"
NEURAL_NETWORK = "neural_network"

SUPPORTED_ALGORITHMS: List[str] = [
    LOGISTIC_REGRESSION, RANDOM_FOREST, GRADIENT_BOOSTING,
    XGBOOST, LIGHTGBM, CATBOOST, NEURAL_NETWORK,
]

# Which library each algorithm needs (for availability probing).
_PROBE: Dict[str, str] = {
    LOGISTIC_REGRESSION: "sklearn",
    RANDOM_FOREST: "sklearn",
    GRADIENT_BOOSTING: "sklearn",
    NEURAL_NETWORK: "sklearn",
    XGBOOST: "xgboost",
    LIGHTGBM: "lightgbm",
    CATBOOST: "catboost",
}


class BackendUnavailableError(RuntimeError):
    """Raised when the library backing a requested algorithm is not installed."""


def backend_available(algorithm: str) -> bool:
    """Whether the library backing ``algorithm`` is importable in this env."""
    module = _PROBE.get(algorithm)
    if module is None:
        return False
    try:
        return importlib.util.find_spec(module) is not None
    except (ImportError, ValueError):
        return False


def default_hyperparameters(algorithm: str) -> Dict[str, Any]:
    """Sensible, reproducible defaults per algorithm (fixed random_state)."""
    defaults: Dict[str, Dict[str, Any]] = {
        LOGISTIC_REGRESSION: {"C": 1.0, "max_iter": 1000},
        RANDOM_FOREST: {"n_estimators": 200, "max_depth": 8, "min_samples_leaf": 20},
        GRADIENT_BOOSTING: {"n_estimators": 200, "max_depth": 3, "learning_rate": 0.05},
        NEURAL_NETWORK: {"hidden_layer_sizes": (32, 16), "max_iter": 400, "alpha": 1e-3},
        XGBOOST: {"n_estimators": 300, "max_depth": 4, "learning_rate": 0.05,
                  "subsample": 0.9, "colsample_bytree": 0.9},
        LIGHTGBM: {"n_estimators": 300, "max_depth": -1, "num_leaves": 31,
                   "learning_rate": 0.05, "subsample": 0.9},
        CATBOOST: {"iterations": 300, "depth": 5, "learning_rate": 0.05, "verbose": False},
    }
    return dict(defaults.get(algorithm, {}))


def tuning_grid(algorithm: str) -> Dict[str, List[Any]]:
    """A small, fast hyperparameter grid for optional tuning."""
    grids: Dict[str, Dict[str, List[Any]]] = {
        LOGISTIC_REGRESSION: {"C": [0.3, 1.0, 3.0]},
        RANDOM_FOREST: {"n_estimators": [150, 250], "max_depth": [6, 10]},
        GRADIENT_BOOSTING: {"n_estimators": [150, 250], "learning_rate": [0.03, 0.08]},
        NEURAL_NETWORK: {"alpha": [1e-4, 1e-3, 1e-2]},
        XGBOOST: {"max_depth": [3, 5], "learning_rate": [0.03, 0.08]},
        LIGHTGBM: {"num_leaves": [15, 31], "learning_rate": [0.03, 0.08]},
        CATBOOST: {"depth": [4, 6], "learning_rate": [0.03, 0.08]},
    }
    return grids.get(algorithm, {})


def build_estimator(algorithm: str, hyperparameters: Optional[Dict[str, Any]] = None,
                    *, random_state: int = 13) -> Any:
    """Instantiate an unfitted, sklearn-compatible classifier for ``algorithm``.

    Raises :class:`BackendUnavailableError` with a clear message when the
    requested library is not installed, so the pipeline can fall back or report.
    """
    if algorithm not in SUPPORTED_ALGORITHMS:
        raise ValueError(
            f"Unsupported algorithm {algorithm!r}. Supported: {SUPPORTED_ALGORITHMS}"
        )
    if not backend_available(algorithm):
        raise BackendUnavailableError(
            f"Algorithm '{algorithm}' requires the '{_PROBE[algorithm]}' package, "
            "which is not installed in this environment."
        )
    params = default_hyperparameters(algorithm)
    if hyperparameters:
        params.update(hyperparameters)

    builder = _BUILDERS[algorithm]
    return builder(params, random_state)


# -- Per-algorithm builders (imports are local so optional libs stay optional) --

def _logreg(params: Dict[str, Any], rs: int) -> Any:
    from sklearn.linear_model import LogisticRegression
    return LogisticRegression(random_state=rs, class_weight="balanced", **params)


def _rf(params: Dict[str, Any], rs: int) -> Any:
    from sklearn.ensemble import RandomForestClassifier
    return RandomForestClassifier(random_state=rs, class_weight="balanced", n_jobs=-1, **params)


def _gb(params: Dict[str, Any], rs: int) -> Any:
    from sklearn.ensemble import GradientBoostingClassifier
    return GradientBoostingClassifier(random_state=rs, **params)


def _mlp(params: Dict[str, Any], rs: int) -> Any:
    from sklearn.neural_network import MLPClassifier
    return MLPClassifier(random_state=rs, **params)


def _xgb(params: Dict[str, Any], rs: int) -> Any:
    from xgboost import XGBClassifier
    return XGBClassifier(
        random_state=rs, eval_metric="logloss", tree_method="hist",
        use_label_encoder=False, **params,
    )


def _lgbm(params: Dict[str, Any], rs: int) -> Any:
    from lightgbm import LGBMClassifier
    return LGBMClassifier(random_state=rs, class_weight="balanced", n_jobs=-1,
                          verbose=-1, **params)


def _catboost(params: Dict[str, Any], rs: int) -> Any:
    from catboost import CatBoostClassifier
    return CatBoostClassifier(random_state=rs, **params)


_BUILDERS: Dict[str, Callable[[Dict[str, Any], int], Any]] = {
    LOGISTIC_REGRESSION: _logreg,
    RANDOM_FOREST: _rf,
    GRADIENT_BOOSTING: _gb,
    NEURAL_NETWORK: _mlp,
    XGBOOST: _xgb,
    LIGHTGBM: _lgbm,
    CATBOOST: _catboost,
}
