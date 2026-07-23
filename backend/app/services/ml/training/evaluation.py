"""Model evaluation metrics — the full credit-risk metric suite.

Produces the classification and rank-ordering metrics banks actually use to
sign off a scorecard: discrimination (ROC-AUC, Gini, KS), calibration (Brier,
reliability bins) and the confusion-matrix family (accuracy/precision/recall/
F1). All metrics are computed from ``(y_true, y_prob)`` so they apply uniformly
to every algorithm and to live monitoring against realised outcomes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

import numpy as np


@dataclass
class EvaluationResult:
    """A complete evaluation of predicted probabilities against true labels."""

    threshold: float
    n_samples: int
    positive_rate: float
    accuracy: float
    precision: float
    recall: float
    f1: float
    roc_auc: float
    ks_statistic: float
    gini: float
    brier_score: float
    log_loss: float
    confusion_matrix: Dict[str, int]
    calibration: List[Dict[str, float]] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "threshold": round(self.threshold, 4),
            "n_samples": self.n_samples,
            "positive_rate": round(self.positive_rate, 6),
            "accuracy": round(self.accuracy, 6),
            "precision": round(self.precision, 6),
            "recall": round(self.recall, 6),
            "f1": round(self.f1, 6),
            "roc_auc": round(self.roc_auc, 6),
            "ks_statistic": round(self.ks_statistic, 6),
            "gini": round(self.gini, 6),
            "brier_score": round(self.brier_score, 6),
            "log_loss": round(self.log_loss, 6),
            "confusion_matrix": self.confusion_matrix,
            "calibration": self.calibration,
        }


def _safe_div(a: float, b: float) -> float:
    return float(a) / float(b) if b else 0.0


def ks_statistic(y_true: np.ndarray, y_prob: np.ndarray) -> float:
    """Kolmogorov–Smirnov separation between good/bad score distributions."""
    pos = np.sort(y_prob[y_true == 1])
    neg = np.sort(y_prob[y_true == 0])
    if pos.size == 0 or neg.size == 0:
        return 0.0
    grid = np.sort(np.unique(y_prob))
    cdf_pos = np.searchsorted(pos, grid, side="right") / pos.size
    cdf_neg = np.searchsorted(neg, grid, side="right") / neg.size
    return float(np.max(np.abs(cdf_pos - cdf_neg)))


def roc_auc(y_true: np.ndarray, y_prob: np.ndarray) -> float:
    """ROC-AUC via the rank (Mann–Whitney U) formulation — no sklearn dependency
    and robust to ties."""
    n_pos = int(np.sum(y_true == 1))
    n_neg = int(np.sum(y_true == 0))
    if n_pos == 0 or n_neg == 0:
        return 0.5
    order = np.argsort(y_prob, kind="mergesort")
    ranks = np.empty_like(order, dtype=float)
    ranks[order] = np.arange(1, len(y_prob) + 1)
    # average ranks for ties
    _assign_tie_ranks(y_prob, ranks)
    sum_ranks_pos = float(np.sum(ranks[y_true == 1]))
    auc = (sum_ranks_pos - n_pos * (n_pos + 1) / 2.0) / (n_pos * n_neg)
    return float(auc)


def _assign_tie_ranks(values: np.ndarray, ranks: np.ndarray) -> None:
    order = np.argsort(values, kind="mergesort")
    sorted_vals = values[order]
    i = 0
    n = len(values)
    while i < n:
        j = i
        while j + 1 < n and sorted_vals[j + 1] == sorted_vals[i]:
            j += 1
        if j > i:
            avg = np.mean(ranks[order[i:j + 1]])
            ranks[order[i:j + 1]] = avg
        i = j + 1


def calibration_bins(y_true: np.ndarray, y_prob: np.ndarray, n_bins: int = 10) -> List[Dict[str, float]]:
    """Reliability curve: mean predicted vs observed frequency per probability bin."""
    edges = np.linspace(0.0, 1.0, n_bins + 1)
    bins: List[Dict[str, float]] = []
    for b in range(n_bins):
        lo, hi = edges[b], edges[b + 1]
        mask = (y_prob >= lo) & (y_prob < hi if b < n_bins - 1 else y_prob <= hi)
        count = int(np.sum(mask))
        if count == 0:
            continue
        bins.append({
            "bin": b,
            "lower": round(float(lo), 4),
            "upper": round(float(hi), 4),
            "count": count,
            "mean_predicted": round(float(np.mean(y_prob[mask])), 6),
            "observed_rate": round(float(np.mean(y_true[mask])), 6),
        })
    return bins


def evaluate(y_true, y_prob, *, threshold: float = 0.5, n_bins: int = 10) -> EvaluationResult:
    """Compute the full metric suite from true labels and predicted PDs."""
    y_true = np.asarray(y_true).astype(int)
    y_prob = np.clip(np.asarray(y_prob, dtype=float), 1e-9, 1 - 1e-9)
    y_pred = (y_prob >= threshold).astype(int)

    tp = int(np.sum((y_pred == 1) & (y_true == 1)))
    tn = int(np.sum((y_pred == 0) & (y_true == 0)))
    fp = int(np.sum((y_pred == 1) & (y_true == 0)))
    fn = int(np.sum((y_pred == 0) & (y_true == 1)))
    n = len(y_true)

    precision = _safe_div(tp, tp + fp)
    recall = _safe_div(tp, tp + fn)
    f1 = _safe_div(2 * precision * recall, precision + recall)
    accuracy = _safe_div(tp + tn, n)
    auc = roc_auc(y_true, y_prob)
    brier = float(np.mean((y_prob - y_true) ** 2))
    logloss = float(-np.mean(y_true * np.log(y_prob) + (1 - y_true) * np.log(1 - y_prob)))

    return EvaluationResult(
        threshold=threshold,
        n_samples=n,
        positive_rate=_safe_div(int(np.sum(y_true)), n),
        accuracy=accuracy,
        precision=precision,
        recall=recall,
        f1=f1,
        roc_auc=auc,
        ks_statistic=ks_statistic(y_true, y_prob),
        gini=2.0 * auc - 1.0,
        brier_score=brier,
        log_loss=logloss,
        confusion_matrix={"tp": tp, "tn": tn, "fp": fp, "fn": fn},
        calibration=calibration_bins(y_true, y_prob, n_bins=n_bins),
    )
