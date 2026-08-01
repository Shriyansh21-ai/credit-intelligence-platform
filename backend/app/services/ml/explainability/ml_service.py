"""DB-integrated enterprise explanation service.

Resolves the served model (production or requested), produces the full
enterprise explainability payload and persists it to :class:`MLExplanation` for
audit and reproducibility.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from backend.app.models.ml_platform import MLExplanation
from backend.app.services.ml import serving
from backend.app.services.ml.inference import features_to_mapping

from .enterprise import enterprise_payload, explain_model


def explain(
    db: Session,
    features: Any,
    *,
    model_id: Optional[int] = None,
    model_key: Optional[str] = None,
    entity_type: Optional[str] = None,
    entity_id: Optional[int] = None,
    prediction_log_id: Optional[int] = None,
    persist: bool = True,
) -> Dict[str, Any]:
    """Explain a feature set under the resolved model and optionally store it."""
    mapping = features_to_mapping(features)
    model, record = serving.resolve_model(db, model_id=model_id, model_key=model_key)
    explanation = explain_model(mapping, model)
    payload = enterprise_payload(explanation)
    payload["model"] = {
        "id": record.id if record else None,
        "model_key": record.model_key if record else model.model_metadata().model_type,
        "version": record.version if record else None,
        "inference_mode": model.model_metadata().inference_mode,
    }
    # Genuine per-instance SHAP values, when the model can supply them.
    shap_fn = getattr(model, "shap_values", None)
    if callable(shap_fn):
        sv = shap_fn(mapping)
        if sv:
            payload["shap_values"] = {k: round(v, 6) for k, v in sv.items()}

    if persist:
        row = _persist(db, payload, record, entity_type, entity_id, prediction_log_id)
        if row is not None:
            payload["explanation_id"] = row.id
    return payload


def _persist(db, payload, record, entity_type, entity_id, prediction_log_id) -> Optional[MLExplanation]:
    try:
        waterfall = payload.get("waterfall", [])
        base_value = waterfall[0]["cumulative_pd"] if waterfall else None
        narratives = payload.get("narratives", {})
        row = MLExplanation(
            prediction_log_id=prediction_log_id,
            model_id=record.id if record else None,
            model_key=payload["model"]["model_key"],
            entity_type=entity_type,
            entity_id=entity_id,
            method=payload.get("method", "contribution"),
            base_value=base_value,
            predicted_value=payload.get("probability_of_default"),
            top_positive=payload.get("top_positive_contributors", []),
            top_negative=payload.get("top_negative_contributors", []),
            reason_codes=payload.get("reason_codes", []),
            waterfall=waterfall,
            feature_importance={i["feature"]: i["importance"] for i in payload.get("global_importance", [])},
            business_summary=narratives.get("business_summary"),
            executive_summary=narratives.get("executive_summary"),
            analyst_explanation=narratives.get("analyst_explanation"),
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return row
    except Exception:
        db.rollback()
        return None


def get_explanation(db: Session, explanation_id: int) -> Optional[MLExplanation]:
    return db.query(MLExplanation).filter(MLExplanation.id == explanation_id).first()


def history(
    db: Session,
    *,
    model_id: Optional[int] = None,
    entity_id: Optional[int] = None,
    limit: int = 50,
) -> List[MLExplanation]:
    q = db.query(MLExplanation)
    if model_id is not None:
        q = q.filter(MLExplanation.model_id == model_id)
    if entity_id is not None:
        q = q.filter(MLExplanation.entity_id == entity_id)
    return q.order_by(MLExplanation.created_at.desc(), MLExplanation.id.desc()).limit(limit).all()


def explanation_as_dict(row: MLExplanation) -> dict:
    return {
        "id": row.id,
        "prediction_log_id": row.prediction_log_id,
        "model_id": row.model_id,
        "model_key": row.model_key,
        "entity_type": row.entity_type,
        "entity_id": row.entity_id,
        "method": row.method,
        "base_value": row.base_value,
        "predicted_value": row.predicted_value,
        "top_positive": row.top_positive,
        "top_negative": row.top_negative,
        "reason_codes": row.reason_codes,
        "waterfall": row.waterfall,
        "feature_importance": row.feature_importance,
        "business_summary": row.business_summary,
        "executive_summary": row.executive_summary,
        "analyst_explanation": row.analyst_explanation,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }
