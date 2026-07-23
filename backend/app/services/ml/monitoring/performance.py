"""Model Performance Monitoring (Phase 6, Milestone 8).

Tracks a model's predictive quality against realised outcomes over time:
accuracy, precision, recall, F1, ROC-AUC, KS, Gini, Brier, calibration and the
confusion matrix, plus business KPIs (approval rate, expected loss). Each
evaluation is stored as an :class:`MLPerformanceRecord` so performance trends
are queryable and auditable.

Because production ground-truth accrues slowly, evaluation can be run against a
reproducible held-out sample drawn from the model's own dataset spec (a fresh
seed → genuinely out-of-sample rows), giving a realistic, repeatable performance
signal for the platform.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import numpy as np
from sqlalchemy.orm import Session

from backend.app.models.ml_platform import MLModel, MLPerformanceRecord
from backend.app.services.ml import registry
from backend.app.services.ml.data.dataset import TrainingDataset, dataset_from_spec
from backend.app.services.ml.training.evaluation import evaluate

# Portfolio loss assumptions for the business-KPI proxy.
_ASSUMED_EAD = 1_000_000.0   # exposure at default (per obligor, illustrative)
_ASSUMED_LGD = 0.45          # loss given default


def _business_kpis(y_true: np.ndarray, y_prob: np.ndarray, threshold: float = 0.20) -> Dict[str, Any]:
    approved = y_prob < threshold
    n = len(y_true)
    approved_bad = int(np.sum(approved & (y_true == 1)))
    expected_loss = float(np.sum(y_prob * _ASSUMED_EAD * _ASSUMED_LGD))
    return {
        "approval_rate": round(float(np.mean(approved)), 6) if n else None,
        "avg_pd": round(float(np.mean(y_prob)), 6) if n else None,
        "observed_default_rate": round(float(np.mean(y_true)), 6) if n else None,
        "bad_rate_in_approved": round(approved_bad / max(1, int(np.sum(approved))), 6),
        "expected_loss": round(expected_loss, 2),
        "expected_loss_per_obligor": round(expected_loss / n, 2) if n else None,
    }


def record_performance(
    db: Session,
    *,
    model: MLModel,
    y_true,
    y_prob,
    note: Optional[str] = None,
) -> MLPerformanceRecord:
    """Evaluate predictions against labels and persist a performance record."""
    y_true = np.asarray(y_true).astype(int)
    y_prob = np.asarray(y_prob, dtype=float)
    metrics = evaluate(y_true, y_prob)
    row = MLPerformanceRecord(
        model_id=model.id,
        model_key=model.model_key,
        n_samples=len(y_true),
        metrics=metrics.as_dict(),
        business_kpis=_business_kpis(y_true, y_prob),
        note=note,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def evaluate_on_dataset(db: Session, model: MLModel, dataset: TrainingDataset,
                        *, note: Optional[str] = None) -> MLPerformanceRecord:
    """Score a labelled dataset with the model's artifact and record performance."""
    trained = registry.load_trained_model(db, model)
    rows = dataset.rows_as_dicts()
    y_prob = np.array([trained.predict_proba(r)[1] for r in rows], dtype=float)
    return record_performance(db, model=model, y_true=dataset.y, y_prob=y_prob,
                              note=note or f"Evaluated on {dataset.name} ({dataset.n_rows} rows)")


def evaluate_reproduced(db: Session, model: MLModel, *, holdout_seed: int = 9999,
                        n_rows: int = 1500) -> MLPerformanceRecord:
    """Evaluate on a fresh, out-of-sample draw from the model's dataset spec.

    The model was trained on one seed; drawing with a different seed yields
    genuinely unseen rows from the same population — a realistic, reproducible
    performance check.
    """
    ds_row = None
    if model.dataset_id is not None:
        from backend.app.models.ml_platform import MLDataset
        ds_row = db.query(MLDataset).filter(MLDataset.id == model.dataset_id).first()
    spec = dict(ds_row.spec) if ds_row and ds_row.spec else {
        "generator": "synthetic_v1", "seed": 42, "n_rows": n_rows, "label_noise": 0.03,
    }
    spec = {**spec, "seed": holdout_seed, "n_rows": n_rows}
    dataset = dataset_from_spec(spec, name="holdout")
    return evaluate_on_dataset(db, model, dataset, note="Out-of-sample holdout evaluation")


def performance_trend(db: Session, *, model_id: Optional[int] = None,
                      model_key: Optional[str] = None, limit: int = 50) -> List[MLPerformanceRecord]:
    q = db.query(MLPerformanceRecord)
    if model_id is not None:
        q = q.filter(MLPerformanceRecord.model_id == model_id)
    if model_key is not None:
        q = q.filter(MLPerformanceRecord.model_key == model_key)
    return q.order_by(MLPerformanceRecord.evaluated_at.asc(), MLPerformanceRecord.id.asc()).limit(limit).all()


def record_as_dict(row: MLPerformanceRecord) -> dict:
    return {
        "id": row.id,
        "model_id": row.model_id,
        "model_key": row.model_key,
        "evaluated_at": row.evaluated_at.isoformat() if row.evaluated_at else None,
        "n_samples": row.n_samples,
        "metrics": row.metrics,
        "business_kpis": row.business_kpis,
        "note": row.note,
    }
