"""Data Drift Detection.

Detects when the live applicant population has drifted away from the data a
model was trained on — the leading indicator that a model needs retraining.
It computes, per feature and overall

* **Population Stability Index (PSI)** — the industry-standard drift measure
  with the conventional bands (<0.1 stable, 0.1–0.25 moderate, >0.25 significant).
* **Feature drift** — PSI plus mean shift for every feature.
* **Target drift** — shift in the predicted-PD distribution.
* **Distribution shift** — the aggregate picture (share of features drifted).
* **Missing-feature rate** — data-completeness regression.
* **Schema changes** — features that appeared or disappeared versus the model's
  training feature set.

Runs are persisted to :class:`MLDriftReport`; a breach raises a risk alert
through the existing alert store when available.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Mapping, Optional

import numpy as np
from sqlalchemy.orm import Session

from backend.app.models.ml_platform import MLDataset, MLDriftReport, MLModel
from backend.app.services.ml.data.dataset import dataset_from_spec

# PSI interpretation bands.
PSI_MODERATE = 0.10
PSI_SIGNIFICANT = 0.25
# A report is "breached" when either overall PSI or the drifted share crosses.
DEFAULT_PSI_THRESHOLD = 0.25
DEFAULT_DRIFTED_SHARE_THRESHOLD = 0.30
_EPS = 1e-6


def population_stability_index(reference: np.ndarray, current: np.ndarray, *, bins: int = 10) -> float:
    """PSI between a reference and a current sample of one feature."""
    reference = reference[np.isfinite(reference)]
    current = current[np.isfinite(current)]
    if reference.size == 0 or current.size == 0:
        return 0.0
    # Quantile edges from the reference so bins carry ~equal reference mass.
    quantiles = np.linspace(0, 100, bins + 1)
    edges = np.unique(np.percentile(reference, quantiles))
    if edges.size < 2:
        return 0.0
    edges[0], edges[-1] = -np.inf, np.inf
    ref_counts, _ = np.histogram(reference, bins=edges)
    cur_counts, _ = np.histogram(current, bins=edges)
    ref_pct = ref_counts / max(1, ref_counts.sum())
    cur_pct = cur_counts / max(1, cur_counts.sum())
    ref_pct = np.clip(ref_pct, _EPS, None)
    cur_pct = np.clip(cur_pct, _EPS, None)
    return float(np.sum((cur_pct - ref_pct) * np.log(cur_pct / ref_pct)))


def _band(psi: float) -> str:
    if psi >= PSI_SIGNIFICANT:
        return "significant"
    if psi >= PSI_MODERATE:
        return "moderate"
    return "stable"


def _matrix(rows: List[Mapping[str, Any]], feature_names: List[str]) -> np.ndarray:
    return np.array(
        [[_num(r.get(f)) for f in feature_names] for r in rows],
        dtype=float,
    ) if rows else np.empty((0, len(feature_names)))


def _num(v: Any) -> float:
    try:
        return float(v) if v is not None else np.nan
    except (TypeError, ValueError):
        return np.nan


def compute_drift(
    reference_matrix: np.ndarray,
    current_rows: List[Mapping[str, Any]],
    feature_names: List[str],
    *,
    psi_threshold: float = DEFAULT_PSI_THRESHOLD,
) -> Dict[str, Any]:
    """Core drift computation over aligned feature matrices (no persistence)."""
    current_matrix = _matrix(current_rows, feature_names)
    n_current = current_matrix.shape[0]

    per_feature: List[Dict[str, Any]] = []
    psis: List[float] = []
    for j, name in enumerate(feature_names):
        ref_col = reference_matrix[:, j] if reference_matrix.size else np.array([])
        cur_col = current_matrix[:, j] if n_current else np.array([])
        psi = population_stability_index(ref_col, cur_col)
        psis.append(psi)
        ref_mean = float(np.nanmean(ref_col)) if ref_col.size else None
        cur_mean = float(np.nanmean(cur_col)) if cur_col.size else None
        missing = float(np.mean(~np.isfinite(cur_col))) if cur_col.size else 1.0
        per_feature.append({
            "feature": name,
            "psi": round(psi, 6),
            "band": _band(psi),
            "drifted": psi >= psi_threshold,
            "reference_mean": None if ref_mean is None else round(ref_mean, 6),
            "current_mean": None if cur_mean is None else round(cur_mean, 6),
            "mean_shift": None if (ref_mean is None or cur_mean is None) else round(cur_mean - ref_mean, 6),
            "missing_rate": round(missing, 6),
        })

    drifted = [f for f in per_feature if f["drifted"]]
    overall_psi = float(np.mean(psis)) if psis else 0.0
    drifted_share = len(drifted) / len(feature_names) if feature_names else 0.0
    missing_rate = float(np.mean([f["missing_rate"] for f in per_feature])) if per_feature else 0.0

    return {
        "n_current": n_current,
        "n_features": len(feature_names),
        "overall_psi": round(overall_psi, 6),
        "psi_band": _band(overall_psi),
        "n_drifted": len(drifted),
        "drifted_share": round(drifted_share, 6),
        "missing_feature_rate": round(missing_rate, 6),
        "per_feature": per_feature,
        "drifted_features": [f["feature"] for f in drifted],
    }


def schema_changes(current_rows: List[Mapping[str, Any]], expected: List[str]) -> Dict[str, List[str]]:
    seen: set = set()
    for r in current_rows:
        seen.update(r.keys())
    expected_set = set(expected)
    return {
        "missing_features": sorted(expected_set - seen),
        "unexpected_features": sorted(seen - expected_set),
    }


def _reference_for_model(db: Session, model: MLModel):
    """Regenerate the model's training feature matrix as the drift reference."""
    ds_row = (
        db.query(MLDataset).filter(MLDataset.id == model.dataset_id).first()
        if model.dataset_id else None
    )
    spec = dict(ds_row.spec) if ds_row and ds_row.spec else {
        "generator": "synthetic_v1", "seed": 42, "n_rows": 3000, "label_noise": 0.03,
    }
    dataset = dataset_from_spec(spec, name="drift_reference")
    return dataset.X, dataset.feature_names


def detect(
    db: Session,
    model: MLModel,
    current_rows: List[Mapping[str, Any]],
    *,
    report_type: str = "overall",
    psi_threshold: float = DEFAULT_PSI_THRESHOLD,
    persist: bool = True,
    raise_alert: bool = True,
) -> MLDriftReport:
    """Detect drift of ``current_rows`` against the model's training reference."""
    reference_matrix, feature_names = _reference_for_model(db, model)
    drift = compute_drift(reference_matrix, current_rows, feature_names, psi_threshold=psi_threshold)
    schema = schema_changes(current_rows, feature_names)

    breached = (
        drift["overall_psi"] >= psi_threshold
        or drift["drifted_share"] >= DEFAULT_DRIFTED_SHARE_THRESHOLD
        or bool(schema["missing_features"])
    )

    report = MLDriftReport(
        model_id=model.id,
        model_key=model.model_key,
        report_type=report_type,
        reference_dataset_id=model.dataset_id,
        psi_overall=drift["overall_psi"],
        drift_score=drift["drifted_share"],
        n_features=drift["n_features"],
        n_drifted=drift["n_drifted"],
        missing_feature_rate=drift["missing_feature_rate"],
        drifted_features=drift["drifted_features"],
        schema_changes=schema,
        detail={"per_feature": drift["per_feature"], "n_current": drift["n_current"],
                "psi_band": drift["psi_band"]},
        threshold=psi_threshold,
        breached=breached,
    )
    if persist:
        db.add(report)
        db.commit()
        db.refresh(report)
        if breached and raise_alert:
            _notify_breach(db, model, report)
    return report


def detect_target_drift(
    db: Session,
    model: MLModel,
    current_pds: List[float],
    *,
    reference_pds: Optional[List[float]] = None,
    persist: bool = True,
) -> MLDriftReport:
    """Drift in the predicted-PD distribution (target drift)."""
    if reference_pds is None:
        ref_matrix, names = _reference_for_model(db, model)
        # Reference PD proxy: the training positive rate spread — approximate with
        # the model's own scoring of the reference sample when available.
        from backend.app.services.ml import registry
        trained = registry.load_trained_model(db, model)
        ref_rows = [dict(zip(names, row)) for row in ref_matrix[:1000]]
        reference_pds = [trained.predict_proba(r)[1] for r in ref_rows]
    ref = np.asarray(reference_pds, dtype=float)
    cur = np.asarray(current_pds, dtype=float)
    psi = population_stability_index(ref, cur)
    breached = psi >= DEFAULT_PSI_THRESHOLD
    report = MLDriftReport(
        model_id=model.id, model_key=model.model_key, report_type="target",
        reference_dataset_id=model.dataset_id, psi_overall=round(psi, 6),
        drift_score=round(psi, 6), n_features=1, n_drifted=1 if breached else 0,
        missing_feature_rate=0.0, drifted_features=["predicted_pd"] if breached else [],
        schema_changes={}, threshold=DEFAULT_PSI_THRESHOLD, breached=breached,
        detail={"reference_mean_pd": round(float(ref.mean()), 6) if ref.size else None,
                "current_mean_pd": round(float(cur.mean()), 6) if cur.size else None,
                "psi_band": _band(psi)},
    )
    if persist:
        db.add(report)
        db.commit()
        db.refresh(report)
    return report


def _notify_breach(db: Session, model: MLModel, report: MLDriftReport) -> None:
    """Best-effort notification on a drift breach (never breaks detection).

    The persisted ``breached`` flag is the authoritative alert state consumed by
    the drift dashboard and the retraining trigger (M9). We additionally emit a
    platform notification when the notification service is available.
    """
    try:
        from backend.app.services import notifications
        notify = getattr(notifications, "notify_safe", None)
        if callable(notify) and model.author:
            notify(
                db, user_email=model.author, event_type="model_drift_detected",
                title=f"Data drift detected for model '{model.model_key}'",
                body=(f"Overall PSI {report.psi_overall} ({report.detail.get('psi_band')}); "
                      f"{report.n_drifted}/{report.n_features} features drifted."),
            )
    except Exception:
        db.rollback()


def history(db: Session, *, model_id: Optional[int] = None, model_key: Optional[str] = None,
            report_type: Optional[str] = None, limit: int = 50) -> List[MLDriftReport]:
    q = db.query(MLDriftReport)
    if model_id is not None:
        q = q.filter(MLDriftReport.model_id == model_id)
    if model_key is not None:
        q = q.filter(MLDriftReport.model_key == model_key)
    if report_type is not None:
        q = q.filter(MLDriftReport.report_type == report_type)
    return q.order_by(MLDriftReport.created_at.desc(), MLDriftReport.id.desc()).limit(limit).all()


def report_as_dict(row: MLDriftReport, *, include_detail: bool = False) -> dict:
    data = {
        "id": row.id,
        "model_id": row.model_id,
        "model_key": row.model_key,
        "report_type": row.report_type,
        "psi_overall": row.psi_overall,
        "drift_score": row.drift_score,
        "n_features": row.n_features,
        "n_drifted": row.n_drifted,
        "missing_feature_rate": row.missing_feature_rate,
        "drifted_features": row.drifted_features,
        "schema_changes": row.schema_changes,
        "threshold": row.threshold,
        "breached": row.breached,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }
    if include_detail:
        data["detail"] = row.detail
    return data
