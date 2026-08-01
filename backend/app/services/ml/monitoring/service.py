"""Model Monitoring.

Operational monitoring of the serving layer, computed from the prediction log
prediction latency, volume, model confidence, class distribution, input data
quality, failures, usage statistics, API latency and success rate. Everything
is derived from :class:`MLPredictionLog` rows, so monitoring is always exactly
consistent with what was actually served.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import numpy as np
from sqlalchemy.orm import Session

from backend.app.models.ml_platform import MLPredictionLog


def _query(db: Session, model_id: Optional[int], model_key: Optional[str], since: Optional[datetime]):
    q = db.query(MLPredictionLog)
    if model_id is not None:
        q = q.filter(MLPredictionLog.model_id == model_id)
    if model_key is not None:
        q = q.filter(MLPredictionLog.model_key == model_key)
    if since is not None:
        q = q.filter(MLPredictionLog.created_at >= since)
    return q


def _percentiles(values: List[float]) -> Dict[str, Optional[float]]:
    if not values:
        return {"avg": None, "p50": None, "p95": None, "p99": None, "max": None}
    arr = np.asarray(values, dtype=float)
    return {
        "avg": round(float(arr.mean()), 4),
        "p50": round(float(np.percentile(arr, 50)), 4),
        "p95": round(float(np.percentile(arr, 95)), 4),
        "p99": round(float(np.percentile(arr, 99)), 4),
        "max": round(float(arr.max()), 4),
    }


def latency_stats(db: Session, *, model_id=None, model_key=None, window_hours: Optional[int] = None) -> Dict[str, Any]:
    since = _since(window_hours)
    rows = _query(db, model_id, model_key, since).all()
    latencies = [r.latency_ms for r in rows if r.latency_ms is not None]
    return {"count": len(latencies), **_percentiles(latencies)}


def summary(db: Session, *, model_id=None, model_key=None, window_hours: Optional[int] = None) -> Dict[str, Any]:
    """The full monitoring dashboard payload for a model (or all models)."""
    since = _since(window_hours)
    rows = _query(db, model_id, model_key, since).all()
    total = len(rows)
    successes = [r for r in rows if r.success]
    failures = [r for r in rows if not r.success]
    latencies = [r.latency_ms for r in rows if r.latency_ms is not None]
    pds = [r.probability_of_default for r in successes if r.probability_of_default is not None]

    # Confidence = distance of PD from the 0.5 decision boundary (0..1).
    confidence = [abs(p - 0.5) * 2.0 for p in pds]
    grade_dist = Counter(r.risk_grade for r in successes if r.risk_grade)
    type_dist = Counter(r.inference_type for r in rows)
    approvals = sum(1 for r in successes if r.approval)

    # Input data quality: fraction of non-null feature values across requests.
    populated, cells = 0, 0
    for r in rows:
        feats = r.input_features or {}
        cells += len(feats)
        populated += sum(1 for v in feats.values() if v is not None)

    return {
        "window_hours": window_hours,
        "prediction_volume": {
            "total": total,
            "success": len(successes),
            "failed": len(failures),
            "cached": sum(1 for r in rows if r.cached),
            "by_type": dict(type_dist),
        },
        "success_rate": round(len(successes) / total, 6) if total else None,
        "failure_rate": round(len(failures) / total, 6) if total else None,
        "latency_ms": {"count": len(latencies), **_percentiles(latencies)},
        "model_confidence": {
            "avg": round(float(np.mean(confidence)), 6) if confidence else None,
            "low_confidence_share": round(
                float(np.mean([c < 0.2 for c in confidence])), 6) if confidence else None,
        },
        "pd_distribution": {
            "avg": round(float(np.mean(pds)), 6) if pds else None,
            "p50": round(float(np.percentile(pds, 50)), 6) if pds else None,
            "p95": round(float(np.percentile(pds, 95)), 6) if pds else None,
        },
        "class_distribution": {
            "approved": approvals,
            "declined": len(successes) - approvals,
            "approval_rate": round(approvals / len(successes), 6) if successes else None,
            "grade_distribution": dict(grade_dist),
        },
        "data_quality": {
            "populated_rate": round(populated / cells, 6) if cells else None,
            "missing_rate": round(1 - populated / cells, 6) if cells else None,
        },
    }


def failures(db: Session, *, model_id=None, model_key=None, limit: int = 50) -> List[Dict[str, Any]]:
    rows = (
        _query(db, model_id, model_key, None)
        .filter(MLPredictionLog.success.is_(False))
        .order_by(MLPredictionLog.created_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {"id": r.id, "model_key": r.model_key, "inference_type": r.inference_type,
         "error": r.error, "created_at": r.created_at.isoformat() if r.created_at else None}
        for r in rows
    ]


def usage_statistics(db: Session, *, window_hours: Optional[int] = None) -> Dict[str, Any]:
    since = _since(window_hours)
    rows = _query(db, None, None, since).all()
    by_model = Counter(r.model_key for r in rows if r.model_key)
    by_user = Counter(r.created_by for r in rows if r.created_by)
    by_type = Counter(r.inference_type for r in rows)
    return {
        "total_predictions": len(rows),
        "by_model": dict(by_model),
        "by_user": dict(by_user.most_common(20)),
        "by_inference_type": dict(by_type),
        "unique_entities": len({r.entity_id for r in rows if r.entity_id is not None}),
    }


def volume_timeseries(db: Session, *, model_id=None, model_key=None, days: int = 14) -> List[Dict[str, Any]]:
    since = _since(days * 24)
    rows = _query(db, model_id, model_key, since).all()
    buckets: Dict[str, Dict[str, int]] = {}
    for r in rows:
        if not r.created_at:
            continue
        day = r.created_at.date().isoformat()
        b = buckets.setdefault(day, {"count": 0, "failed": 0})
        b["count"] += 1
        if not r.success:
            b["failed"] += 1
    return [{"date": d, **v} for d, v in sorted(buckets.items())]


def _since(window_hours: Optional[int]) -> Optional[datetime]:
    if window_hours is None:
        return None
    return datetime.utcnow() - timedelta(hours=window_hours)
