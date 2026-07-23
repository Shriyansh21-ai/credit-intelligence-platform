"""Synthetic data + dataset abstraction for the ML training platform."""

from .dataset import (
    TrainingDataset,
    dataset_from_spec,
    make_synthetic_dataset,
    train_test_split,
)
from .synthetic import SyntheticDataset, generate, signal_feature_names

__all__ = [
    "TrainingDataset",
    "SyntheticDataset",
    "make_synthetic_dataset",
    "dataset_from_spec",
    "train_test_split",
    "generate",
    "signal_feature_names",
]
