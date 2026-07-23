"""Dataset abstraction, splitting and reproducible snapshotting.

A :class:`TrainingDataset` bundles a design matrix, labels and the *spec* that
produced them. Because synthetic data is fully determined by its spec (generator
+ seed + row count + drift), a dataset can be snapshotted as a small JSON spec
and a content hash rather than by copying raw rows — this is what makes every
trained model exactly reproducible from its registry record.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Dict, List, Mapping, Optional, Tuple

import numpy as np

from . import synthetic


@dataclass
class TrainingDataset:
    """A materialised training dataset with a reproducible spec."""

    name: str
    X: np.ndarray
    y: np.ndarray
    feature_names: List[str]
    spec: Dict            # everything needed to regenerate this dataset
    pd_true: Optional[np.ndarray] = None
    metadata: Dict = field(default_factory=dict)

    @property
    def n_rows(self) -> int:
        return int(self.X.shape[0])

    @property
    def n_features(self) -> int:
        return int(self.X.shape[1])

    @property
    def positive_rate(self) -> float:
        return float(self.y.mean()) if self.n_rows else 0.0

    def rows_as_dicts(self) -> List[Dict[str, float]]:
        """Feature rows as ``{feature_name: value}`` mappings (inference shape)."""
        return [
            {name: float(self.X[i, j]) for j, name in enumerate(self.feature_names)}
            for i in range(self.n_rows)
        ]

    def content_hash(self) -> str:
        """A stable hash over the spec — the reproducibility fingerprint."""
        blob = json.dumps(self.spec, sort_keys=True, default=str).encode("utf-8")
        return hashlib.sha256(blob).hexdigest()[:16]

    def snapshot(self) -> Dict:
        """A compact, serialisable description sufficient to regenerate the data."""
        return {
            "name": self.name,
            "spec": self.spec,
            "feature_names": list(self.feature_names),
            "n_rows": self.n_rows,
            "n_features": self.n_features,
            "positive_rate": round(self.positive_rate, 6),
            "content_hash": self.content_hash(),
        }


def make_synthetic_dataset(
    *,
    name: str = "synthetic_lending",
    seed: int = 42,
    n_rows: int = 4000,
    drift: Optional[Mapping[str, float]] = None,
    label_noise: float = 0.03,
) -> TrainingDataset:
    """Build a reproducible synthetic :class:`TrainingDataset`."""
    ds = synthetic.generate(seed=seed, n_rows=n_rows, drift=drift, label_noise=label_noise)
    spec = {
        "generator": "synthetic_v1",
        "seed": seed,
        "n_rows": n_rows,
        "drift": dict(drift) if drift else None,
        "label_noise": label_noise,
    }
    return TrainingDataset(
        name=name,
        X=ds.X,
        y=ds.y,
        feature_names=ds.feature_names,
        spec=spec,
        pd_true=ds.pd_true,
        metadata={"source": "synthetic", "positive_rate": round(float(ds.y.mean()), 6)},
    )


def dataset_from_spec(spec: Mapping, name: str = "reproduced") -> TrainingDataset:
    """Regenerate a dataset from a stored spec — the core of reproducibility."""
    if spec.get("generator") != "synthetic_v1":
        raise ValueError(f"Unknown dataset generator: {spec.get('generator')!r}")
    return make_synthetic_dataset(
        name=name,
        seed=int(spec["seed"]),
        n_rows=int(spec["n_rows"]),
        drift=spec.get("drift"),
        label_noise=float(spec.get("label_noise", 0.0)),
    )


def train_test_split(
    dataset: TrainingDataset, *, test_size: float = 0.25, seed: int = 7
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """A dependency-light, seeded, stratified train/test split."""
    rng = np.random.default_rng(seed)
    y = dataset.y
    train_idx: List[int] = []
    test_idx: List[int] = []
    for cls in np.unique(y):
        idx = np.where(y == cls)[0]
        rng.shuffle(idx)
        cut = int(round(len(idx) * test_size))
        test_idx.extend(idx[:cut].tolist())
        train_idx.extend(idx[cut:].tolist())
    rng.shuffle(train_idx)
    rng.shuffle(test_idx)
    return (
        dataset.X[train_idx],
        dataset.X[test_idx],
        dataset.y[train_idx],
        dataset.y[test_idx],
    )
