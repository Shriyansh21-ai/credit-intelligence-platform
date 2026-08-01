"""Enterprise feature store: lineage, point-in-time retrieval and reuse (M1).

The feature store already persists versioned feature vectors. This module
adds the enterprise-store capabilities the brief calls for on top of that
substrate, without changing how vectors are produced or stored

* **Lineage** — for any feature: its definition, category, data source, unit
  version, plus the models that were trained on it. This is the provenance trail
  auditors and the governance layer rely on.
* **Point-in-time retrieval** — the exact feature vector that was current for an
  entity *as of* a given timestamp, so a historical decision can be reproduced
  with the features it actually saw (no leakage from later recomputes).
* **Reuse & catalog** — a single catalog view over the registry so features are
  discoverable and reusable across models.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from backend.app.models.feature_vector import FeatureVector
from backend.app.services.ml.features import feature_registry as fr


def feature_catalog() -> Dict[str, Any]:
    """The full, versioned feature catalog grouped by category (for discovery)."""
    grouped = fr.definitions_by_category()
    return {
        "feature_set_version": fr.FEATURE_SET_VERSION,
        "feature_count": len(fr.feature_names()),
        "categories": {
            category: [d.metadata() for d in defns]
            for category, defns in grouped.items()
        },
    }


def feature_lineage(db: Optional[Session], feature_name: str) -> Dict[str, Any]:
    """Provenance for a single feature: definition + models that consumed it."""
    definition = fr.get_definition(feature_name)
    if definition is None:
        raise KeyError(f"Unknown feature '{feature_name}'.")
    lineage: Dict[str, Any] = {
        "feature": definition.name,
        "definition": definition.metadata(),
        "source": definition.source,
        "category": definition.category,
        "unit": definition.unit,
        "version": definition.version,
        "consumed_by_models": [],
    }
    if db is not None:
        lineage["consumed_by_models"] = _models_using(db, feature_name)
    return lineage


def _models_using(db: Session, feature_name: str) -> List[Dict[str, Any]]:
    """Registry models whose training feature set includes ``feature_name``."""
    try:
        from backend.app.models.ml_platform import MLModel
        models = db.query(MLModel).all()
    except Exception:
        return []
    used = []
    for m in models:
        if feature_name in (m.feature_names or []):
            used.append({"model_id": m.id, "model_key": m.model_key,
                         "version": m.version, "production_status": m.production_status})
    return used


def point_in_time(db: Session, assessment_id: int, as_of: Any) -> Optional[FeatureVector]:
    """The feature vector that was current for ``assessment_id`` as of ``as_of``.

    Returns the most recent version whose ``created_at`` is at or before the
    reference time — the features a decision made at that time actually saw.
    """
    as_of_dt = _parse(as_of)
    q = db.query(FeatureVector).filter(FeatureVector.assessment_id == assessment_id)
    if as_of_dt is not None:
        q = q.filter(FeatureVector.created_at <= as_of_dt)
    return q.order_by(FeatureVector.version.desc(), FeatureVector.id.desc()).first()


def lineage_for_vector(vector: FeatureVector) -> Dict[str, Any]:
    """Trace a persisted vector back to its feature set and generation context."""
    return {
        "vector_id": vector.id,
        "assessment_id": vector.assessment_id,
        "version": vector.version,
        "is_current": vector.is_current,
        "feature_set_version": vector.feature_set_version,
        "generated_time": vector.generated_time,
        "coverage": vector.coverage,
        "feature_count": vector.feature_count,
        "registry_metadata": vector.registry_metadata,
        "created_at": vector.created_at.isoformat() if vector.created_at else None,
    }


def _parse(as_of: Any) -> Optional[datetime]:
    if as_of is None:
        return None
    if isinstance(as_of, datetime):
        return as_of
    try:
        return datetime.fromisoformat(str(as_of).replace("Z", "+00:00"))
    except ValueError:
        return None
