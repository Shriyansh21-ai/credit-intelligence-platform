"""Enterprise Model Registry (Phase 6, Milestone 3)."""

from . import service
from .service import (
    RegistryError,
    any_production_model,
    approve,
    dataset_as_dict,
    deployment_history,
    event_as_dict,
    list_models,
    load_trained_model,
    model_as_dict,
    production_model,
    promote,
    register_dataset,
    register_model,
    reject,
    rollback,
    submit_for_approval,
    versions,
)

__all__ = [
    "service",
    "RegistryError",
    "any_production_model",
    "register_model",
    "register_dataset",
    "list_models",
    "versions",
    "production_model",
    "load_trained_model",
    "deployment_history",
    "submit_for_approval",
    "approve",
    "reject",
    "promote",
    "rollback",
    "model_as_dict",
    "event_as_dict",
    "dataset_as_dict",
]
