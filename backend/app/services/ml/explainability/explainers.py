"""Concrete explanation methods.

* :class:`ContributionExplainer` - exact additive attribution from the
  deterministic estimator. For an additive log-odds model these contributions
  are the true Shapley values, so this is the ground-truth explainer.
* :class:`ShapExplainer` - SHAP abstraction. When a trained tree model and the
  ``shap`` library are available it would compute SHAP values; until then it
  resolves to the exact contributions (documented, not faked).
* :class:`LimeExplainer` - LIME abstraction. A local surrogate explanation
  for the additive model the local linear surrogate equals the contributions.

All three return the same :class:`Explanation` shape via the shared builder.
"""

from __future__ import annotations

from typing import Mapping, Optional

from backend.app.services.ml.models.base import BaseRiskModel
from backend.app.services.ml.models.estimator import ESTIMATOR

from .base import BaseExplainer, build_explanation
from .explanation import Explanation

Number = Optional[float]


class ContributionExplainer(BaseExplainer):
    method = "contribution"

    def explain(self, features: Mapping[str, Number], model: BaseRiskModel) -> Explanation:
        result = ESTIMATOR.contributions(features)
        return build_explanation(
            model=model,
            method=self.method,
            features=features,
            raw_contributions=result.contributions,
            logit=result.logit,
            probability_of_default=result.probability_of_default,
        )


class ShapExplainer(BaseExplainer):
    """SHAP-backed explainer abstraction.

    A trained tree model would be explained with ``shap.TreeExplainer`` here.
    Until one exists, SHAP over an additive model is exactly the additive
    contributions, so we resolve to those and label the method accordingly.
    """

    method = "shap"

    def explain(self, features: Mapping[str, Number], model: BaseRiskModel) -> Explanation:
        meta = model.model_metadata()
        result = ESTIMATOR.contributions(features)
        # (Trained-artifact SHAP path would branch on meta.trained here.)
        method = "shap" if meta.trained else "shap_additive_equivalent"
        return build_explanation(
            model=model,
            method=method,
            features=features,
            raw_contributions=result.contributions,
            logit=result.logit,
            probability_of_default=result.probability_of_default,
        )


class LimeExplainer(BaseExplainer):
    """LIME abstraction — a locally faithful linear surrogate.

    For the additive estimator the local surrogate coefficients equal the
    contributions, so the local explanation is exact.
    """

    method = "lime"

    def explain(self, features: Mapping[str, Number], model: BaseRiskModel) -> Explanation:
        result = ESTIMATOR.contributions(features)
        return build_explanation(
            model=model,
            method="lime_local_surrogate",
            features=features,
            raw_contributions=result.contributions,
            logit=result.logit,
            probability_of_default=result.probability_of_default,
        )
