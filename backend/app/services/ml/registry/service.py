"""Enterprise Model Registry (Phase 6, Milestone 3).

The registry is the system of record for every trained model version. It:

* assigns monotonic versions per ``model_key`` and marks the latest current;
* persists the training report, metrics, hyperparameters, dataset lineage and
  the serialised artifact path — everything needed to reproduce and audit a
  model;
* drives two governance state machines — an **approval** flow
  (draft → pending → approved / rejected) and a **production** flow
  (none → staging → production → archived / rolled_back) — with an append-only
  deployment history behind every transition;
* supports rollback to a previously-promoted version.

The registry never trains; it records the output of :mod:`training.pipeline`.
Serving loads production artifacts back through :class:`TrainedRiskModel`.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from sqlalchemy.orm import Session

from backend.app.models.ml_platform import MLDataset, MLDeploymentEvent, MLModel
from backend.app.services.ml.training.pipeline import TrainingResult
from backend.app.services.ml.training.trained_model import TrainedRiskModel

ARTIFACTS_DIR = Path(__file__).resolve().parent.parent / "artifacts" / "registry"

# Approval lifecycle.
APPROVAL_DRAFT = "draft"
APPROVAL_PENDING = "pending"
APPROVAL_APPROVED = "approved"
APPROVAL_REJECTED = "rejected"

# Production lifecycle.
PROD_NONE = "none"
PROD_STAGING = "staging"
PROD_PRODUCTION = "production"
PROD_ARCHIVED = "archived"
PROD_ROLLED_BACK = "rolled_back"


class RegistryError(RuntimeError):
    """Raised on an invalid registry state transition."""


# ---------------------------------------------------------------------------
# Datasets
# ---------------------------------------------------------------------------

def register_dataset(db: Session, snapshot: dict, *, created_by: Optional[str] = None) -> MLDataset:
    """Persist a dataset snapshot, reusing an existing row with the same hash."""
    content_hash = snapshot.get("content_hash")
    existing = (
        db.query(MLDataset).filter(MLDataset.content_hash == content_hash).first()
        if content_hash else None
    )
    if existing is not None:
        return existing
    version = (
        db.query(MLDataset).filter(MLDataset.name == snapshot.get("name")).count() + 1
    )
    row = MLDataset(
        name=snapshot.get("name", "dataset"),
        version=version,
        generator=snapshot.get("spec", {}).get("generator", "synthetic_v1"),
        spec=snapshot.get("spec", {}),
        feature_names=snapshot.get("feature_names", []),
        n_rows=snapshot.get("n_rows", 0),
        n_features=snapshot.get("n_features", 0),
        positive_rate=snapshot.get("positive_rate", 0.0),
        content_hash=content_hash or "",
        created_by=created_by,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


# ---------------------------------------------------------------------------
# Model registration
# ---------------------------------------------------------------------------

def _next_version(db: Session, model_key: str) -> int:
    latest = (
        db.query(MLModel)
        .filter(MLModel.model_key == model_key)
        .order_by(MLModel.version.desc())
        .first()
    )
    return (latest.version + 1) if latest else 1


def register_model(
    db: Session,
    result: TrainingResult,
    *,
    model_key: Optional[str] = None,
    name: Optional[str] = None,
    author: Optional[str] = None,
    dataset: Optional[MLDataset] = None,
) -> MLModel:
    """Register a trained model version: persist metadata, artifact and lineage."""
    key = model_key or result.algorithm
    version = _next_version(db, key)

    if dataset is None:
        dataset = register_dataset(db, result.dataset_snapshot, created_by=author)

    # Supersede the previous current version for this key.
    prior_current = (
        db.query(MLModel)
        .filter(MLModel.model_key == key, MLModel.is_current.is_(True))
        .all()
    )
    for m in prior_current:
        m.is_current = False
        db.add(m)

    # Serialise the artifact.
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    artifact_path = ARTIFACTS_DIR / f"{key}_v{version}.joblib"
    result.model.model_version = str(version)
    result.model.save_model(str(artifact_path))

    row = MLModel(
        model_key=key,
        name=name or f"{result.algorithm} v{version}",
        algorithm=result.algorithm,
        version=version,
        is_current=True,
        dataset_id=dataset.id if dataset else None,
        parent_model_id=(prior_current[0].id if prior_current else None),
        hyperparameters=result.hyperparameters,
        metrics=result.metrics.as_dict(),
        feature_names=result.feature_names,
        feature_set_version="1.0",
        report=result.report(),
        training_time_seconds=result.training_time_seconds,
        author=author,
        artifact_path=str(artifact_path),
        approval_status=APPROVAL_DRAFT,
        production_status=PROD_NONE,
        trained_at=result.trained_at,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    _event(db, row, "register", None, APPROVAL_DRAFT, actor=author,
           note=f"Registered {result.algorithm} v{version}")
    return row


# ---------------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------------

def get_model(db: Session, model_id: int) -> Optional[MLModel]:
    return db.query(MLModel).filter(MLModel.id == model_id).first()


def list_models(
    db: Session,
    *,
    model_key: Optional[str] = None,
    approval_status: Optional[str] = None,
    production_status: Optional[str] = None,
    current_only: bool = False,
) -> List[MLModel]:
    q = db.query(MLModel)
    if model_key:
        q = q.filter(MLModel.model_key == model_key)
    if approval_status:
        q = q.filter(MLModel.approval_status == approval_status)
    if production_status:
        q = q.filter(MLModel.production_status == production_status)
    if current_only:
        q = q.filter(MLModel.is_current.is_(True))
    return q.order_by(MLModel.model_key, MLModel.version.desc()).all()


def versions(db: Session, model_key: str) -> List[MLModel]:
    return (
        db.query(MLModel)
        .filter(MLModel.model_key == model_key)
        .order_by(MLModel.version.desc())
        .all()
    )


def production_model(db: Session, model_key: str) -> Optional[MLModel]:
    return (
        db.query(MLModel)
        .filter(MLModel.model_key == model_key,
                MLModel.production_status == PROD_PRODUCTION)
        .order_by(MLModel.version.desc())
        .first()
    )


def any_production_model(db: Session) -> Optional[MLModel]:
    """The most recent production model of any key (default for serving)."""
    return (
        db.query(MLModel)
        .filter(MLModel.production_status == PROD_PRODUCTION)
        .order_by(MLModel.updated_at.desc())
        .first()
    )


def deployment_history(db: Session, model_id: int) -> List[MLDeploymentEvent]:
    return (
        db.query(MLDeploymentEvent)
        .filter(MLDeploymentEvent.model_id == model_id)
        .order_by(MLDeploymentEvent.created_at.asc(), MLDeploymentEvent.id.asc())
        .all()
    )


def load_trained_model(db: Session, model: MLModel) -> TrainedRiskModel:
    """Rehydrate the serialised artifact as a live ``TrainedRiskModel``."""
    if not model.artifact_path or not Path(model.artifact_path).exists():
        raise RegistryError(f"Artifact for model {model.id} is missing on disk.")
    tm = TrainedRiskModel.from_artifact(model.artifact_path)
    tm.model_type = model.model_key
    tm.model_version = str(model.version)
    return tm


# ---------------------------------------------------------------------------
# Governance transitions
# ---------------------------------------------------------------------------

def submit_for_approval(db: Session, model_id: int, *, actor: Optional[str] = None) -> MLModel:
    model = _require(db, model_id)
    if model.approval_status not in (APPROVAL_DRAFT, APPROVAL_REJECTED):
        raise RegistryError(f"Cannot submit a model in '{model.approval_status}'.")
    prev = model.approval_status
    model.approval_status = APPROVAL_PENDING
    db.add(model)
    db.commit()
    db.refresh(model)
    _event(db, model, "submit_for_approval", prev, APPROVAL_PENDING, actor=actor)
    return model


def approve(db: Session, model_id: int, *, actor: Optional[str] = None, note: Optional[str] = None) -> MLModel:
    model = _require(db, model_id)
    if model.approval_status != APPROVAL_PENDING:
        raise RegistryError("Only a pending model can be approved.")
    model.approval_status = APPROVAL_APPROVED
    if model.production_status == PROD_NONE:
        model.production_status = PROD_STAGING
    db.add(model)
    db.commit()
    db.refresh(model)
    _event(db, model, "approve", APPROVAL_PENDING, APPROVAL_APPROVED, actor=actor, note=note)
    return model


def reject(db: Session, model_id: int, *, actor: Optional[str] = None, note: Optional[str] = None) -> MLModel:
    model = _require(db, model_id)
    if model.approval_status != APPROVAL_PENDING:
        raise RegistryError("Only a pending model can be rejected.")
    model.approval_status = APPROVAL_REJECTED
    db.add(model)
    db.commit()
    db.refresh(model)
    _event(db, model, "reject", APPROVAL_PENDING, APPROVAL_REJECTED, actor=actor, note=note)
    return model


def promote(db: Session, model_id: int, *, actor: Optional[str] = None, note: Optional[str] = None) -> MLModel:
    """Promote an approved model to production, archiving the incumbent."""
    model = _require(db, model_id)
    if model.approval_status != APPROVAL_APPROVED:
        raise RegistryError("Only an approved model can be promoted to production.")

    incumbent = production_model(db, model.model_key)
    if incumbent is not None and incumbent.id != model.id:
        incumbent.production_status = PROD_ARCHIVED
        db.add(incumbent)
        _event(db, incumbent, "archive", PROD_PRODUCTION, PROD_ARCHIVED, actor=actor,
               note=f"Superseded by v{model.version}")

    prev = model.production_status
    model.production_status = PROD_PRODUCTION
    db.add(model)
    db.commit()
    db.refresh(model)
    _event(db, model, "promote", prev, PROD_PRODUCTION, actor=actor, note=note)
    return model


def rollback(db: Session, model_key: str, *, actor: Optional[str] = None,
             note: Optional[str] = None) -> MLModel:
    """Roll production back to the most recently archived (prior) version."""
    current = production_model(db, model_key)
    target = (
        db.query(MLModel)
        .filter(MLModel.model_key == model_key,
                MLModel.production_status == PROD_ARCHIVED)
        .order_by(MLModel.version.desc())
        .first()
    )
    if target is None:
        raise RegistryError(f"No archived version of '{model_key}' to roll back to.")

    if current is not None:
        current.production_status = PROD_ROLLED_BACK
        db.add(current)
        _event(db, current, "rollback", PROD_PRODUCTION, PROD_ROLLED_BACK, actor=actor,
               note=note or f"Rolled back in favour of v{target.version}")

    target.production_status = PROD_PRODUCTION
    db.add(target)
    db.commit()
    db.refresh(target)
    _event(db, target, "promote", PROD_ARCHIVED, PROD_PRODUCTION, actor=actor,
           note="Restored via rollback")
    return target


# ---------------------------------------------------------------------------
# Serialisation
# ---------------------------------------------------------------------------

def model_as_dict(model: MLModel, *, include_report: bool = False) -> dict:
    data = {
        "id": model.id,
        "model_key": model.model_key,
        "name": model.name,
        "algorithm": model.algorithm,
        "version": model.version,
        "is_current": model.is_current,
        "dataset_id": model.dataset_id,
        "parent_model_id": model.parent_model_id,
        "hyperparameters": model.hyperparameters,
        "metrics": model.metrics,
        "feature_set_version": model.feature_set_version,
        "feature_count": len(model.feature_names or []),
        "training_time_seconds": model.training_time_seconds,
        "author": model.author,
        "approval_status": model.approval_status,
        "production_status": model.production_status,
        "trained_at": model.trained_at,
        "created_at": model.created_at.isoformat() if model.created_at else None,
    }
    if include_report:
        data["report"] = model.report
        data["feature_names"] = model.feature_names
    return data


def event_as_dict(event: MLDeploymentEvent) -> dict:
    return {
        "id": event.id,
        "model_id": event.model_id,
        "action": event.action,
        "from_status": event.from_status,
        "to_status": event.to_status,
        "actor": event.actor,
        "note": event.note,
        "created_at": event.created_at.isoformat() if event.created_at else None,
    }


def dataset_as_dict(ds: MLDataset) -> dict:
    return {
        "id": ds.id,
        "name": ds.name,
        "version": ds.version,
        "generator": ds.generator,
        "spec": ds.spec,
        "n_rows": ds.n_rows,
        "n_features": ds.n_features,
        "positive_rate": ds.positive_rate,
        "content_hash": ds.content_hash,
        "feature_names": ds.feature_names,
        "created_by": ds.created_by,
        "created_at": ds.created_at.isoformat() if ds.created_at else None,
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _require(db: Session, model_id: int) -> MLModel:
    model = get_model(db, model_id)
    if model is None:
        raise RegistryError(f"Model {model_id} not found.")
    return model


def _event(db: Session, model: MLModel, action: str, from_status: Optional[str],
           to_status: Optional[str], *, actor: Optional[str] = None,
           note: Optional[str] = None) -> MLDeploymentEvent:
    event = MLDeploymentEvent(
        model_id=model.id, action=action, from_status=from_status,
        to_status=to_status, actor=actor, note=note,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event
