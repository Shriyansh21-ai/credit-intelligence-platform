"""Explainer registry — configurable explanation-method selection.

The method is chosen by name (``contribution`` / ``shap`` / ``lime``) or via the
``ML_EXPLAINER`` setting. ``auto`` picks SHAP when the active model is trained and
falls back to the exact contribution explainer otherwise.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Type

from backend.app.config import settings

from .base import BaseExplainer
from .explainers import ContributionExplainer, LimeExplainer, ShapExplainer

_REGISTRY: Dict[str, Type[BaseExplainer]] = {
    ContributionExplainer.method: ContributionExplainer,
    ShapExplainer.method: ShapExplainer,
    LimeExplainer.method: LimeExplainer,
}

_FALLBACK = "contribution"


def registered_methods() -> List[str]:
    return list(_REGISTRY) + ["auto"]


def default_explainer_method() -> str:
    configured = getattr(settings, "ML_EXPLAINER", None) or "auto"
    return configured


def get_explainer(method: Optional[str] = None, *, model_trained: bool = False) -> BaseExplainer:
    resolved = (method or default_explainer_method()).lower()
    if resolved == "auto":
        resolved = "shap" if model_trained else _FALLBACK
    if resolved not in _REGISTRY:
        resolved = _FALLBACK
    return _REGISTRY[resolved]()
