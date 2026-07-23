"""Model Serving Engine (Phase 6, Milestone 4).

Production inference for the platform. One service exposes every inference mode
the brief requires — real-time, batch, portfolio, bulk and async — over a single
resolution + logging core:

* **Model resolution** picks the artifact to serve: an explicit model id, the
  production model for a key, the most-recent production model of any key, or —
  when nothing is trained yet — the deterministic scorecard. Serving therefore
  never fails for lack of a trained model (full backward compatibility).
* **Caching** memoises both loaded artifacts (joblib load is slow) and identical
  prediction requests, cutting latency for hot inputs.
* **Prediction history + latency** are persisted to :class:`MLPredictionLog`
  for every call, which is also the substrate for model monitoring (M6/M8).

Async inference returns a ``request_id`` immediately and records the result
under it; the platform has no external task queue, so execution is inline but
the contract is queue-ready.
"""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from typing import Any, Dict, List, Mapping, Optional

from sqlalchemy.orm import Session

from backend.app.core.cache import TTLCache
from backend.app.models.ml_platform import MLModel, MLPredictionLog
from backend.app.services.ml import registry
from backend.app.services.ml.inference import features_to_mapping
from backend.app.services.ml.models import get_model
from backend.app.services.ml.models.base import BaseRiskModel

# Artifact cache (model_id -> loaded model). Long TTL; invalidated on promote.
_MODEL_CACHE = TTLCache(ttl_seconds=600.0)
# Prediction cache ((model_id, feature-hash) -> prediction dict). Short TTL.
_PREDICTION_CACHE = TTLCache(ttl_seconds=120.0)


def clear_caches() -> None:
    _MODEL_CACHE.clear()
    _PREDICTION_CACHE.clear()


# ---------------------------------------------------------------------------
# Model resolution
# ---------------------------------------------------------------------------

def resolve_model(
    db: Session,
    *,
    model_id: Optional[int] = None,
    model_key: Optional[str] = None,
) -> tuple[BaseRiskModel, Optional[MLModel]]:
    """Resolve the model to serve and its registry row (if any).

    Precedence: explicit ``model_id`` → production for ``model_key`` → any
    production model → deterministic fallback.
    """
    record: Optional[MLModel] = None
    if model_id is not None:
        record = registry.service.get_model(db, model_id)
        if record is None:
            raise registry.RegistryError(f"Model {model_id} not found.")
    elif model_key is not None:
        record = registry.production_model(db, model_key)
        if record is None:
            current = registry.list_models(db, model_key=model_key, current_only=True)
            record = current[0] if current else None
    else:
        record = registry.any_production_model(db)

    if record is None:
        # Nothing trained/promoted yet: deterministic scorecard keeps serving.
        return get_model(None), None

    cache_key = f"model:{record.id}"
    cached = _MODEL_CACHE.get(cache_key)
    if cached is not None:
        return cached, record
    model = registry.load_trained_model(db, record)
    _MODEL_CACHE.set(cache_key, model)
    return model, record


# ---------------------------------------------------------------------------
# Core inference
# ---------------------------------------------------------------------------

def _feature_hash(model_id: Optional[int], features: Mapping[str, Any]) -> str:
    blob = json.dumps({"m": model_id, "f": features}, sort_keys=True, default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:20]


def predict(
    db: Session,
    features: Any,
    *,
    model_id: Optional[int] = None,
    model_key: Optional[str] = None,
    inference_type: str = "realtime",
    entity_type: Optional[str] = None,
    entity_id: Optional[int] = None,
    request_id: Optional[str] = None,
    use_cache: bool = True,
    created_by: Optional[str] = None,
    log: bool = True,
) -> Dict[str, Any]:
    """Run a single inference, logging latency and outcome."""
    mapping = features_to_mapping(features)
    model, record = resolve_model(db, model_id=model_id, model_key=model_key)
    rec_id = record.id if record else None

    cache_key = _feature_hash(rec_id, mapping)
    if use_cache:
        cached = _PREDICTION_CACHE.get(cache_key)
        if cached is not None:
            result = dict(cached)
            result["cached"] = True
            if log:
                _log_prediction(db, record, mapping, result, inference_type,
                                entity_type, entity_id, request_id, cached=True,
                                created_by=created_by)
            return result

    started = time.perf_counter()
    success, error, prediction = True, None, None
    try:
        prediction = model.predict_risk(mapping).as_dict()
    except Exception as exc:  # inference must fail safe and be logged
        success, error = False, str(exc)
    latency_ms = (time.perf_counter() - started) * 1000.0

    result: Dict[str, Any] = {
        "success": success,
        "error": error,
        "cached": False,
        "latency_ms": round(latency_ms, 4),
        "inference_type": inference_type,
        "model": {
            "id": rec_id,
            "model_key": record.model_key if record else model.model_metadata().model_type,
            "version": record.version if record else None,
            "inference_mode": model.model_metadata().inference_mode,
        },
        "prediction": prediction,
    }
    if success and use_cache:
        _PREDICTION_CACHE.set(cache_key, result)
    if log:
        _log_prediction(db, record, mapping, result, inference_type,
                        entity_type, entity_id, request_id, cached=False,
                        created_by=created_by)
    return result


def batch_predict(
    db: Session,
    items: List[Any],
    *,
    model_id: Optional[int] = None,
    model_key: Optional[str] = None,
    inference_type: str = "batch",
    created_by: Optional[str] = None,
) -> Dict[str, Any]:
    """Score a batch of feature sets under a single request id."""
    request_id = f"batch-{uuid.uuid4().hex[:12]}"
    results: List[Dict[str, Any]] = []
    for i, item in enumerate(items):
        entity_id = None
        features = item
        if isinstance(item, Mapping) and "features" in item:
            entity_id = item.get("entity_id")
            features = item["features"]
        res = predict(
            db, features, model_id=model_id, model_key=model_key,
            inference_type=inference_type, entity_id=entity_id,
            request_id=request_id, created_by=created_by,
        )
        res["index"] = i
        results.append(res)
    return {
        "request_id": request_id,
        "count": len(results),
        "results": results,
        "summary": _summarise(results),
    }


def portfolio_predict(
    db: Session,
    *,
    model_id: Optional[int] = None,
    model_key: Optional[str] = None,
    limit: int = 200,
    created_by: Optional[str] = None,
) -> Dict[str, Any]:
    """Score the current feature vectors across the portfolio."""
    from backend.app.models.feature_vector import FeatureVector

    vectors = (
        db.query(FeatureVector)
        .filter(FeatureVector.is_current.is_(True))
        .order_by(FeatureVector.created_at.desc())
        .limit(limit)
        .all()
    )
    request_id = f"portfolio-{uuid.uuid4().hex[:12]}"
    results: List[Dict[str, Any]] = []
    for v in vectors:
        mapping = features_to_mapping({"features": v.features or []})
        res = predict(
            db, mapping, model_id=model_id, model_key=model_key,
            inference_type="portfolio", entity_type="assessment",
            entity_id=v.assessment_id, request_id=request_id, created_by=created_by,
        )
        res["assessment_id"] = v.assessment_id
        results.append(res)
    return {
        "request_id": request_id,
        "count": len(results),
        "results": results,
        "summary": _summarise(results),
    }


def async_submit(
    db: Session,
    features: Any,
    *,
    model_id: Optional[int] = None,
    model_key: Optional[str] = None,
    entity_type: Optional[str] = None,
    entity_id: Optional[int] = None,
    created_by: Optional[str] = None,
) -> Dict[str, Any]:
    """Submit an async inference; returns a request id the result is stored under.

    Execution is inline (no external queue), but the request/response contract is
    identical to a queued worker: poll :func:`get_by_request` with the id.
    """
    request_id = f"async-{uuid.uuid4().hex[:12]}"
    res = predict(
        db, features, model_id=model_id, model_key=model_key,
        inference_type="async", entity_type=entity_type, entity_id=entity_id,
        request_id=request_id, created_by=created_by,
    )
    return {"request_id": request_id, "status": "completed", "result": res}


# ---------------------------------------------------------------------------
# History & logging
# ---------------------------------------------------------------------------

def _log_prediction(db, record, mapping, result, inference_type, entity_type,
                    entity_id, request_id, *, cached, created_by) -> Optional[MLPredictionLog]:
    try:
        pred = result.get("prediction") or {}
        row = MLPredictionLog(
            model_id=record.id if record else None,
            model_key=result["model"]["model_key"],
            model_version=result["model"]["version"],
            inference_type=inference_type,
            request_id=request_id,
            entity_type=entity_type,
            entity_id=entity_id,
            input_features=mapping,
            probability_of_default=pred.get("probability_of_default"),
            risk_score=pred.get("risk_score"),
            risk_grade=pred.get("risk_grade"),
            approval=pred.get("approval"),
            inference_mode=result["model"]["inference_mode"],
            latency_ms=result.get("latency_ms"),
            cached=cached,
            success=result.get("success", True),
            error=result.get("error"),
            created_by=created_by,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        result["prediction_log_id"] = row.id
        return row
    except Exception:
        db.rollback()
        return None


def prediction_history(
    db: Session,
    *,
    model_id: Optional[int] = None,
    model_key: Optional[str] = None,
    inference_type: Optional[str] = None,
    entity_id: Optional[int] = None,
    limit: int = 100,
) -> List[MLPredictionLog]:
    q = db.query(MLPredictionLog)
    if model_id is not None:
        q = q.filter(MLPredictionLog.model_id == model_id)
    if model_key is not None:
        q = q.filter(MLPredictionLog.model_key == model_key)
    if inference_type is not None:
        q = q.filter(MLPredictionLog.inference_type == inference_type)
    if entity_id is not None:
        q = q.filter(MLPredictionLog.entity_id == entity_id)
    return q.order_by(MLPredictionLog.created_at.desc(), MLPredictionLog.id.desc()).limit(limit).all()


def get_by_request(db: Session, request_id: str) -> List[MLPredictionLog]:
    return (
        db.query(MLPredictionLog)
        .filter(MLPredictionLog.request_id == request_id)
        .order_by(MLPredictionLog.id.asc())
        .all()
    )


def log_as_dict(row: MLPredictionLog) -> dict:
    return {
        "id": row.id,
        "model_id": row.model_id,
        "model_key": row.model_key,
        "model_version": row.model_version,
        "inference_type": row.inference_type,
        "request_id": row.request_id,
        "entity_type": row.entity_type,
        "entity_id": row.entity_id,
        "probability_of_default": row.probability_of_default,
        "risk_score": row.risk_score,
        "risk_grade": row.risk_grade,
        "approval": row.approval,
        "inference_mode": row.inference_mode,
        "latency_ms": row.latency_ms,
        "cached": row.cached,
        "success": row.success,
        "error": row.error,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def _summarise(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    ok = [r for r in results if r.get("success") and r.get("prediction")]
    pds = [r["prediction"]["probability_of_default"] for r in ok]
    approvals = sum(1 for r in ok if r["prediction"].get("approval"))
    latencies = [r["latency_ms"] for r in results if r.get("latency_ms") is not None]
    n = len(pds)
    return {
        "scored": len(ok),
        "failed": len(results) - len(ok),
        "approved": approvals,
        "avg_pd": round(sum(pds) / n, 6) if n else None,
        "max_pd": round(max(pds), 6) if n else None,
        "avg_latency_ms": round(sum(latencies) / len(latencies), 4) if latencies else None,
    }
