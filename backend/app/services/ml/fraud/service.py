"""Fraud ML engine service (Phase 6, Milestone 10).

Fits an unsupervised :class:`FraudEnsemble` on the historical applicant
population and scores entities for anomaly / fraud risk. Beyond a single fraud
probability it produces:

* **method scores** — Isolation Forest, LOF and reconstruction (autoencoder)
  scores side by side;
* **dimension anomalies** — behavioural, transaction and network views computed
  over feature subsets;
* **contributing factors** — the features that deviate most from the population;
* **risk clustering** — a KMeans cluster assignment and per-cluster profiles.

Results persist to :class:`MLFraudResult`. The detector is fitted lazily on the
reproducible synthetic population and cached per process, so scoring is fast and
deterministic.
"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional

import numpy as np
from sqlalchemy.orm import Session

from backend.app.models.ml_platform import MLFraudResult
from backend.app.services.ml.data import make_synthetic_dataset

from .detectors import FraudEnsemble

# Feature subsets giving the behavioural / transaction / network anomaly views.
_DIMENSIONS: Dict[str, List[str]] = {
    "behavioral": ["credit_utilization", "emi_to_inflow", "prior_defaults_flag"],
    "transaction": ["operating_cash_flow_ratio", "cash_flow_to_debt", "net_margin", "ebitda_margin"],
    "network": ["customer_concentration_score", "industry_risk_score", "geographical_risk_score"],
}


class _DetectorState:
    """Fitted ensemble + reference statistics, cached for the process."""

    def __init__(self) -> None:
        self.ensemble: Optional[FraudEnsemble] = None
        self.feature_names: List[str] = []
        self.ref_mean: Optional[np.ndarray] = None
        self.ref_std: Optional[np.ndarray] = None


_STATE = _DetectorState()


def get_detector(*, refit: bool = False) -> _DetectorState:
    """Return the cached fitted detector, fitting it on first use."""
    if _STATE.ensemble is not None and not refit:
        return _STATE
    dataset = make_synthetic_dataset(seed=2024, n_rows=3000)
    ensemble = FraudEnsemble(contamination=0.05, n_clusters=4).fit(dataset.X, dataset.feature_names)
    _STATE.ensemble = ensemble
    _STATE.feature_names = dataset.feature_names
    _STATE.ref_mean = np.nanmean(dataset.X, axis=0)
    _STATE.ref_std = np.nanstd(dataset.X, axis=0)
    return _STATE


def reset_detector() -> None:
    _STATE.ensemble = None


def _row_vector(features: Mapping[str, Any], names: List[str]) -> np.ndarray:
    return np.array([[_num(features.get(n)) for n in names]], dtype=float)


def _num(v: Any) -> float:
    try:
        return float(v) if v is not None else 0.0
    except (TypeError, ValueError):
        return 0.0


def _contributing_factors(row: np.ndarray, state: _DetectorState, top_n: int = 5) -> List[dict]:
    z = np.zeros_like(row)
    mask = state.ref_std > 1e-9
    z[mask] = (row[mask] - state.ref_mean[mask]) / state.ref_std[mask]
    order = np.argsort(-np.abs(z))[:top_n]
    return [
        {"feature": state.feature_names[i], "value": round(float(row[i]), 6),
         "z_score": round(float(z[i]), 4),
         "direction": "above_norm" if z[i] > 0 else "below_norm"}
        for i in order if abs(z[i]) > 1e-9
    ]


def _dimension_anomalies(features: Mapping[str, Any], state: _DetectorState) -> Dict[str, float]:
    idx = {n: i for i, n in enumerate(state.feature_names)}
    out: Dict[str, float] = {}
    for dim, feats in _DIMENSIONS.items():
        zs = []
        for f in feats:
            i = idx.get(f)
            if i is None or state.ref_std[i] < 1e-9:
                continue
            zs.append(abs((_num(features.get(f)) - state.ref_mean[i]) / state.ref_std[i]))
        out[dim] = round(float(np.mean(zs)), 4) if zs else 0.0
    return out


def score(
    db: Session,
    features: Mapping[str, Any],
    *,
    entity_type: Optional[str] = None,
    entity_id: Optional[int] = None,
    created_by: Optional[str] = None,
    persist: bool = True,
) -> Dict[str, Any]:
    """Score one entity for fraud / anomaly risk."""
    state = get_detector()
    row = _row_vector(features, state.feature_names)
    result = state.ensemble.score(row)

    payload = {
        "entity_type": entity_type,
        "entity_id": entity_id,
        "fraud_probability": round(float(result["fraud_probability"][0]), 6),
        "anomaly_score": round(float(result["ensemble"][0]), 6),
        "is_anomaly": bool(result["is_anomaly"][0]),
        "cluster": int(result["cluster"][0]),
        "method_scores": {k: round(float(v[0]), 6) for k, v in result["method_scores"].items()},
        "dimension_anomalies": _dimension_anomalies(features, state),
        "contributing_factors": _contributing_factors(row[0], state),
    }
    if persist:
        row_db = _persist(db, payload, created_by)
        if row_db is not None:
            payload["id"] = row_db.id
    return payload


def score_batch(db: Session, items: List[Mapping[str, Any]], *, created_by: Optional[str] = None,
                persist: bool = True) -> Dict[str, Any]:
    results = []
    for item in items:
        features = item.get("features", item) if isinstance(item, Mapping) else item
        entity_id = item.get("entity_id") if isinstance(item, Mapping) else None
        results.append(score(db, features, entity_id=entity_id, created_by=created_by, persist=persist))
    flagged = sum(1 for r in results if r["is_anomaly"])
    return {
        "count": len(results),
        "flagged": flagged,
        "flag_rate": round(flagged / len(results), 6) if results else 0.0,
        "results": results,
    }


def cluster_profiles() -> List[Dict[str, Any]]:
    """Describe each risk cluster over the reference population."""
    state = get_detector()
    dataset = make_synthetic_dataset(seed=2024, n_rows=3000)
    scored = state.ensemble.score(dataset.X)
    clusters = scored["cluster"]
    ensemble = scored["ensemble"]
    profiles = []
    for c in sorted(set(clusters.tolist())):
        mask = clusters == c
        profiles.append({
            "cluster": int(c),
            "size": int(mask.sum()),
            "share": round(float(mask.mean()), 6),
            "avg_anomaly_score": round(float(ensemble[mask].mean()), 6),
            "avg_default_label": round(float(dataset.y[mask].mean()), 6),
        })
    return sorted(profiles, key=lambda p: p["avg_anomaly_score"], reverse=True)


def _persist(db, payload, created_by) -> Optional[MLFraudResult]:
    try:
        row = MLFraudResult(
            entity_type=payload.get("entity_type"),
            entity_id=payload.get("entity_id"),
            method="ensemble",
            anomaly_score=payload["anomaly_score"],
            fraud_probability=payload["fraud_probability"],
            is_anomaly=payload["is_anomaly"],
            cluster=payload["cluster"],
            contributing_factors=payload["contributing_factors"],
            method_scores={**payload["method_scores"], "dimensions": payload["dimension_anomalies"]},
            created_by=created_by,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return row
    except Exception:
        db.rollback()
        return None


def history(db: Session, *, entity_id: Optional[int] = None, anomalies_only: bool = False,
            limit: int = 100) -> List[MLFraudResult]:
    q = db.query(MLFraudResult)
    if entity_id is not None:
        q = q.filter(MLFraudResult.entity_id == entity_id)
    if anomalies_only:
        q = q.filter(MLFraudResult.is_anomaly.is_(True))
    return q.order_by(MLFraudResult.created_at.desc(), MLFraudResult.id.desc()).limit(limit).all()


def result_as_dict(row: MLFraudResult) -> dict:
    return {
        "id": row.id,
        "entity_type": row.entity_type,
        "entity_id": row.entity_id,
        "method": row.method,
        "anomaly_score": row.anomaly_score,
        "fraud_probability": row.fraud_probability,
        "is_anomaly": row.is_anomaly,
        "cluster": row.cluster,
        "contributing_factors": row.contributing_factors,
        "method_scores": row.method_scores,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }
