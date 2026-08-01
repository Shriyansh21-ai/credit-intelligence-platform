"""Explainable AI layer.

Turns a model's per-feature contributions into analyst- and business-readable
explanations: global importance, local importance, a waterfall from the base
rate to the borrower's probability of default, the top risk-increasing and
risk-reducing drivers, and plain-language narratives such as

    "Debt Service Coverage reduced overall risk by 11%."

The layer is method-agnostic behind :class:`BaseExplainer`: SHAP and LIME are
first-class abstractions, and until a trained model exists every method resolves
to the exact additive contributions of the deterministic estimator (which, for
an additive log-odds model, *are* the true Shapley values). Swapping in a trained
model later changes only which explainer the registry returns.
"""

from .registry import default_explainer_method, get_explainer  # noqa: F401
from .service import explain_features, explain_vector  # noqa: F401
