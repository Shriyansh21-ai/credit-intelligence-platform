"""Seeded synthetic lending-data generator (Phase 6, Milestone 2 support).

Real machine learning needs historical labelled data. Rather than fabricate an
opaque dataset, this generator reuses the platform's existing, curated
:data:`~backend.app.services.ml.models.estimator.ESTIMATOR` as the **latent risk
process**: for each synthetic borrower we sample plausible feature values, run
them through the deterministic additive log-odds estimator to obtain a *true*
probability of default, then draw the observed default label from that
probability.

This has three important properties:

* **Reproducible** — every draw is governed by an explicit integer seed, so the
  same seed always yields byte-identical data. Predictions are reproducible and
  datasets can be snapshotted by seed alone (no raw rows to store).
* **Learnable** — because the labels are generated from a real monotonic risk
  structure, a well-specified model genuinely recovers signal, and its learned
  feature importances line up with the scorecard's economic intuition.
* **Honest** — the generator never leaks the true PD into the features; models
  see only noisy observable features and must learn the mapping.

The generator can also inject controlled distribution shift (``drift``) so the
drift-detection and retraining milestones can be exercised end-to-end.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Mapping, Optional, Tuple

import numpy as np

from backend.app.services.ml.models.estimator import ESTIMATOR, Weight

# Features that are naturally bounded to [0, 1] (encoded scores / fractions).
_UNIT_INTERVAL = {
    "industry_risk_score", "geographical_risk_score", "customer_concentration_score",
    "compliance_score", "expansion_stage_score",
}
# Features that are a 0/1 indicator.
_BINARY = {"prior_defaults_flag"}
# Features that may legitimately go negative (margins, growth).
_MAY_BE_NEGATIVE = {"net_margin", "ebitda_margin", "return_on_equity", "revenue_growth"}


@dataclass(frozen=True)
class FeatureSpec:
    """Sampling parameters for one observable feature, derived from the estimator
    driver table so the generated distribution is centred on the model's neutral
    point and spread by its scale."""

    name: str
    center: float
    scale: float
    lo: float
    hi: float
    binary_p: Optional[float] = None  # if set, feature is a Bernoulli indicator


def _specs() -> List[FeatureSpec]:
    """Build a sampling spec for every driver in the estimator weight table."""
    specs: List[FeatureSpec] = []
    for w in ESTIMATOR.weights:  # type: Weight
        if w.feature in _BINARY:
            specs.append(FeatureSpec(w.feature, w.center, w.scale, 0.0, 1.0, binary_p=0.12))
            continue
        if w.feature in _UNIT_INTERVAL:
            specs.append(FeatureSpec(w.feature, w.center, w.scale, 0.0, 1.0))
            continue
        lo = w.center - 3.0 * w.scale
        hi = w.center + 3.0 * w.scale
        if w.feature not in _MAY_BE_NEGATIVE:
            lo = max(lo, 0.0)
        specs.append(FeatureSpec(w.feature, w.center, w.scale, lo, hi))
    return specs


_SPECS: Tuple[FeatureSpec, ...] = tuple(_specs())
_SIGNAL_FEATURES: Tuple[str, ...] = tuple(s.name for s in _SPECS)


def signal_feature_names() -> List[str]:
    """The observable features that carry genuine risk signal."""
    return list(_SIGNAL_FEATURES)


@dataclass
class SyntheticDataset:
    """A generated dataset: a numeric design matrix plus its default labels."""

    X: np.ndarray                 # shape (n_rows, n_features)
    y: np.ndarray                 # shape (n_rows,), 0/1 default label
    pd_true: np.ndarray           # shape (n_rows,), latent true PD (audit only)
    feature_names: List[str]
    seed: int
    n_rows: int
    drift: Optional[Mapping[str, float]] = None

    def rows_as_dicts(self) -> List[Dict[str, float]]:
        """Feature rows as ``{feature_name: value}`` mappings (inference shape)."""
        return [
            {name: float(self.X[i, j]) for j, name in enumerate(self.feature_names)}
            for i in range(self.n_rows)
        ]


def _sample_feature(
    rng: np.random.Generator, spec: FeatureSpec, n: int, drift_shift: float
) -> np.ndarray:
    """Draw ``n`` values for one feature, optionally shifted by ``drift_shift``
    standardised units (used to simulate population drift)."""
    if spec.binary_p is not None:
        # Drift raises the incidence of the indicator (e.g. more prior defaults).
        p = min(0.95, max(0.0, spec.binary_p + 0.12 * drift_shift))
        return rng.binomial(1, p, size=n).astype(float)
    z = rng.normal(0.0, 1.15, size=n) + drift_shift
    values = spec.center + z * spec.scale
    return np.clip(values, spec.lo, spec.hi)


def generate(
    *,
    seed: int = 42,
    n_rows: int = 4000,
    drift: Optional[Mapping[str, float]] = None,
    label_noise: float = 0.0,
) -> SyntheticDataset:
    """Generate a reproducible synthetic lending dataset.

    Parameters
    ----------
    seed:
        Integer seed governing every random draw. Same seed → identical data.
    n_rows:
        Number of synthetic borrowers.
    drift:
        Optional ``{feature_name: shift}`` map. Each named feature's sampling
        distribution is shifted by ``shift`` standardised units, simulating a
        change in the applicant population (for drift/retraining tests).
    label_noise:
        Probability of flipping a label, to make the problem non-separable.
    """
    rng = np.random.default_rng(seed)
    drift = dict(drift or {})

    columns: List[np.ndarray] = []
    for spec in _SPECS:
        shift = float(drift.get(spec.name, 0.0))
        columns.append(_sample_feature(rng, spec, n_rows, shift))
    X = np.column_stack(columns)

    # Latent true PD from the deterministic estimator (the honest risk process).
    pd_true = np.empty(n_rows, dtype=float)
    for i in range(n_rows):
        row = {name: float(X[i, j]) for j, name in enumerate(_SIGNAL_FEATURES)}
        pd_true[i] = ESTIMATOR.probability_of_default(row)

    y = (rng.random(n_rows) < pd_true).astype(int)
    if label_noise > 0.0:
        flip = rng.random(n_rows) < label_noise
        y = np.where(flip, 1 - y, y)

    return SyntheticDataset(
        X=X,
        y=y,
        pd_true=pd_true,
        feature_names=list(_SIGNAL_FEATURES),
        seed=seed,
        n_rows=n_rows,
        drift=drift or None,
    )
